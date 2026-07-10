"""Position (central entity), its event timeline, and the 1:1 Application.

PLATFORM_SPEC.md §4.1 / §4.2 / §4.3.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.base import Base, TimestampMixin
from api.models.enums import PositionStatus

if TYPE_CHECKING:
    from api.models.company import Company
    from api.models.content import Document
    from api.models.search import Search, SearchRunPosition


class Position(Base, TimestampMixin):
    __tablename__ = "positions"

    # Slug PK, e.g. "acme-automation-engineer-a1b2c3" (source + role + hash).
    id: Mapped[str] = mapped_column(String(255), primary_key=True)

    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    search_id: Mapped[int | None] = mapped_column(
        ForeignKey("searches.id", ondelete="SET NULL"), index=True
    )

    # Provenance. `source` is the primary/first source; `sources` is the full
    # list when the same role is discovered on multiple boards (dedup merge).
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    sources: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    # Stable identity used to dedupe across runs (Stage 3). Nullable for manual
    # intake; unique when present is enforced at the service layer, not the DB,
    # because legacy migrated rows may collide.
    dedupe_key: Mapped[str | None] = mapped_column(String(255), index=True)

    tipo: Mapped[str | None] = mapped_column(String(20))  # full-time | gig | freelance
    track: Mapped[str | None] = mapped_column(String(20))

    role: Mapped[str] = mapped_column(String(300), nullable=False)
    url: Mapped[str | None] = mapped_column(String(1000))
    location: Mapped[str | None] = mapped_column(String(255))
    remote: Mapped[str | None] = mapped_column(String(40))

    salary_raw: Mapped[str | None] = mapped_column(String(255))
    salary_min_usd_month: Mapped[int | None] = mapped_column(Integer)
    salary_max_usd_month: Mapped[int | None] = mapped_column(Integer)
    salary_gate: Mapped[str | None] = mapped_column(String(20))

    date_posted: Mapped[date | None] = mapped_column(Date)
    date_discovered: Mapped[date | None] = mapped_column(Date)

    # Scoring outputs. Null until evaluated.
    score: Mapped[float | None] = mapped_column(Float)
    score_category: Mapped[str | None] = mapped_column(String(20))
    rank: Mapped[int | None] = mapped_column(Integer)
    scoring_config_version: Mapped[int | None] = mapped_column(Integer)
    # Per-criterion breakdown: {criterion_id: {score, weight, rationale}}.
    evaluation: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    summary: Mapped[str | None] = mapped_column(Text)
    recommended_action: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        String(40), default=PositionStatus.DISCOVERED.value, nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(Text)  # capped at 3000 chars upstream
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    company: Mapped["Company | None"] = relationship(back_populates="positions")
    search: Mapped["Search | None"] = relationship(back_populates="positions")
    events: Mapped[list["PositionEvent"]] = relationship(
        back_populates="position",
        cascade="all, delete-orphan",
        order_by="PositionEvent.created_at",
    )
    application: Mapped["Application | None"] = relationship(
        back_populates="position", cascade="all, delete-orphan", uselist=False
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="position",
        cascade="all, delete-orphan",
        foreign_keys="Document.position_id",
    )
    run_links: Mapped[list["SearchRunPosition"]] = relationship(
        back_populates="position", cascade="all, delete-orphan"
    )


class PositionEvent(Base):
    """Append-only history timeline for a position (PLATFORM_SPEC.md §4.2)."""

    __tablename__ = "position_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    position_id: Mapped[str] = mapped_column(
        ForeignKey("positions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    from_value: Mapped[str | None] = mapped_column(String(255))
    to_value: Mapped[str | None] = mapped_column(String(255))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    actor: Mapped[str] = mapped_column(String(20), nullable=False)  # user | agent | system
    # Append-only, so `created_at` only — no `updated_at` (not a TimestampMixin).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    position: Mapped["Position"] = relationship(back_populates="events")


class Application(Base):
    """1:1 application record for a position (PLATFORM_SPEC.md §4.3)."""

    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    position_id: Mapped[str] = mapped_column(
        ForeignKey("positions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # Plain FKs to documents.id — no back-relationship needed and this avoids a
    # circular dependency (documents already point at positions).
    cv_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    cover_letter_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )

    date_applied: Mapped[date | None] = mapped_column(Date)
    applied_via: Mapped[str | None] = mapped_column(String(120))
    contact: Mapped[str | None] = mapped_column(String(255))
    response_date: Mapped[date | None] = mapped_column(Date)
    interview_date: Mapped[date | None] = mapped_column(Date)
    outcome: Mapped[str | None] = mapped_column(String(120))
    follow_up_due: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    position: Mapped["Position"] = relationship(back_populates="application")
