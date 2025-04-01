"""Config API Handler."""
import logging
from http import HTTPStatus

from viseron.components.compreface.const import COMPONENT
from viseron.components.compreface.face_recognition import FaceRecognition
from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.domains.face_recognition.const import DOMAIN as FACE_RECOGNITION_DOMAIN

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
            return

        added_subjects = []
        for face_rec in self._vis.get_registered_identifiers(
            FACE_RECOGNITION_DOMAIN
        ).values():
            if isinstance(face_rec, FaceRecognition):
                added_subjects.extend(face_rec.update_subject_entities())

        response = {}
        response["added_subjects"] = added_subjects
        await self.response_success(response=response)
