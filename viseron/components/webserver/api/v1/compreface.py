"""Config API Handler."""
import logging
from http import HTTPStatus

from compreface.collections import Subjects

from viseron.components.compreface.const import (
    COMPONENT,
    CONFIG_FACE_RECOGNITION,
    SUBJECTS,
)
from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.const import REGISTERED_DOMAINS
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN
from viseron.domains.face_recognition.binary_sensor import FaceDetectionBinarySensor

LOGGER = logging.getLogger(__name__)


class ComprefaceAPIHandler(BaseAPIHandler):
    """Handler for API calls related to compreface."""

    routes = [
        {
            "path_pattern": r"/compreface/update_subjects",
            "supported_methods": ["GET"],
            "method": "update_subjects",
        },
    ]

    async def update_subjects(self) -> None:
        """Update Viseron subjects."""
        if COMPONENT not in self._vis.data:
            self.response_error(
                status_code=HTTPStatus.BAD_REQUEST,
                reason="Compreface Recognition not initialized.",
            )
        else:
            subjects: Subjects = self._vis.data[COMPONENT][
                CONFIG_FACE_RECOGNITION
            ].get_subjects()
            added_subjects = []
            for camera in (
                self._vis.data[REGISTERED_DOMAINS].get(CAMERA_DOMAIN, {}).values()
            ):
                for subject in subjects.list()[SUBJECTS]:
                    binary_sensor = FaceDetectionBinarySensor(
                        self._vis, camera, subject
                    )
                    if not self._vis.states.entity_exists(binary_sensor):
                        added_subjects.append(f"{camera.identifier}_{subject}")
                        self._vis.add_entity(
                            COMPONENT,
                            FaceDetectionBinarySensor(self._vis, camera, subject),
                        )
            response = {}
            response["added_subjects"] = added_subjects
            await self.response_success(response=response)
