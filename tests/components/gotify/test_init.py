"""Tests for the gotify component."""

from __future__ import annotations

import datetime
from http import HTTPStatus
from typing import TYPE_CHECKING, Any
from unittest.mock import ANY, MagicMock, call, patch

import cv2
import numpy as np
import pytest

from viseron.components.gotify import CONFIG_SCHEMA, GotifyEventNotifier, setup
from viseron.components.gotify.const import COMPONENT
from viseron.components.storage.models import TriggerTypes
from viseron.domains.camera.const import EVENT_RECORDER_START
from viseron.domains.camera.recorder import EventRecorderData, Recording
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.events import Event
from viseron.helpers.config_validation import validate_config
from viseron.helpers.logs import SensitiveInformationFilter

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from tests.conftest import MockViseron

    SetUp = Callable[..., GotifyEventNotifier]

CAMERA = "camera_one"
TOKEN = "AbCdEf123"
THUMBNAIL = np.zeros((50, 100, 3), dtype=np.uint8)


@pytest.fixture(name="set_up")
def fixture_set_up(vis: MockViseron) -> Iterator[SetUp]:
    """Return a function that sets up gotify with the given keys."""
    notifiers: list[GotifyEventNotifier] = []

    def _set_up(**keys: Any) -> GotifyEventNotifier:
        config = {
            "gotify": {
                "gotify_url": "https://gotify.example.com",
                "gotify_token": TOKEN,
                "cameras": {CAMERA: None},
                **keys,
            }
        }
        with patch("viseron.components.gotify.RestartableThread"):
            assert setup(vis, validate_config(CONFIG_SCHEMA, config))
        notifiers.append(vis.data[COMPONENT])
        return vis.data[COMPONENT]

    yield _set_up
    for notifier in notifiers:
        notifier.stop()
        notifier._loop.close()


def _event(labels: list[str], thumbnail: np.ndarray | None) -> Event[EventRecorderData]:
    """Return a recorder start event of CAMERA with objects of the given labels."""
    camera = MagicMock()
    camera.identifier = CAMERA
    start = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    recording = Recording(
        id=1,
        start_time=start,
        start_timestamp=start.timestamp(),
        end_time=None,
        end_timestamp=None,
        date="2026-01-01",
        thumbnail=thumbnail,
        thumbnail_path=None,
        clip_path=None,
        objects=[
            DetectedObject(label, 0.9, 0.1, 0.1, 0.5, 0.5, frame_res=(1920, 1080))
            for label in labels
        ],
        trigger_type=TriggerTypes.OBJECT,
    )
    return Event(
        name=EVENT_RECORDER_START.format(camera_identifier=CAMERA),
        data=EventRecorderData(camera=camera, recording=recording),
        timestamp=0.0,
    )


def _record(
    notifier: GotifyEventNotifier,
    labels: list[str],
    thumbnail: np.ndarray | None = None,
) -> tuple[MagicMock, MagicMock]:
    """Let the notifier handle a recording start, return its two send mocks."""
    with (
        patch("viseron.components.gotify.asyncio"),
        patch.object(
            notifier, "_send_text_notification", new_callable=MagicMock
        ) as send_text,
        patch.object(
            notifier, "_send_notification_with_image", new_callable=MagicMock
        ) as send_image,
    ):
        notifier._recording_start_event_handler(_event(labels, thumbnail))
    return send_text, send_image


def test_listens_to_recorder_start_of_each_camera(
    set_up: SetUp, vis: MockViseron
) -> None:
    """A listener is registered for each configured camera."""
    set_up(cameras={"camera_one": None, "camera_two": None})
    assert vis.listen_event.call_args_list == [
        call(EVENT_RECORDER_START.format(camera_identifier="camera_one"), ANY),
        call(EVENT_RECORDER_START.format(camera_identifier="camera_two"), ANY),
    ]


def test_token_is_redacted_from_logs(set_up: SetUp) -> None:
    """The plain token is registered with the filter that redacts logs."""
    set_up()
    assert TOKEN in SensitiveInformationFilter.sensitive_strings


@pytest.mark.parametrize(
    ("keys", "labels", "expected"),
    [
        pytest.param({}, ["car", "person"], "person", id="default"),
        pytest.param({}, ["car"], None, id="default_no_match"),
        pytest.param(
            {"detection_label": "cat, dog"}, ["person", "dog"], "dog", id="global_list"
        ),
        pytest.param(
            {"detection_label": ""}, ["car", "person"], "car", id="global_empty_is_any"
        ),
        pytest.param(
            {"cameras": {CAMERA: {"detection_label": "car"}}},
            ["person", "car"],
            "car",
            id="camera_override",
        ),
        pytest.param(
            {"detection_label": "dog", "cameras": {CAMERA: {"detection_label": ""}}},
            ["car"],
            "car",
            id="camera_empty_is_any",
        ),
    ],
)
def test_detection_label(
    set_up: SetUp, keys: dict[str, Any], labels: list[str], expected: str | None
) -> None:
    """The camera's detection label wins over the global one."""
    send_text, send_image = _record(set_up(**keys), labels)
    send_image.assert_not_called()
    if expected is None:
        send_text.assert_not_called()
    else:
        send_text.assert_called_once_with(
            f"{CAMERA} recording started: {expected}",
            f"Recording started for {expected}",
        )


@pytest.mark.parametrize(
    ("keys", "expected"),
    [
        pytest.param({}, "text", id="default"),
        pytest.param({"send_thumbnail": True}, "image", id="global"),
        pytest.param(
            {"send_thumbnail": True, "cameras": {CAMERA: {"send_thumbnail": False}}},
            "text",
            id="camera_disables",
        ),
        pytest.param(
            {"cameras": {CAMERA: {"send_thumbnail": True}}},
            "image",
            id="camera_enables",
        ),
        pytest.param(
            {"send_thumbnail": True, "use_public_url": True},
            "public_url",
            id="global_public_url",
        ),
        pytest.param(
            {
                "send_thumbnail": True,
                "use_public_url": True,
                "cameras": {CAMERA: {"use_public_url": False}},
            },
            "image",
            id="camera_disables_public_url",
        ),
        pytest.param(
            {"send_thumbnail": True, "cameras": {CAMERA: {"use_public_url": True}}},
            "public_url",
            id="camera_enables_public_url",
        ),
    ],
)
def test_thumbnail(set_up: SetUp, keys: dict[str, Any], expected: str) -> None:
    """The camera's thumbnail settings win over the global ones."""
    send_text, send_image = _record(set_up(**keys), ["person"], THUMBNAIL)
    if expected == "text":
        send_text.assert_called_once()
        send_image.assert_not_called()
    else:
        send_text.assert_not_called()
        use_public_url = send_image.call_args.args[3]
        assert use_public_url is (expected == "public_url")


@pytest.mark.parametrize(
    ("keys", "shape"),
    [
        pytest.param({}, (400, 800, 3), id="default"),
        pytest.param({"image_max_size": 100}, (50, 100, 3), id="smaller"),
        pytest.param({"image_max_size": 0}, (500, 1000, 3), id="no_resize"),
    ],
)
def test_thumbnail_resize(
    set_up: SetUp, keys: dict[str, Any], shape: tuple[int, int, int]
) -> None:
    """The thumbnail is scaled down to image_max_size, unless it is 0."""
    thumbnail = np.zeros((500, 1000, 3), dtype=np.uint8)
    _, send_image = _record(set_up(send_thumbnail=True, **keys), ["person"], thumbnail)
    assert send_image.call_args.args[2].shape == shape


def test_message_with_image(set_up: SetUp) -> None:
    """The message goes to the configured server with token, priority, quality."""
    notifier = set_up(
        gotify_url="https://gotify.example.com/", priority=8, image_quality=70
    )
    with (
        patch("viseron.components.gotify.requests.post") as post,
        patch("viseron.components.gotify.cv2.imencode", wraps=cv2.imencode) as imencode,
    ):
        post.return_value.status_code = HTTPStatus.OK
        notifier._send_gotify_message_with_image("title", "message", THUMBNAIL)

    assert imencode.call_args.args[2] == [cv2.IMWRITE_JPEG_QUALITY, 70]
    assert post.call_args.args == ("https://gotify.example.com/message",)
    assert post.call_args.kwargs["headers"] == {"X-Gotify-Key": TOKEN}
    assert post.call_args.kwargs["json"]["priority"] == 8
