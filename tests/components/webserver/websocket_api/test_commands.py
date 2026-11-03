"""Tests for WebSocket API commands."""

from __future__ import annotations

import asyncio
import datetime
from concurrent.futures import Future
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from viseron.components.storage.const import TIMELAPSE_RENDER_MANAGER
from viseron.components.storage.timelapse_render import (
    TimelapseNoFramesError,
    TimelapseRenderBusyError,
    TimelapseRenderCancelled,
    TimelapseRenderError,
    TimelapseRenderJob,
)
from viseron.components.webserver.auth import Role, User
from viseron.components.webserver.websocket_api import commands
from viseron.components.webserver.websocket_api.commands import (
    _camera_identifier_from_event,
    _event_allowed,
    _state_changed_allowed,
    export_timespan,
    get_entities,
    render_timelapse,
    subscribe_event,
    subscribe_states,
    unsubscribe_event,
)
from viseron.events import Event, EventData
from viseron.states import EventStateChangedData, State

if TYPE_CHECKING:
    from collections.abc import Callable

COMMANDS = "viseron.components.webserver.websocket_api.commands"


class _CameraEventData(EventData):
    """Event data that carries a camera identifier."""

    def __init__(self, camera_identifier: str) -> None:
        self.camera_identifier = camera_identifier


def _user(role: Role = Role.READ, assigned_cameras: list[str] | None = None) -> User:
    """Return a user with the given role and camera assignment."""
    return User(
        name="test",
        username="test",
        password="test",
        role=role,
        assigned_cameras=assigned_cameras,
    )


def _connection(user: User | None, cameras: tuple[str, ...] = ("cam_a", "cam_b")):
    """Return a mocked WebSocketHandler."""
    connection = MagicMock()
    connection.current_user = user
    connection.subscriptions = {}
    connection.async_send_message = AsyncMock()
    connection.vis.get_registered_identifiers.return_value = {
        identifier: MagicMock() for identifier in cameras
    }
    return connection


def _event(name: str, data: EventData | None = None) -> Event:
    """Return an event."""
    return Event(name, data if data is not None else MagicMock(spec=EventData), 0.0)


class TestCameraIdentifierFromEvent:
    """Tests for _camera_identifier_from_event."""

    def test_reads_identifier_from_event_data(self) -> None:
        """Event data carrying camera_identifier is authoritative."""
        connection = _connection(_user())
        event = _event("some/topic", _CameraEventData("cam_b"))

        assert _camera_identifier_from_event(connection.vis, event) == "cam_b"

    def test_reads_identifier_from_first_topic_segment(self) -> None:
        """Per-camera topics are prefixed with the identifier."""
        connection = _connection(_user())
        event = _event("cam_b/face/detected/alice")

        assert _camera_identifier_from_event(connection.vis, event) == "cam_b"

    def test_reads_identifier_from_second_topic_segment(self) -> None:
        """Some topics embed the identifier as the second segment."""
        connection = _connection(_user())
        event = _event("object_detector/cam_b/result")

        assert _camera_identifier_from_event(connection.vis, event) == "cam_b"

    def test_reads_identifier_from_trailing_topic_segment(self) -> None:
        """Domain setup topics embed the identifier last."""
        connection = _connection(_user())
        event = _event("domain/setup/ok/camera/cam_b")

        assert _camera_identifier_from_event(connection.vis, event) == "cam_b"

    def test_returns_none_for_topic_without_camera(self) -> None:
        """Topics unrelated to a camera resolve to no identifier."""
        connection = _connection(_user())
        event = _event("component/setup/ok/webserver")

        assert _camera_identifier_from_event(connection.vis, event) is None


class TestEventAllowed:
    """Tests for _event_allowed."""

    def test_unauthenticated_connection_is_allowed(self) -> None:
        """With auth disabled there is no user and no restriction."""
        connection = _connection(None)

        assert _event_allowed(connection, _event("cam_b/objects")) is True

    def test_admin_is_allowed(self) -> None:
        """Admins are never restricted by assigned_cameras."""
        connection = _connection(_user(Role.ADMIN, ["cam_a"]))

        assert _event_allowed(connection, _event("cam_b/objects")) is True

    def test_unassigned_user_is_allowed(self) -> None:
        """An empty assignment grants access to all cameras."""
        connection = _connection(_user(Role.READ, None))

        assert _event_allowed(connection, _event("cam_b/objects")) is True

    def test_assigned_camera_is_allowed(self) -> None:
        """Events for an assigned camera are forwarded."""
        connection = _connection(_user(Role.READ, ["cam_a"]))

        assert _event_allowed(connection, _event("cam_a/objects")) is True

    def test_unassigned_camera_is_denied(self) -> None:
        """Events for a camera the user was not granted are dropped."""
        connection = _connection(_user(Role.READ, ["cam_a"]))

        assert _event_allowed(connection, _event("cam_b/objects")) is False

    def test_unassigned_camera_in_event_data_is_denied(self) -> None:
        """The identifier is also read from the event payload."""
        connection = _connection(_user(Role.READ, ["cam_a"]))
        event = _event("some/topic", _CameraEventData("cam_b"))

        assert _event_allowed(connection, event) is False

    def test_event_without_camera_is_allowed(self) -> None:
        """Events not tied to a camera are unaffected."""
        connection = _connection(_user(Role.READ, ["cam_a"]))

        event = _event("component/setup/ok/webserver")
        assert _event_allowed(connection, event) is True


class TestSubscribeEvent:
    """Tests for the subscribe_event command."""

    @staticmethod
    def _forward(connection, event: Event) -> None:
        """Run subscribe_event and invoke the registered callback."""

        async def run() -> None:
            await subscribe_event(
                connection,
                {
                    "type": "subscribe_event",
                    "command_id": 1,
                    "event": "*",
                    "debounce": None,
                },
            )
            callback = connection.vis.listen_event.call_args[0][1]
            connection.async_send_message.reset_mock()
            await callback(event)

        asyncio.run(run())

    def test_wildcard_does_not_leak_unassigned_camera(self) -> None:
        """A wildcard subscription must not fan out past the assignment."""
        connection = _connection(_user(Role.READ, ["cam_a"]))

        self._forward(connection, _event("cam_b/face/detected/alice"))

        connection.async_send_message.assert_not_called()

    def test_wildcard_still_delivers_assigned_camera(self) -> None:
        """The wildcard the frontend relies on keeps working."""
        connection = _connection(_user(Role.READ, ["cam_a"]))

        self._forward(connection, _event("cam_a/face/detected/alice"))

        connection.async_send_message.assert_called_once()

    def test_admin_still_receives_every_camera(self) -> None:
        """Admins keep the previous behaviour."""
        connection = _connection(_user(Role.ADMIN, ["cam_a"]))

        self._forward(connection, _event("cam_b/face/detected/alice"))

        connection.async_send_message.assert_called_once()


class TestStateChangedAllowed:
    """Tests for _state_changed_allowed."""

    @staticmethod
    def _state_changed(entity_id: str) -> Event[EventStateChangedData]:
        """Return a state_changed event for an entity."""
        return Event(
            "state_changed",
            EventStateChangedData(
                entity_id=entity_id,
                previous_state=None,
                current_state=State(entity_id, "on", {}),
            ),
            0.0,
        )

    @staticmethod
    def _with_entities(connection, entities: dict[str, str | None]) -> None:
        """Register entities under the identifiers they were added with."""
        connection.vis.states.get_entity_identifier.side_effect = entities.get

    def test_entity_of_assigned_camera_is_allowed(self) -> None:
        """State changes for an assigned camera are forwarded."""
        connection = _connection(_user(Role.READ, ["cam_a"]))
        self._with_entities(connection, {"binary_sensor.cam_a_face": "cam_a"})

        event = self._state_changed("binary_sensor.cam_a_face")
        assert _state_changed_allowed(connection, event) is True

    def test_entity_of_unassigned_camera_is_denied(self) -> None:
        """State changes for an unassigned camera are dropped."""
        connection = _connection(_user(Role.READ, ["cam_a"]))
        self._with_entities(connection, {"binary_sensor.cam_b_face": "cam_b"})

        event = self._state_changed("binary_sensor.cam_b_face")
        assert _state_changed_allowed(connection, event) is False

    def test_entity_without_identifier_is_allowed(self) -> None:
        """Entities not scoped to an identifier are unaffected."""
        connection = _connection(_user(Role.READ, ["cam_a"]))
        self._with_entities(connection, {"sensor.cpu": None})

        event = self._state_changed("sensor.cpu")
        assert _state_changed_allowed(connection, event) is True

    def test_entity_of_non_camera_identifier_is_allowed(self) -> None:
        """Identifiers that name something other than a camera are unaffected."""
        connection = _connection(_user(Role.READ, ["cam_a"]))
        self._with_entities(connection, {"sensor.tier_usage": "tier_1"})

        event = self._state_changed("sensor.tier_usage")
        assert _state_changed_allowed(connection, event) is True

    def test_admin_is_allowed(self) -> None:
        """Admins keep the previous behaviour."""
        connection = _connection(_user(Role.ADMIN, ["cam_a"]))
        self._with_entities(connection, {"binary_sensor.cam_b_face": "cam_b"})

        event = self._state_changed("binary_sensor.cam_b_face")
        assert _state_changed_allowed(connection, event) is True


class TestSubscribeStates:
    """Tests for the subscribe_states command."""

    def test_unfiltered_subscription_does_not_leak(self) -> None:
        """subscribe_states without entity filter respects the assignment."""
        connection = _connection(_user(Role.READ, ["cam_a"]))
        connection.vis.states.get_entity_identifier.return_value = "cam_b"

        async def run() -> None:
            await subscribe_states(
                connection, {"type": "subscribe_states", "command_id": 1}
            )
            callback = connection.vis.listen_event.call_args[0][1]
            connection.async_send_message.reset_mock()
            await callback(
                TestStateChangedAllowed._state_changed("binary_sensor.cam_b")
            )

        asyncio.run(run())

        connection.async_send_message.assert_not_called()


class TestGetEntities:
    """Tests for the get_entities command."""

    @staticmethod
    def _get_entities(connection) -> dict:
        """Run get_entities and return the entities sent to the client."""
        connection.run_in_executor = AsyncMock(
            return_value={
                "sensor.cam_a_access_token": MagicMock(),
                "sensor.cam_b_access_token": MagicMock(),
                "sensor.cpu": MagicMock(),
            }
        )
        connection.vis.states.get_entity_identifier.side_effect = {
            "sensor.cam_a_access_token": "cam_a",
            "sensor.cam_b_access_token": "cam_b",
        }.get

        asyncio.run(get_entities(connection, {"type": "get_entities", "command_id": 1}))
        return connection.async_send_message.call_args[0][0]["result"]

    def test_unassigned_camera_entities_are_dropped(self) -> None:
        """Entities of cameras outside the assignment are not returned."""
        entities = self._get_entities(_connection(_user(Role.READ, ["cam_a"])))

        assert set(entities) == {"sensor.cam_a_access_token", "sensor.cpu"}

    def test_admin_gets_all_entities(self) -> None:
        """Admins keep the previous behaviour."""
        entities = self._get_entities(_connection(_user(Role.ADMIN, ["cam_a"])))

        assert len(entities) == 3


def test_export_timespan_filename() -> None:
    """The exported file keeps a single dot before the extension."""
    connection = _connection(_user())
    connection.get_camera.return_value.identifier = "cam_a"
    connection.get_camera.return_value.fragmenter.concatenate_fragments.return_value = (
        "/tmp/abc.mp4"
    )

    async def _run_in_executor(func: Any, *args: Any) -> Any:
        return func(*args)

    connection.run_in_executor = _run_in_executor
    connection.webserver.download_tokens = {}
    start = 1723111156
    with (
        patch(
            "viseron.components.webserver.websocket_api.commands."
            "get_time_period_fragments",
            return_value=[MagicMock()],
        ),
        patch("viseron.components.webserver.websocket_api.commands.shutil.move"),
        patch("viseron.components.webserver.websocket_api.commands.create_directory"),
    ):
        asyncio.run(
            export_timespan(
                connection,
                {
                    "type": "export_timespan",
                    "command_id": 1,
                    "camera_identifier": "cam_a",
                    "start": start,
                    "end": start + 60,
                },
            )
        )

    (token,) = connection.webserver.download_tokens.values()
    time_string = datetime.datetime.fromtimestamp(start).strftime("%Y-%m-%d-%H-%M-%S")
    assert token.filename.endswith(f"/cam_a-{time_string}.mp4")


async def _wait_for_render_tasks() -> None:
    await asyncio.gather(*commands._RENDER_TASKS)


class TestRenderTimelapse:
    """Tests for the render_timelapse command."""

    START = 1723111156

    def _message(self, **overrides: Any) -> dict[str, Any]:
        return {
            "type": "render_timelapse",
            "command_id": 1,
            "camera_identifier": "cam_a",
            "start": self.START,
            "end": self.START + 3600,
            "fps": 30,
            "max_frames": 1800,
            "max_width": None,
            **overrides,
        }

    def _connection(self) -> tuple[MagicMock, Future[str], MagicMock]:
        connection = _connection(_user())
        connection.get_camera.return_value.identifier = "cam_a"
        connection.get_camera.return_value.timelapse_folder = "/timelapse/cam_a"
        connection.webserver.download_tokens = {}

        async def _run_in_executor(func: Any, *args: Any) -> Any:
            return func(*args)

        connection.run_in_executor = _run_in_executor
        future: Future[str] = Future()
        cancel_event = MagicMock()
        render_manager = MagicMock()
        render_manager.submit.return_value = TimelapseRenderJob(future, cancel_event)
        connection.vis.data = {TIMELAPSE_RENDER_MANAGER: render_manager}
        return connection, future, cancel_event

    def _sent(self, connection: MagicMock) -> list[dict[str, Any]]:
        return [call.args[0] for call in connection.async_send_message.call_args_list]

    def test_render_done(self) -> None:
        """The handler returns before the render finishes, then sends the token."""
        connection, future, _ = self._connection()

        async def _test() -> None:
            await render_timelapse(connection, self._message())
            # The command must not block the connection while rendering
            assert self._sent(connection) == [
                {"command_id": 1, "type": "result", "success": True, "result": None}
            ]
            assert 1 in connection.subscriptions

            future.set_result("/tmp/viseron/timelapse-abc.mp4")
            await _wait_for_render_tasks()

        with (
            patch(f"{COMMANDS}.shutil.move") as move,
            patch(f"{COMMANDS}.create_directory"),
        ):
            asyncio.run(_test())

        (token,) = connection.webserver.download_tokens.values()
        start_string, end_string = (
            datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d-%H-%M-%S")
            for timestamp in (self.START, self.START + 3600)
        )
        assert token.filename.endswith(
            f"/cam_a-timelapse-{start_string}-{end_string}-{token.token[:8]}.mp4"
        )
        assert token.delete_after_download
        move.assert_called_once_with("/tmp/viseron/timelapse-abc.mp4", token.filename)
        assert self._sent(connection)[1:] == [
            {
                "command_id": 1,
                "type": "subscription_result",
                "success": True,
                "result": {
                    "status": "done",
                    "filename": token.filename,
                    "token": token.token,
                },
            },
            {"command_id": 1, "type": "cancel_subscription"},
        ]
        assert 1 not in connection.subscriptions

    def test_render_status_forwarded(self) -> None:
        """Status updates from the render thread are sent thread-safely."""
        connection, _, _ = self._connection()

        asyncio.run(render_timelapse(connection, self._message()))

        submit = connection.vis.data[TIMELAPSE_RENDER_MANAGER].submit
        on_status = submit.call_args.args[2]
        on_status({"status": "queued"})
        connection.send_message.assert_called_once_with(
            {
                "command_id": 1,
                "type": "subscription_result",
                "success": True,
                "result": {"status": "queued"},
            }
        )

    @pytest.mark.parametrize(
        "exception, code, error_message",
        [
            pytest.param(
                TimelapseNoFramesError("No frames"),
                "not_found",
                "No frames",
                id="no_frames",
            ),
            pytest.param(
                TimelapseRenderError("Render timed out"),
                "uknown_error",
                "Render timed out",
                id="render_error",
            ),
            pytest.param(
                RuntimeError("/secret/path"),
                "uknown_error",
                "Unknown error",
                id="unexpected_error_hidden",
            ),
        ],
    )
    def test_render_error(
        self, exception: Exception, code: str, error_message: str
    ) -> None:
        """A failed render sends a subscription error and ends the subscription."""
        connection, future, _ = self._connection()

        async def _test() -> None:
            await render_timelapse(connection, self._message())
            future.set_exception(exception)
            await _wait_for_render_tasks()

        asyncio.run(_test())

        assert self._sent(connection)[1:] == [
            {
                "command_id": 1,
                "type": "subscription_result",
                "success": False,
                "error": {"code": code, "message": error_message},
            },
            {"command_id": 1, "type": "cancel_subscription"},
        ]
        assert 1 not in connection.subscriptions

    def test_render_busy(self) -> None:
        """A render rejected by a full queue ends the subscription."""
        connection, _, _ = self._connection()
        submit = connection.vis.data[TIMELAPSE_RENDER_MANAGER].submit
        submit.side_effect = TimelapseRenderBusyError

        asyncio.run(render_timelapse(connection, self._message()))

        assert [
            (message["type"], message.get("success"))
            for message in self._sent(connection)
        ] == [
            ("result", True),
            ("subscription_result", False),
            ("cancel_subscription", None),
        ]
        assert 1 not in connection.subscriptions

    @pytest.mark.parametrize(
        "before_cancel, after_cancel",
        [
            pytest.param(lambda _future: None, lambda _future: None, id="queued"),
            pytest.param(
                lambda future: future.set_running_or_notify_cancel(),
                lambda future: future.set_exception(TimelapseRenderCancelled()),
                id="rendering",
            ),
        ],
    )
    def test_unsubscribe_cancels(
        self,
        before_cancel: Callable[[Future[str]], Any],
        after_cancel: Callable[[Future[str]], Any],
    ) -> None:
        """unsubscribe_event cancels the render and nothing more is sent."""
        connection, future, cancel_event = self._connection()

        async def _test() -> None:
            await render_timelapse(connection, self._message())
            before_cancel(future)
            await unsubscribe_event(
                connection,
                {"type": "unsubscribe_event", "command_id": 2, "subscription": 1},
            )
            after_cancel(future)
            await _wait_for_render_tasks()

        asyncio.run(_test())

        cancel_event.set.assert_called_once()
        assert [message["type"] for message in self._sent(connection)] == [
            "result",
            "result",
        ]

    @pytest.mark.parametrize("cancel_during_move", [False, True])
    def test_cancelled_after_render_finished(self, cancel_during_move: bool) -> None:
        """A render cancelled while finishing removes the video."""
        connection, future, _ = self._connection()

        def _move(_src: str, _dst: str) -> None:
            if cancel_during_move:
                connection.subscriptions.pop(1)

        async def _test() -> None:
            await render_timelapse(connection, self._message())
            if not cancel_during_move:
                connection.subscriptions.pop(1)
            future.set_result("/tmp/viseron/timelapse-abc.mp4")
            await _wait_for_render_tasks()

        with (
            patch(f"{COMMANDS}.shutil.move", side_effect=_move) as move,
            patch(f"{COMMANDS}.create_directory"),
            patch(f"{COMMANDS}.os.remove") as remove,
        ):
            asyncio.run(_test())

        remove.assert_called_once_with(move.call_args.args[1])
        assert not connection.webserver.download_tokens
        assert len(self._sent(connection)) == 1

    def test_move_to_downloads_failed(self) -> None:
        """A failed move sends an error and removes both paths."""
        connection, future, _ = self._connection()

        async def _test() -> None:
            await render_timelapse(connection, self._message())
            future.set_result("/tmp/viseron/timelapse-abc.mp4")
            await _wait_for_render_tasks()

        with (
            patch(f"{COMMANDS}.shutil.move", side_effect=OSError("disk full")) as move,
            patch(f"{COMMANDS}.create_directory"),
            patch(f"{COMMANDS}.os.remove") as remove,
        ):
            asyncio.run(_test())

        assert [call.args[0] for call in remove.call_args_list] == list(
            move.call_args.args
        )
        assert not connection.webserver.download_tokens
        assert self._sent(connection)[1:] == [
            {
                "command_id": 1,
                "type": "subscription_result",
                "success": False,
                "error": {"code": "uknown_error", "message": "Unknown error"},
            },
            {"command_id": 1, "type": "cancel_subscription"},
        ]
        assert 1 not in connection.subscriptions

    def test_error_after_unsubscribe(self) -> None:
        """A render that fails after it was unsubscribed sends nothing more."""
        connection, future, _ = self._connection()

        async def _test() -> None:
            await render_timelapse(connection, self._message())
            connection.subscriptions.pop(1)
            future.set_exception(TimelapseRenderError("Render timed out"))
            await _wait_for_render_tasks()

        asyncio.run(_test())

        assert len(self._sent(connection)) == 1

    @pytest.mark.parametrize("key", ["start", "end"])
    @pytest.mark.parametrize("value", ["nan", "inf", "-inf", 1e300, -1])
    def test_schema_rejects_invalid_timestamps(self, key: str, value: Any) -> None:
        """Timestamps that datetime cannot represent are rejected by the schema."""
        with pytest.raises(vol.Invalid):
            render_timelapse.schema(self._message(**{key: value}))

    @pytest.mark.parametrize(
        "camera, overrides, code",
        [
            pytest.param(None, {}, "not_found", id="camera_not_accessible"),
            pytest.param(
                MagicMock(timelapse_folder=None), {}, "not_found", id="timelapse_off"
            ),
            pytest.param(
                MagicMock(timelapse_folder="/timelapse/cam_a"),
                {"end": START},
                "invalid_format",
                id="end_not_after_start",
            ),
        ],
    )
    def test_rejected(
        self, camera: MagicMock | None, overrides: dict[str, Any], code: str
    ) -> None:
        """Invalid requests are rejected before a render is submitted."""
        connection, _, _ = self._connection()
        connection.get_camera.return_value = camera

        asyncio.run(render_timelapse(connection, self._message(**overrides)))

        (sent,) = self._sent(connection)
        assert sent["success"] is False
        assert sent["error"]["code"] == code
        connection.vis.data[TIMELAPSE_RENDER_MANAGER].submit.assert_not_called()
