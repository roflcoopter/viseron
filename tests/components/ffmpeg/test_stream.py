"""FFmpeg stream tests."""
from __future__ import annotations

from contextlib import nullcontext
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from viseron.components.ffmpeg.const import (
    COMPONENT,
    CONFIG_AUDIO_CODEC,
    CONFIG_CODEC,
    CONFIG_FFMPEG_LOGLEVEL,
    CONFIG_FFMPEG_RECOVERABLE_ERRORS,
    CONFIG_FFPROBE_LOGLEVEL,
    CONFIG_FPS,
    CONFIG_HEIGHT,
    CONFIG_PIX_FMT,
    CONFIG_RECORDER,
    CONFIG_SUBSTREAM,
    CONFIG_WIDTH,
    DEFAULT_AUDIO_CODEC,
    DEFAULT_CODEC,
    DEFAULT_FPS,
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
)
from viseron.components.ffmpeg.stream import Stream
from viseron.domains.camera.const import CONFIG_EXTENSION
from viseron.exceptions import StreamInformationError

from tests.common import MockCamera

CONFIG = {
    CONFIG_FFMPEG_RECOVERABLE_ERRORS: [],
    CONFIG_FFMPEG_LOGLEVEL: "info",
    CONFIG_FFPROBE_LOGLEVEL: "info",
    CONFIG_WIDTH: DEFAULT_WIDTH,
    CONFIG_HEIGHT: DEFAULT_HEIGHT,
    CONFIG_FPS: DEFAULT_FPS,
    CONFIG_CODEC: DEFAULT_CODEC,
    CONFIG_AUDIO_CODEC: DEFAULT_AUDIO_CODEC,
    CONFIG_PIX_FMT: "yuv420p",
    CONFIG_RECORDER: {
        CONFIG_EXTENSION: "mp4",
    },
}

CONFIG_WITH_SUBSTREAM: dict[str, Any] = {
    **CONFIG,
    **{
        CONFIG_SUBSTREAM: {
            CONFIG_WIDTH: 1921,
            CONFIG_HEIGHT: 1081,
            CONFIG_FPS: 31,
            CONFIG_CODEC: "h265",
            CONFIG_AUDIO_CODEC: DEFAULT_AUDIO_CODEC,
            CONFIG_PIX_FMT: "yuv420p",
        },
    },
}


class TestStream:
    """Test the Stream class."""

    @pytest.mark.parametrize(
        (
            "config, stream_information, expected_width, expected_height, "
            "expected_fps, expected_codec, expected_audio_codec, expected_extension, "
            "expected_caplog, raises"
        ),
        [
            (
                CONFIG,
                (1920, 1080, 30, "h264", "aac"),
                1920,
                1080,
                30,
                "h264",
                "aac",
                "mp4",
                None,
                nullcontext(),
            ),
            (
                CONFIG_WITH_SUBSTREAM,
                (1920, 1080, 30, "h264", "aac"),
                1921,
                1081,
                31,
                "h264",
                "aac",
                "mp4",
                None,
                nullcontext(),
            ),
            (
                CONFIG,
                (1920, 1080, 30, "h264", "pcm_alaw"),
                1920,
                1080,
                30,
                "h264",
                "pcm_alaw",
                "mkv",
                (
                    "Container mp4 does not support pcm_alaw audio codec, "
                    "using mkv instead. Consider changing extension in your config"
                ),
                nullcontext(),
            ),
            (
                CONFIG,
                (None, 1080, 30, "h264", "mp4"),
                1920,
                1080,
                30,
                "h264",
                "pcm_alaw",
                "mkv",
                None,
                pytest.raises(StreamInformationError),
            ),
        ],
    )
    def test_init(
        self,
        vis,
        config,
        stream_information,
        expected_width,
        expected_height,
        expected_fps,
        expected_codec,
        expected_audio_codec,
        expected_extension,
        expected_caplog,
        raises,
        caplog,
    ):
        """Test that the stream is correctly initialized."""
        mocked_camera = MockCamera(identifier="test_camera_identifier")
        vis.data[COMPONENT] = {}
        vis.data[COMPONENT]["test_camera_identifier"] = mocked_camera

        with raises, patch.object(
            Stream, "get_stream_information", MagicMock(return_value=stream_information)
        ) as mock_get_stream_information, patch.object(
            Stream, "create_symlink", MagicMock()
        ), patch.object(
            Stream, "output_stream_url", MagicMock()
        ):
            stream = Stream(vis, config, "test_camera_identifier")
            mock_get_stream_information.assert_called_once()
            assert stream._camera == mocked_camera  # pylint: disable=protected-access
            assert stream.width == expected_width
            assert stream.height == expected_height
            assert stream.fps == expected_fps
            assert stream.stream_codec == expected_codec
            assert stream.stream_audio_codec == expected_audio_codec
            assert (
                stream._extension  # pylint: disable=protected-access
                == expected_extension
            )
        if expected_caplog:
            assert expected_caplog in caplog.text
        caplog.clear()
