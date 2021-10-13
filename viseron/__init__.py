"""Viseron init file."""
import concurrent.futures
import logging
import signal
import sys
import threading

import voluptuous as vol

from viseron.cleanup import Cleanup
from viseron.components import setup_components
from viseron.components.data_stream import (
    COMPONENT as DATA_STREAM_COMPONENT,
    DataStream,
)
from viseron.config import VISERON_CONFIG_SCHEMA, NVRConfig, ViseronConfig, load_config
from viseron.const import (
    FAILED,
    LOADED,
    LOADING,
    THREAD_STORE_CATEGORY_NVR,
    VISERON_SIGNAL_SHUTDOWN,
)
from viseron.detector import Detector
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
    VISERON_SIGNAL_SHUTDOWN: "/viseron/signal/shutdown",
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


class Viseron:
    """Viseron."""

    def __init__(self):
        self.data = {}
        self.setup_threads = []

        self.data[LOADING] = set()
        self.data[LOADED] = set()
        self.data[FAILED] = set()

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

        self.data[DATA_STREAM_COMPONENT].subscribe_data(
            f"/viseron/signal/{viseron_signal}", callback
        )

    def shutdown(self):
        """Shut down Viseron."""
        if self.data.get(DATA_STREAM_COMPONENT, None):
            data_stream: DataStream = self.data[DATA_STREAM_COMPONENT]
            data_stream.publish_data(VISERON_SIGNALS["shutdown"])

        def join_thread(thread):
            thread.join(timeout=5)
            if thread.is_alive():
                LOGGER.error(f"Thread {thread.name} did not exit in time")

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            thread_future = {
                executor.submit(join_thread, thread): thread
                for thread in threading.enumerate()
                if not thread.daemon and thread != threading.current_thread()
            }
            for future in concurrent.futures.as_completed(thread_future):
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

        detector = Detector(config.object_detection)

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

        LOGGER.info("Initializing NVR threads")
        for camera in config.cameras:
            setup_thread = SetupNVR(
                config,
                camera,
                detector,
            )
            self.setup_threads.append(setup_thread)
        for thread in self.setup_threads:
            thread.join()

        LOGGER.info("Initialization complete")

        def signal_term(*_):
            LOGGER.info("Kill received! Sending kill to threads..")
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
            LOGGER.info("Exiting")

        # Listen to signals
        signal.signal(signal.SIGTERM, signal_term)
        signal.signal(signal.SIGINT, signal_term)


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
