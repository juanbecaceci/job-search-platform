"""Declarative base and shared column mixins.

All ORM models inherit from ``Base`` so a single ``Base.metadata`` sees every
table (that's what Alembic autogenerate and ``create_all`` walk). Timestamps
are stored timezone-aware and defaulted at the DB level so rows written outside
the ORM (e.g. the migration script's bulk upserts) still get them.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for every ORM model in the app."""


class TimestampMixin:
    """`created_at` / `updated_at`, UTC, maintained by the DB.

    ``server_default``/``onupdate`` mean inserts and updates get correct
    timestamps even when rows are written via Core (bulk upserts in the Sheets
    migration) rather than through the ORM unit of work.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
