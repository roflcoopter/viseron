"""Test the FileKeyHandler class."""

from __future__ import annotations

import datetime
import os
from http import HTTPStatus
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import insert

from viseron.components.storage.models import Files
from viseron.domain_registry import DomainState
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN

from tests.common import MockCamera
from tests.components.webserver.common import TestAppBaseAuth, TestAppBaseNoAuth

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from sqlalchemy.orm import Session, sessionmaker


class FileKeyTestMixin:
    """Stores files in the test database and on disk."""

    _get_db_session: sessionmaker[Session]
    _handler_get_session: Mock
    _tmp_path: Path

    @pytest.fixture(autouse=True)
    def inject_db(
        self, get_db_session: sessionmaker[Session], tmp_path: Path
    ) -> Iterator[None]:
        """Route the handler's database session to the test database."""
        self._get_db_session = get_db_session
        self._tmp_path = tmp_path
        with patch(
            "viseron.components.webserver.request_handler.ViseronRequestHandler"
            "._get_session",
            side_effect=get_db_session,
        ) as handler_get_session:
            self._handler_get_session = handler_get_session
            yield

    def _store_file(
        self,
        tier_id: int,
        content: bytes | None,
        camera_identifier: str = "test",
        file_key: int | None = None,
    ) -> int:
        """Insert a row for a segment, writing it to disk unless content is None."""
        tier_path = os.path.join(self._tmp_path, f"tier{tier_id}")
        directory = os.path.join(tier_path, "segments", camera_identifier)
        path = os.path.join(directory, "1.m4s")
        os.makedirs(directory, exist_ok=True)
        if content is not None:
            with open(path, "wb") as file:
                file.write(content)

        values = {
            "tier_id": tier_id,
            "tier_path": tier_path,
            "camera_identifier": camera_identifier,
            "category": "recorder",
            "subcategory": "segments",
            "path": path,
            "directory": directory,
            "filename": "1.m4s",
            "size": 10,
            "orig_ctime": datetime.datetime.now(datetime.timezone.utc),
        }
        if file_key is not None:
            values["file_key"] = file_key
        with self._get_db_session() as session:
            key = session.execute(
                insert(Files).values(**values).returning(Files.file_key)
            ).scalar_one()
            session.commit()
        return key


def _url(camera_identifier: str, file_key: int) -> str:
    return f"/file/{camera_identifier}/{file_key:x}"


class TestFileKeyHandler(FileKeyTestMixin, TestAppBaseNoAuth):
    """Test the FileKeyHandler class without auth."""

    def test_serves_file_by_key(self) -> None:
        """Test that a file is served from the path its key resolves to."""
        file_key = self._store_file(0, b"segment")

        response = self.fetch(_url("test", file_key))

        assert response.code == HTTPStatus.OK
        assert response.body == b"segment"
        assert response.headers["Etag"]

    def test_prefers_source_while_both_copies_exist(self) -> None:
        """Test that the source is served while the destination may be mid-copy."""
        file_key = self._store_file(0, b"source")
        self._store_file(1, b"partial", file_key=file_key)

        response = self.fetch(_url("test", file_key))

        assert response.code == HTTPStatus.OK
        assert response.body == b"source"

    def test_serves_destination_once_source_removed(self) -> None:
        """Test the window where the source is gone but its row is not yet deleted."""
        file_key = self._store_file(0, None)
        self._store_file(1, b"destination", file_key=file_key)

        response = self.fetch(_url("test", file_key))

        assert response.code == HTTPStatus.OK
        assert response.body == b"destination"

    def test_unknown_key(self) -> None:
        """Test that a key without a row is not found."""
        file_key = self._store_file(0, b"segment")

        response = self.fetch(_url("test", file_key + 1))

        assert response.code == HTTPStatus.NOT_FOUND

    def test_key_without_file_on_disk(self) -> None:
        """Test that a key whose rows all lack a file on disk is not found."""
        file_key = self._store_file(0, None)

        response = self.fetch(_url("test", file_key))

        assert response.code == HTTPStatus.NOT_FOUND

    def test_key_of_other_camera(self) -> None:
        """Test that a key only resolves under the camera it belongs to."""
        file_key = self._store_file(0, b"segment")

        response = self.fetch(_url("other", file_key))

        assert response.code == HTTPStatus.NOT_FOUND

    def test_malformed_key(self) -> None:
        """Test that malformed keys are not found without querying the database."""
        self._store_file(0, b"segment")

        # int(value, 16) accepts all of these, so the route has to reject them
        assert self.fetch("/file/test/0x1").code == HTTPStatus.NOT_FOUND
        assert self.fetch("/file/test/1_0").code == HTTPStatus.NOT_FOUND
        assert self.fetch("/file/test/A").code == HTTPStatus.NOT_FOUND
        # Out of range for BIGINT, which would make PostgreSQL scan the whole table
        assert self.fetch(_url("test", 2**63)).code == HTTPStatus.NOT_FOUND
        assert self.fetch("/file/test/a-b").code == HTTPStatus.NOT_FOUND
        self._handler_get_session.assert_not_called()


class TestFileKeyHandlerAuth(FileKeyTestMixin, TestAppBaseAuth):
    """Test the FileKeyHandler class with auth."""

    def test_unauthenticated(self) -> None:
        """Test that unauthenticated requests are rejected before any query."""
        MockCamera(vis=self.vis, identifier="test")
        file_key = self._store_file(0, b"segment")

        response = self.fetch(_url("test", file_key))

        assert response.code == HTTPStatus.UNAUTHORIZED
        self._handler_get_session.assert_not_called()

    def test_authenticated(self) -> None:
        """Test that a valid token for the camera in the URL is served the file."""
        MockCamera(vis=self.vis, identifier="test")
        file_key = self._store_file(0, b"segment")

        response = self.fetch(
            f"{_url('test', file_key)}?access_token=test_access_token"
        )

        assert response.code == HTTPStatus.OK
        assert response.body == b"segment"

    def test_token_for_other_camera(self) -> None:
        """Test that a token for one camera cannot fetch another camera's file."""
        MockCamera(vis=self.vis, identifier="test")
        MockCamera(vis=self.vis, identifier="other", access_tokens=["other_token"])
        file_key = self._store_file(0, b"segment")

        wrong_token = self.fetch(f"{_url('test', file_key)}?access_token=other_token")
        wrong_camera = self.fetch(f"{_url('other', file_key)}?access_token=other_token")

        assert wrong_token.code == HTTPStatus.UNAUTHORIZED
        assert wrong_camera.code == HTTPStatus.NOT_FOUND

    def test_failed_camera(self) -> None:
        """Test that files of a camera that failed to set up can still be served."""
        self.vis.domain_registry.register(
            component_name="test",
            component_path="test",
            domain=CAMERA_DOMAIN,
            identifier="failed",
            config={},
        )
        self.vis.domain_registry.set_state(
            domain=CAMERA_DOMAIN,
            identifier="failed",
            state=DomainState.FAILED,
            error_instance=MockCamera(identifier="failed"),
        )
        file_key = self._store_file(0, b"segment", "failed")

        response = self.fetch(
            f"{_url('failed', file_key)}?access_token=test_access_token"
        )

        assert response.code == HTTPStatus.OK
        assert response.body == b"segment"
