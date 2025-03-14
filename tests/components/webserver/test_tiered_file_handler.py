"""Test the TieredFileHandler class."""
# pylint: disable=protected-access
import os
import shutil
from typing import TYPE_CHECKING
from unittest.mock import Mock

import tornado.web

from viseron.components.storage import RequestedFilesCount
from viseron.components.storage.const import COMPONENT as STORAGE_COMPONENT, CONFIG_PATH
from viseron.components.webserver.tiered_file_handler import TieredFileHandler

from tests.components.webserver.common import TestAppBaseNoAuth

if TYPE_CHECKING:
    from viseron.components.storage import Storage


class TestTieredFileHandler(TestAppBaseNoAuth):
    """Test the BaseAPIHandler class."""

    def get_app(self):
        """Return an app with fake endpoints."""
        return tornado.web.Application()

    def test_get(self):
        """Test get."""
        storage: Storage = self.vis.data[STORAGE_COMPONENT]
        storage.camera_requested_files_count["test_camera"] = RequestedFilesCount()

        tier1 = "/tmp/viseron/test/tier1"
        tier2 = "/tmp/viseron/test/tier2"
        os.makedirs("/tmp/viseron/test/tier1", exist_ok=True)
        os.makedirs("/tmp/viseron/test/tier2", exist_ok=True)

        self._app.add_handlers(
            r".*",
            [
                (
                    rf"/files{tier1}/(.*)",
                    TieredFileHandler,
                    {
                        "path": tier1,
                        "vis": self.vis,
                        "camera_identifier": "test_camera",
                        "failed": False,
                        "category": "recorder",
                        "subcategory": "segmments",
                    },
                ),
                (
                    rf"/files{tier2}/(.*)",
                    TieredFileHandler,
                    {
                        "path": tier2,
                        "vis": self.vis,
                        "camera_identifier": "test_camera",
                        "failed": False,
                        "category": "recorder",
                        "subcategory": "segmments",
                    },
                ),
            ],
        )

        tier_handler1 = Mock(tier={CONFIG_PATH: f"{tier1}/"})
        tier_handler2 = Mock(tier={CONFIG_PATH: f"{tier2}/"})
        storage._camera_tier_handlers["test_camera"] = {}
        storage._camera_tier_handlers["test_camera"]["recorder"] = []
        storage._camera_tier_handlers["test_camera"]["recorder"].append(
            {"segmments": tier_handler1}
        )
        storage._camera_tier_handlers["test_camera"]["recorder"].append(
            {"segmments": tier_handler2}
        )

        # Test accessing file from tier 2 with tier 1 path
        with open(f"{tier2}/test1.jpg", "wb") as tier2_file:
            tier2_file.write(b"test1")
        response = self.fetch(f"/files{tier1}/test1.jpg")
        assert response.code == 200
        assert response.body == b"test1"
        assert "Redirecting to" in self._caplog.text

        # Test accessing file from tier 1 with tier 1 path
        with open(f"{tier1}/test2.jpg", "wb") as tier1_file:
            tier1_file.write(b"test2")
        self._caplog.clear()
        response = self.fetch(f"/files{tier1}/test2.jpg")
        assert response.code == 200
        assert response.body == b"test2"
        assert "Redirecting to" not in self._caplog.text

        shutil.rmtree(tier1)
        shutil.rmtree(tier2)
