"""Viseron init file."""
from __future__ import annotations

import concurrent.futures
import logging
import multiprocessing
import signal
import sys
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List

import voluptuous as vol

from viseron.cleanup import Cleanup
from viseron.components import setup_components
from viseron.components.data_stream import (
    COMPONENT as DATA_STREAM_COMPONENT,
    DataStream,
)
from viseron.components.nvr import COMPONENT as NVR_COMPONENT
from viseron.config import VISERON_CONFIG_SCHEMA, NVRConfig, ViseronConfig, load_config
from viseron.const import (
    EVENT_ENTITY_ADDED,
    EVENT_STATE_CHANGED,
    FAILED,
    LOADED,
    LOADING,
    REGISTERED_CAMERAS,
    REGISTERED_MOTION_DETECTORS,
    REGISTERED_OBJECT_DETECTORS,
    THREAD_STORE_CATEGORY_NVR,
    VISERON_SIGNAL_SHUTDOWN,
)
from viseron.domains.motion_detector.const import DATA_MOTION_DETECTOR_SCAN
from viseron.domains.object_detector.const import DATA_OBJECT_DETECTOR_SCAN
from viseron.exceptions import (
    FFprobeError,
    FFprobeTimeout,
    PostProcessorImportError,
    PostProcessorStructureError,
)
from viseron.helpers import slugify
from viseron.helpers.logs import (
    DuplicateFilter,
    SensitiveInformationFilter,
    ViseronLogFormat,
)
from viseron.nvr import FFMPEGNVR
from viseron.post_processors import PostProcessor
from viseron.watchdog.subprocess_watchdog import SubprocessWatchDog
from viseron.watchdog.thread_watchdog import RestartableThread, ThreadWatchDog

if TYPE_CHECKING:
    from viseron.components import Component
    from viseron.helpers.entity import Entity

VISERON_SIGNALS = {
    VISERON_SIGNAL_SHUTDOWN: "viseron/signal/shutdown",
}

SIGNAL_SCHEMA = vol.Schema(
    vol.In(
        VISERON_SIGNALS.keys(),
    )
)

LOGGER = logging.getLogger(__name__)


def enable_logging():
    """Enable logging."""
    LOGGER.propagate = False
    handler = logging.StreamHandler()
    formatter = ViseronLogFormat()
    handler.setFormatter(formatter)
    handler.addFilter(DuplicateFilter())
    handler.addFilter(SensitiveInformationFilter())
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)

    # Silence noisy loggers
    logging.getLogger("apscheduler.scheduler").setLevel(logging.ERROR)
    logging.getLogger("apscheduler.executors").setLevel(logging.ERROR)

    sys.excepthook = lambda *args: logging.getLogger(None).exception(
        "Uncaught exception", exc_info=args  # type: ignore
    )
    threading.excepthook = lambda args: logging.getLogger(None).exception(
        "Uncaught thread exception",
        exc_info=(
            args.exc_type,
            args.exc_value,
            args.exc_traceback,
        ),  # type: ignore[arg-type]
    )


def setup_viseron():
    """Set up and run Viseron."""
    vis = Viseron()
    enable_logging()

    LOGGER.info("-------------------------------------------")
    LOGGER.info("Initializing...")

    config = load_config()
    setup_components(vis, config)
    vis.setup()


@dataclass
class EventData:
    """Dataclass that holds an event."""

    name: str
    data: Any


class Viseron:
    """Viseron."""

    vis = None

    def __init__(self):
        Viseron.vis = self

        self.states = States(self)

        self.setup_threads = []

        self.data = {}
        self.data[LOADING] = {}
        self.data[LOADED] = {}
        self.data[FAILED] = {}
        self.data[REGISTERED_OBJECT_DETECTORS] = {}
        self.data[REGISTERED_MOTION_DETECTORS] = {}

        self._camera_register_lock = threading.Lock()
        self.data[REGISTERED_CAMERAS] = {}
        self._wait_for_camera_store = {}

    def register_signal_handler(self, viseron_signal, callback):
        """Register a callback which gets called on signals emitted by Viseron.

        Signals currently available:
            - shutdown = Emitted when shutdown has been requested
        """
        if DATA_STREAM_COMPONENT not in self.data[LOADED]:
            LOGGER.error(
                f"Failed to register signal handler for {viseron_signal}: "
                f"{DATA_STREAM_COMPONENT} is not loaded"
            )
            return False

        try:
            SIGNAL_SCHEMA(viseron_signal)
        except vol.Invalid as err:
            LOGGER.error(
                f"Failed to register signal handler for {viseron_signal}: {err}"
            )
            return False

        return self.data[DATA_STREAM_COMPONENT].subscribe_data(
            f"viseron/signal/{viseron_signal}", callback
        )

    def listen_event(self, event, callback):
        """Register a listener to an event."""
        if DATA_STREAM_COMPONENT not in self.data[LOADED]:
            LOGGER.error(
                f"Failed to register event listener for {event}: "
                f"{DATA_STREAM_COMPONENT} is not loaded"
            )
            return False

        return self.data[DATA_STREAM_COMPONENT].subscribe_data(
            f"event/{event}", callback
        )

    def dispatch_event(self, event, data):
        """Dispatch an event."""
        event = f"event/{event}"
        self.data[DATA_STREAM_COMPONENT].publish_data(
            event, data=EventData(event, data)
        )

    def register_object_detector(self, camera_identifier, detector):
        """Register an object detector that can be used by components."""
        LOGGER.debug(f"Registering object detector for camera: {camera_identifier}")
        topic = DATA_OBJECT_DETECTOR_SCAN.format(camera_identifier=camera_identifier)
        self.data[DATA_STREAM_COMPONENT].subscribe_data(
            data_topic=topic,
            callback=detector.object_detection_queue,
        )
        self.data[REGISTERED_OBJECT_DETECTORS][camera_identifier] = detector

    def get_object_detector(self, detector_name):
        """Return a registered object detector."""
        if not self.data[REGISTERED_OBJECT_DETECTORS]:
            LOGGER.error("No object detectors are registered")
            return False

        if not self.data[REGISTERED_OBJECT_DETECTORS].get(detector_name, None):
            LOGGER.error(
                f"Requested object detector {detector_name} has not been registered. "
                "Available object detectors are: "
                f"{list(self.data[REGISTERED_OBJECT_DETECTORS].keys())}"
            )
            return False

        return self.data[REGISTERED_OBJECT_DETECTORS][detector_name]

    def register_motion_detector(self, camera_identifier, detector):
        """Register an motion detector that can be used by components."""
        LOGGER.debug(f"Registering motion detector for camera: {camera_identifier}")
        topic = DATA_MOTION_DETECTOR_SCAN.format(camera_identifier=camera_identifier)
        self.data[DATA_STREAM_COMPONENT].subscribe_data(
            data_topic=topic,
            callback=detector.motion_detection_queue,
        )
        self.data[REGISTERED_MOTION_DETECTORS][camera_identifier] = detector

    def get_motion_detector(self, detector_name):
        """Return a registered motion detector."""
        if not self.data[REGISTERED_MOTION_DETECTORS]:
            LOGGER.error("No motion detectors are registered")
            return False

        if not self.data[REGISTERED_MOTION_DETECTORS].get(detector_name, None):
            LOGGER.error(
                f"Requested motion detector {detector_name} has not been registered. "
                "Available motion detectors are: "
                f"{list(self.data[REGISTERED_MOTION_DETECTORS].keys())}"
            )
            return False
        return self.data[REGISTERED_MOTION_DETECTORS][detector_name]

    def register_camera(self, camera_identifier, camera_instance):
        """Register a camera."""
        LOGGER.debug(f"Registering camera: {camera_identifier}")
        with self._camera_register_lock:
            self.data[REGISTERED_CAMERAS][camera_identifier] = camera_instance

            if camera_listeners := self._wait_for_camera_store.get(
                camera_identifier, None
            ):
                for thread_event in camera_listeners:
                    thread_event.set()
                del self._wait_for_camera_store[camera_identifier]

    def get_registered_camera(self, camera_identifier):
        """Return a registered camera."""
        if not self.data[REGISTERED_CAMERAS]:
            LOGGER.error("No cameras are registered")
            return False

        if not self.data[REGISTERED_CAMERAS].get(camera_identifier, None):
            LOGGER.error(
                f"Requested camera {camera_identifier} has not been registered. "
                "Available cameras are: "
                f"{list(self.data[REGISTERED_CAMERAS].keys())}"
            )
            return False

        return self.data[REGISTERED_CAMERAS][camera_identifier]

    def wait_for_camera(self, camera_identifier):
        """Wait for a camera to register."""
        with self._camera_register_lock:
            if camera_identifier in self.data[REGISTERED_CAMERAS]:
                return

            LOGGER.debug(f"Waiting for camera {camera_identifier} to register")
            event = threading.Event()
            self._wait_for_camera_store.setdefault(camera_identifier, []).append(event)
        event.wait()
        LOGGER.debug(f"Done waiting for camera {camera_identifier} to register")

    def shutdown(self):
        """Shut down Viseron."""
        if self.data.get(DATA_STREAM_COMPONENT, None):
            data_stream: DataStream = self.data[DATA_STREAM_COMPONENT]
            data_stream.publish_data(VISERON_SIGNALS["shutdown"])

        def join(thread_or_process):
            thread_or_process.join(timeout=8)
            time.sleep(0.5)  # Wait for process to exit properly
            if thread_or_process.is_alive():
                LOGGER.error(f"{thread_or_process.name} did not exit in time")

        threads_and_processes = [
            thread
            for thread in threading.enumerate()
            if not thread.daemon and thread != threading.current_thread()
        ]
        threads_and_processes += multiprocessing.active_children()

        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
            thread_or_process_future = {
                executor.submit(join, thread_or_process): thread_or_process
                for thread_or_process in threads_and_processes
            }
            for future in concurrent.futures.as_completed(thread_or_process_future):
                future.result()

    def add_entity(self, component: str, entity: Entity):
        """Add entity to states registry."""
        self.states.add_entity(self.data[LOADING][component], entity)

    def add_entities(self, component: str, entities: List[Entity]):
        """Add entities to states registry."""
        self.states.add_entities(self.data[LOADING][component], entities)

    def get_entities(self):
        """Return all registered entities."""
        return self.states.get_entities()

    def setup(self):
        """Set up Viseron."""
        config = ViseronConfig(VISERON_CONFIG_SCHEMA(load_config()))

        thread_watchdog = ThreadWatchDog()
        subprocess_watchdog = SubprocessWatchDog()

        schedule_cleanup(config)

        post_processors = {}
        for (
            post_processor_type,
            post_processor_config,
        ) in config.post_processors.post_processors.items():
            try:
                post_processors[post_processor_type] = PostProcessor(
                    config,
                    post_processor_type,
                    post_processor_config,
                )
            except (PostProcessorImportError, PostProcessorStructureError) as error:
                LOGGER.error(
                    "Error loading post processor {}. {}".format(
                        post_processor_type, error
                    )
                )

        if not self.data.get(NVR_COMPONENT):
            LOGGER.warning("No nvr component is configured.")
            self.shutdown()

        LOGGER.info("Initialization complete")

        def signal_term(*_):
            LOGGER.info("Initiating shutdown")
            thread_watchdog.stop()
            subprocess_watchdog.stop()
            nvr_threads = RestartableThread.thread_store.get(
                THREAD_STORE_CATEGORY_NVR, []
            ).copy()
            for thread in nvr_threads:
                thread.stop()
            for thread in nvr_threads:
                thread.join()

            self.shutdown()
            LOGGER.info("Shutdown complete")

        # Listen to signals
        signal.signal(signal.SIGTERM, signal_term)
        signal.signal(signal.SIGINT, signal_term)
        signal.pause()


@dataclass
class EventStateChangedData:
    """State changed event data."""

    entity: Entity
    previous_state: State | None
    current_state: State


@dataclass
class EventEntityAddedData:
    """Entity event data."""

    entity: Entity


class State:
    """Hold the state of a single entity."""

    def __init__(self, entity: Entity, state: str, attributes: dict):
        self.entity = entity
        self.state = state
        self.attributes = attributes
        self.timestamp = time.time()


class States:
    """Keep track of entity states."""

    def __init__(self, vis: Viseron):
        self._vis = vis
        self._registry: Dict[str, Entity] = {}
        self._registry_lock = threading.Lock()

        self._current_states: Dict[str, State] = {}

    def set_state(self, entity: Entity):
        """Set the state in the states registry."""
        LOGGER.debug(
            "Setting state of %s to state: %s, attributes %s",
            entity.entity_id,
            entity.state,
            entity.attributes,
        )

        previous_state = self._current_states.get(entity.entity_id, None)
        current_state = State(entity, entity.state, entity.attributes)

        self._current_states[entity.entity_id] = current_state
        self._vis.dispatch_event(
            EVENT_STATE_CHANGED,
            EventStateChangedData(entity, previous_state, current_state),
        )

    def add_entity(self, component: Component, entity: Entity):
        """Add entity to states registry."""
        with self._registry_lock:
            if not entity.name:
                LOGGER.error(
                    f"Component {component.name} is adding entities without name. "
                    "name is required for all entities"
                )
                return

            LOGGER.debug(f"Adding entity {entity.name} from component {component.name}")

            if entity.entity_id:
                entity_id = entity.entity_id
            else:
                entity_id = self._generate_entity_id(entity)

            if entity_id in self._registry:
                LOGGER.error(
                    f"Component {component.name} does not generate unique entity IDs"
                )
                suffix_number = 1
                while True:
                    if (
                        unique_entity_id := f"{entity_id}_{suffix_number}"
                    ) in self._registry:
                        suffix_number += 1
                    else:
                        entity_id = unique_entity_id
                        break

            entity.entity_id = entity_id
            entity.vis = self._vis

            self._registry[entity_id] = entity
            self._vis.dispatch_event(
                EVENT_ENTITY_ADDED,
                EventEntityAddedData(entity),
            )
            self.set_state(entity)

    def add_entities(self, component: Component, entities: List[Entity]):
        """Add entities to states registry."""
        for entity in entities:
            self.add_entity(component, entity)

    def get_entities(self):
        """Return all registered entities."""
        with self._registry_lock:
            return self._registry

    @staticmethod
    def _assign_object_id(entity: Entity):
        """Assign object id to entity if it is missing."""
        if entity.object_id:
            entity.object_id = slugify(entity.object_id)
        else:
            entity.object_id = slugify(entity.name)

    def _generate_entity_id(self, entity: Entity):
        """Generate entity id for an entity."""
        self._assign_object_id(entity)
        return f"{entity.domain}.{entity.object_id}"


class SetupNVR(RestartableThread):
    """Thread to setup NVR."""

    def __init__(self, config, camera, detector, register=True):
        super().__init__(
            name=f"setup.{camera['name']}",
            daemon=True,
            register=register,
            base_class=SetupNVR,
            base_class_args=(
                config,
                camera,
                detector,
            ),
        )
        self._config = config
        self._camera = camera
        self._detector = detector
        self.start()

    def run(self):
        """Validate config and setup NVR."""
        camera_config = NVRConfig(
            self._camera,
            self._config.object_detection,
            self._config.motion_detection,
            self._config.recorder,
            self._config.mqtt,
        )
        try:
            FFMPEGNVR(camera_config, self._detector)
        except (FFprobeError, FFprobeTimeout) as error:
            LOGGER.error(
                f"Failed to initialize camera {camera_config.camera.name}: {error}"
            )
        else:
            # Unregister thread from watchdog only if it succeeds
            self.stop()


def schedule_cleanup(config):
    """Start timed cleanup of old recordings."""
    LOGGER.debug("Starting cleanup scheduler")
    cleanup = Cleanup(config)
    cleanup.start()
    LOGGER.debug("Running initial cleanup")
    cleanup.cleanup()
