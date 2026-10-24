"""Tests for the telegram component."""

from __future__ import annotations

import asyncio
import datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import ANY, AsyncMock, MagicMock, call, patch

import pytest
from telegram.constants import ParseMode

from viseron.components.onvif.const import COMPONENT as ONVIF_COMPONENT
from viseron.components.storage.models import TriggerTypes
from viseron.components.telegram import (
    CONFIG_SCHEMA,
    TelegramEventNotifier,
    setup,
    unload,
)
from viseron.components.telegram.const import COMPONENT, DATA_NOTIFIER, DATA_PTZ
from viseron.components.telegram.ptz_control import TelegramPTZ
from viseron.domains.camera.const import EVENT_RECORDER_COMPLETE
from viseron.domains.camera.recorder import EventRecorderData, Recording
from viseron.domains.object_detector.detected_object import DetectedObject
from viseron.events import Event
from viseron.exceptions import ComponentNotReady
from viseron.helpers.config_validation import validate_config
from viseron.helpers.logs import SensitiveInformationFilter

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

    from tests.conftest import MockViseron

    SetUp = Callable[..., TelegramEventNotifier]

CAMERA = "camera_one"
TOKEN = "123456:AbCdEf"
CHAT_ID = 1001


def make_config(*, onvif: bool = False, **keys: Any) -> dict[str, Any]:
    """Return a whole config with telegram set up with the given keys."""
    config: dict[str, Any] = {
        "telegram": {
            "telegram_bot_token": TOKEN,
            "telegram_chat_ids": [CHAT_ID],
            "cameras": {CAMERA: None},
            **keys,
        }
    }
    if onvif:
        config[ONVIF_COMPONENT] = {"cameras": {CAMERA: {"host": "192.168.1.2"}}}
    return config


@pytest.fixture(name="mocks")
def fixture_mocks() -> Iterator[SimpleNamespace]:
    """Patch the Telegram bot and application and the threads of the component."""
    with (
        patch("viseron.components.telegram.Bot") as bot_class,
        patch("viseron.components.telegram.Application") as application,
        patch("viseron.components.telegram.RestartableThread") as thread,
        patch(
            "viseron.components.telegram.ptz_control.RestartableThread"
        ) as ptz_thread,
    ):
        bot = bot_class.return_value
        bot.send_message = AsyncMock()
        bot.send_photo = AsyncMock()
        bot.send_video = AsyncMock()
        thread.return_value.is_alive.return_value = False
        ptz_thread.return_value.is_alive.return_value = False
        yield SimpleNamespace(
            bot_class=bot_class,
            bot=bot,
            application=application,
            ptz_thread=ptz_thread,
        )


@pytest.fixture(name="set_up")
def fixture_set_up(
    vis: MockViseron,
    mocks: SimpleNamespace,  # noqa: ARG001  # pylint: disable=unused-argument
) -> Iterator[SetUp]:
    """Return a function that sets up telegram with the given keys."""
    notifiers: list[TelegramEventNotifier] = []

    def _set_up(*, onvif: bool = False, **keys: Any) -> TelegramEventNotifier:
        config = make_config(onvif=onvif, **keys)
        # As at startup, vis.config is the whole config and setup gets it validated
        vis.set_config(config)
        assert setup(vis, validate_config(CONFIG_SCHEMA, config))
        notifier = vis.data[COMPONENT][DATA_NOTIFIER]
        notifiers.append(notifier)
        return notifier

    yield _set_up
    unload(vis)
    for notifier in notifiers:
        notifier._loop.close()


def make_event(
    labels: list[str],
    *,
    camera: str = CAMERA,
    thumbnail_path: str | None = None,
    clip_path: str | None = None,
) -> Event[EventRecorderData]:
    """Return a recorder complete event with objects of the given labels."""
    camera_mock = MagicMock()
    camera_mock.identifier = camera
    start = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    recording = Recording(
        id=1,
        start_time=start,
        start_timestamp=start.timestamp(),
        end_time=None,
        end_timestamp=None,
        date="2026-01-01",
        thumbnail=None,
        thumbnail_path=thumbnail_path,
        clip_path=clip_path,
        objects=[
            DetectedObject(label, 0.9, 0.1, 0.1, 0.5, 0.5, frame_res=(1920, 1080))
            for label in labels
        ],
        trigger_type=TriggerTypes.OBJECT if labels else TriggerTypes.MANUAL,
    )
    return Event(
        name=EVENT_RECORDER_COMPLETE.format(camera_identifier=camera),
        data=EventRecorderData(camera=camera_mock, recording=recording),
        timestamp=0.0,
    )


def notify(notifier: TelegramEventNotifier, event: Event[EventRecorderData]) -> None:
    """Let the notifier send the notifications of an event."""
    asyncio.run(notifier._send_notifications(event))


def make_update(user_id: int, chat_type: str) -> MagicMock:
    """Return a command sent by a user in a chat of the given type."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat.type = chat_type
    update.message.reply_text = AsyncMock()
    return update


def test_listens_to_recorder_complete_of_each_camera(
    set_up: SetUp, vis: MockViseron
) -> None:
    """A listener is registered for each configured camera."""
    set_up(cameras={"camera_one": None, "camera_two": None})
    assert vis.listen_event.call_args_list == [
        call(EVENT_RECORDER_COMPLETE.format(camera_identifier="camera_one"), ANY),
        call(EVENT_RECORDER_COMPLETE.format(camera_identifier="camera_two"), ANY),
    ]


def test_token_is_used_in_plain_text(set_up: SetUp, mocks: SimpleNamespace) -> None:
    """The bot and the application get the token, and logs redact it."""
    set_up()
    mocks.bot_class.assert_called_once_with(token=TOKEN)
    builder = mocks.application.builder.return_value
    builder.request.return_value.token.assert_called_once_with(TOKEN)
    assert TOKEN in SensitiveInformationFilter.sensitive_strings


def test_active_camera_is_the_first_camera(set_up: SetUp) -> None:
    """Commands act on the first configured camera until another is selected."""
    notifier = set_up(cameras={"camera_two": None, "camera_one": None})
    assert notifier.active_camera_identifier == "camera_two"


def test_no_cameras(set_up: SetUp, vis: MockViseron) -> None:
    """Without cameras nothing is listened to, and commands have no camera."""
    notifier = set_up(cameras={}, telegram_user_ids=[5])
    vis.listen_event.assert_not_called()
    update = make_update(5, "group")
    asyncio.run(notifier._which_cam(update, MagicMock()))
    update.message.reply_text.assert_awaited_once_with("No camera selected.")


@pytest.mark.filterwarnings("error::DeprecationWarning")
@pytest.mark.parametrize(
    ("keys", "expected"),
    [
        pytest.param({}, ["person"], id="default"),
        pytest.param(
            {"detection_labels": ["person", "dog"]}, ["person", "dog"], id="global_list"
        ),
        pytest.param({"detection_labels": []}, ["person"], id="global_list_empty"),
        pytest.param(
            {"detection_label": "person,dog,cat"},
            ["person", "dog", "cat"],
            id="global_comma",
        ),
        pytest.param(
            {"detection_label": " person , dog , cat "},
            ["person", "dog", "cat"],
            id="global_comma_whitespace",
        ),
        pytest.param(
            {"detection_label": "person,,dog,,,cat"},
            ["person", "dog", "cat"],
            id="global_comma_empty_entries",
        ),
        pytest.param(
            {"detection_label": "global_comma", "detection_labels": ["global_list"]},
            ["global_comma"],
            id="global_comma_over_global_list",
        ),
        pytest.param(
            {"detection_label": "", "detection_labels": ["global_list"]},
            ["global_list"],
            id="global_comma_empty",
        ),
        pytest.param(
            {
                "detection_labels": ["global"],
                "cameras": {CAMERA: {"detection_labels": ["camera"]}},
            },
            ["camera"],
            id="camera_list_over_global_list",
        ),
        pytest.param(
            {
                "detection_label": "global_a,global_b",
                "cameras": {CAMERA: {"detection_labels": ["camera"]}},
            },
            ["camera"],
            id="camera_list_over_global_comma",
        ),
        pytest.param(
            {
                "detection_labels": ["global"],
                "cameras": {CAMERA: {"detection_label": "camera_a,camera_b"}},
            },
            ["camera_a", "camera_b"],
            id="camera_comma_over_global_list",
        ),
        pytest.param(
            {
                "detection_label": "global",
                "cameras": {CAMERA: {"detection_label": "camera"}},
            },
            ["camera"],
            id="camera_comma_over_global_comma",
        ),
        pytest.param(
            {
                "cameras": {
                    CAMERA: {"detection_label": "comma", "detection_labels": ["list"]}
                }
            },
            ["comma"],
            id="camera_comma_over_camera_list",
        ),
        pytest.param(
            {"cameras": {CAMERA: {"detection_label": ""}}}, [], id="camera_comma_empty"
        ),
        pytest.param(
            {
                "detection_labels": ["global"],
                "cameras": {CAMERA: {"detection_labels": []}},
            },
            ["global"],
            id="camera_list_empty",
        ),
        pytest.param(
            {
                "detection_labels": ["global"],
                "cameras": {CAMERA: {"detection_labels": None}},
            },
            ["global"],
            id="camera_list_null",
        ),
        pytest.param(
            {"detection_labels": ["global"], "cameras": {CAMERA: None}},
            ["global"],
            id="camera_not_set",
        ),
    ],
)
def test_detection_labels(
    set_up: SetUp, keys: dict[str, Any], expected: list[str]
) -> None:
    """The camera's labels win over the global ones, detection_label wins per level."""
    assert set_up(**keys)._get_effective_detection_labels(CAMERA) == expected


def test_detection_labels_of_unknown_camera(set_up: SetUp) -> None:
    """A camera that is not configured gets the global labels."""
    notifier = set_up(detection_labels=["global"])
    assert notifier._get_effective_detection_labels("unknown_camera") == ["global"]


@pytest.mark.parametrize(
    ("labels", "sent"),
    [
        pytest.param(["car", "person"], True, id="match"),
        pytest.param(["car"], False, id="no_match"),
        pytest.param([], True, id="no_objects"),
    ],
)
def test_notifies_for_matching_objects(
    set_up: SetUp, mocks: SimpleNamespace, labels: list[str], sent: bool
) -> None:
    """Only recordings with an object of a configured label, or none, notify."""
    notify(set_up(), make_event(labels))
    assert mocks.bot.send_message.await_count == (1 if sent else 0)


def test_cameras_have_their_own_labels(set_up: SetUp, mocks: SimpleNamespace) -> None:
    """Each camera is filtered by its own labels."""
    notifier = set_up(
        cameras={
            "camera_one": {"detection_labels": ["person"]},
            "camera_two": {"detection_labels": ["car"]},
        }
    )
    notify(notifier, make_event(["person"], camera="camera_two"))
    mocks.bot.send_message.assert_not_awaited()
    notify(notifier, make_event(["car"], camera="camera_two"))
    mocks.bot.send_message.assert_awaited_once()


def test_message_is_sent_to_each_chat(set_up: SetUp, mocks: SimpleNamespace) -> None:
    """By default a text message goes to each chat, and nothing else is sent."""
    notify(set_up(telegram_chat_ids=[1, 2]), make_event(["person"]))
    assert mocks.bot.send_message.await_args_list == [
        call(chat_id=1, text=f"Event from {CAMERA}"),
        call(chat_id=2, text=f"Event from {CAMERA}"),
    ]
    mocks.bot.send_photo.assert_not_awaited()
    mocks.bot.send_video.assert_not_awaited()


def test_message_can_be_turned_off(set_up: SetUp, mocks: SimpleNamespace) -> None:
    """No text message is sent when send_detection_message is off."""
    notify(set_up(send_detection_message=False), make_event(["person"]))
    mocks.bot.send_message.assert_not_awaited()


def test_thumbnail_is_sent(
    set_up: SetUp, mocks: SimpleNamespace, tmp_path: Path
) -> None:
    """The thumbnail is sent when send_detection_thumbnail is on."""
    thumbnail = tmp_path / "thumbnail.jpg"
    thumbnail.write_bytes(b"jpg")
    notify(
        set_up(send_detection_thumbnail=True),
        make_event(["person"], thumbnail_path=str(thumbnail)),
    )
    mocks.bot.send_photo.assert_awaited_once_with(
        chat_id=CHAT_ID, photo=ANY, caption=f"Thumbnail for {CAMERA}"
    )
    mocks.bot.send_photo.await_args.kwargs["photo"].close()


def test_video_is_sent(set_up: SetUp, mocks: SimpleNamespace, tmp_path: Path) -> None:
    """The clip is sent when send_detection_video is on."""
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"mp4")
    notify(
        set_up(send_detection_video=True),
        make_event(["person"], clip_path=str(clip)),
    )
    mocks.bot.send_video.assert_awaited_once_with(
        chat_id=CHAT_ID,
        thumbnail=None,
        video=ANY,
        caption=f"{CAMERA} detected a person",
    )


@pytest.mark.parametrize(
    ("keys", "chat_type", "allowed"),
    [
        pytest.param({"telegram_user_ids": [5]}, "group", True, id="listed_user"),
        pytest.param({"telegram_chat_ids": [5]}, "private", True, id="private_chat"),
        pytest.param({"telegram_chat_ids": [5]}, "group", False, id="group_chat"),
        pytest.param({}, "private", False, id="unknown_user"),
    ],
)
def test_access_to_commands(
    set_up: SetUp, keys: dict[str, Any], chat_type: str, allowed: bool
) -> None:
    """Listed users, and chat ids in private chats, may use commands."""
    update = make_update(5, chat_type)
    asyncio.run(set_up(**keys)._which_cam(update, MagicMock()))
    if allowed:
        update.message.reply_text.assert_awaited_once_with(
            f"Active camera: <b>{CAMERA}</b>", parse_mode=ParseMode.HTML
        )
    else:
        update.message.reply_text.assert_awaited_once_with(
            text="Access denied for user 5."
        )


@pytest.mark.parametrize(
    ("keys", "logged"),
    [
        pytest.param({}, False, id="default"),
        pytest.param({"telegram_log_ids": True}, True, id="log_ids"),
    ],
)
def test_denied_user_is_logged(
    set_up: SetUp,
    caplog: pytest.LogCaptureFixture,
    keys: dict[str, Any],
    logged: bool,
) -> None:
    """The id of a denied user is logged only when telegram_log_ids is on."""
    asyncio.run(set_up(**keys)._which_cam(make_update(5, "group"), MagicMock()))
    assert ("Access denied for user 5." in caplog.text) is logged


def test_no_ptz_without_onvif(set_up: SetUp, vis: MockViseron) -> None:
    """The PTZ controller is not started when onvif is not configured."""
    set_up()
    assert vis.data[COMPONENT][DATA_PTZ] is None


@pytest.mark.usefixtures("mocks")
def test_waits_for_onvif(vis: MockViseron) -> None:
    """Setup is retried while a configured onvif component is not loaded."""
    config = make_config(onvif=True)
    vis.set_config(config)
    with pytest.raises(ComponentNotReady):
        setup(vis, validate_config(CONFIG_SCHEMA, config))


def test_ptz_is_started_with_onvif(
    set_up: SetUp, vis: MockViseron, mocks: SimpleNamespace
) -> None:
    """The PTZ controller is started when onvif is configured and loaded."""
    vis.data[ONVIF_COMPONENT] = MagicMock()
    notifier = set_up(onvif=True)
    ptz = vis.data[COMPONENT][DATA_PTZ]
    assert isinstance(ptz, TelegramPTZ)
    assert ptz._telegram is notifier
    mocks.ptz_thread.return_value.start.assert_called_once()


@pytest.mark.parametrize(
    ("keys", "allowed"),
    [
        pytest.param({"telegram_user_ids": [5]}, True, id="listed_user"),
        pytest.param({}, False, id="unknown_user"),
    ],
)
def test_access_to_ptz_commands(
    set_up: SetUp, vis: MockViseron, keys: dict[str, Any], allowed: bool
) -> None:
    """PTZ commands check access against the telegram config."""
    onvif = MagicMock()
    onvif.get_ptz_service.return_value.goto_home_position = AsyncMock(return_value=True)
    vis.data[ONVIF_COMPONENT] = onvif
    set_up(onvif=True, **keys)
    update = make_update(5, "group")
    asyncio.run(vis.data[COMPONENT][DATA_PTZ]._home(update, MagicMock()))
    if allowed:
        update.message.reply_text.assert_awaited_once_with(
            f"<b>HOME</b> executed for {CAMERA}", parse_mode=ParseMode.HTML
        )
    else:
        update.message.reply_text.assert_awaited_once_with(
            text="Access denied for user 5."
        )
