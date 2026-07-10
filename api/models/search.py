"""Search config, its runs, the run↔position join, and the async Job record.

PLATFORM_SPEC.md §4.4 (Search) / §4.5 (Job).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
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
from api.models.enums import JobStatus, SearchStatus

if TYPE_CHECKING:
    from api.models.position import Position


class Search(Base, TimestampMixin):
    __tablename__ = "searches"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    sources: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    posted_within_days: Mapped[int | None] = mapped_column(Integer)
    markets: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), default=SearchStatus.DRAFT.value, nullable=False, index=True
    )
    # Persisted aggregate metrics (shown in the searches list without recompute).
    total_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_new: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_evaluated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_score: Mapped[float | None] = mapped_column(Float)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    positions: Mapped[list["Position"]] = relationship(back_populates="search")
    runs: Mapped[list["SearchRun"]] = relationship(
        back_populates="search",
        cascade="all, delete-orphan",
        order_by="SearchRun.created_at",
    )


class SearchRun(Base):
    """One execution of a search (PLATFORM_SPEC.md §4.4 `runs[]`)."""

    __tablename__ = "search_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    search_id: Mapped[int] = mapped_column(
        ForeignKey("searches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The async Job that carried this run (nullable until dispatched / for
    # migrated historical runs that never had a job).
    job_id: Mapped[str | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Per-source counters: {source: {fetched, new, duplicates, errors}}.
    stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    search: Mapped["Search"] = relationship(back_populates="runs")
    job: Mapped["Job | None"] = relationship(back_populates="search_run")
    position_links: Mapped[list["SearchRunPosition"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class SearchRunPosition(Base):
    """Association: which positions a run surfaced, and whether new that run."""

    __tablename__ = "search_run_positions"

    search_run_id: Mapped[int] = mapped_column(
        ForeignKey("search_runs.id", ondelete="CASCADE"), primary_key=True
    )
    position_id: Mapped[str] = mapped_column(
        ForeignKey("positions.id", ondelete="CASCADE"), primary_key=True
    )
    source: Mapped[str | None] = mapped_column(String(40))  # board it came from this run
    is_new: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    run: Mapped["SearchRun"] = relationship(back_populates="position_links")
    position: Mapped["Position"] = relationship(back_populates="run_links")


class Job(Base):
    """Async work record driven by the JobRunner (PLATFORM_SPEC.md §4.5)."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # uuid4
    type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), default=JobStatus.QUEUED.value, nullable=False, index=True
    )
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    progress_message: Mapped[str | None] = mapped_column(String(500))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    search_run: Mapped["SearchRun | None"] = relationship(back_populates="job")
