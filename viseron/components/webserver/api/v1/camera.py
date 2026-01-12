"""Camera API Handler."""
from __future__ import annotations

import asyncio
import logging
import time
from http import HTTPStatus

import cv2
import httpx
import imutils
import numpy as np
import voluptuous as vol

from viseron.components.storage.models import TriggerTypes
from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.components.webserver.auth import Role
from viseron.domains.camera import AbstractCamera
from viseron.domains.camera.const import (
    AUTHENTICATION_BASIC,
    AUTHENTICATION_DIGEST,
    CONFIG_AUTHENTICATION,
    CONFIG_PASSWORD,
    CONFIG_URL,
    CONFIG_USE_LAST_SNAPSHOT_ON_ERROR,
    CONFIG_USERNAME,
)
from viseron.domains.camera.recorder import ManualRecording
from viseron.helpers.validators import request_argument_bool

LOGGER = logging.getLogger(__name__)


class CameraAPIHandler(BaseAPIHandler):
    """Handler for API calls related to a camera."""

    camera_snapshots: dict[str, bytes | None] = {}

    routes = [
        {
            "requires_auth": False,
            "requires_camera_token": True,
            "path_pattern": r"/camera/(?P<camera_identifier>[A-Za-z0-9_]+)/snapshot",
            "supported_methods": ["GET"],
            "method": "get_snapshot",
            "request_arguments_schema": vol.Schema(
                {
                    vol.Optional("rand", default=None): vol.Maybe(str),
                    vol.Optional("width", default=None): vol.Maybe(vol.Coerce(int)),
                    vol.Optional("height", default=None): vol.Maybe(vol.Coerce(int)),
                    vol.Optional("access_token", default=None): vol.Maybe(str),
                },
            ),
        },
        {
            "path_pattern": r"/camera/(?P<camera_identifier>[A-Za-z0-9_]+)",
            "supported_methods": ["GET"],
            "method": "get_camera_endpoint",
            "request_arguments_schema": vol.Schema(
                {
                    vol.Optional("failed", default=False): request_argument_bool,
                },
            ),
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": r"/camera/(?P<camera_identifier>[A-Za-z0-9_]+)/start",
            "supported_methods": ["POST"],
            "method": "post_start_camera",
        },
        {
            "requires_role": [Role.ADMIN],
            "path_pattern": r"/camera/(?P<camera_identifier>[A-Za-z0-9_]+)/stop",
            "supported_methods": ["POST"],
            "method": "post_stop_camera",
        },
        {
            "path_pattern": (
                r"/camera/(?P<camera_identifier>[A-Za-z0-9_]+)/manual_recording"
            ),
            "supported_methods": ["POST"],
            "method": "post_manual_recording",
            "json_body_schema": vol.Schema(
                vol.Any(
                    {
                        vol.Required("action"): vol.All(vol.Lower, "start"),
                        vol.Optional("duration"): vol.All(
                            vol.Coerce(int), vol.Range(min=1)
                        ),
                    },
                    {
                        vol.Required("action"): vol.All(vol.Lower, "stop"),
                    },
                )
            ),
        },
    ]

    def _get_auth(
        self, camera: AbstractCamera
    ) -> httpx.DigestAuth | httpx.BasicAuth | None:
        """Return auth for camera."""
        if (
            camera.still_image
            and camera.still_image[CONFIG_USERNAME]
            and camera.still_image[CONFIG_PASSWORD]
        ):
            if camera.still_image[CONFIG_AUTHENTICATION] == AUTHENTICATION_DIGEST:
                return httpx.DigestAuth(
                    camera.still_image[CONFIG_USERNAME],
                    camera.still_image[CONFIG_PASSWORD],
                )
            if camera.still_image[CONFIG_AUTHENTICATION] == AUTHENTICATION_BASIC:
                return httpx.BasicAuth(
                    camera.still_image[CONFIG_USERNAME],
                    camera.still_image[CONFIG_PASSWORD],
                )
        return None

    def _snapshot_from_url(self, camera: AbstractCamera) -> bytes | None:
        """Return snapshot from camera url."""
        auth = self._get_auth(camera)
        response = httpx.get(
            camera.still_image[CONFIG_URL],
            auth=auth,
        )
        if response.status_code == 200:
            img_array = np.asarray(bytearray(response.content), dtype=np.uint8)
            img = cv2.imdecode(img_array, -1)
            if self.request_arguments["width"] and self.request_arguments["height"]:
                img = cv2.resize(
                    img,
                    (self.request_arguments["width"], self.request_arguments["height"]),
                    interpolation=cv2.INTER_AREA,
                )
            elif self.request_arguments["width"] or self.request_arguments["height"]:
                img = imutils.resize(
                    img,
                    self.request_arguments["width"],
                    self.request_arguments["height"],
                )

            ret, jpg = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
            if ret:
                return jpg.tobytes()
            return None

        LOGGER.error(
            "Failed to retrieve the image from the camera. Status code: %s",
            response.status_code,
        )
        return None

    def _snapshot_from_memory(self, camera: AbstractCamera) -> bytes | None:
        """Return snapshot from camera memory."""
        if camera.current_frame:
            with camera.current_frame:
                ret, jpg = camera.get_snapshot(
                    camera.current_frame,
                    self.request_arguments["width"],
                    self.request_arguments["height"],
                )
                if ret:
                    return jpg
        return None

    async def get_snapshot(self, camera_identifier: str) -> None:
        """Return camera snapshot."""
        camera = await self.run_in_executor(self._get_camera, camera_identifier)
        if not camera:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason=f"Camera {camera_identifier} not found",
            )
            return

        jpg = None
        try:
            if camera.still_image_configured:
                jpg = await self.run_in_executor(self._snapshot_from_url, camera)
            else:
                jpg = await self.run_in_executor(self._snapshot_from_memory, camera)
        except Exception as exception:  # pylint: disable=broad-except
            LOGGER.error(
                "Error fetching camera snapshot for camera %s: %s",
                camera_identifier,
                exception,
            )
            if camera.still_image[CONFIG_USE_LAST_SNAPSHOT_ON_ERROR]:
                jpg = CameraAPIHandler.camera_snapshots.get(camera_identifier, None)
        else:
            if camera.still_image[CONFIG_USE_LAST_SNAPSHOT_ON_ERROR]:
                CameraAPIHandler.camera_snapshots[camera_identifier] = jpg

        if jpg is None:
            self.response_error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                reason="Could not fetch camera snapshot",
            )
            return

        await self.response_success(
            response=jpg, headers={"Content-Type": "image/jpeg"}
        )
        return

    async def get_camera_endpoint(self, camera_identifier: str) -> None:
        """Return camera."""
        camera = self._get_camera(
            camera_identifier, failed=self.request_arguments["failed"]
        )
        if not camera:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason=f"Camera {camera_identifier} not found",
            )
            return

        await self.response_success(response=camera.as_dict())
        return

    async def post_start_camera(self, camera_identifier: str) -> None:
        """Start camera."""
        camera = self._get_camera(camera_identifier, failed=False)
        if not camera:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason=f"Camera {camera_identifier} not found",
            )
            return

        nvr = self.get_nvr(camera_identifier)
        if not nvr:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason=f"NVR for camera {camera_identifier} not found",
            )
            return

        if camera.is_on:
            await self.response_success()
            return

        await self.run_in_executor(camera.start_camera)
        await self.response_success()
        return

    async def post_stop_camera(self, camera_identifier: str) -> None:
        """Stop camera."""
        camera = self._get_camera(camera_identifier, failed=False)
        if not camera:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason=f"Camera {camera_identifier} not found",
            )
            return

        nvr = self.get_nvr(camera_identifier)
        if not nvr:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason=f"NVR for camera {camera_identifier} not found",
            )
            return

        if not camera.is_on:
            await self.response_success()
            return

        await self.run_in_executor(camera.stop_camera)
        await self.response_success()
        return

    async def post_manual_recording(self, camera_identifier: str) -> None:
        """Start/stop manual recording."""
        camera = self._get_camera(camera_identifier, failed=False)
        if not camera:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason=f"Camera {camera_identifier} not found",
            )
            return

        nvr = self.get_nvr(camera_identifier)
        if not nvr:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason=f"NVR for camera {camera_identifier} not found",
            )
            return

        if not camera.is_on or not camera.connected:
            self.response_error(
                HTTPStatus.BAD_REQUEST,
                reason="Camera is off or disconnected",
            )
            return

        if nvr.operation_state == "idle":
            self.response_error(
                HTTPStatus.BAD_REQUEST,
                reason="NVR is idle",
            )
            return

        async def wait_for_recording_start(timeout=5) -> bool:
            """Wait for recording to start."""
            start_time = time.time()
            while True:
                if time.time() - start_time > timeout:
                    return False

                if (
                    nvr.camera.is_recording
                    and nvr.camera.recorder.active_recording
                    and (
                        nvr.camera.recorder.active_recording.trigger_type
                        == TriggerTypes.MANUAL
                    )
                ):
                    return True
                await asyncio.sleep(0.1)

        async def wait_for_recording_stop(timeout=5) -> bool:
            """Wait for recording to stop."""
            start_time = time.time()
            while True:
                if time.time() - start_time > timeout:
                    return False

                if not nvr.camera.is_recording:
                    return True
                await asyncio.sleep(0.1)

        action = self.json_body["action"]
        if action == "start":
            duration = self.json_body.get("duration", None)
            manual_recording = ManualRecording(duration=duration)
            await self.run_in_executor(nvr.start_manual_recording, manual_recording)
            if await wait_for_recording_start():
                await self.response_success()
                return
            return self.response_error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                reason="Failed to start manual recording",
            )

        if action == "stop":
            await self.run_in_executor(nvr.stop_manual_recording)
            if await wait_for_recording_stop():
                await self.response_success()
                return
            return self.response_error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                reason="Failed to stop manual recording",
            )

        self.response_error(
            HTTPStatus.BAD_REQUEST,
            reason="Invalid action specified",
        )
        return
