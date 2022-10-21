"""Image classification constants."""
from typing import Final

DOMAIN: Final = "image_classification"


# Event topic constants
EVENT_IMAGE_CLASSIFICATION_RESULT = "{camera_identifier}/image_classification/result"
EVENT_IMAGE_CLASSIFICATION_EXPIRED = "{camera_identifier}/image_classification/expired"


# BASE_CONFIG_SCHEMA constants
CONFIG_EXPIRE_AFTER = "expire_after"

DEFAULT_EXPIRE_AFTER = 5

DESC_EXPIRE_AFTER = "Time in seconds before a classification expires."
