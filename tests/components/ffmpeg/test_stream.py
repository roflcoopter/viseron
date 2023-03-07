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
        "config, stream_information, expected_width, expected_height, "
        "expected_fps, expected_codec, expected_audio_codec, raises",
        [
            (
                CONFIG,
                (1920, 1080, 30, "h264", "aac"),
                1920,
                1080,
                30,
                "h264",
                "aac",
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
        raises,
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

    @pytest.mark.parametrize(
        "config_audio_codec, stream_audio_codec, extension, expected_audio_cmd",
        [
            (DEFAULT_AUDIO_CODEC, "aac", "mp4", ["-c:a", "copy"]),
            (DEFAULT_AUDIO_CODEC, "pcm_alaw", "mp4", ["-c:a", "aac"]),
            ("test_codec", "pcm_alaw", "mkv", ["-c:a", "test_codec"]),
            (DEFAULT_AUDIO_CODEC, None, "mp4", []),
        ],
    )
    def test_get_audio_codec(
        self, vis, config_audio_codec, stream_audio_codec, extension, expected_audio_cmd
    ):
        """Test that the correct audio codec is returned."""
        mocked_camera = MockCamera(identifier="test_camera_identifier")
        vis.data[COMPONENT] = {}
        vis.data[COMPONENT]["test_camera_identifier"] = mocked_camera
        config = CONFIG
        config[CONFIG_AUDIO_CODEC] = config_audio_codec

        with patch.object(
            Stream, "__init__", MagicMock(spec=Stream, return_value=None)
        ):
            stream = Stream(vis, config, "test_camera_identifier")
            stream._logger = MagicMock()  # pylint: disable=protected-access
            assert (
                stream.get_audio_codec(config, stream_audio_codec, extension)
                == expected_audio_cmd
            )
