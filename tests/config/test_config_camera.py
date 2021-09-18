"""Tests for camera config."""
from contextlib import nullcontext
from unittest import mock

import pytest
import voluptuous

from viseron.config import config_camera

from tests.common import assert_config_instance_config_dict


@pytest.mark.parametrize(
    "test_input, expected, raises",
    [
        ("this-is-a-slug", "this-is-a-slug", nullcontext()),
        ("this is not a slug", "", pytest.raises(voluptuous.error.Invalid)),
    ],
)
def test_ensure_slug(test_input, expected, raises):
    """Test that slug is returned."""
    with raises:
        assert config_camera.ensure_slug(test_input) == expected


@pytest.mark.parametrize(
    "test_input, expected, raises",
    [
        (
            {"name": "This is a valid name", "mqtt_name": "this_is_a_valid_mqtt_name"},
            {"name": "This is a valid name", "mqtt_name": "this_is_a_valid_mqtt_name"},
            nullcontext(),
        ),
        (
            {"name": "This is a valid name", "mqtt_name": None},
            {"name": "This is a valid name", "mqtt_name": "this_is_a_valid_name"},
            nullcontext(),
        ),
        (
            {
                "name": "This is a valid name",
                "mqtt_name": "This is an invalid mqtt name",
            },
            {},
            pytest.raises(voluptuous.error.Invalid),
        ),
    ],
)
def test_ensure_mqtt_name(test_input, expected, raises):
    """Test that MQTT name is returned."""
    with raises:
        assert config_camera.ensure_mqtt_name(test_input) == expected


@pytest.mark.parametrize(
    "env_vaapi_supported, test_input, expected",
    [
        ("false", ["-hwaccel", "vaapi"], ["-hwaccel", "vaapi"]),
        ("false", [], []),
        ("true", [], ["-hwaccel", "vaapi", "-vaapi_device", "/dev/dri/renderD128"]),
    ],
)
def test_check_for_hwaccels(monkeypatch, env_vaapi_supported, test_input, expected):
    """Test correct hwaccel args are returned."""
    monkeypatch.setenv("VISERON_CUDA_SUPPORTED", "false")
    monkeypatch.setenv("VISERON_VAAPI_SUPPORTED", env_vaapi_supported)
    assert config_camera.check_for_hwaccels(test_input) == expected


class TestCameraConfig:
    """Test CameraConfig."""

    @pytest.fixture
    def camera_config_dict(self, raw_config_full):
        """Return raw single camera config."""
        return raw_config_full["cameras"][0]

    @pytest.fixture
    def config(self, camera_config_dict, raw_config_full):
        """Return CameraConfig object."""
        return config_camera.CameraConfig(
            camera_config_dict, raw_config_full["motion_detection"]
        )

    def test_init(self, config):
        """Test instantiation."""
        assert_config_instance_config_dict(
            config,
            config.validated_config,
            ignore_keys=["codec", "input_args", "zones"],
        )
        assert (
            config.substream.input_args
            == [
                "-avoid_negative_ts",
                "make_zero",
                "-fflags",
                "nobuffer",
                "-flags",
                "low_delay",
                "-strict",
                "experimental",
                "-fflags",
                "+genpts",
                "-use_wallclock_as_timestamps",
                "1",
                "-vsync",
                "0",
            ]
            + config.substream.timeout_option
        )
        assert config.substream.codec == [
            "-c:v",
            config.validated_config["substream"]["codec"],
        ]
        for index, zone in enumerate(config.zones):
            assert zone["name"] == config.validated_config["zones"][index]["name"]
        assert config.codec == [
            "-c:v",
            config.validated_config["codec"],
        ]
        assert (
            config.input_args
            == [
                "-avoid_negative_ts",
                "make_zero",
                "-fflags",
                "nobuffer",
                "-flags",
                "low_delay",
                "-strict",
                "experimental",
                "-fflags",
                "+genpts",
                "-use_wallclock_as_timestamps",
                "1",
                "-vsync",
                "0",
            ]
            + config.timeout_option
        )
        assert config.name_slug == config_camera.slugify(
            config.validated_config["name"]
        )
        assert config.output_args == [
            "-f",
            "rawvideo",
            "-pix_fmt",
            config.validated_config["pix_fmt"],
            "pipe:1",
        ]

    def test_generate_zones_labels_inherited(self, config):
        """Test that zone labels are inherited from object_detection."""
        del config.validated_config["zones"][0]["labels"]
        for camera_label, zone_label in zip(
            config.generate_zones(config.validated_config["zones"])[0]["labels"],
            config.object_detection["labels"],
        ):
            assert camera_label.confidence == zone_label["confidence"]
            assert camera_label.label == zone_label["label"]

    @pytest.mark.parametrize(
        "stream_format, env_var, expected",
        [
            ("", "", {}),
            ("rtsp", "", {}),
            (
                "rtsp",
                "VISERON_CUDA_SUPPORTED",
                {
                    "h264": "h264_cuvid",
                    "h265": "hevc_cuvid",
                },
            ),
            (
                "rtmp",
                "VISERON_RASPBERRYPI3",
                {
                    "h264": "h264_mmal",
                },
            ),
            (
                "rtmp",
                "VISERON_RASPBERRYPI4",
                {
                    "h264": "h264_v4l2m2m",
                },
            ),
            (
                "rtmp",
                "VISERON_JETSON_NANO",
                {
                    "h264": "h264_nvmpi",
                    "h265": "hevc_nvmpi",
                },
            ),
        ],
    )
    def test_codec_map(self, monkeypatch, config, stream_format, env_var, expected):
        """Test that codec is returned properly."""
        if env_var:
            monkeypatch.setenv(env_var, "true")
        with mock.patch.object(config, "_stream_format", stream_format):
            assert config.codec_map == expected

    def test_input_args(self, config):
        """Test that input_args are returned properly."""
        with mock.patch.object(config, "_input_args", ["-arg1", "value1"]):
            assert config.input_args == ["-arg1", "value1"]

    def test_protocol(self, config):
        """Test that protocol is set correctly."""
        assert config.protocol == "rtsp"

    @pytest.mark.parametrize(
        "username, password, expected",
        [
            (
                "",
                "",
                "rtsp://wowzaec2demo.streamlock.net:554/vod/mp4:BigBuckBunny_115k.mov",
            ),
            (
                "user",
                "",
                "rtsp://wowzaec2demo.streamlock.net:554/vod/mp4:BigBuckBunny_115k.mov",
            ),
            (
                "user",
                "pass",
                (
                    "rtsp://user:pass@wowzaec2demo.streamlock.net:"
                    "554/vod/mp4:BigBuckBunny_115k.mov"
                ),
            ),
        ],
    )
    def test_stream_url(self, config, username, password, expected):
        """Test that stream_url is generated correctly."""
        with mock.patch.multiple(config, _username=username, _password=password):
            assert config.stream_url == expected
