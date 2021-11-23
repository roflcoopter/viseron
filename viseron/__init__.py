"""Viseron init file."""
import concurrent.futures
import logging
import multiprocessing
import signal
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any

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
from viseron.helpers.logs import DuplicateFilter, ViseronLogFormat
from viseron.mqtt import MQTT
from viseron.nvr import FFMPEGNVR
from viseron.post_processors import PostProcessor
from viseron.watchdog.subprocess_watchdog import SubprocessWatchDog
from viseron.watchdog.thread_watchdog import RestartableThread, ThreadWatchDog

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
        self.data = {}
        self.setup_threads = []

        self.data[LOADING] = {}
        self.data[LOADED] = {}
        self.data[FAILED] = {}

        self.data[REGISTERED_OBJECT_DETECTORS] = {}
        self.data[REGISTERED_MOTION_DETECTORS] = {}
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
        self.data[REGISTERED_CAMERAS][camera_identifier] = camera_instance

        if camera_listeners := self._wait_for_camera_store.get(camera_identifier, None):
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

    def setup(self):
        """Set up Viseron."""
        config = ViseronConfig(VISERON_CONFIG_SCHEMA(load_config()))

        thread_watchdog = ThreadWatchDog()
        subprocess_watchdog = SubprocessWatchDog()

        schedule_cleanup(config)

        mqtt = None
        if config.mqtt:
            mqtt = MQTT(config)
            mqtt_publisher = RestartableThread(
                name="mqtt_publisher",
                target=mqtt.publisher,
                daemon=True,
                register=True,
            )
            mqtt.connect()
            mqtt_publisher.start()

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
