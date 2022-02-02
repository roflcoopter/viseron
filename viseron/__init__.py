"""Viseron init file."""
from __future__ import annotations

import concurrent.futures
import logging
import multiprocessing
import sys
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, List

import voluptuous as vol
from apscheduler.schedulers.background import BackgroundScheduler

from viseron.components import setup_components
from viseron.components.data_stream import (
    COMPONENT as DATA_STREAM_COMPONENT,
    DataStream,
)
from viseron.components.nvr import COMPONENT as NVR_COMPONENT
from viseron.config import load_config
from viseron.const import (
    EVENT_CAMERA_REGISTERED,
    FAILED,
    LOADED,
    LOADING,
    REGISTERED_CAMERAS,
    REGISTERED_MOTION_DETECTORS,
    REGISTERED_OBJECT_DETECTORS,
    VISERON_SIGNAL_SHUTDOWN,
)
from viseron.domains.motion_detector.const import DATA_MOTION_DETECTOR_SCAN
from viseron.domains.object_detector.const import DATA_OBJECT_DETECTOR_SCAN
from viseron.exceptions import DataStreamNotLoaded
from viseron.helpers.logs import (
    DuplicateFilter,
    SensitiveInformationFilter,
    ViseronLogFormat,
)
from viseron.states import States
from viseron.watchdog.subprocess_watchdog import SubprocessWatchDog
from viseron.watchdog.thread_watchdog import ThreadWatchDog

if TYPE_CHECKING:
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
    enable_logging()
    LOGGER.info("-------------------------------------------")
    LOGGER.info("Initializing...")

    config = load_config()

    vis = Viseron()

    setup_components(vis, config)
    vis.setup()

    return vis


@dataclass
class Event:
    """Dataclass that holds an event."""

    name: str
    data: Any
    timestamp: float

    def as_dict(self) -> dict[str, Any]:
        """Convert Event to dict."""
        return {
            "name": self.name.split("/", 1)[1],
            "data": self.data,
            "timestamp": self.timestamp,
        }


class Viseron:
    """Viseron."""

    def __init__(self):
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

        self._thread_watchdog = ThreadWatchDog()
        self._subprocess_watchdog = SubprocessWatchDog()
        self._periodic_update_scheduler = BackgroundScheduler(
            timezone="UTC", daemon=True
        )

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

    def listen_event(self, event, callback, ioloop=None) -> Callable[[], None]:
        """Register a listener to an event."""
        if DATA_STREAM_COMPONENT not in self.data[LOADED]:
            LOGGER.error(
                f"Failed to register event listener for {event}: "
                f"{DATA_STREAM_COMPONENT} is not loaded"
            )
            raise DataStreamNotLoaded

        data_stream: DataStream = self.data[DATA_STREAM_COMPONENT]
        topic = f"event/{event}"
        uuid = data_stream.subscribe_data(topic, callback, ioloop=ioloop)

        def unsubscribe():
            data_stream.unsubscribe_data(topic, uuid)

        return unsubscribe

    def dispatch_event(self, event, data):
        """Dispatch an event."""
        event = f"event/{event}"
        self.data[DATA_STREAM_COMPONENT].publish_data(
            event, data=Event(event, data, time.time())
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
        """Register a motion detector that can be used by components."""
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
            self.dispatch_event(EVENT_CAMERA_REGISTERED, camera_instance)

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
        LOGGER.info("Initiating shutdown")

        if self.data.get(DATA_STREAM_COMPONENT, None):
            data_stream: DataStream = self.data[DATA_STREAM_COMPONENT]
            data_stream.publish_data(VISERON_SIGNALS["shutdown"])

        self._thread_watchdog.stop()
        self._subprocess_watchdog.stop()
        self._periodic_update_scheduler.shutdown()

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
        LOGGER.info("Shutdown complete")

    def add_entity(self, component: str, entity: Entity):
        """Add entity to states registry."""
        component_instance = self.data[LOADED].get(component, None)
        if not component_instance:
            component_instance = self.data[LOADING][component]
        self.states.add_entity(component_instance, entity)

    def add_entities(self, component: str, entities: List[Entity]):
        """Add entities to states registry."""
        for entity in entities:
            self.add_entity(component, entity)

    def get_entities(self):
        """Return all registered entities."""
        return self.states.get_entities()

    def schedule_periodic_update(self, entity: Entity, update_interval: int):
        """Schedule entity update at a fixed interval."""
        self._periodic_update_scheduler.add_job(
            entity.update, "interval", seconds=update_interval
        )

    def setup(self):
        """Set up Viseron."""
        if not self.data.get(NVR_COMPONENT):
            LOGGER.warning("No nvr component is configured.")
            self.shutdown()

        self._periodic_update_scheduler.start()

        LOGGER.info("Initialization complete")
