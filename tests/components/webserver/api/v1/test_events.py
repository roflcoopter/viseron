"""Test the Events API handler."""
from __future__ import annotations

import datetime
import json
from unittest.mock import patch

import pytest
from sqlalchemy import insert
from sqlalchemy.orm.session import Session, sessionmaker

from viseron.components.storage.models import Motion, PostProcessorResults
from viseron.domains.camera.const import CONFIG_LOOKBACK, CONFIG_RECORDER

from tests.common import BaseTestWithRecordings, MockCamera
from tests.components.webserver.common import TestAppBaseNoAuth


class TestEventsApiHandler(TestAppBaseNoAuth, BaseTestWithRecordings):
    """Test the Events API handler."""

    @pytest.fixture(scope="function", autouse=True)
    def prepare_and_mock(self, get_db_session: sessionmaker[Session]):
        """Prepare the database with events and setup mocks."""
        with get_db_session() as session:
            session.execute(
                insert(Motion).values(
                    camera_identifier="test",
                    start_time=datetime.datetime(
                        2024, 6, 22, 1, 0, 0, tzinfo=datetime.timezone.utc
                    ),
                    end_time=datetime.datetime(
                        2024, 6, 22, 1, 1, 0, tzinfo=datetime.timezone.utc
                    ),
                )
            )
            session.execute(
                insert(Motion).values(
                    camera_identifier="test",
                    start_time=datetime.datetime(
                        2024, 6, 22, 3, 0, 0, tzinfo=datetime.timezone.utc
                    ),
                    end_time=datetime.datetime(
                        2024, 6, 22, 3, 1, 0, tzinfo=datetime.timezone.utc
                    ),
                )
            )
            session.execute(
                insert(PostProcessorResults).values(
                    camera_identifier="test",
                    domain="face_recognition",
                    snapshot_path="test",
                    data={"label": "test", "confidence": 0.5},
                    created_at=datetime.datetime(
                        2024, 6, 22, 1, 0, 0, tzinfo=datetime.timezone.utc
                    ),
                )
            )
            session.execute(
                insert(PostProcessorResults).values(
                    camera_identifier="test",
                    domain="face_recognition",
                    snapshot_path="test",
                    data={"label": "test", "confidence": 0.5},
                    created_at=datetime.datetime(
                        2024, 6, 22, 23, 0, 0, tzinfo=datetime.timezone.utc
                    ),
                )
            )
            session.commit()

        mocked_camera = MockCamera(
            identifier="test", config={CONFIG_RECORDER: {CONFIG_LOOKBACK: 5}}
        )
        with patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler."
                "_get_camera"
            ),
            return_value=mocked_camera,
        ), patch(
            (
                "viseron.components.webserver.request_handler.ViseronRequestHandler"
                "._get_session"
            ),
            return_value=get_db_session(),
        ):
            yield

    def test_get_events(self):
        """Test getting events."""
        response = self.fetch("/api/v1/events/test?time_from=0&time_to=100000000000")
        assert response.code == 200

    def test_get_events_utc_offset_negative(self):
        """Test getting events with utc offset."""
        response = self.fetch(
            "/api/v1/events/test?date=2024-06-22",
            headers={
                "X-Client-UTC-Offset": "-120",
            },
        )
        assert response.code == 200

        body = json.loads(response.body)
        assert len(body["events"]) == 2
        assert body["events"][0]["type"] == "motion"
        assert body["events"][0]["start_time"] == "2024-06-22T03:00:00+00:00"
        assert body["events"][1]["type"] == "face_recognition"
        assert body["events"][1]["created_at"] == "2024-06-22T23:00:00+00:00"

    def test_get_events_utc_offset_positive(self):
        """Test getting events with utc offset."""
        response = self.fetch(
            "/api/v1/events/test?date=2024-06-22",
            headers={
                "X-Client-UTC-Offset": "120",
            },
        )
        assert response.code == 200

        body = json.loads(response.body)
        assert len(body["events"]) == 3
        assert body["events"][0]["type"] == "motion"
        assert body["events"][0]["start_time"] == "2024-06-22T03:00:00+00:00"
        assert body["events"][1]["type"] == "motion"
        assert body["events"][1]["start_time"] == "2024-06-22T01:00:00+00:00"
        assert body["events"][2]["type"] == "face_recognition"
        assert body["events"][2]["created_at"] == "2024-06-22T01:00:00+00:00"

    def test_get_events_amount(self):
        """Test getting events with amount."""
        response = self.fetch(
            "/api/v1/events/test/amount",
            headers={
                "X-Client-UTC-Offset": "0",
            },
        )

        assert response.code == 200

        body = json.loads(response.body)
        assert body["events_amount"]["2024-06-22"]["motion"] == 2
        assert body["events_amount"]["2024-06-22"]["face_recognition"] == 2

    def test_get_events_amount_utc_offset_negative(self):
        """Test getting events with amount and utc offset."""
        response = self.fetch(
            "/api/v1/events/test/amount",
            headers={
                "X-Client-UTC-Offset": "-120",
            },
        )

        assert response.code == 200

        body = json.loads(response.body)
        assert body["events_amount"]["2024-06-21"]["motion"] == 1
        assert body["events_amount"]["2024-06-22"]["motion"] == 1
        assert body["events_amount"]["2024-06-21"]["face_recognition"] == 1
        assert body["events_amount"]["2024-06-22"]["face_recognition"] == 1

    def test_get_events_amount_utc_offset_positive(self):
        """Test getting events with amount and utc offset."""
        response = self.fetch(
            "/api/v1/events/test/amount", headers={"X-Client-UTC-Offset": "1320"}
        )

        assert response.code == 200

        body = json.loads(response.body)
        assert body["events_amount"]["2024-06-22"]["motion"] == 1
        assert body["events_amount"]["2024-06-23"]["motion"] == 1
        assert body["events_amount"]["2024-06-22"]["face_recognition"] == 1

    def test_post_dates_of_interest(self):
        """Test getting dates of interest."""
        response = self.fetch(
            "/api/v1/events/dates_of_interest",
            method="POST",
            body=json.dumps(
                {
                    "camera_identifiers": ["test"],
                }
            ),
            headers={
                "X-Client-UTC-Offset": "0",
            },
        )

        assert response.code == 200

        body = json.loads(response.body)
        assert body["dates_of_interest"]["2024-06-22"]["events"] == 4

    def test_post_dates_of_interest_utc_offset_negative(self):
        """Test getting dates of interest with utc offset."""
        response = self.fetch(
            "/api/v1/events/dates_of_interest",
            method="POST",
            body=json.dumps(
                {
                    "camera_identifiers": ["test"],
                }
            ),
            headers={
                "X-Client-UTC-Offset": "-120",
            },
        )

        assert response.code == 200

        body = json.loads(response.body)
        assert body["dates_of_interest"]["2024-06-21"]["events"] == 2
        assert body["dates_of_interest"]["2024-06-22"]["events"] == 2
