"""FFmpeg stream tests."""
from __future__ import annotations

from contextlib import nullcontext
from typing import Any
from unittest.mock import ANY, MagicMock, patch

import pytest

from viseron.components.ffmpeg.const import (
    CONFIG_AUDIO_CODEC,
    CONFIG_CODEC,
    CONFIG_FFMPEG_LOGLEVEL,
    CONFIG_FFMPEG_RECOVERABLE_ERRORS,
    CONFIG_FFPROBE_LOGLEVEL,
    CONFIG_FPS,
    CONFIG_HEIGHT,
    CONFIG_HOST,
    CONFIG_PASSWORD,
    CONFIG_PATH,
    CONFIG_PIX_FMT,
    CONFIG_PORT,
    CONFIG_PROTOCOL,
    CONFIG_RECORDER,
    CONFIG_RECORDER_AUDIO_CODEC,
    CONFIG_STREAM_FORMAT,
    CONFIG_SUBSTREAM,
    CONFIG_USERNAME,
    CONFIG_WIDTH,
    DEFAULT_AUDIO_CODEC,
    DEFAULT_CODEC,
    DEFAULT_FPS,
    DEFAULT_HEIGHT,
    DEFAULT_PASSWORD,
    DEFAULT_PROTOCOL,
    DEFAULT_RECORDER_AUDIO_CODEC,
    DEFAULT_STREAM_FORMAT,
    DEFAULT_USERNAME,
    DEFAULT_WIDTH,
)
from viseron.components.ffmpeg.stream import FFprobe, Stream
from viseron.const import (
    ENV_CUDA_SUPPORTED,
    ENV_JETSON_NANO,
    ENV_RASPBERRYPI3,
    ENV_RASPBERRYPI4,
)
from viseron.exceptions import StreamInformationError

from tests.common import MockCamera

CONFIG: dict[str, Any] = {
    CONFIG_HOST: "test_host",
    CONFIG_PORT: 1234,
    CONFIG_PATH: "/",
    CONFIG_USERNAME: "test_username",
    CONFIG_PASSWORD: "test_password",
    CONFIG_PROTOCOL: DEFAULT_PROTOCOL,
    CONFIG_STREAM_FORMAT: DEFAULT_STREAM_FORMAT,
    CONFIG_FFMPEG_RECOVERABLE_ERRORS: [],
    CONFIG_FFMPEG_LOGLEVEL: "info",
    CONFIG_FFPROBE_LOGLEVEL: "info",
    CONFIG_WIDTH: DEFAULT_WIDTH,
    CONFIG_HEIGHT: DEFAULT_HEIGHT,
    CONFIG_FPS: DEFAULT_FPS,
    CONFIG_CODEC: DEFAULT_CODEC,
    CONFIG_AUDIO_CODEC: DEFAULT_AUDIO_CODEC,
    CONFIG_PIX_FMT: "yuv420p",
    CONFIG_RECORDER: {},
}

CONFIG_WITH_SUBSTREAM: dict[str, Any] = {
    **CONFIG,
    **{
        CONFIG_SUBSTREAM: {
            CONFIG_PROTOCOL: DEFAULT_PROTOCOL,
            CONFIG_STREAM_FORMAT: DEFAULT_STREAM_FORMAT,
            CONFIG_PORT: 1234,
            CONFIG_PATH: "/",
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
        "expected_fps, raises",
        [
            (
                CONFIG,
                (1920, 1080, 30, "h264", "aac"),
                1920,
                1080,
                30,
                nullcontext(),
            ),
            (
                CONFIG_WITH_SUBSTREAM,
                (1920, 1080, 30, "h264", "aac"),
                1921,
                1081,
                31,
                nullcontext(),
            ),
            (
                CONFIG,
                (1920, 1080, 30, "h264", "pcm_alaw"),
                1920,
                1080,
                30,
                nullcontext(),
            ),
            (
                CONFIG,
                (None, 1080, 30, "h264", "mp4"),
                1920,
                1080,
                30,
                pytest.raises(StreamInformationError),
            ),
        ],
    )
    def test_init(
        self,
        config,
        stream_information,
        expected_width,
        expected_height,
        expected_fps,
        raises,
    ) -> None:
        """Test that the stream is correctly initialized."""
        mocked_camera = MockCamera(identifier="test_camera_identifier")
        with raises, patch.object(
            FFprobe, "stream_information", MagicMock(return_value=stream_information)
        ) as mock_stream_information, patch.object(
            Stream, "create_symlink", MagicMock()
        ):
            stream = Stream(config, mocked_camera, "test_camera_identifier")
            assert mock_stream_information.call_count == (
                2 if config.get(CONFIG_SUBSTREAM) else 1
            )
            assert stream._camera == mocked_camera  # pylint: disable=protected-access
            assert stream.width == expected_width
            assert stream.height == expected_height
            assert stream.fps == expected_fps

    @pytest.mark.parametrize(
        "config_codec, stream_codec, device_env, expected_cmd",
        [
            ("test_codec", "hevc", None, ["-c:v", "test_codec"]),
            (DEFAULT_CODEC, "h264", ENV_RASPBERRYPI3, ["-c:v", "h264_mmal"]),
            (DEFAULT_CODEC, "h264", ENV_RASPBERRYPI4, ["-c:v", "h264_v4l2m2m"]),
            (DEFAULT_CODEC, "h264", ENV_JETSON_NANO, ["-c:v", "h264_nvv4l2dec"]),
            (DEFAULT_CODEC, "h264", ENV_CUDA_SUPPORTED, ["-c:v", "h264_cuvid"]),
            (DEFAULT_CODEC, "dummy", ENV_CUDA_SUPPORTED, []),
        ],
    )
    def test_get_decoder_codec(
        self, monkeypatch, config_codec, stream_codec, device_env, expected_cmd
    ) -> None:
        """Test that the correct codec is returned."""
        mocked_camera = MockCamera(identifier="test_camera_identifier")
        config = CONFIG
        config[CONFIG_CODEC] = config_codec

        if device_env:
            monkeypatch.setenv(device_env, "true")

        with patch.object(
            Stream, "__init__", MagicMock(spec=Stream, return_value=None)
        ):
            stream = Stream(config, mocked_camera, "test_camera_identifier")
            stream._logger = MagicMock()  # pylint: disable=protected-access
            assert stream.get_decoder_codec(config, stream_codec) == expected_cmd

    @pytest.mark.parametrize(
        "config_audio_codec, stream_audio_codec, expected_audio_cmd",
        [
            (DEFAULT_RECORDER_AUDIO_CODEC, "aac", ["-c:a", "copy"]),
            (DEFAULT_RECORDER_AUDIO_CODEC, "pcm_alaw", ["-c:a", "aac"]),
            ("test_codec", "pcm_alaw", ["-c:a", "test_codec"]),
            (DEFAULT_RECORDER_AUDIO_CODEC, None, ["-an"]),
            (None, None, ["-an"]),
            (None, "aac", ["-an"]),
        ],
    )
    def test_get_encoder_audio_codec(
        self, vis, config_audio_codec, stream_audio_codec, expected_audio_cmd
    ) -> None:
        """Test that the correct audio codec is returned."""
        mocked_camera = MockCamera(identifier="test_camera_identifier")
        config = CONFIG
        config[CONFIG_RECORDER][CONFIG_RECORDER_AUDIO_CODEC] = config_audio_codec

        with patch.object(
            Stream, "__init__", MagicMock(spec=Stream, return_value=None)
        ):
            stream = Stream(config, mocked_camera, "test_camera_identifier")
            stream._logger = MagicMock()  # pylint: disable=protected-access
            stream._config = config  # pylint: disable=protected-access
            assert (
                stream.get_encoder_audio_codec(stream_audio_codec) == expected_audio_cmd
            )

    @pytest.mark.parametrize(
        "username, password, expected_url",
        [
            (
                "test_username",
                "test_password",
                "rtsp://test_username:test_password@test_host:1234/",
            ),
            ("admin", "", "rtsp://admin:@test_host:1234/"),
            (DEFAULT_USERNAME, DEFAULT_PASSWORD, "rtsp://test_host:1234/"),
        ],
    )
    def test_get_stream_url(self, username, password, expected_url) -> None:
        """Test that the correct stream url is returned."""
        mocked_camera = MockCamera(identifier="test_camera_identifier")
        config = dict(CONFIG)
        config[CONFIG_USERNAME] = username
        config[CONFIG_PASSWORD] = password

        with patch.object(
            Stream, "__init__", MagicMock(spec=Stream, return_value=None)
        ):
            stream = Stream(CONFIG, mocked_camera, "test_camera_identifier")
            stream._config = config  # pylint: disable=protected-access
            assert stream.get_stream_url(config) == expected_url

    def test_get_stream_information(self):
        """Test that the correct stream information is returned."""
        mocked_camera = MockCamera(identifier="test_camera_identifier")
        config = CONFIG
        config[CONFIG_CODEC] = DEFAULT_CODEC
        config[CONFIG_AUDIO_CODEC] = DEFAULT_AUDIO_CODEC

        with patch.object(
            Stream, "__init__", MagicMock(spec=Stream, return_value=None)
        ), patch.object(
            Stream, "get_stream_url", MagicMock(return_value="test_stream_url")
        ):
            stream = Stream(config, mocked_camera, "test_camera_identifier")
            mock_ffprobe = MagicMock(spec=FFprobe)
            mock_ffprobe.stream_information.return_value = (
                1920,
                1080,
                30,
                "h264",
                "aac",
            )
            stream._ffprobe = mock_ffprobe  # pylint: disable=protected-access
            mock_logger = MagicMock()
            stream._logger = mock_logger  # pylint: disable=protected-access

            result = stream.get_stream_information(config)

            assert result.width == 1920
            assert result.height == 1080
            assert result.fps == 30
            assert result.codec == "h264"
            assert result.audio_codec == "aac"

            mock_ffprobe.stream_information.assert_called_once_with(
                "test_stream_url", ANY
            )

    def test_get_stream_information_missing_parameters(self):
        """Test that StreamInformationError is raised when parameters are missing."""
        mocked_camera = MockCamera(identifier="test_camera_identifier")
        config = CONFIG
        config[CONFIG_CODEC] = DEFAULT_CODEC
        config[CONFIG_AUDIO_CODEC] = DEFAULT_AUDIO_CODEC

        with patch.object(
            Stream, "__init__", MagicMock(spec=Stream, return_value=None)
        ), patch.object(
            Stream, "get_stream_url", MagicMock(return_value="test_stream_url")
        ):
            stream = Stream(config, mocked_camera, "test_camera_identifier")
            mock_ffprobe = MagicMock(spec=FFprobe)
            mock_ffprobe.stream_information.return_value = (
                None,
                1080,
                30,
                "h264",
                "mp4",
            )
            stream._ffprobe = mock_ffprobe  # pylint: disable=protected-access
            mock_logger = MagicMock()
            stream._logger = mock_logger  # pylint: disable=protected-access

            with pytest.raises(StreamInformationError) as excinfo:
                stream.get_stream_information(config)

            assert "Width: None Height: 1080 FPS: 30 Codec: h264" in str(excinfo.value)

            mock_ffprobe.stream_information.assert_called_once_with(
                "test_stream_url", ANY
            )
