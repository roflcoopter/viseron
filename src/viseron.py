import logging
import signal
from queue import Queue
from threading import Thread

from const import LOG_LEVELS
from lib.cleanup import Cleanup
from lib.config import CONFIG, NVRConfig, ViseronConfig
from lib.data_stream import DataStream
from lib.detector import Detector
from lib.mqtt import MQTT
from lib.nvr import FFMPEGNVR
from lib.post_processors import PostProcessor
from lib.webserver import WebServer
from viseron_exceptions import FFprobeError

LOGGER = logging.getLogger()


class Viseron:
    def __init__(self):
        config = ViseronConfig(CONFIG)

        log_settings(config)
        LOGGER.info("-------------------------------------------")
        LOGGER.info("Initializing...")

        webserver = WebServer()
        webserver.start()

        data_stream = DataStream(webserver.ioloop)

        schedule_cleanup(config)

        mqtt_queue = None
        mqtt = None
        if config.mqtt:
            mqtt_queue = Queue(maxsize=100)
            mqtt = MQTT(config)
            mqtt_publisher = Thread(target=mqtt.publisher, args=(mqtt_queue,))
            mqtt_publisher.daemon = True

        detector = Detector(config.object_detection)

        post_processors = {}
        for (
            post_processor_type,
            post_processor_config,
        ) in config.post_processors.post_processors.items():
            post_processors[post_processor_type] = PostProcessor(
                config, post_processor_type, post_processor_config, mqtt_queue
            )

        LOGGER.info("Initializing NVR threads")
        self.setup_threads = []
        self.nvr_threads = []
        for camera in config.cameras:
            setup_thread = Thread(
                target=self.setup_nvr, args=(config, camera, detector, mqtt_queue,),
            )
            setup_thread.start()
            self.setup_threads.append(setup_thread)
        for thread in self.setup_threads:
            thread.join()

        if mqtt:
            mqtt.connect()
            mqtt_publisher.start()

        for thread in self.nvr_threads:
            thread.start()

        LOGGER.info("Initialization complete")

        def signal_term(*_):
            LOGGER.info("Kill received! Sending kill to threads..")
            for thread in self.nvr_threads:
                thread.stop()
            for thread in self.nvr_threads:
                thread.join()

        # Listen to sigterm
        signal.signal(signal.SIGTERM, signal_term)

        try:
            for thread in self.nvr_threads:
                thread.join()
        except KeyboardInterrupt:
            LOGGER.info("Ctrl-C received! Sending kill to threads..")
            for thread in self.nvr_threads:
                thread.stop()
            for thread in self.nvr_threads:
                thread.join()

        LOGGER.info("Exiting")

    def setup_nvr(
        self, config, camera, detector, mqtt_queue,
    ):
        camera_config = NVRConfig(
            camera,
            config.object_detection,
            config.motion_detection,
            config.recorder,
            config.mqtt,
            config.logging,
        )
        try:
            nvr = FFMPEGNVR(camera_config, detector, mqtt_queue=mqtt_queue,)
            self.nvr_threads.append(nvr)
        except FFprobeError:
            LOGGER.error(f"Failed to initialize camera {camera_config.camera.name}")


def schedule_cleanup(config):
    LOGGER.debug("Starting cleanup scheduler")
    cleanup = Cleanup(config)
    cleanup.start()
    LOGGER.debug("Running initial cleanup")
    cleanup.cleanup()


def log_settings(config):
    LOGGER.setLevel(LOG_LEVELS[config.logging.level])
    formatter = logging.Formatter(
        "[%(asctime)s] [%(name)-12s] [%(levelname)-8s] - %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    formatter = MyFormatter()
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(DuplicateFilter())
    LOGGER.addHandler(handler)


class MyFormatter(logging.Formatter):
    # pylint: disable=protected-access
    base_format = "[%(asctime)s] [%(name)-24s] [%(levelname)-8s] - %(message)s"
    overwrite_fmt = "\x1b[80D\x1b[1A\x1b[K" + base_format

    def __init__(self):
        super().__init__(
            fmt=self.base_format, datefmt="%Y-%m-%d %H:%M:%S", style="%",
        )
        self.current_count = 0

    def format(self, record):
        # Save the original format configured by the user
        # when the logger formatter was instantiated
        format_orig = self._style._fmt

        # Replace the original format with one customized by logging level
        if "message repeated" in str(record.msg):
            self._style._fmt = self.overwrite_fmt

        # Call the original formatter class to do the grunt work
        result = logging.Formatter.format(self, record)

        # Restore the original format configured by the user
        self._style._fmt = format_orig

        return result


class DuplicateFilter(logging.Filter):
    # pylint: disable=attribute-defined-outside-init
    def filter(self, record):
        current_log = (record.name, record.module, record.levelno, record.msg)
        try:
            if current_log != getattr(self, "last_log", None):
                self.last_log = current_log
                self.current_count = 0
            else:
                self.current_count += 1
                if self.current_count > 0:
                    record.msg = "{}, message repeated {} times".format(
                        record.msg, self.current_count + 1
                    )
        except ValueError:
            pass
        return True


if __name__ == "__main__":
    Viseron()
