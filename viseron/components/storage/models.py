"""Database models for storage component."""

from __future__ import annotations

import datetime
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from sqlalchemy import (
    ColumnElement,
    DateTime,
    Float,
    Index,
    Integer,
    Label,
    LargeBinary,
    String,
    text,
    types,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.sql import expression

ColumnMeta = dict[str, str]


class UTCDateTime(types.TypeDecorator):
    """A DateTime type which can only store UTC datetimes."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, _dialect):
        """Remove timezone info from datetime."""
        # Only allow UTC datetimes
        if isinstance(value, datetime.datetime):
            if value.tzinfo is None:
                raise ValueError("Only UTC datetimes are allowed")
            return value.replace(tzinfo=None)
        return value

    def process_result_value(self, value, _dialect):
        """Add timezone info to datetime."""
        if isinstance(value, datetime.datetime):
            return value.replace(tzinfo=datetime.timezone.utc)
        return value

    class Comparator(DateTime.Comparator):
        """Comparator for UTCDateTime."""

        def local(
            self, utc_offset: datetime.timedelta | None = None
        ) -> Label | ColumnElement:
            """Convert UTC timestamp to local time using PostgreSQL timezone arithmetic.

            Args:
                utc_offset: User's UTC offset as timedelta (e.g., timedelta(hours=-5))

            Returns:
                Column expression with localized timestamp
            """
            if utc_offset is None:
                return self.expr

            # Convert timedelta to PostgreSQL interval string
            total_seconds = int(utc_offset.total_seconds())
            hours, remainder = divmod(abs(total_seconds), 3600)
            minutes, _seconds = divmod(remainder, 60)
            offset_str = f"{'-' if total_seconds < 0 else '+'}{hours:02d}:{minutes:02d}"

            # Convert UTC timestamp to local time using interval arithmetic
            return (self.expr + text(f"interval '{offset_str}'")).label(
                "local_timestamp"
            )

    comparator_factory = Comparator


class UTCNow(expression.FunctionElement):
    """Return the current timestamp in UTC."""

    type = UTCDateTime()
    inherit_cache = True


@compiles(UTCNow, "postgresql")
def pg_utcnow(
    _element, _compiler, **_kw
) -> Literal["TIMEZONE('utc', CURRENT_TIMESTAMP)"]:
    """Compile utcnow function for postgresql."""
    return "TIMEZONE('utc', CURRENT_TIMESTAMP)"


class Base(DeclarativeBase):
    """Base class for database models."""

    type_annotation_map = {ColumnMeta: JSONB}


class Files(Base):
    """Database model for files."""

    __tablename__ = "files"

    __table_args__ = (
        Index("idx_files_path", "path"),
        Index("idx_files_camera_id", "camera_identifier"),
        Index(
            "idx_files_tier_lookup",
            "camera_identifier",
            "tier_id",
            "category",
            "subcategory",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tier_id: Mapped[int] = mapped_column(Integer)
    tier_path: Mapped[str] = mapped_column(String)
    camera_identifier: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    subcategory: Mapped[str] = mapped_column(String)
    path: Mapped[str] = mapped_column(String, unique=True)
    directory: Mapped[str] = mapped_column(String)
    filename: Mapped[str] = mapped_column(String)
    size: Mapped[int] = mapped_column(Integer)
    duration: Mapped[float] = mapped_column(Float, nullable=True)
    orig_ctime: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(timezone=False), nullable=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(timezone=False), server_default=UTCNow(), nullable=True
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(timezone=False), onupdate=UTCNow(), nullable=True
    )


@dataclass
class FilesMeta:
    """Files meta dataclass.

    Holds temporary information about files before they are inserted into the DB.
    """

    orig_ctime: datetime.datetime
    duration: float


class TriggerTypes(Enum):
    """Trigger types for recordings."""

    MOTION = "motion"
    OBJECT = "object"


class Recordings(Base):
    """Database model for recordings."""

    __tablename__ = "recordings"

    __table_args__ = (
        Index(
            "idx_recordings_camera_times", "camera_identifier", "start_time", "end_time"
        ),
        Index("idx_recordings_thumbnail", "thumbnail_path"),
        Index("idx_recordings_clip", "clip_path"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_identifier: Mapped[str] = mapped_column(String)
    start_time: Mapped[datetime.datetime] = mapped_column(UTCDateTime(timezone=False))
    end_time: Mapped[datetime.datetime | None] = mapped_column(
        UTCDateTime(timezone=False), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(timezone=False), server_default=UTCNow(), nullable=True
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(timezone=False), onupdate=UTCNow(), nullable=True
    )

    trigger_type: Mapped[TriggerTypes | None] = mapped_column(nullable=True)
    trigger_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_path: Mapped[str] = mapped_column(String, nullable=True)
    clip_path: Mapped[str] = mapped_column(String, nullable=True)
    adjusted_start_time: Mapped[datetime.datetime | None] = mapped_column(
        UTCDateTime(timezone=False), nullable=False
    )

    def get_fragments(
        self, lookback: float, get_session: Callable[[], Session], now=None
    ):
        """Get all files for this recording.

        Local import to avoid circular imports.
        """
        # pylint: disable-next=import-outside-toplevel
        from viseron.components.storage.queries import get_recording_fragments

        return get_recording_fragments(self.id, lookback, get_session, now)


class Objects(Base):
    """Database model for objects."""

    __tablename__ = "objects"

    __table_args__ = (Index("idx_objects_snapshot", "snapshot_path"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_identifier: Mapped[str] = mapped_column(String)
    label: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float)
    width: Mapped[float] = mapped_column(Float)
    height: Mapped[float] = mapped_column(Float)
    x1: Mapped[float] = mapped_column(Float)
    y1: Mapped[float] = mapped_column(Float)
    x2: Mapped[float] = mapped_column(Float)
    y2: Mapped[float] = mapped_column(Float)
    snapshot_path: Mapped[str] = mapped_column(String, nullable=True)
    zone: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(timezone=False), server_default=UTCNow(), nullable=True
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(timezone=False), onupdate=UTCNow(), nullable=True
    )


class Motion(Base):
    """Database model for motion."""

    __tablename__ = "motion"

    __table_args__ = (Index("idx_motion_snapshot", "snapshot_path"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_identifier: Mapped[str] = mapped_column(String)
    start_time: Mapped[datetime.datetime] = mapped_column(UTCDateTime(timezone=False))
    end_time: Mapped[datetime.datetime | None] = mapped_column(
        UTCDateTime(timezone=False), nullable=True
    )
    snapshot_path: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(timezone=False), server_default=UTCNow(), nullable=True
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(timezone=False), onupdate=UTCNow(), nullable=True
    )


class MotionContours(Base):
    """Database model for motion contours."""

    __tablename__ = "motion_contours"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    motion_id: Mapped[int] = mapped_column(Integer)
    contour: Mapped[LargeBinary] = mapped_column(LargeBinary)
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(timezone=False), server_default=UTCNow(), nullable=True
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(timezone=False), onupdate=UTCNow(), nullable=True
    )


class PostProcessorResults(Base):
    """Database model for post processor results."""

    __tablename__ = "post_processor_results"

    __table_args__ = (Index("idx_ppr_snapshot", "snapshot_path"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_identifier: Mapped[str] = mapped_column(String)
    domain: Mapped[str] = mapped_column(String)
    snapshot_path: Mapped[str] = mapped_column(String, nullable=True)
    data: Mapped[ColumnMeta] = mapped_column(JSONB)
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(timezone=False), server_default=UTCNow(), nullable=True
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(timezone=False), onupdate=UTCNow(), nullable=True
    )


class Events(Base):
    """Database model for dispatched events."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    data: Mapped[ColumnMeta] = mapped_column(JSONB)
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(timezone=False), server_default=UTCNow(), nullable=True
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(timezone=False), onupdate=UTCNow(), nullable=True
    )
