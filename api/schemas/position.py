"""Position, event, application, and document response shapes (§4.1–4.3, 4.11)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel

from api.schemas.common import ORMModel


class CompanyRef(ORMModel):
    """Compact company reference nested inside a position."""

    id: int
    name: str
    industry: str | None = None
    size: str | None = None
    website: str | None = None


class PositionCard(ORMModel):
    """Compact card for board columns / top lists / the positions table."""

    id: str
    role: str
    company: CompanyRef | None = None
    source: str
    status: str
    score: float | None = None
    score_category: str | None = None
    rank: int | None = None
    salary_raw: str | None = None
    url: str | None = None
    track: str | None = None
    # The positions table has a "Discovered" column; without this it rendered an
    # em dash on every row regardless of the data.
    date_discovered: date | None = None


class PositionOut(ORMModel):
    """Full position detail (§4.1)."""

    id: str
    company: CompanyRef | None = None
    search_id: int | None = None
    source: str
    sources: list[str] = []
    tipo: str | None = None
    track: str | None = None
    role: str
    url: str | None = None
    location: str | None = None
    remote: str | None = None
    salary_raw: str | None = None
    salary_min_usd_month: int | None = None
    salary_max_usd_month: int | None = None
    salary_gate: str | None = None
    date_posted: date | None = None
    date_discovered: date | None = None
    score: float | None = None
    score_category: str | None = None
    rank: int | None = None
    scoring_config_version: int | None = None
    evaluation: dict[str, Any] | None = None
    summary: str | None = None
    recommended_action: str | None = None
    status: str
    description: str | None = None
    tags: list[str] = []
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PositionEventOut(ORMModel):
    id: int
    position_id: str
    event_type: str
    from_value: str | None = None
    to_value: str | None = None
    payload: dict[str, Any] | None = None
    actor: str
    created_at: datetime | None = None


class ApplicationOut(ORMModel):
    id: int
    position_id: str
    cv_document_id: int | None = None
    cover_letter_document_id: int | None = None
    date_applied: date | None = None
    applied_via: str | None = None
    contact: str | None = None
    response_date: date | None = None
    interview_date: date | None = None
    outcome: str | None = None
    follow_up_due: date | None = None
    notes: str | None = None


class DocumentOut(ORMModel):
    id: int
    position_id: str | None = None
    company_id: int | None = None
    kind: str
    version: int
    content_md: str | None = None
    pdf_available: bool = False
    docx_available: bool = False
    drive_url: str | None = None
    status: str
    created_by: str
    created_at: datetime | None = None


class PositionDetail(BaseModel):
    """Aggregate returned by GET /positions/{id} (§5)."""

    position: PositionOut
    events: list[PositionEventOut] = []
    application: ApplicationOut | None = None
    documents: list[DocumentOut] = []
