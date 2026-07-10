"""Chat + pending-change response/request shapes (§4.6, §4.7)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from api.schemas.common import ORMModel


class ThreadCreate(BaseModel):
    title: str | None = None
    module: str
    entity_type: str | None = None
    entity_id: str | None = None


class ChatThreadOut(ORMModel):
    id: int
    title: str | None = None
    module: str
    entity_type: str | None = None
    entity_id: str | None = None
    archived: bool = False


class ChatMessageOut(ORMModel):
    id: int
    thread_id: int
    role: str
    content: str | None = None
    attachments: list[dict[str, Any]] | None = None
    status: str
    pending_change_ids: list[int] | None = None
    created_at: datetime | None = None


class PendingChangeOut(ORMModel):
    id: int
    thread_id: int | None = None
    module: str
    change_type: str
    target_table: str | None = None
    target_id: str | None = None
    summary: str | None = None
    diff: Any = None
    status: str
    applied_at: datetime | None = None
    apply_error: str | None = None
    created_at: datetime | None = None
    edited_at: datetime | None = None


class RejectBody(BaseModel):
    reason: str | None = None


class ChangeEdit(BaseModel):
    """User rewrite of a still-pending proposal (`PATCH /changes/{id}`).

    `diff` replaces the proposal wholesale — the applier's field whitelists
    still police what it's allowed to contain, so an edit can't reach anywhere
    the agent's original couldn't.
    """

    diff: Any
    summary: str | None = None
