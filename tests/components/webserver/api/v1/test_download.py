"""Test the Download API handler."""

from __future__ import annotations

import os
import shutil

from viseron.components.webserver.download_token import DownloadToken

from tests.components.webserver.common import TestAppBaseNoAuth

DOWNLOAD_DIR = "/tmp/viseron/test/download"


class TestDownloadApiHandler(TestAppBaseNoAuth):
    """Test the DownloadAPIHandler."""

    def _add_download_token(self, filename: str) -> None:
        """Write a file and register a download token pointing at it."""
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        with open(os.path.join(DOWNLOAD_DIR, filename), "wb") as download_file:
            download_file.write(b"test")
        self.webserver.download_tokens["token"] = DownloadToken(
            filename=os.path.join(DOWNLOAD_DIR, filename),
            token="token",
            delete_after_download=False,
        )

    def test_download(self):
        """Test downloading a file."""
        self._add_download_token("recording.mp4")
        response = self.fetch("/api/v1/download?token=token")
        assert response.code == 200
        assert response.body == b"test"
        assert (
            response.headers["Content-Disposition"]
            == 'attachment; filename="recording.mp4"'
        )
        shutil.rmtree(DOWNLOAD_DIR)

    def test_download_unsafe_filename(self):
        """Test that a basename with CR/LF or quotes cannot split headers."""
        self._add_download_token('evil"\r\nX-Injected: yes.mp4')
        response = self.fetch("/api/v1/download?token=token")
        assert response.code == 200
        assert response.body == b"test"
        assert (
            response.headers["Content-Disposition"]
            == 'attachment; filename="download.mp4"'
        )
        assert "X-Injected" not in response.headers
        shutil.rmtree(DOWNLOAD_DIR)

    def test_download_token_not_found(self):
        """Test downloading with an unknown token."""
        response = self.fetch("/api/v1/download?token=missing")
        assert response.code == 404
