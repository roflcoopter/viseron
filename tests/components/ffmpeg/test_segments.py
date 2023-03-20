"""FFmpeg segments tests."""
from __future__ import annotations

from unittest.mock import MagicMock

from viseron.components.ffmpeg.segments import Segments

from tests.common import MockCamera

CONFIG = {
    "recorder": {
        "ffmpeg_loglevel": "info",
    },
}

SEGMENT_INFORMATION = {
    "20230320072451.mp4": {"start_time": 1679293491.0, "end_time": 1679293495.837},
    "20230320072431.mp4": {"start_time": 1679293471.0, "end_time": 1679293475.898},
    "20230320072411.mp4": {"start_time": 1679293451.0, "end_time": 1679293456.365},
    "20230320072456.mp4": {"start_time": 1679293496.0, "end_time": 1679293500.946},
    "20230320072446.mp4": {"start_time": 1679293486.0, "end_time": 1679293491.365},
    "20230320072426.mp4": {"start_time": 1679293466.0, "end_time": 1679293470.867},
    "20230320072436.mp4": {"start_time": 1679293476.0, "end_time": 1679293481.396},
    "20230320072421.mp4": {"start_time": 1679293461.0, "end_time": 1679293466.41},
    "20230320072441.mp4": {"start_time": 1679293481.0, "end_time": 1679293485.876},
    "20230320072406.mp4": {"start_time": 1679293446.0, "end_time": 1679293450.941},
    "20230320072501.mp4": {"start_time": 1679293501.0, "end_time": 1679293506.322},
    "20230320072416.mp4": {"start_time": 1679293456.0, "end_time": 1679293460.887},
}


class TestSegments:
    """FFmpeg segments tests."""

    def setup_method(self, vis):
        """Set up method."""
        self.segments = Segments(
            MagicMock(), CONFIG, vis, MockCamera(), "/test/segments/"
        )

    def test_get_concat_segments(self):
        """Test that the segments are correctly sorted."""
        concat_segments = self.segments.get_concat_segments(
            SEGMENT_INFORMATION, "20230320072431.mp4", "20230320072441.mp4"
        )
        assert concat_segments == [
            "20230320072431.mp4",
            "20230320072436.mp4",
            "20230320072441.mp4",
        ]

    def test_generate_segment_script(self):
        """Test generating segment script."""
        segment_script = self.segments.generate_segment_script(
            ["20230320072421.mp4", "20230320072426.mp4"],
            SEGMENT_INFORMATION,
            1679293463,
            1679293469,
        )
        assert (
            segment_script == "file 'file:/test/segments/20230320072421.mp4'\n"
            "inpoint 2\n"
            "file 'file:/test/segments/20230320072426.mp4'\n"
            "outpoint 3"
        )

    def test_generate_segment_script_no_inpoint(self):
        """Test generating segment script with no inpoint."""
        segment_script = self.segments.generate_segment_script(
            ["20230320072421.mp4", "20230320072426.mp4"],
            SEGMENT_INFORMATION,
            1679293459,
            1679293469,
        )
        assert (
            segment_script == "file 'file:/test/segments/20230320072421.mp4'\n"
            "file 'file:/test/segments/20230320072426.mp4'\n"
            "outpoint 3"
        )

    def test_generate_segment_script_no_outpoint(self):
        """Test generating segment script with no outpoint."""
        segment_script = self.segments.generate_segment_script(
            ["20230320072421.mp4", "20230320072426.mp4"],
            SEGMENT_INFORMATION,
            1679293463,
            1679293471,
        )
        assert (
            segment_script == "file 'file:/test/segments/20230320072421.mp4'\n"
            "inpoint 2\n"
            "file 'file:/test/segments/20230320072426.mp4'"
        )

    def test_generate_segment_script_short(self):
        """Test generating segment script with a single segment."""
        segment_script = self.segments.generate_segment_script(
            ["20230320072421.mp4"],
            SEGMENT_INFORMATION,
            1679293463,
            1679293464,
        )
        assert (
            segment_script
            == "file 'file:/test/segments/20230320072421.mp4'\ninpoint 2\noutpoint 3"
        )
