"""GStreamer segments tests."""
import logging

from viseron.components.gstreamer.segments import Segments

from tests.common import MockCamera


class TestSegments:
    """Test the Segments class."""

    def test_get_concat_segments(self, vis):
        """Test that the segments are correctly sorted."""
        config = {}
        logger = logging.getLogger("viseron.components.gstreamer")
        mocked_camera = MockCamera(identifier="test_camera_identifier")
        segments = Segments(logger, config, vis, mocked_camera, "/testing")

        segs = {
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
        concat_segments = segments.get_concat_segments(segs, "39.mp4", "41.mp4")
        assert concat_segments == ["39.mp4", "40.mp4", "41.mp4"]
