"""Post processor domain constants."""

# CAMERA_SCHEMA constants
CONFIG_CAMERAS = "cameras"
CONFIG_MASK = "mask"
CONFIG_COORDINATES = "coordinates"
CONFIG_LABELS = "labels"

DEFAULT_MASK: list[dict[str, int]] = []

DESC_CAMERAS = (
    "Camera-specific configuration. All subordinate "
    "keys corresponds to the <code>camera_identifier</code> of a configured camera."
)
DESC_LABELS_GLOBAL = (
    "A list of labels that when detected will be sent to the post processor. "
    "Applies to <b>all</b> cameras defined under <code>cameras</code>."
)
DESC_LABELS_LOCAL = (
    "A list of labels that when detected will be sent to the post processor. "
    "Applies <b>only</b> to this specific camera."
)
DESC_MASK = "A mask is used to exclude certain areas in the image from post processing."
DESC_COORDINATES = "List of X and Y coordinates to form a polygon"
