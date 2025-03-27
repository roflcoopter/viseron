"""Image classification module."""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from threading import Timer
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from viseron.domains.post_processor import BASE_CONFIG_SCHEMA, AbstractPostProcessor
from viseron.events import EventData
from viseron.helpers.schemas import FLOAT_MIN_ZERO

from .const import (
    CONFIG_EXPIRE_AFTER,
    DEFAULT_EXPIRE_AFTER,
    DESC_EXPIRE_AFTER,
    DOMAIN,
    EVENT_IMAGE_CLASSIFICATION_EXPIRED,
    EVENT_IMAGE_CLASSIFICATION_RESULT,
)
from .sensor import ImageClassificationSensor

if TYPE_CHECKING:
    from viseron.domains.post_processor import PostProcessorFrame


BASE_CONFIG_SCHEMA = BASE_CONFIG_SCHEMA.extend(
    {
        vol.Optional(
            CONFIG_EXPIRE_AFTER,
            default=DEFAULT_EXPIRE_AFTER,
            description=DESC_EXPIRE_AFTER,
        ): FLOAT_MIN_ZERO,
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
class EventImageClassification(EventData):
    """Hold information on image classification event."""

    camera_identifier: str
    result: list[ImageClassificationResult] | None


class AbstractImageClassification(AbstractPostProcessor):
    """Abstract image classification."""

    def __init__(self, vis, component, config, camera_identifier) -> None:
        super().__init__(vis, config, camera_identifier)
        self._expire_timer: Timer | None = None
        vis.add_entity(component, ImageClassificationSensor(vis, self._camera))

    def __post_init__(self, *args, **kwargs):
        """Post init hook."""
        self._vis.register_domain(DOMAIN, self._camera_identifier, self)

    @abstractmethod
    def image_classification(
        self, post_processor_frame: PostProcessorFrame
    ) -> list[ImageClassificationResult]:
        """Perform image classification."""

    def process(self, post_processor_frame: PostProcessorFrame) -> None:
        """Process frame and run image classification."""
        if self._expire_timer:
            self._expire_timer.cancel()

        result = self.image_classification(post_processor_frame)

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

    def expire_result(self, result: ImageClassificationResult) -> None:
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
