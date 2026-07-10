"""Versioned templates and generated documents.

PLATFORM_SPEC.md §4.9 (Template) / §4.11 (Document).

Note on the active version: rather than a `templates.active_version_id` FK
pointing back at `template_versions` (which, with `template_versions.template_id`
pointing at `templates`, is a circular FK SQLite can't add via ALTER), the
active version is flagged with `TemplateVersion.is_active`. The API composes the
nested `active_version` shape from the flagged row. `ScoringConfig` uses the
same `is_active` pattern for consistency.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from api.models.position import Position


class Template(Base, TimestampMixin):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # cv | cover_letter
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    versions: Mapped[list["TemplateVersion"]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="TemplateVersion.version",
    )


class TemplateVersion(Base):
    __tablename__ = "template_versions"
    __table_args__ = (
        UniqueConstraint("template_id", "version", name="uq_template_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    content_md: Mapped[str | None] = mapped_column(Text)
    change_note: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    template: Mapped["Template"] = relationship(back_populates="versions")


class Document(Base, TimestampMixin):
    """A generated CV / cover letter / company research doc (§4.11).

    Position-scoped for cv/cover_letter; company-scoped (position_id null) for
    company_research. Binary artifacts live under `data/` — the DB stores only
    their relative paths and availability flags.
    """

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    position_id: Mapped[str | None] = mapped_column(
        ForeignKey("positions.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # cv | cover_letter | company_research
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    content_md: Mapped[str | None] = mapped_column(Text)

    pdf_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    docx_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pdf_path: Mapped[str | None] = mapped_column(String(1000))  # relative to data/
    docx_path: Mapped[str | None] = mapped_column(String(1000))
    drive_url: Mapped[str | None] = mapped_column(String(1000))

    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    created_by: Mapped[str] = mapped_column(String(20), default="agent", nullable=False)

    position: Mapped["Position | None"] = relationship(
        back_populates="documents", foreign_keys=[position_id]
    )
