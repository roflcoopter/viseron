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
    PostProcessorImportError,
    PostProcessorStructureError,
)
from viseron.mqtt import MQTT
from viseron.nvr import FFMPEGNVR
from viseron.post_processors import PostProcessor
from viseron.thread_watchdog import RestartableThread, ThreadWatchDog
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
        webserver = WebServer()
        webserver.start()

        DataStream(webserver.ioloop)

        schedule_cleanup(config)

        mqtt_queue = None
        mqtt = None
        if config.mqtt:
            mqtt_queue = Queue(maxsize=100)
            mqtt = MQTT(config)
            mqtt_publisher = RestartableThread(
                name="mqtt_publisher",
                target=mqtt.publisher,
                args=(mqtt_queue,),
                daemon=True,
                register=True,
            )

        detector = Detector(config.object_detection)

        post_processors = {}
        for (
            post_processor_type,
            post_processor_config,
        ) in config.post_processors.post_processors.items():
            try:
                post_processors[post_processor_type] = PostProcessor(
                    config, post_processor_type, post_processor_config, mqtt_queue
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
            setup_thread = threading.Thread(
                target=self.setup_nvr,
                args=(
                    config,
                    camera,
                    detector,
                    mqtt_queue,
                ),
            )
            setup_thread.start()
            self.setup_threads.append(setup_thread)
        for thread in self.setup_threads:
            thread.join()

        if mqtt:
            mqtt.connect()
            mqtt_publisher.start()

        for thread in RestartableThread.thread_store[THREAD_STORE_CATEGORY_NVR]:
            thread.start()

        LOGGER.info("Initialization complete")

        def signal_term(*_):
            LOGGER.info("Kill received! Sending kill to threads..")
            thread_watchdog.stop()
            for thread in RestartableThread.thread_store[THREAD_STORE_CATEGORY_NVR]:
                LOGGER.debug(thread)
                thread.stop()
            for thread in RestartableThread.thread_store[THREAD_STORE_CATEGORY_NVR]:
                thread.join()
            webserver.stop()
            webserver.join()
            LOGGER.info("Exiting")

        # Listen to signals
        signal.signal(signal.SIGTERM, signal_term)
        signal.signal(signal.SIGINT, signal_term)

    @staticmethod
    def setup_nvr(config, camera, detector, mqtt_queue):
        """Setup NVR for each configured camera."""
        camera_config = NVRConfig(
            camera,
            config.object_detection,
            config.motion_detection,
            config.recorder,
            config.mqtt,
            config.logging,
        )
        try:
            nvr = FFMPEGNVR(
                camera_config,
                detector,
                mqtt_queue=mqtt_queue,
            )
            RestartableThread(
                name=str(nvr),
                target=nvr.run,
                stop_target=nvr.stop,
                thread_store_category=THREAD_STORE_CATEGORY_NVR,
                register=True,
            )
        except FFprobeError as error:
            LOGGER.error(
                f"Failed to initialize camera {camera_config.camera.name}: {error}"
            )


def schedule_cleanup(config):
    """Start timed cleanup of old recordings."""
    LOGGER.debug("Starting cleanup scheduler")
    cleanup = Cleanup(config)
    cleanup.start()
    LOGGER.debug("Running initial cleanup")
    cleanup.cleanup()


def log_settings(config):
    """Sets log level."""
    LOGGER.setLevel(LOG_LEVELS[config.logging.level])
    logging.getLogger("apscheduler.scheduler").setLevel(logging.ERROR)
    logging.getLogger("apscheduler.executors").setLevel(logging.ERROR)
