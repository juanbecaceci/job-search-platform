"""Company — deduplicated employer records referenced by positions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from api.models.position import Position


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    industry: Mapped[str | None] = mapped_column(String(120))
    size: Mapped[str | None] = mapped_column(String(40))
    website: Mapped[str | None] = mapped_column(String(500))
    # Agent-produced company research (POST /companies/{id}/research). The same
    # text is also mirrored into a `company_research` document; this column is
    # the quick-access copy shown on the company detail view.
    research_md: Mapped[str | None] = mapped_column(Text)

    positions: Mapped[list["Position"]] = relationship(back_populates="company")
