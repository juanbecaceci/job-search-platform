"""Company, memory, settings, dashboard, and analytics response shapes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from api.schemas.common import ORMModel
from api.schemas.position import PositionCard


class JobOut(ORMModel):
    id: str
    type: str
    status: str
    progress: float
    progress_message: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class CompanyOut(ORMModel):
    id: int
    name: str
    industry: str | None = None
    size: str | None = None
    website: str | None = None
    research_md: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ModuleMemoryOut(ORMModel):
    module: str
    content_md: str | None = None
    updated_by: str
    updated_at: datetime | None = None


# ─── dashboard & analytics ───────────────────────────────────


class SourceSummary(BaseModel):
    source: str
    found: int
    avg_score: float | None = None


class DashboardSummary(BaseModel):
    positions_found: int
    positions_evaluated: int
    avg_score: float | None = None
    searches_run: int
    by_source: list[SourceSummary] = []
    top_positions: list[PositionCard] = []


class SourceEffectiveness(BaseModel):
    source: str
    discovered: int
    avg_score: float | None = None
    applied: int
    interviews: int
    offers: int


class Funnel(BaseModel):
    discovered: int
    applied: int
    responded: int
    interviews: int
    offers: int
    accepted: int


class StaleItem(BaseModel):
    position: PositionCard
    days_stale: int
    suggested_action: str  # "follow_up" | "mark_ghosted"
