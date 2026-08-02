"""Search list/detail response shapes (§4.4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from api.schemas.common import ORMModel
from api.schemas.position import PositionCard


class SearchOut(ORMModel):
    id: int
    name: str
    keywords: list[str] = []
    sources: list[str] = []
    posted_within_days: int | None = None
    markets: list[str] = []
    status: str
    total_found: int = 0
    total_new: int = 0
    total_evaluated: int = 0
    avg_score: float | None = None
    last_run_at: datetime | None = None


class SearchRunOut(ORMModel):
    id: int
    job_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    stats: dict[str, Any] = {}


class SourceBucket(BaseModel):
    source: str
    positions: list[PositionCard] = []


class SearchDetail(SearchOut):
    """Full detail incl. runs and positions grouped by source (§5)."""

    runs: list[SearchRunOut] = []
    positions_by_source: list[SourceBucket] = []


class SourceDefault(BaseModel):
    id: str
    label: str
    enabled_default: bool


class RegionDefault(BaseModel):
    id: str
    label: str


class SearchDefaults(BaseModel):
    sources: list[SourceDefault]
    keyword_groups: dict[str, list[str]]
    # Geography choices for `searches.markets`, served from core's REGIONS so
    # the wizard never keeps its own copy of the list.
    regions: list[RegionDefault] = []
    # What an empty `markets` resolves to (`TARGET_REGION`), so the UI can say
    # "defaults to X" instead of implying no filtering.
    default_region: str = "worldwide"
