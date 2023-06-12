"""Database models for storage component."""
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for database models."""


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
    created_at = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),  # pylint: disable=not-callable
    )
    updated_at = mapped_column(
        DateTime(timezone=False),
        onupdate=func.now(),  # pylint: disable=not-callable
    )
