"""Storage component constants."""
from __future__ import annotations

from typing import Any, Final

COMPONENT = "storage"

DATABASE_URL = "postgresql://localhost/viseron"

MOVE_FILES_THROTTLE_SECONDS = 10

# Storage configuration
DESC_COMPONENT = "Storage configuration."
DEFAULT_COMPONENT: dict[str, Any] = {}
CONFIG_PATH: Final = "path"
CONFIG_POLL: Final = "poll"
CONFIG_MOVE_ON_SHUTDOWN: Final = "move_on_shutdown"
CONFIG_MIN_SIZE: Final = "min_size"
CONFIG_MAX_SIZE: Final = "max_size"
CONFIG_MAX_AGE: Final = "max_age"
CONFIG_MIN_AGE: Final = "min_age"
CONFIG_GB: Final = "gb"
CONFIG_MB: Final = "mb"
CONFIG_DAYS: Final = "days"
CONFIG_HOURS: Final = "hours"
CONFIG_MINUTES: Final = "minutes"
CONFIG_RECORDER: Final = "recorder"
CONFIG_CREATE_EVENT_CLIP: Final = "create_event_clip"
CONFIG_CONTINUOUS: Final = "continuous"
CONFIG_EVENTS: Final = "events"
CONFIG_SNAPSHOTS: Final = "snapshots"
CONFIG_FACE_RECOGNITION: Final = "face_recognition"
CONFIG_OBJECT_DETECTION: Final = "object_detection"
CONFIG_TIERS: Final = "tiers"


DEFAULT_RECORDER: dict[str, Any] = {}
DEFAULT_RECORDER_TIERS = [
    {
        CONFIG_PATH: "/",
        CONFIG_EVENTS: {
            CONFIG_MAX_AGE: {
                CONFIG_DAYS: 7,
            },
        },
    },
]
DEFAULT_CREATE_EVENT_CLIP = False
DEFAULT_SNAPSHOTS: dict[str, Any] = {}
DEFAULT_SNAPSHOTS_TIERS = [
    {
        CONFIG_PATH: "/",
        CONFIG_MAX_AGE: {
            CONFIG_DAYS: 7,
        },
    },
]
DEFAULT_FACE_RECOGNITION: Final = None
DEFAULT_OBJECT_DETECTION: Final = None

DEFAULT_POLL = False
DEFAULT_MOVE_ON_SHUTDOWN = False
DEFAULT_GB: Final = None
DEFAULT_MB: Final = None
DEFAULT_DAYS: Final = None
DEFAULT_HOURS: Final = None
DEFAULT_MINUTES: Final = None
DEFAULT_MIN_SIZE: dict[str, Any] = {}
DEFAULT_MAX_SIZE: dict[str, Any] = {}
DEFAULT_MIN_AGE: dict[str, Any] = {}
DEFAULT_MAX_AGE: dict[str, Any] = {}
DEFAULT_CONTINUOUS: Final = None
DEFAULT_EVENTS: Final = None

DESC_RECORDER = "Configuration for recordings."
DESC_CREATE_EVENT_CLIP = (
    "Concatenate segments to an MP4 file for each event. "
    "WARNING: Will store both the segments AND the MP4 file."
)
DESC_TYPE = (
    "<code>continuous</code>: Will save everything but highlight Events.<br>"
    "<code>events</code>: Will only save Events.<br>"
    "Events are started by <code>trigger_recorder</code>, and ends when either no "
    "objects or no motion (or both) is detected, depending on the configuration."
)
DESC_RECORDER_TIERS = (
    "Tiers are used to move files between different storage locations. "
    "When a file reaches the max age or max size of a tier, it will be moved to the "
    "next tier. "
    "If the file is already in the last tier, it will be deleted. "
)
DESC_SNAPSHOTS = (
    "Snapshots are images taken when events are triggered or post processors finds "
    "anything. "
    "Snapshots will be taken for object detection, motiond detection, and any post "
    "processor that scans the image, for example face and license plate recognition."
)
DESC_SNAPSHOTS_TIERS = (
    "Default tiers for all domains, unless overridden in the domain configuration.<br>"
    f"{DESC_RECORDER_TIERS} "
)
DESC_DOMAIN_TIERS = DESC_RECORDER_TIERS
DESC_FACE_RECOGNITION = (
    "Override the default snapshot tiers for face recognition. "
    "If not set, the default tiers will be used."
)
DESC_OBJECT_DETECTION = (
    "Override the default snapshot tiers for object detection. "
    "If not set, the default tiers will be used."
)
DESC_GB = "Max size in GB. Added together with <code>max_mb</code>."
DESC_MB = "Max size in MB. Added together with <code>max_gb</code>."
DESC_DAYS = "Max age in days."
DESC_HOURS = "Max age in hours."
DESC_MINUTES = "Max age in minutes."
DESC_PATH = (
    "Path to store files in. Cannot be <code>/tmp</code> or <code>/tmp/viseron</code>."
)
DESC_POLL = (
    "Poll the file system for new files. "
    "Much slower than non-polling but required for some file systems like NTFS mounts."
)
DESC_MOVE_ON_SHUTDOWN = (
    "Move/delete files to the next tier when Viseron shuts down. "
    "Useful to not lose files when shutting down Viseron if using a RAM disk."
)
DESC_MIN_SIZE = "Minimum size of files to keep in this tier."
DESC_MAX_SIZE = "Maximum size of files to keep in this tier."
DESC_MIN_AGE = "Minimum age of files to keep in this tier."
DESC_MAX_AGE = "Maximum age of files to keep in this tier."
DESC_CONTINUOUS = "Retention rules for continuous recordings."
DESC_EVENTS = "Retention rules for event recordings."
