"""Common mocks for Viseron tests."""
from __future__ import annotations

import datetime
from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy import insert
from sqlalchemy.orm import Session

from viseron.components import Component
from viseron.components.storage.models import Files, Recordings
from viseron.const import LOADED
from viseron.domain_registry import DomainState
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN
from viseron.domains.motion_detector import AbstractMotionDetectorScanner
from viseron.domains.object_detector import AbstractObjectDetector
from viseron.helpers import utcnow

if TYPE_CHECKING:
    from viseron import Viseron


class MockComponent(Component):
    """Representation of a fake component."""

    def __init__(  # pylint: disable=dangerous-default-value
        self,
        vis: Viseron,
        component: str,
        config: dict = {},
        setup_component: Callable | None = None,
    ):
        """Initialize the mock component."""
        self.__name__ = f"viseron.components.{component}"
        self.__file__ = f"viseron/components/{component}"
        super().__init__(vis, self.__file__, component, config)

        if setup_component is None:
            vis.data[LOADED][component] = self
        else:
            self.setup_component: Callable = setup_component


@dataclass
class MockDomainModule:
    """Configurable mock for a domain module.

    Args:
        setup_return: Return value for setup(). Can be True, False, or any value.
        setup_exception: Exception to raise during setup() (e.g., DomainNotReady).
        setup_num_params: Number of parameters for setup (3 or 4).
        config_schema: A callable schema, or None to indicate no CONFIG_SCHEMA attr.
        config_schema_exception: Exception to raise when CONFIG_SCHEMA is called.
        setup_failed_handler: Optional setup_failed handler function.
        setup_call_count: Track number of setup calls (for retry testing).
        setup_side_effects: List of (return_value, exception) tuples for sequential
            calls.
    """

    setup_return: Any = True
    setup_exception: Exception | None = None
    setup_num_params: int = 3
    config_schema: Callable[[dict], dict] | None = None
    config_schema_exception: Exception | None = None
    setup_failed_handler: Callable | None = None
    setup_call_count: int = field(default=0, init=False)
    setup_side_effects: list[tuple[Any, Exception | None]] = field(default_factory=list)

    def setup(  # pylint: disable=unused-argument
        self, vis: Viseron, config: dict, identifier: str, tries: int = 1
    ) -> Any:
        """Mock setup function with configurable signature."""
        self.setup_call_count += 1

        # Handle sequential side effects for retry testing
        if self.setup_side_effects:
            idx = min(self.setup_call_count - 1, len(self.setup_side_effects) - 1)
            return_val, exc = self.setup_side_effects[idx]
            if exc:
                raise exc
            return return_val

        if self.setup_exception:
            raise self.setup_exception
        return self.setup_return

    @property
    def CONFIG_SCHEMA(  # pylint: disable=invalid-name
        self,
    ) -> Callable[[dict], dict] | None:
        """Return config schema if configured."""
        if self.config_schema is None and self.config_schema_exception is None:
            raise AttributeError("No CONFIG_SCHEMA")
        if self.config_schema_exception:

            def _raise(config):
                raise self.config_schema_exception  # type: ignore[misc]

            return _raise
        return self.config_schema

    def has_config_schema(self) -> bool:
        """Check if module has CONFIG_SCHEMA."""
        return (
            self.config_schema is not None or self.config_schema_exception is not None
        )

    def setup_failed(self, vis: Viseron, entry) -> Any:
        """Mock setup_failed handler."""
        if self.setup_failed_handler:
            return self.setup_failed_handler(vis, entry)
        raise AttributeError("No setup_failed handler")


class MockCamera(MagicMock):
    """Representation of a fake camera."""

    def __init__(  # pylint: disable=dangerous-default-value
        self,
        vis: Viseron | None = None,
        identifier="test_camera_identifier",
        resolution=(1920, 1080),
        extension="mp4",
        access_tokens=["test_access_token", "test_access_token_2"],
        lookback: int = 5,
        **kwargs,
    ):
        """Initialize the mock camera."""
        super().__init__(
            recorder=MagicMock(lookback=lookback),
            identifier=identifier,
            resolution=resolution,
            extension=extension,
            access_tokens=access_tokens,
            **kwargs,
        )
        if vis:
            vis._domain_registry.register(
                component_name="test",
                component_path="test",
                domain=CAMERA_DOMAIN,
                identifier=identifier,
                config={},
                require_domains=None,
                optional_domains=None,
            )
            vis.register_domain(CAMERA_DOMAIN, identifier, self)
            vis._domain_registry.set_state(
                domain=CAMERA_DOMAIN,
                identifier=identifier,
                state=DomainState.LOADED,
                instance=self,
            )


class MockMotionDetector(MagicMock):
    """Representation of a fake motion detector scanner."""

    def __init__(
        self,
        *,
        fps: int = 5,
        trigger_event_recording: bool = True,
        recorder_keepalive: bool = False,
        max_recorder_keepalive: int | None = None,
        motion_detected: bool = False,
        motion_contours=None,
        **kwargs,
    ):
        """Initialize the mock motion detector."""
        super().__init__(
            spec=AbstractMotionDetectorScanner,
            fps=fps,
            trigger_event_recording=trigger_event_recording,
            recorder_keepalive=recorder_keepalive,
            max_recorder_keepalive=max_recorder_keepalive,
            motion_detected=motion_detected,
            motion_contours=motion_contours,
            **kwargs,
        )


class MockObjectDetector(MagicMock):
    """Representation of a fake object detector."""

    def __init__(
        self,
        *,
        fps: int = 5,
        scan_on_motion_only: bool = False,
        objects_in_fov: list | None = None,
        zones: list | None = None,
        object_filters: dict[str, Any] | None = None,
        **kwargs,
    ):
        super().__init__(
            spec=AbstractObjectDetector,
            fps=fps,
            scan_on_motion_only=scan_on_motion_only,
            objects_in_fov=[] if objects_in_fov is None else objects_in_fov,
            zones=[] if zones is None else zones,
            object_filters={} if object_filters is None else object_filters,
            **kwargs,
        )


class BaseTestWithRecordings:
    """Test class that provides a database with recordings."""

    _get_db_session: Callable[[], Session]
    _now: datetime.datetime
    # Represents the timestamp of the last inserted file
    _simulated_now: datetime.datetime

    def insert_data(self, get_session: Callable[[], Session]):
        """Insert data used tests."""
        with get_session() as session:
            for i in range(15):
                timestamp = self._now + datetime.timedelta(seconds=5 * i)
                filename = f"{int(timestamp.timestamp())}.m4s"
                session.execute(
                    insert(Files).values(
                        tier_id=0,
                        tier_path="/test/",
                        camera_identifier="test",
                        category="recorder",
                        subcategory="segments",
                        path=f"/test/{filename}",
                        directory="test",
                        filename=filename,
                        size=10,
                        orig_ctime=timestamp,
                        duration=5,
                        created_at=timestamp,
                    )
                )
                session.execute(
                    insert(Files).values(
                        tier_id=0,
                        tier_path="/test2/",
                        camera_identifier="test2",
                        category="recorder",
                        subcategory="segments",
                        path=f"/test2/{filename}",
                        directory="test2",
                        filename=filename,
                        size=10,
                        orig_ctime=timestamp,
                        duration=5,
                        created_at=timestamp,
                    )
                )
            BaseTestWithRecordings._simulated_now = timestamp
            session.execute(
                insert(Recordings).values(
                    camera_identifier="test",
                    start_time=self._now + datetime.timedelta(seconds=7),
                    adjusted_start_time=self._now + datetime.timedelta(seconds=2),
                    end_time=self._now + datetime.timedelta(seconds=10),
                    created_at=self._now + datetime.timedelta(seconds=7),
                    thumbnail_path="/test/test1.jpg",
                )
            )
            session.execute(
                insert(Recordings).values(
                    camera_identifier="test2",
                    start_time=self._now + datetime.timedelta(seconds=7),
                    adjusted_start_time=self._now + datetime.timedelta(seconds=2),
                    end_time=self._now + datetime.timedelta(seconds=10),
                    created_at=self._now + datetime.timedelta(seconds=7),
                    thumbnail_path="/test2/test4.jpg",
                )
            )
            session.execute(
                insert(Recordings).values(
                    camera_identifier="test",
                    start_time=self._now + datetime.timedelta(seconds=26),
                    adjusted_start_time=self._now + datetime.timedelta(seconds=21),
                    end_time=self._now + datetime.timedelta(seconds=36),
                    created_at=self._now + datetime.timedelta(seconds=26),
                    thumbnail_path="/test/test2.jpg",
                )
            )
            session.execute(
                insert(Recordings).values(
                    camera_identifier="test",
                    start_time=self._now + datetime.timedelta(seconds=40),
                    adjusted_start_time=self._now + datetime.timedelta(seconds=35),
                    end_time=self._now + datetime.timedelta(seconds=45),
                    created_at=self._now + datetime.timedelta(seconds=40),
                    thumbnail_path="/test/test3.jpg",
                )
            )
            session.commit()
            yield

    @pytest.fixture(autouse=True, scope="function")
    def setup_get_db_session(
        self, get_db_session: Callable[[], Session]
    ) -> Generator[None, Any, None]:
        """Insert data used by all tests."""
        BaseTestWithRecordings._get_db_session = get_db_session
        BaseTestWithRecordings._now = utcnow()
        yield from self.insert_data(get_db_session)
