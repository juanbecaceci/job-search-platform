"""Versioned scoring configuration (PLATFORM_SPEC.md §4.10).

One active version at a time (`is_active`). `salary_gate`, `categories`, and
`criteria` are stored as JSON blobs — their internal shape is validated at the
service layer (weights must sum to 1.0; category ranges must cover 0–100 with
no gaps/overlaps).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class ScoringConfig(Base):
    __tablename__ = "scoring_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # { floor_usd_month, evaluation_basis, unpublished_status }
    salary_gate: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    score_threshold_auto_discard: Mapped[int] = mapped_column(
        Integer, default=45, nullable=False
    )
    scale_max: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    # [{ id, min_score, max_score, recommended_action }]
    categories: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    # [{ id, name, weight, scale, description, hints }]
    criteria: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )

    created_by: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
