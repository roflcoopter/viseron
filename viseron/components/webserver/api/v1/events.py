"""API handler for Events."""
from __future__ import annotations

import datetime
import logging
from collections.abc import Callable
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from sqlalchemy import func, select

from viseron.components.storage.models import (
    Files,
    Motion,
    Objects,
    PostProcessorResults,
    Recordings,
)
from viseron.components.webserver.api.handlers import BaseAPIHandler
from viseron.components.webserver.auth import Role
from viseron.domains.camera import FailedCamera
from viseron.domains.face_recognition.const import DOMAIN as FACE_RECOGNITION_DOMAIN
from viseron.domains.license_plate_recognition.const import (
    DOMAIN as LICENSE_PLATE_RECOGNITION_DOMAIN,
)
from viseron.helpers import daterange_to_utc

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
        {
            "path_pattern": (r"/events/(?P<camera_identifier>[A-Za-z0-9_]+)/amount"),
            "supported_methods": ["GET"],
            "method": "get_events_amount",
        },
        {
            "requires_role": [Role.ADMIN, Role.READ, Role.WRITE],
            "path_pattern": r"/events/amount",
            "supported_methods": ["POST"],
            "method": "post_events_amount_multiple",
            "json_body_schema": vol.Schema(
                {
                    vol.Required("camera_identifiers"): [str],
                }
            ),
        },
        {
            "requires_role": [Role.ADMIN, Role.READ, Role.WRITE],
            "path_pattern": r"/events/dates_of_interest",
            "supported_methods": ["POST"],
            "method": "post_events_dates_of_interest",
            "json_body_schema": vol.Schema(
                {
                    vol.Required("camera_identifiers"): [str],
                }
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
        time_from_datetime = datetime.datetime.fromtimestamp(
            time_from, tz=datetime.timezone.utc
        )
        time_to_datetime = datetime.datetime.fromtimestamp(
            time_to, tz=datetime.timezone.utc
        )
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
                        "camera_identifier": event.camera_identifier,
                        "type": "motion",
                        "id": event.id,
                        "start_time": event.start_time,
                        "start_timestamp": event.start_time.timestamp(),
                        "end_time": event.end_time,
                        "end_timestamp": event.end_time.timestamp()
                        if event.end_time
                        else None,
                        "duration": (event.end_time - event.start_time).total_seconds()
                        if event.end_time
                        else None,
                        "snapshot_path": f"/files{event.snapshot_path}"
                        if event.snapshot_path
                        else None,
                        "created_at": event.created_at,
                        "created_at_timestamp": event.created_at.timestamp(),
                        "lookback": camera.recorder.lookback,
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
        time_from_datetime = datetime.datetime.fromtimestamp(
            time_from, tz=datetime.timezone.utc
        )
        time_to_datetime = datetime.datetime.fromtimestamp(
            time_to, tz=datetime.timezone.utc
        )
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
                        "camera_identifier": event.camera_identifier,
                        "type": "object",
                        "id": event.id,
                        "time": event.created_at,
                        "timestamp": event.created_at.timestamp(),
                        "label": event.label,
                        "confidence": event.confidence,
                        "created_at": event.created_at,
                        "created_at_timestamp": event.created_at.timestamp(),
                        "snapshot_path": f"/files{event.snapshot_path}",
                        "lookback": camera.recorder.lookback,
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
        time_from_datetime = datetime.datetime.fromtimestamp(
            time_from, tz=datetime.timezone.utc
        )
        time_to_datetime = datetime.datetime.fromtimestamp(
            time_to, tz=datetime.timezone.utc
        )
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
                        "camera_identifier": event.camera_identifier,
                        "type": "recording",
                        "id": event.id,
                        "trigger_type": event.trigger_type,
                        "start_time": event.start_time,
                        "start_timestamp": event.start_time.timestamp(),
                        "end_time": event.end_time,
                        "end_timestamp": event.end_time.timestamp()
                        if event.end_time
                        else None,
                        "duration": (event.end_time - event.start_time).total_seconds()
                        if event.end_time
                        else None,
                        "hls_url": (
                            "/api/v1/hls/"
                            f"{event.camera_identifier}/{event.id}/index.m3u8"
                        ),
                        "thumbnail_path": f"/files{event.thumbnail_path}",
                        "created_at": event.created_at,
                        "created_at_timestamp": event.created_at.timestamp(),
                        "lookback": camera.recorder.lookback,
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
        time_from_datetime = datetime.datetime.fromtimestamp(
            time_from, tz=datetime.timezone.utc
        )
        time_to_datetime = datetime.datetime.fromtimestamp(
            time_to, tz=datetime.timezone.utc
        )
        with get_session() as session:
            stmt = (
                select(PostProcessorResults)
                .where(PostProcessorResults.camera_identifier == camera.identifier)
                .where(
                    PostProcessorResults.domain.in_(
                        [FACE_RECOGNITION_DOMAIN, LICENSE_PLATE_RECOGNITION_DOMAIN]
                    )
                )
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
                        "camera_identifier": event.camera_identifier,
                        "type": event.domain,
                        "id": event.id,
                        "time": event.created_at,
                        "timestamp": event.created_at.timestamp(),
                        "snapshot_path": f"/files{event.snapshot_path}",
                        "data": event.data,
                        "created_at": event.created_at,
                        "created_at_timestamp": event.created_at.timestamp(),
                        "lookback": camera.recorder.lookback,
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

        # Convert local start of day to UTC
        if "date" in self.request_arguments:
            _time_from, _time_to = daterange_to_utc(
                self.request_arguments["date"], self.utc_offset
            )
            time_from = _time_from.timestamp()
            time_to = _time_to.timestamp()
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

        def sort_events():
            return sorted(
                motion_events
                + recording_events
                + object_events
                + post_processor_events,
                key=lambda k: k["created_at"],
                reverse=True,
            )

        sorted_events = await self.run_in_executor(sort_events)
        await self.response_success(response={"events": sorted_events})

    def _events_amount(
        self,
        get_session: Callable[[], Session],
        camera_identifiers: list[str],
    ) -> dict[str, dict[str, Any]]:
        with get_session() as session:
            stmt = (
                select(
                    func.date(Motion.start_time + self.utc_offset),
                    func.count(),  # pylint: disable=not-callable
                )
                .where(Motion.camera_identifier.in_(camera_identifiers))
                .group_by(func.date(Motion.start_time + self.utc_offset))
            )
            motion_events = session.execute(stmt).all()

            stmt = (
                select(
                    func.date(Recordings.start_time + self.utc_offset),
                    func.count(),  # pylint: disable=not-callable
                )
                .where(Recordings.camera_identifier.in_(camera_identifiers))
                .group_by(func.date(Recordings.start_time + self.utc_offset))
            )
            recording_events = session.execute(stmt).all()

            stmt = (
                select(
                    func.date(Objects.created_at + self.utc_offset),
                    func.count(),  # pylint: disable=not-callable
                )
                .where(Objects.camera_identifier.in_(camera_identifiers))
                .group_by(func.date(Objects.created_at + self.utc_offset))
            )
            object_events = session.execute(stmt).all()

            stmt_pp = (
                select(
                    func.date(PostProcessorResults.created_at + self.utc_offset),
                    PostProcessorResults.domain,
                    func.count(),  # pylint: disable=not-callable
                )
                .where(PostProcessorResults.camera_identifier.in_(camera_identifiers))
                .group_by(
                    func.date(PostProcessorResults.created_at + self.utc_offset),
                    PostProcessorResults.domain,
                )
            )
            post_processor_events = session.execute(stmt_pp).all()

        events_amount: dict[str, dict[str, Any]] = {}
        day: datetime.date
        count: int
        for day, count in motion_events:
            events_amount.setdefault(day.isoformat(), {}).setdefault("motion", count)

        for day, count in recording_events:
            events_amount.setdefault(day.isoformat(), {}).setdefault("recording", count)

        for day, count in object_events:
            events_amount.setdefault(day.isoformat(), {}).setdefault("object", count)

        for day, domain, count in post_processor_events:
            events_amount.setdefault(day.isoformat(), {}).setdefault(domain, count)

        return events_amount

    async def get_events_amount(
        self,
        camera_identifier: str,
    ) -> None:
        """Get amount of events per day.

        The time is adjusted to the client's timezone.
        """
        camera = self._get_camera(camera_identifier, failed=True)

        if not camera:
            self.response_error(
                HTTPStatus.NOT_FOUND,
                reason=f"Camera {camera_identifier} not found",
            )
            return

        events_amount = await self.run_in_executor(
            self._events_amount,
            self._get_session,
            [camera.identifier],
        )
        await self.response_success(response={"events_amount": events_amount})

    async def post_events_amount_multiple(self):
        """Get amount of events per day for multiple cameras.

        The time is adjusted to the client's timezone.
        """
        events_amount = await self.run_in_executor(
            self._events_amount,
            self._get_session,
            self.json_body["camera_identifiers"],
        )
        await self.response_success(response={"events_amount": events_amount})

    async def post_events_dates_of_interest(self):
        """Get dates of interest for multiple cameras.

        This returns a list of dates with the amount of events and whether
        there are timespans available for that date.
        """
        camera_identifiers = self.json_body["camera_identifiers"]
        if not camera_identifiers:
            self.response_error(
                HTTPStatus.BAD_REQUEST, reason="No camera identifiers provided"
            )
            return

        events_amount = await self.run_in_executor(
            self._events_amount,
            self._get_session,
            camera_identifiers,
        )
        events_per_day = {}
        for date, event_types in events_amount.items():
            events_per_day[date] = sum(event_types.values())

        timespans_per_day = await self.run_in_executor(
            _get_timespans_per_day,
            self._get_session,
            camera_identifiers,
            self.utc_offset,
        )

        combined = {}
        for date, event_count in events_per_day.items():
            combined[date] = {
                "events": event_count,
                "timespanAvailable": date in timespans_per_day,
            }

        # Add dates that have timespans but no events
        for date in timespans_per_day:
            if date not in combined:
                combined[date] = {
                    "events": 0,
                    "timespanAvailable": True,
                }
        await self.response_success(response={"dates_of_interest": combined})


def _get_timespans_per_day(
    get_session: Callable[[], Session],
    camera_identifiers: list[str],
    utc_offset: datetime.timedelta,
) -> list[str]:
    """Get the dates with timespans available for multiple cameras."""
    with get_session() as session:
        stmt = (
            select(
                func.date(Files.created_at + utc_offset),
            )
            .where(Files.camera_identifier.in_(camera_identifiers))
            .group_by(func.date(Files.created_at + utc_offset))
            .order_by(func.date(Files.created_at + utc_offset))
        )
        dates = session.execute(stmt).all()
    date_list = [str(d[0]) for d in dates]
    return date_list
