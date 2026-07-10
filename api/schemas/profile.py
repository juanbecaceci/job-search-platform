"""Profile response shapes (§4.8)."""

from __future__ import annotations

from datetime import datetime

from api.schemas.common import ORMModel


class ProfileBasicsOut(ORMModel):
    full_name: str | None = None
    headline: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None


class ProfileSectionOut(ORMModel):
    id: int
    slug: str
    title: str
    content_md: str | None = None
    sort_order: int
    updated_by: str
    updated_at: datetime | None = None
