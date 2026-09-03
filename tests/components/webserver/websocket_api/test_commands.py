"""Tests for WebSocket API commands."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from viseron.components.webserver.auth import Role, User
from viseron.components.webserver.websocket_api.commands import (
    _camera_identifier_from_event,
    _event_allowed,
    _state_changed_allowed,
    subscribe_event,
    subscribe_states,
)
from viseron.events import Event, EventData
from viseron.states import EventStateChangedData, State


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
