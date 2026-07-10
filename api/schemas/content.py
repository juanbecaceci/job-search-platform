"""Template + scoring config response shapes (§4.9, §4.10)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from api.schemas.common import ORMModel


class TemplateVersionOut(ORMModel):
    id: int
    version: int
    is_active: bool
    content_md: str | None = None
    change_note: str | None = None
    created_by: str
    created_at: datetime | None = None


class TemplateOut(BaseModel):
    """Template with its active version nested (§4.9)."""

    id: int
    kind: str
    name: str
    active_version: TemplateVersionOut | None = None


class ScoringConfigOut(ORMModel):
    version: int
    is_active: bool
    salary_gate: dict[str, Any] = {}
    score_threshold_auto_discard: int
    scale_max: int
    categories: list[dict[str, Any]] = []
    criteria: list[dict[str, Any]] = []
    created_by: str
    created_at: datetime | None = None
