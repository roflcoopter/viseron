"""Concatenate GStreamer segments to a single video file."""
from __future__ import annotations

import os

from viseron.components.ffmpeg.const import CAMERA_SEGMENT_DURATION
from viseron.components.ffmpeg.segments import (
    SegmentCleanup as FFmpegSegmentCleanup,
    Segments as FFmpegSegments,
)


class Segments(FFmpegSegments):
    """Use FFmpeg to concatenate segments between two timestamps."""

    def get_start_time(self, segment):
        """Get start time of segment."""
        # Need to subtract the segment duration since creation time changes
        # until segment is written completely
        return (
            os.path.getctime(os.path.join(self._segments_folder, segment))
            - CAMERA_SEGMENT_DURATION
        )


class SegmentCleanup(FFmpegSegmentCleanup):
    """Clean up segments created by GStreamer."""

    def get_start_time(self, segment):
        """Get start time of segment."""
        # Need to subtract the segment duration since creation time changes
        # until segment is written completely
        return (
            os.path.getctime(os.path.join(self._directory, segment))
            - CAMERA_SEGMENT_DURATION
        )
