"""NVR component."""

import logging
import threading
from queue import Queue
from typing import List

import voluptuous as vol

from viseron.components.data_stream import (
    COMPONENT as DATA_STREAM_COMPONENT,
    DataStream,
)
from viseron.const import VISERON_SIGNAL_SHUTDOWN
from viseron.domains.camera import DOMAIN as CAMERA_DOMAIN, SharedFrame, SharedFrames
from viseron.helpers.validators import ensure_slug
from viseron.watchdog.thread_watchdog import RestartableThread

from .const import (
    COMPONENT,
    CONFIG_COORDINATES,
    CONFIG_FPS,
    CONFIG_LABEL_CONFIDENCE,
    CONFIG_LABEL_HEIGHT_MAX,
    CONFIG_LABEL_HEIGHT_MIN,
    CONFIG_LABEL_LABEL,
    CONFIG_LABEL_POST_PROCESSOR,
    CONFIG_LABEL_REQUIRE_MOTION,
    CONFIG_LABEL_TRIGGER_RECORDER,
    CONFIG_LABEL_WIDTH_MAX,
    CONFIG_LABEL_WIDTH_MIN,
    CONFIG_LABELS,
    CONFIG_LOG_ALL_OBJECTS,
    CONFIG_MASK,
    CONFIG_MAX_FRAME_AGE,
    CONFIG_MOTION_DETECTOR,
    CONFIG_OBJECT_DETECTOR,
    CONFIG_TRIGGER_DETECTOR,
    CONFIG_X,
    CONFIG_Y,
    CONFIG_ZONE_LABELS,
    CONFIG_ZONE_NAME,
    CONFIG_ZONES,
    DEFAULT_FPS,
    DEFAULT_LABEL_CONFIDENCE,
    DEFAULT_LABEL_HEIGHT_MAX,
    DEFAULT_LABEL_HEIGHT_MIN,
    DEFAULT_LABEL_POST_PROCESSOR,
    DEFAULT_LABEL_REQUIRE_MOTION,
    DEFAULT_LABEL_TRIGGER_RECORDER,
    DEFAULT_LABEL_WIDTH_MAX,
    DEFAULT_LABEL_WIDTH_MIN,
    DEFAULT_LABELS,
    DEFAULT_LOG_ALL_OBJECTS,
    DEFAULT_MASK,
    DEFAULT_MAX_FRAME_AGE,
    DEFAULT_TRIGGER_DETECTOR,
    DEFAULT_ZONES,
)
from .zone import Zone

LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        COMPONENT: vol.Schema(
            {
                vol.All(str, ensure_slug): vol.Maybe({vol.Extra: object}),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

COORDINATES_SCHEMA = vol.Schema(
    [
        {
            vol.Required(CONFIG_X): int,
            vol.Required(CONFIG_Y): int,
        }
    ]
)

MIN_MAX_SCHEMA = vol.Schema(
    vol.All(
        vol.Any(0, 1, vol.All(float, vol.Range(min=0.0, max=1.0))), vol.Coerce(float)
    )
)


def ensure_min_max(label: dict) -> dict:
    """Ensure min values are not larger than max values."""
    if label["height_min"] >= label["height_max"]:
        raise vol.Invalid("height_min may not be larger or equal to height_max")
    if label["width_min"] >= label["width_max"]:
        raise vol.Invalid("width_min may not be larger or equal to width_max")
    return label


LABEL_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_LABEL_LABEL): str,
        vol.Optional(
            CONFIG_LABEL_CONFIDENCE, default=DEFAULT_LABEL_CONFIDENCE
        ): MIN_MAX_SCHEMA,
        vol.Optional(
            CONFIG_LABEL_HEIGHT_MIN, default=DEFAULT_LABEL_HEIGHT_MIN
        ): MIN_MAX_SCHEMA,
        vol.Optional(
            CONFIG_LABEL_HEIGHT_MAX, default=DEFAULT_LABEL_HEIGHT_MAX
        ): MIN_MAX_SCHEMA,
        vol.Optional(
            CONFIG_LABEL_WIDTH_MIN, default=DEFAULT_LABEL_WIDTH_MIN
        ): MIN_MAX_SCHEMA,
        vol.Optional(
            CONFIG_LABEL_WIDTH_MAX, default=DEFAULT_LABEL_WIDTH_MAX
        ): MIN_MAX_SCHEMA,
        vol.Optional(
            CONFIG_LABEL_TRIGGER_RECORDER, default=DEFAULT_LABEL_TRIGGER_RECORDER
        ): bool,
        vol.Optional(
            CONFIG_LABEL_REQUIRE_MOTION, default=DEFAULT_LABEL_REQUIRE_MOTION
        ): bool,
        vol.Optional(
            CONFIG_LABEL_POST_PROCESSOR, default=DEFAULT_LABEL_POST_PROCESSOR
        ): vol.Any(str, None),
    },
    ensure_min_max,
)

ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_ZONE_NAME): str,
        vol.Required(CONFIG_COORDINATES): COORDINATES_SCHEMA,
        vol.Optional(CONFIG_ZONE_LABELS): [LABEL_SCHEMA],
    }
)


OBJECT_DETECTOR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONFIG_FPS, default=DEFAULT_FPS): vol.All(
            vol.Any(float, int), vol.Coerce(float), vol.Range(min=0.0)
        ),
        vol.Optional(CONFIG_LABELS, default=DEFAULT_LABELS): vol.Any(
            [], [LABEL_SCHEMA]
        ),
        vol.Optional(CONFIG_MAX_FRAME_AGE, default=DEFAULT_MAX_FRAME_AGE): vol.All(
            vol.Any(float, int), vol.Coerce(float), vol.Range(min=0.0)
        ),
        vol.Optional(CONFIG_LOG_ALL_OBJECTS, default=DEFAULT_LOG_ALL_OBJECTS): bool,
        vol.Optional(CONFIG_MASK, default=DEFAULT_MASK): [
            {vol.Required(CONFIG_COORDINATES): COORDINATES_SCHEMA}
        ],
    }
)

MOTION_DETECTOR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONFIG_TRIGGER_DETECTOR, default=DEFAULT_TRIGGER_DETECTOR): bool,
    }
)

NVR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONFIG_OBJECT_DETECTOR): OBJECT_DETECTOR_SCHEMA,
        vol.Optional(CONFIG_MOTION_DETECTOR): MOTION_DETECTOR_SCHEMA,
        vol.Optional(CONFIG_ZONES, default=DEFAULT_ZONES): [ZONE_SCHEMA],
    }
)


def validate_nvr_config(config, camera_identifier):
    """Validate the config of an NVR entry."""
    try:
        return NVR_SCHEMA(config)
    except vol.Invalid as ex:
        LOGGER.exception(f"Error setting up nvr for camera {camera_identifier}: {ex}")
        return None
    except Exception:  # pylint: disable=broad-except
        LOGGER.exception("Unknown error calling %s CONFIG_SCHEMA", camera_identifier)
        return None
    return True


def setup(vis, config):
    """Set up the nvr component."""
    config = config[COMPONENT]
    for camera_identifier in config.keys():
        if config[camera_identifier] is None:
            config[camera_identifier] = {}
        if validated_config := validate_nvr_config(
            config[camera_identifier], camera_identifier
        ):
            nvr = NVR(vis, validated_config, camera_identifier)
            vis.register_signal_handler(VISERON_SIGNAL_SHUTDOWN, nvr.stop)

    return True


class NVR:
    """NVR class that orchestrates all handling of camera streams."""

    def __init__(self, vis, config: dict, camera_identifier: str):
        vis.data.setdefault(COMPONENT, {})[camera_identifier] = self
        self._config = config
        self._camera = vis.data[CAMERA_DOMAIN][camera_identifier]

        self.setup_loggers()
        self._logger = logging.getLogger(__name__ + "." + camera_identifier)
        self._logger.debug(f"Initializing NVR for camera {self._camera.name}")

        self._kill_received = False
        self._data_stream: DataStream = vis.data[DATA_STREAM_COMPONENT]
        self._shared_frames = SharedFrames()

        self._motion_detector = config.get(CONFIG_MOTION_DETECTOR, None)
        if not self._motion_detector:
            self._logger.info("Motion detector is disabled")
        self._scan_motion = threading.Event()
        self._motion_scan_interval = round(
            self._camera.output_fps / config[CONFIG_MOTION_DETECTOR][CONFIG_FPS]
        )

        self._object_detector = config.get(CONFIG_OBJECT_DETECTOR, None)
        if not self._object_detector:
            self._logger.info("Object detector is disabled")
        self._scan_object = threading.Event()
        self._object_scan_interval = round(
            self._camera.output_fps / config[CONFIG_OBJECT_DETECTOR][CONFIG_FPS]
        )

        if (
            self._motion_detector
            and config[CONFIG_MOTION_DETECTOR][CONFIG_TRIGGER_DETECTOR]
        ):
            self._scan_motion.set()
            self._scan_object.clear()
        else:
            if self._object_detector:
                self._scan_object.set()
            self._scan_motion.clear()

        self._zones: List[Zone] = []
        for zone in config[CONFIG_ZONES]:
            self._zones.append(Zone(vis, camera_identifier, config, zone))

        self._frame_queue: "Queue[bytes]" = Queue(maxsize=100)
        self._data_stream.subscribe_data(
            self._camera.frame_bytes_topic, self._frame_queue
        )
        RestartableThread(
            name=str(self),
            target=self.run,
            stop_target=self.stop,
            daemon=False,
            register=True,
        ).start()

        self._camera.start_camera()
        self._logger.debug(f"NVR for camera {self._camera.name} initialized")

    def setup_loggers(self):
        """Set up custom log names and levels."""
        self._logger = logging.getLogger(__name__ + "." + self._camera.identifier)
        self._motion_logger = logging.getLogger(
            __name__ + "." + self._camera.identifier + ".motion"
        )
        self._object_logger = logging.getLogger(
            __name__ + "." + self._camera.identifier + ".object"
        )

    def check_scan_interval(self, frame_number, frame_interval):
        """Check if frame should be marked for scanning."""
        return frame_number % frame_interval == 0

    def process_frame(self, shared_frame: SharedFrame):
        """Process frame."""
        self._logger.debug(f"Processing frame {shared_frame}")
        shared_frame.nvr_config = self._config

        self._shared_frames.remove(shared_frame)

    def run(self):
        """Read frames from camera."""
        self._logger.debug("Waiting for first frame")
        frame = self._frame_queue.get()
        self._logger.debug("First frame received")
        self.process_frame(frame)

        while not self._kill_received:
            frame = self._frame_queue.get()
            self._logger.debug("Got new frame")
            self.process_frame(frame)

    def stop(self):
        """Stop processing of events."""
        self._logger.info("Stopping NVR thread")
        self._kill_received = True

        # Stop frame grabber
        self._camera.stop_camera()

        # Stop potential recording
        if self._camera.is_recording:
            self._camera.stop_recording()
