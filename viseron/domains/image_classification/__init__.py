"""Image classification module."""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from threading import Timer
from typing import TYPE_CHECKING, Any, List

import numpy as np
import voluptuous as vol

from viseron.domains.post_processor import BASE_CONFIG_SCHEMA, AbstractPostProcessor
from viseron.helpers.validators import none_to_dict

from .const import (
    CONFIG_CAMERAS,
    CONFIG_EXPIRE_AFTER,
    DEFAULT_EXPIRE_AFTER,
    EVENT_IMAGE_CLASSIFICATION_EXPIRED,
    EVENT_IMAGE_CLASSIFICATION_RESULT,
)
from .sensor import ImageClassificationSensor

if TYPE_CHECKING:
    from viseron.domains.post_processor import PostProcessorFrame


BASE_CONFIG_SCHEMA = BASE_CONFIG_SCHEMA.extend(
    {
        vol.Optional(CONFIG_EXPIRE_AFTER, default=DEFAULT_EXPIRE_AFTER): vol.All(
            vol.Any(vol.All(int, vol.Range(min=0)), vol.All(float, vol.Range(min=0.0))),
            vol.Coerce(float),
        ),
        vol.Required(CONFIG_CAMERAS): {
            str: vol.All(
                None,
                none_to_dict,
            )
        },
    }
)


@dataclass
class ImageClassificationResult:
    """Object that holds information on image classification."""

    camera_identifier: str
    label: str
    confidence: float

    def as_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "camera_identifier": self.camera_identifier,
            "label": self.label,
            "confidence": round(float(self.confidence), 3),
        }


@dataclass
class EventImageClassification:
    """Hold information on image classification event."""

    camera_identifier: str
    result: List[ImageClassificationResult] | None


class AbstractImageClassification(AbstractPostProcessor):
    """Abstract image classification."""

    def __init__(self, vis, component, config, camera_identifier):
        super().__init__(vis, config, camera_identifier)
        self._expire_timer: Timer | None = None
        vis.add_entity(component, ImageClassificationSensor(vis, self._camera))

    @abstractmethod
    def preprocess(self, post_processor_frame: PostProcessorFrame) -> np.ndarray:
        """Perform preprocessing of frame before running classification."""

    @abstractmethod
    def image_classification(
        self, frame: np.ndarray, post_processor_frame: PostProcessorFrame
    ) -> List[ImageClassificationResult]:
        """Perform image classification."""

    def process(self, post_processor_frame: PostProcessorFrame):
        """Process frame and run image classification."""
        if self._expire_timer:
            self._expire_timer.cancel()

        preprocessed_frame = self.preprocess(post_processor_frame)
        result = self.image_classification(preprocessed_frame, post_processor_frame)
        self._vis.dispatch_event(
            EVENT_IMAGE_CLASSIFICATION_RESULT.format(
                camera_identifier=self._camera.identifier
            ),
            EventImageClassification(
                camera_identifier=self._camera.identifier,
                result=result,
            ),
        )
        if self._config[CONFIG_EXPIRE_AFTER] and result:
            self._expire_timer = Timer(
                self._config[CONFIG_EXPIRE_AFTER], self.expire_result, (result,)
            )
            self._expire_timer.start()

    def expire_result(self, result: ImageClassificationResult):
        """Expire result after a given number of seconds."""
        self._logger.debug(f"Expiring image classification result {result}")
        self._vis.dispatch_event(
            EVENT_IMAGE_CLASSIFICATION_EXPIRED.format(
                camera_identifier=self._camera.identifier, result=result
            ),
            EventImageClassification(
                camera_identifier=self._camera.identifier,
                result=None,
            ),
        )
