"""Tests for fragmenter."""
from __future__ import annotations

import os
import shutil
import tempfile
from unittest.mock import MagicMock, Mock, patch

from viseron.domains.camera.fragmenter import Fragment, Fragmenter, generate_playlist
from viseron.helpers import utcnow


def test_generate_playlist() -> None:
    """Test generate_playlist."""
    now = utcnow()
    fragments = [
        Fragment("test1.mp4", "/test/test1.mp4", 5.1, now),
        Fragment("test2.mp4", "/test/test2.mp4", 4.123, now),
    ]
    program_date_time = now.isoformat(timespec="milliseconds")

    playlist = generate_playlist(fragments, "/test/init.mp4", end=True)
    assert (
        playlist
        == f"""#EXTM3U
#EXT-X-VERSION:6
#EXT-X-MEDIA-SEQUENCE:0
#EXT-X-TARGETDURATION:6
#EXT-X-INDEPENDENT-SEGMENTS
#EXT-X-MAP:URI="/test/init.mp4"
#EXT-X-DISCONTINUITY
#EXT-X-PROGRAM-DATE-TIME:{program_date_time}
#EXTINF:5.1,
/test/test1.mp4
#EXT-X-DISCONTINUITY
#EXT-X-PROGRAM-DATE-TIME:{program_date_time}
#EXTINF:4.123,
/test/test2.mp4
#EXT-X-ENDLIST"""
    )


class TestFragmenter:
    """Tests for Fragmenter."""

    def setup_method(self):
        """Set up test method."""
        self.vis = MagicMock()
        self.camera = MagicMock()
        self.camera.identifier = "test_camera"
        self.camera.temp_segments_folder = tempfile.mkdtemp()
        self.camera.segments_folder = tempfile.mkdtemp()
        self.fragmenter = Fragmenter(self.vis, self.camera)

    def teardown_method(self):
        """Tear down test method."""
        shutil.rmtree(self.camera.temp_segments_folder)
        shutil.rmtree(self.camera.segments_folder)

    @patch("viseron.domains.camera.fragmenter.sp.run")
    def test_mp4box_command(self, mock_sp_run: Mock):
        """Test mp4box command generation."""
        mock_sp_run.return_value = MagicMock()
        self.fragmenter._mp4box_command("test.mp4")  # pylint: disable=protected-access
        mock_sp_run.assert_called_once_with(
            [
                "MP4Box",
                "-logs",
                "dash@error:ncl",
                "-noprog",
                "-dash",
                "10000",
                "-rap",
                "-frag-rap",
                "-segment-name",
                "clip_",
                "-out",
                os.path.join(self.camera.temp_segments_folder, "test", "master.m3u8"),
                os.path.join(self.camera.temp_segments_folder, "test.mp4"),
            ],
            stdout=self.fragmenter._log_pipe,  # pylint: disable=protected-access
            stderr=self.fragmenter._log_pipe,  # pylint: disable=protected-access
            check=True,
        )

    @patch("viseron.domains.camera.fragmenter.shutil.move")
    def test_move_to_segments_folder_mp4box(self, mock_shutil_move: Mock):
        """Test that the files are moved to the segments folder."""
        mock_shutil_move.return_value = MagicMock()
        self.fragmenter._move_to_segments_folder_mp4box(  # pylint: disable=protected-access
            "test.mp4"
        )
        mock_shutil_move.assert_any_call(
            os.path.join(self.camera.temp_segments_folder, "test", "clip_1.m4s"),
            os.path.join(self.camera.segments_folder, "test.m4s"),
        )

        mock_shutil_move.assert_any_call(
            os.path.join(self.camera.temp_segments_folder, "test", "clip_init.mp4"),
            os.path.join(self.camera.segments_folder, "init.mp4"),
        )
        assert mock_shutil_move.call_count == 2
