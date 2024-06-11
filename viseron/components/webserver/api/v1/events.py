"""API handler for Events."""
from __future__ import annotations

import datetime
import logging
import time
from collections.abc import Callable
from http import HTTPStatus
from typing import TYPE_CHECKING

import voluptuous as vol
from sqlalchemy import select

from viseron.components.storage.models import (
    Motion,
    Objects,
    PostProcessorResults,
    Recordings,
)
from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.domains.camera import FailedCamera
from viseron.domains.face_recognition import DOMAIN as FACE_RECOGNITION_DOMAIN

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from viseron.domains.camera import AbstractCamera

LOGGER = logging.getLogger(__name__)


class EventsAPIHandler(BaseAPIHandler):
    """API handler for Events."""

    routes = [
        {
            "path_pattern": (r"/events/(?P<camera_identifier>[A-Za-z0-9_]+)"),
            "supported_methods": ["GET"],
            "method": "get_events",
            "request_arguments_schema": vol.Schema(
                vol.Any(
                    {
                        vol.Required("time_from"): vol.Coerce(int),
                        vol.Required("time_to"): vol.Coerce(int),
                    },
                    {
                        vol.Required("date"): str,
                    },
                )
            ),
        },
    ]

    def _motion_events(
        self,
        get_session: Callable[[], Session],
        camera: AbstractCamera | FailedCamera,
        time_from: int,
        time_to: int,
    ) -> list:
        """Select motion events from database."""
        time_from_datetime = datetime.datetime.fromtimestamp(time_from)
        time_to_datetime = datetime.datetime.fromtimestamp(time_to)
        with get_session() as session:
            stmt = (
                select(Motion)
                .where(Motion.camera_identifier == camera.identifier)
                .where(Motion.start_time >= time_from_datetime)
                .where(Motion.start_time <= time_to_datetime)
            ).order_by(Motion.start_time.desc())
            motion = session.execute(stmt).scalars().all()
        motion_events = []
        if motion:
            for event in motion:
                motion_events.append(
                    {
                        "type": "motion",
                        "id": event.id,
                        "start_time": event.start_time,
                        "start_timestamp": event.start_time.timestamp(),
                        "end_time": event.end_time,
                        "end_timestamp": event.end_time.timestamp()
                        if event.end_time
                        else None,
                        "created_at": event.created_at,
                    }
                )
        return motion_events

    def _object_event(
        self,
        get_session: Callable[[], Session],
        camera: AbstractCamera | FailedCamera,
        time_from: int,
        time_to: int,
    ):
        """Select object events from database."""
        time_from_datetime = datetime.datetime.fromtimestamp(time_from)
        time_to_datetime = datetime.datetime.fromtimestamp(time_to)
        with get_session() as session:
            stmt = (
                select(Objects)
                .where(Objects.camera_identifier == camera.identifier)
                .where(Objects.created_at.between(time_from_datetime, time_to_datetime))
            ).order_by(Objects.created_at.desc())
            objects = session.execute(stmt).scalars().all()
        object_events = []
        if objects:
            for event in objects:
                object_events.append(
                    {
                        "type": "object",
                        "id": event.id,
                        "time": event.created_at,
                        "timestamp": event.created_at.timestamp(),
                        "label": event.label,
                        "confidence": event.confidence,
                        "created_at": event.created_at,
                        "snapshot_path": f"/files{event.snapshot_path}",
                    }
                )
        return object_events

    def _recording_events(
        self,
        get_session: Callable[[], Session],
        camera: AbstractCamera | FailedCamera,
        time_from: int,
        time_to: int,
    ) -> list:
        """Select recording events from database."""
        time_from_datetime = datetime.datetime.fromtimestamp(time_from)
        time_to_datetime = datetime.datetime.fromtimestamp(time_to)
        with get_session() as session:
            stmt = (
                select(Recordings)
                .where(Recordings.camera_identifier == camera.identifier)
                .where(Recordings.start_time >= time_from_datetime)
                .where(Recordings.start_time <= time_to_datetime)
            ).order_by(Recordings.start_time.desc())
            recordings = session.execute(stmt).scalars().all()
        recording_events = []
        if recordings:
            for event in recordings:
                recording_events.append(
                    {
                        "type": "recording",
                        "id": event.id,
                        "start_time": event.start_time,
                        "start_timestamp": event.start_time.timestamp(),
                        "end_time": event.end_time,
                        "end_timestamp": event.end_time.timestamp()
                        if event.end_time
                        else None,
                        "hls_url": (
                            "/api/v1/hls/"
                            f"{event.camera_identifier}/{event.id}/index.m3u8"
                        ),
                        "thumbnail_path": f"/files{event.thumbnail_path}",
                        "created_at": event.created_at,
                    }
                )
        return recording_events

    def _post_processor_events(
        self,
        get_session: Callable[[], Session],
        camera: AbstractCamera | FailedCamera,
        time_from: int,
        time_to: int,
    ) -> list:
        """Select post processor events from database."""
        time_from_datetime = datetime.datetime.fromtimestamp(time_from)
        time_to_datetime = datetime.datetime.fromtimestamp(time_to)
        with get_session() as session:
            stmt = (
                select(PostProcessorResults)
                .where(PostProcessorResults.camera_identifier == camera.identifier)
                .where(PostProcessorResults.domain.in_([FACE_RECOGNITION_DOMAIN]))
                .where(
                    PostProcessorResults.created_at.between(
                        time_from_datetime, time_to_datetime
                    )
                )
            ).order_by(PostProcessorResults.created_at.desc())
            post_processor_results = session.execute(stmt).scalars().all()
        post_processor_events = []
        if post_processor_results:
            for event in post_processor_results:
                post_processor_events.append(
                    {
                        "type": event.domain,
                        "id": event.id,
                        "time": event.created_at,
                        "timestamp": event.created_at.timestamp(),
                        "snapshot_path": f"/files{event.snapshot_path}",
                        "data": event.data,
                        "created_at": event.created_at,
                    }
                )
        return post_processor_events

    async def get_events(
        self,
        camera_identifier: str,
    ) -> None:
        """Get events."""
        camera = self._get_camera(camera_identifier, failed=True)

        if not camera:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason=f"Camera {camera_identifier} not found",
            )
            return

        # Get start of day in utc
        if "date" in self.request_arguments:
            time_from = (
                datetime.datetime.strptime(self.request_arguments["date"], "%Y-%m-%d")
                - datetime.timedelta(seconds=time.localtime().tm_gmtoff)
            ).timestamp()
            time_to = time_from + 86400
        else:
            time_from = self.request_arguments["time_from"]
            time_to = self.request_arguments["time_to"]

        motion_events = await self.run_in_executor(
            self._motion_events,
            self._get_session,
            camera,
            time_from,
            time_to,
        )
        recording_events = await self.run_in_executor(
            self._recording_events,
            self._get_session,
            camera,
            time_from,
            time_to,
        )
        object_events = await self.run_in_executor(
            self._object_event,
            self._get_session,
            camera,
            time_from,
            time_to,
        )
        post_processor_events = await self.run_in_executor(
            self._post_processor_events,
            self._get_session,
            camera,
            time_from,
            time_to,
        )

        sorted_events = sorted(
            motion_events + recording_events + object_events + post_processor_events,
            key=lambda k: k["created_at"],
            reverse=True,
        )

        self.response_success(response={"events": sorted_events})
