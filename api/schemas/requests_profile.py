"""Request bodies for direct (user-driven) profile edits.

These are the user editing their own profile through a form — not agent output,
so they don't pass through `pending_changes`/`ChangeApplier` (DECISIONS #6 gates
the *agent's* writes; asking someone to approve their own typing would be
theatre). Agent-proposed profile changes still go through the tray.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ProfileBasicsUpdate(BaseModel):
    full_name: str | None = None
    headline: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None


class ProfileSectionCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=255)
    content_md: str | None = None
    sort_order: int | None = None

    @field_validator("slug")
    @classmethod
    def _normalize_slug(cls, v: str) -> str:
        return v.strip().lower().replace(" ", "_")


class ProfileSectionUpdate(BaseModel):
    """All fields optional — a PATCH-shaped PUT, so the UI can save one field."""

    slug: str | None = Field(default=None, min_length=1, max_length=80)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content_md: str | None = None
    sort_order: int | None = None

    @field_validator("slug")
    @classmethod
    def _normalize_slug(cls, v: str | None) -> str | None:
        return v.strip().lower().replace(" ", "_") if v else v


class ProfileSectionReorder(BaseModel):
    """Full ordered list of section ids — one call, no intermediate bad states."""

    section_ids: list[int] = Field(min_length=1)
