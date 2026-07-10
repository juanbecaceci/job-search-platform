"""Chat threads/messages, HITL pending changes, and per-module memory.

PLATFORM_SPEC.md §4.6 (Pending change) / §4.7 (Chat) / §4.12 (Module memory).

The pending-change flow is structural (DECISIONS.md #6): the agent never writes
to domain tables — it emits proposed changes that land here as `pending`, and
only ChangeApplier (on explicit approval) applies them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.base import Base, TimestampMixin
from api.models.enums import PendingChangeStatus


class ChatThread(Base, TimestampMixin):
    __tablename__ = "chat_threads"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str | None] = mapped_column(String(255))
    module: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # Optional entity binding (e.g. a specific position the chat is about).
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(255))
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Agent CLI conversation id, for `claude -p --resume` continuity (Stage 4).
    adapter_thread_id: Mapped[str | None] = mapped_column(String(255))

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )
    pending_changes: Mapped[list["PendingChange"]] = relationship(
        back_populates="thread"
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(
        ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant | system
    content: Mapped[str | None] = mapped_column(Text)
    attachments: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="complete", nullable=False)
    # IDs of pending_changes this (assistant) message proposed.
    pending_change_ids: Mapped[list[int] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    thread: Mapped["ChatThread"] = relationship(back_populates="messages")


class PendingChange(Base, TimestampMixin):
    """A proposed, not-yet-applied diff awaiting user approval (§4.6)."""

    __tablename__ = "pending_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_threads.id", ondelete="SET NULL"), index=True
    )
    module: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    change_type: Mapped[str] = mapped_column(String(20), nullable=False)  # update|create|delete|action
    target_table: Mapped[str | None] = mapped_column(String(60))
    target_id: Mapped[str | None] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(Text)
    # For update/create/delete: a list of field diffs. For `action`:
    # {"action": "...", "payload": {...}} dispatched instead of written.
    diff: Mapped[Any] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=PendingChangeStatus.PENDING.value, nullable=False, index=True
    )
    # Set when applied/failed; carries the applier's error or result note.
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    apply_error: Mapped[str | None] = mapped_column(Text)
    # Set when the user rewrote the agent's proposed diff before approving
    # (PATCH /changes/{id}). Provenance matters: an applied change is otherwise
    # indistinguishable from the agent's own wording.
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    thread: Mapped["ChatThread | None"] = relationship(back_populates="pending_changes")


class ModuleMemory(Base):
    """Lessons-learned notes per module (§4.12). One row per module."""

    __tablename__ = "module_memories"

    module: Mapped[str] = mapped_column(String(20), primary_key=True)
    content_md: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[str] = mapped_column(String(20), default="agent", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
