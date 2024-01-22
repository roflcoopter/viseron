"""Database models for storage component."""
from __future__ import annotations

import datetime
from typing import Callable, Dict, Literal, Optional

from sqlalchemy import DateTime, Float, Integer, LargeBinary, String, types
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.sql import expression

ColumnMeta = Dict[str, str]


class UTCDateTime(types.TypeDecorator):
    """A DateTime type which can only store UTC datetimes."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, _dialect):
        """Remove timezone info from datetime."""
        if isinstance(value, datetime.datetime):
            return value.replace(tzinfo=None)
        return value

    def process_result_value(self, value, _dialect):
        """Add timezone info to datetime."""
        if isinstance(value, datetime.datetime):
            return value.replace(tzinfo=datetime.timezone.utc)
        return value


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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tier_id: Mapped[int] = mapped_column(Integer)
    camera_identifier: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    path: Mapped[str] = mapped_column(String, unique=True)
    directory: Mapped[str] = mapped_column(String)
    filename: Mapped[str] = mapped_column(String)
    size: Mapped[int] = mapped_column(Integer)
    created_at = mapped_column(UTCDateTime(timezone=False), server_default=UTCNow())
    updated_at = mapped_column(UTCDateTime(timezone=False), onupdate=UTCNow())


class FilesMeta(Base):
    """Database model for files metadata.

    Used to store arbitrary metadata about files.
    """

    __tablename__ = "files_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(String, unique=True)
    orig_ctime = mapped_column(UTCDateTime(timezone=False), nullable=False)
    meta: Mapped[ColumnMeta] = mapped_column(JSONB)
    created_at = mapped_column(UTCDateTime(timezone=False), server_default=UTCNow())
    updated_at = mapped_column(UTCDateTime(timezone=False), onupdate=UTCNow())


class Recordings(Base):
    """Database model for recordings."""

    __tablename__ = "recordings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_identifier: Mapped[str] = mapped_column(String)
    start_time: Mapped[datetime.datetime] = mapped_column(UTCDateTime(timezone=False))
    end_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        UTCDateTime(timezone=False), nullable=True
    )
    created_at = mapped_column(UTCDateTime(timezone=False), server_default=UTCNow())
    updated_at = mapped_column(UTCDateTime(timezone=False), onupdate=UTCNow())

    trigger_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    trigger_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    thumbnail_path: Mapped[str] = mapped_column(String)

    def get_fragments(
        self, lookback: float, get_session: Callable[[], Session], now=UTCNow()
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
    zone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at = mapped_column(UTCDateTime(timezone=False), server_default=UTCNow())
    updated_at = mapped_column(UTCDateTime(timezone=False), onupdate=UTCNow())


class Motion(Base):
    """Database model for motion."""

    __tablename__ = "motion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_identifier: Mapped[str] = mapped_column(String)
    start_time: Mapped[datetime.datetime] = mapped_column(UTCDateTime(timezone=False))
    end_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        UTCDateTime(timezone=False), nullable=True
    )
    created_at = mapped_column(UTCDateTime(timezone=False), server_default=UTCNow())
    updated_at = mapped_column(UTCDateTime(timezone=False), onupdate=UTCNow())


class MotionContours(Base):
    """Database model for motion contours."""

    __tablename__ = "motion_contours"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    motion_id: Mapped[int] = mapped_column(Integer)
    contour: Mapped[LargeBinary] = mapped_column(LargeBinary)
    created_at = mapped_column(UTCDateTime(timezone=False), server_default=UTCNow())
    updated_at = mapped_column(UTCDateTime(timezone=False), onupdate=UTCNow())


class Events(Base):
    """Database model for dispatched events."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    data: Mapped[ColumnMeta] = mapped_column(JSONB)
    created_at = mapped_column(UTCDateTime(timezone=False), server_default=UTCNow())
    updated_at = mapped_column(UTCDateTime(timezone=False), onupdate=UTCNow())
