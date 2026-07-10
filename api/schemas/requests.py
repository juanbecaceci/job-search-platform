"""Request bodies for write endpoints (Stage 3, Stage 5 position-detail actions)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class SearchCreate(BaseModel):
    name: str
    sources: list[str] = []
    keywords: list[str] = []
    posted_within_days: int | None = None
    markets: list[str] = []


class PositionCreate(BaseModel):
    """Manual position intake (POST /positions)."""

    role: str
    company: str | None = None
    source: str = "manual"
    url: str | None = None
    location: str | None = None
    remote: str | None = None
    tipo: str | None = None
    track: str | None = None
    salary_raw: str | None = None
    description: str | None = None
    tags: list[str] = []
    notes: str | None = None


class PositionPatch(BaseModel):
    """Partial field edits (PATCH /positions/{id}). Only provided fields change."""

    role: str | None = None
    url: str | None = None
    location: str | None = None
    remote: str | None = None
    tipo: str | None = None
    track: str | None = None
    salary_raw: str | None = None
    salary_min_usd_month: int | None = None
    salary_max_usd_month: int | None = None
    description: str | None = None
    tags: list[str] | None = None
    notes: str | None = None


class StatusChange(BaseModel):
    status: str
    note: str | None = None


class EvaluateBatchRequest(BaseModel):
    """Body for POST /positions/evaluate — bulk (re-)evaluate."""

    position_ids: list[str] = Field(..., min_length=1)


class SearchRunAccepted(BaseModel):
    job_id: str
    search_run_id: int


class JobAccepted(BaseModel):
    """Generic 202 response for job-kickoff endpoints that don't pre-create a row."""

    job_id: str


class DocumentGenerateRequest(BaseModel):
    kind: str  # "cv" | "cover_letter"
    instructions: str | None = None


class DocumentUpdate(BaseModel):
    content_md: str


class ApplicationCreate(BaseModel):
    date_applied: date | None = None
    applied_via: str | None = None
    contact: str | None = None
    cv_document_id: int | None = None
    cover_letter_document_id: int | None = None
    notes: str | None = None


class ApplicationPatch(BaseModel):
    """Partial field edits (PATCH /applications/{id}). Only provided fields change."""

    date_applied: date | None = None
    applied_via: str | None = None
    contact: str | None = None
    response_date: date | None = None
    interview_date: date | None = None
    outcome: str | None = None
    follow_up_due: date | None = None
    cv_document_id: int | None = None
    cover_letter_document_id: int | None = None
    notes: str | None = None
