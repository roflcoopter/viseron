"""Viseron init file."""
import logging
import signal
import threading
from queue import Queue

from viseron.cleanup import Cleanup
from viseron.config import CONFIG, NVRConfig, ViseronConfig
from viseron.const import LOG_LEVELS, THREAD_STORE_CATEGORY_NVR
from viseron.data_stream import DataStream
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
from viseron.webserver import WebServer

LOGGER = logging.getLogger(__name__)


class Viseron:
    """Viseron."""

    def __init__(self):
        config = ViseronConfig(CONFIG)

        log_settings(config)
        LOGGER.info("-------------------------------------------")
        LOGGER.info("Initializing...")

        thread_watchdog = ThreadWatchDog()
        subprocess_watchdog = SubprocessWatchDog()
        webserver = WebServer()
        webserver.start()

        DataStream(webserver.ioloop)

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
        self.setup_threads = []
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
            webserver.stop()
            webserver.join()
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
            self._config.logging,
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


def log_settings(config):
    """Set custom log settings."""
    LOGGER.propagate = False
    formatter = ViseronLogFormat(config.logging)
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(DuplicateFilter())
    LOGGER.addHandler(handler)

    LOGGER.setLevel(LOG_LEVELS[config.logging.level])
    logging.getLogger("apscheduler.scheduler").setLevel(logging.ERROR)
    logging.getLogger("apscheduler.executors").setLevel(logging.ERROR)
