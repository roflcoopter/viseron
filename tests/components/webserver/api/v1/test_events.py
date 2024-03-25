"""Test the Events API handler."""

import datetime
from unittest.mock import patch

from sqlalchemy import insert

from viseron.components.storage.models import Motion
from viseron.domains.camera.const import CONFIG_LOOKBACK, CONFIG_RECORDER

from tests.common import BaseTestWithRecordings, MockCamera
from tests.components.webserver.common import TestAppBaseNoAuth


class TestEventsApiHandler(TestAppBaseNoAuth, BaseTestWithRecordings):
    """Test the Events API handler."""

    def test_get_events(self):
        """Test getting events."""
        with self._get_db_session() as session:
            session.execute(
                insert(Motion).values(
                    camera_identifier="test",
                    start_time=datetime.datetime.fromtimestamp(10),
                    end_time=datetime.datetime.fromtimestamp(20),
                )
            )
            session.execute(
                insert(Motion).values(
                    camera_identifier="test",
                    start_time=datetime.datetime.fromtimestamp(500),
                    end_time=datetime.datetime.fromtimestamp(550),
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
            return_value=self._get_db_session(),
        ):
            response = self.fetch(
                "/api/v1/events/test?time_from=0&time_to=100000000000"
            )
        assert response.code == 200
