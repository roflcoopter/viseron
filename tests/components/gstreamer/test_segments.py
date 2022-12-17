"""GStreamer segments tests."""
import logging

from viseron.components.gstreamer.segments import Segments


class TestSegments:
    """Test the Segments class."""

    @classmethod
    def setup_class(cls):
        """Set up testcase."""
        config = {}
        logger = logging.getLogger("viseron.components.gstreamer")
        cls.segments = Segments(config, logger, "/testing")

    def test_get_concat_segments(self):
        """Test that the segments are correctly sorted."""
        segments = {
            "38.mp4": {
                "start_time": 1670490410.0108843,
                "end_time": 1670490414.8301842,
            },
            "39.mp4": {
                "start_time": 1670490414.8788238,
                "end_time": 1670490419.7802238,
            },
            "40.mp4": {
                "start_time": 1670490419.610765,
                "end_time": 1670490424.517965,
            },
            "41.mp4": {
                "start_time": 1670490424.4067051,
                "end_time": 1670490429.3205051,
            },
            "42.mp4": {
                "start_time": 1670490429.4067051,
                "end_time": 1670490434.3205051,
            },
            "4.mp4": {
                "start_time": 1670490325.4067051,
                "end_time": 1670490330.3205051,
            },
        }
        concat_segments = self.segments.get_concat_segments(
            segments, "39.mp4", "41.mp4"
        )
        assert concat_segments == ["39.mp4", "40.mp4", "41.mp4"]
