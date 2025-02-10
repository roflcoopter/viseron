"""Storage component."""
from __future__ import annotations

import copy
import logging
import os
import pathlib
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypedDict

import voluptuous as vol
from alembic import command, script
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, create_engine, update
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from viseron.components.storage.config import (
    STORAGE_SCHEMA,
    TIER_SCHEMA_BASE,
    validate_tiers,
)
from viseron.components.storage.const import (
    COMPONENT,
    CONFIG_CONTINUOUS,
    CONFIG_EVENTS,
    CONFIG_MOVE_ON_SHUTDOWN,
    CONFIG_PATH,
    CONFIG_POLL,
    CONFIG_RECORDER,
    CONFIG_SNAPSHOTS,
    CONFIG_TIERS,
    DATABASE_URL,
    DEFAULT_COMPONENT,
    DESC_COMPONENT,
    TIER_CATEGORY_RECORDER,
    TIER_CATEGORY_SNAPSHOTS,
    TIER_SUBCATEGORY_EVENT_CLIPS,
    TIER_SUBCATEGORY_FACE_RECOGNITION,
    TIER_SUBCATEGORY_LICENSE_PLATE_RECOGNITION,
    TIER_SUBCATEGORY_MOTION_DETECTOR,
    TIER_SUBCATEGORY_OBJECT_DETECTOR,
    TIER_SUBCATEGORY_SEGMENTS,
    TIER_SUBCATEGORY_THUMBNAILS,
)
from viseron.components.storage.jobs import CleanupManager
from viseron.components.storage.models import Base, FilesMeta, Motion, Recordings
from viseron.components.storage.tier_handler import (
    EventClipTierHandler,
    SegmentsTierHandler,
    SnapshotTierHandler,
    ThumbnailTierHandler,
)
from viseron.components.storage.util import (
    RequestedFilesCount,
    get_event_clips_path,
    get_segments_path,
    get_snapshots_path,
    get_thumbnails_path,
)
from viseron.const import EVENT_DOMAIN_REGISTERED, VISERON_SIGNAL_STOPPING
from viseron.domains.camera.const import CONFIG_STORAGE, DOMAIN as CAMERA_DOMAIN
from viseron.helpers import utcnow
from viseron.helpers.logs import StreamToLogger
from viseron.types import SnapshotDomain

if TYPE_CHECKING:
    from viseron import Event, Viseron
    from viseron.domains.camera import AbstractCamera

LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(
                COMPONENT, default=DEFAULT_COMPONENT, description=DESC_COMPONENT
            ): STORAGE_SCHEMA
        },
        validate_tiers,
    ),
    extra=vol.ALLOW_EXTRA,
)


class TierSubcategory(TypedDict):
    """Tier subcategory."""

    subcategory: str
    tier_handler: type[
        SnapshotTierHandler
        | SegmentsTierHandler
        | ThumbnailTierHandler
        | EventClipTierHandler
    ]


class TierCategories(TypedDict):
    """Tier categories."""

    recorder: list[TierSubcategory]
    snapshots: list[TierSubcategory]


TIER_CATEGORIES: TierCategories = {
    TIER_CATEGORY_RECORDER: [
        {
            "subcategory": TIER_SUBCATEGORY_SEGMENTS,
            "tier_handler": SegmentsTierHandler,
        },
        {
            "subcategory": TIER_SUBCATEGORY_EVENT_CLIPS,
            "tier_handler": EventClipTierHandler,
        },
        {
            "subcategory": TIER_SUBCATEGORY_THUMBNAILS,
            "tier_handler": ThumbnailTierHandler,
        },
    ],
    TIER_CATEGORY_SNAPSHOTS: [
        {
            "subcategory": TIER_SUBCATEGORY_FACE_RECOGNITION,
            "tier_handler": SnapshotTierHandler,
        },
        {
            "subcategory": TIER_SUBCATEGORY_OBJECT_DETECTOR,
            "tier_handler": SnapshotTierHandler,
        },
        {
            "subcategory": TIER_SUBCATEGORY_LICENSE_PLATE_RECOGNITION,
            "tier_handler": SnapshotTierHandler,
        },
        {
            "subcategory": TIER_SUBCATEGORY_MOTION_DETECTOR,
            "tier_handler": SnapshotTierHandler,
        },
    ],
}


def setup(vis: Viseron, config: dict[str, Any]) -> bool:
    """Set up storage component."""
    vis.data[COMPONENT] = Storage(vis, config[COMPONENT])
    vis.data[COMPONENT].initialize()
    return True


def startup_chores(get_session: Callable[[], Session]) -> None:
    """Various database startup chores."""
    # Set Recordings.end_time and Motion.end_time on startup in case of crashes
    with get_session() as session:
        stmt = (
            update(Recordings)
            .where(Recordings.end_time == None)  # noqa: E711 pylint: disable=C0121
            .values(end_time=utcnow())
        )
        session.execute(stmt)
        session.commit()
    with get_session() as session:
        stmt = (
            update(Motion)
            .where(Motion.end_time == None)  # noqa: E711 pylint: disable=C0121
            .values(end_time=utcnow())
        )
        session.execute(stmt)
        session.commit()


class Storage:
    """Storage component.

    It handles the database connection as well as file storage.

    This component will move stored items up tiers when they reach the max age or max
    size.
    """

    def __init__(self, vis: Viseron, config: dict[str, Any]) -> None:
        self._vis = vis
        self._config = config
        self._recordings_tiers = config[CONFIG_RECORDER][CONFIG_TIERS]
        self._snapshots_tiers = config[CONFIG_SNAPSHOTS][CONFIG_TIERS]
        self._camera_tier_handlers: dict[
            str, dict[str, list[dict[str, SnapshotTierHandler | SegmentsTierHandler]]]
        ] = {}
        self.camera_requested_files_count: dict[str, RequestedFilesCount] = {}

        self.ignored_files: list[str] = []
        self.engine: Engine | None = None
        self._get_session: Callable[[], Session] | None = None

        self.temporary_files_meta: dict[str, FilesMeta] = {}

        self._cleanup_manager = CleanupManager(vis, self)
        self._cleanup_manager.start()

    @property
    def camera_tier_handlers(self):
        """Return camera tier handlers."""
        return self._camera_tier_handlers

    def initialize(self) -> None:
        """Initialize storage component."""
        self._alembic_cfg = self._get_alembic_config()
        self.create_database()

        self._vis.listen_event(
            EVENT_DOMAIN_REGISTERED.format(domain=CAMERA_DOMAIN),
            self._camera_registered,
        )
        self._vis.register_signal_handler(VISERON_SIGNAL_STOPPING, self._shutdown)

    def _get_alembic_config(self) -> Config:
        base_path = pathlib.Path(__file__).parent.resolve()
        alembic_cfg = Config(
            os.path.join(base_path, "alembic.ini"),
            stdout=StreamToLogger(
                logging.getLogger("alembic.stdout"),
                logging.INFO,
            ),
        )
        alembic_cfg.set_main_option(
            "script_location", os.path.join(base_path, "alembic")
        )
        return alembic_cfg

    def _run_migrations(self) -> None:
        """Run database migrations.

        Checks to see if there are any upgrades to be done and applies them.
        """
        LOGGER.warning("Upgrading database, DO NOT INTERRUPT")
        command.upgrade(self._alembic_cfg, "head")
        LOGGER.warning("Database upgrade complete")

    def _create_new_db(self) -> None:
        """Create and stamp a new DB for fresh installs."""
        LOGGER.debug("Creating new database")
        if self.engine is None:
            raise RuntimeError("The database connection has not been established")

        try:
            Base.metadata.create_all(self.engine)
            command.stamp(self._alembic_cfg, "head")
        except Exception as error:  # pylint: disable=[broad-exception-caught]
            LOGGER.error(f"Failed to create new database: {error}", exc_info=True)

    def create_database(self) -> None:
        """Create database."""
        self.engine = create_engine(
            DATABASE_URL, connect_args={"options": "-c timezone=UTC"}
        )

        conn = self.engine.connect()
        context = MigrationContext.configure(conn)
        current_rev = context.get_current_revision()
        LOGGER.debug(f"Current database revision: {current_rev}")

        _script = script.ScriptDirectory.from_config(self._alembic_cfg)

        if current_rev is None:
            self._create_new_db()
        elif current_rev != _script.get_current_head():
            self._run_migrations()

        self._get_session = scoped_session(sessionmaker(bind=self.engine))
        self._get_session_expire = scoped_session(
            sessionmaker(bind=self.engine, expire_on_commit=True)
        )
        startup_chores(self._get_session)

    def get_session(self, expire_on_commit: bool = False) -> Session:
        """Get a new sqlalchemy session.

        Args:
            expire_on_commit: Whether to expire objects when committing.
        """
        if self._get_session is None or self._get_session_expire is None:
            raise RuntimeError("The database connection has not been established")

        if expire_on_commit:
            return self._get_session_expire()
        return self._get_session()

    def get_event_clips_path(self, camera: AbstractCamera) -> str:
        """Get event clips path for camera."""
        self.create_tier_handlers(camera)
        return get_event_clips_path(
            self._camera_tier_handlers[camera.identifier][TIER_CATEGORY_RECORDER][0][
                TIER_SUBCATEGORY_EVENT_CLIPS
            ].tier,
            camera,
        )

    def get_segments_path(self, camera: AbstractCamera) -> str:
        """Get segments path for camera."""
        self.create_tier_handlers(camera)
        return get_segments_path(
            self._camera_tier_handlers[camera.identifier][TIER_CATEGORY_RECORDER][0][
                TIER_SUBCATEGORY_SEGMENTS
            ].tier,
            camera,
        )

    def get_thumbnails_path(self, camera: AbstractCamera) -> str:
        """Get thumbnails path for camera.

        This is an UNMONITORED path, meaning that the files in this path will not be
        moved up tiers. Files are cleaned up automatically with the corresponding
        recording.
        """
        self.create_tier_handlers(camera)
        return get_thumbnails_path(
            self._camera_tier_handlers[camera.identifier][TIER_CATEGORY_RECORDER][0][
                TIER_SUBCATEGORY_EVENT_CLIPS
            ].tier,
            camera,
        )

    def get_snapshots_path(
        self,
        camera: AbstractCamera,
        domain: SnapshotDomain,
    ) -> str:
        """Get snapshots path for camera."""
        self.create_tier_handlers(camera)
        return get_snapshots_path(
            self._camera_tier_handlers[camera.identifier]["snapshots"][0][
                domain.value
            ].tier,
            camera,
            domain,
        )

    def search_file(
        self, camera_identifier: str, category: str, subcategory: str, path: str
    ) -> str | None:
        """Search for file in tiers."""
        prev_tier_handler = None
        for tier_handler in self._camera_tier_handlers[camera_identifier][category]:
            if tier_handler[subcategory].tier[CONFIG_PATH] in path:
                prev_tier_handler = tier_handler
                continue

            if prev_tier_handler is None:
                continue

            new_path = path.replace(
                prev_tier_handler[subcategory].tier[CONFIG_PATH],
                tier_handler[subcategory].tier[CONFIG_PATH],
                1,
            )
            if os.path.exists(new_path):
                LOGGER.debug(
                    f"Found file in tier: {tier_handler[subcategory].tier[CONFIG_PATH]}"
                )
                return new_path
        return None

    def ignore_file(self, filename: str) -> None:
        """Add filename to ignore list.

        Ignored files will not be moved up tiers and are not stored in the database.
        """
        if filename not in self.ignored_files:
            self.ignored_files.append(filename)

    def _camera_registered(self, event_data: Event[AbstractCamera]) -> None:
        camera = event_data.data
        self.create_tier_handlers(camera)

    def create_tier_handlers(self, camera: AbstractCamera) -> None:
        """Start observer for camera."""
        if camera.identifier in self._camera_tier_handlers:
            return

        self._camera_tier_handlers[camera.identifier] = {}
        self.camera_requested_files_count[camera.identifier] = RequestedFilesCount()

        tier_config = _get_tier_config(self._config, camera)
        for category in TIER_CATEGORIES:
            self._camera_tier_handlers[camera.identifier].setdefault(category, [])
            tiers = tier_config[category][CONFIG_TIERS]
            for index, tier in enumerate(tiers):
                self._camera_tier_handlers[camera.identifier][category].append({})
                if index == len(tiers) - 1:
                    next_tier = None
                else:
                    next_tier = tiers[index + 1]
                # pylint: disable-next=line-too-long
                for subcategory in TIER_CATEGORIES[category]:  # type: ignore[literal-required] # noqa: E501
                    self._camera_tier_handlers[camera.identifier][category][index][
                        subcategory["subcategory"]
                    ] = subcategory["tier_handler"](
                        self._vis,
                        camera,
                        index,
                        category,
                        subcategory["subcategory"],
                        tier,
                        next_tier,
                    )

    def _shutdown(self) -> None:
        """Shutdown."""
        if self.engine:
            self.engine.dispose()


def _get_tier_config(config: dict[str, Any], camera: AbstractCamera) -> dict[str, Any]:
    """Construct tier config for camera.

    There are multiple ways to configure tiers for a camera, and this function
    will construct the final tier config for the camera.
    camera > recorder > continuous/events is looked at first.
    camera > recorder > storage > tiers is looked at second.
    storage > recorder > tiers is looked at last.
    """
    if not hasattr(camera, "config"):
        return config
    tier_config = copy.deepcopy(config)
    _tier: dict[str, Any] = {}
    if camera.config[CONFIG_RECORDER].get(CONFIG_CONTINUOUS, None) or camera.config[
        CONFIG_RECORDER
    ].get(CONFIG_EVENTS, None):
        continuous = camera.config[CONFIG_RECORDER].get(CONFIG_CONTINUOUS, None)
        events = camera.config[CONFIG_RECORDER].get(CONFIG_EVENTS, None)
        if continuous is None:
            continuous = TIER_SCHEMA_BASE({})
        if events is None:
            events = TIER_SCHEMA_BASE({})

        _tier[CONFIG_PATH] = "/"
        _tier[CONFIG_CONTINUOUS] = continuous
        _tier[CONFIG_EVENTS] = events
        _tier[CONFIG_MOVE_ON_SHUTDOWN] = False
        _tier[CONFIG_POLL] = False
        tier_config[CONFIG_RECORDER][CONFIG_TIERS] = [_tier]
    elif camera.config[CONFIG_RECORDER][CONFIG_STORAGE]:
        _tier = camera.config[CONFIG_RECORDER][CONFIG_STORAGE][CONFIG_TIERS]
        tier_config[CONFIG_RECORDER][CONFIG_TIERS] = _tier

    if _tier:
        LOGGER.debug(
            f"Camera {camera.name} has custom tiers, "
            "overwriting storage recorder tiers"
        )
    return tier_config
