"""Profile basics (single record) and ordered profile sections.

PLATFORM_SPEC.md §4.8.
"""

from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base, TimestampMixin


class ProfileBasics(Base, TimestampMixin):
    """Single-row table (id is pinned to 1 by the seed/migration)."""

    __tablename__ = "profile_basics"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    full_name: Mapped[str | None] = mapped_column(String(255))
    headline: Mapped[str | None] = mapped_column(String(500))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(60))
    location: Mapped[str | None] = mapped_column(String(255))
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    portfolio_url: Mapped[str | None] = mapped_column(String(500))


class ProfileSection(Base, TimestampMixin):
    """A free-form CV/profile section (experience, skills, …), user-ordered.

    The API response shape (§4.8) exposes only `updated_at`; `created_at` from
    the mixin is harmless and just isn't serialized.
    """

    __tablename__ = "profile_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_md: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_by: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
