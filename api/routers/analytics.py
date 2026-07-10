"""Analytics endpoints: source effectiveness, funnel, stale list (§5).

Progress metrics are approximated from a position's *current* status: since
migrated data carries only the latest status (not full history), a position is
counted as having "reached" a stage when its current pipeline index is at or
past that stage. Terminal states (Rejected/Withdrawn/Ghosted) have no pipeline
index and so aren't counted as having reached a forward stage.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from api.db.engine import get_session
from api.models import Position
from api.models.enums import PIPELINE_ORDER, TERMINAL_STATUSES, PositionStatus
from api.schemas.misc import Funnel, SourceEffectiveness, StaleItem
from api.schemas.position import PositionCard

router = APIRouter(prefix="/analytics", tags=["analytics"])

_TERMINAL = {s.value for s in TERMINAL_STATUSES}
_ORDER_INDEX = {s.value: i for i, s in enumerate(PIPELINE_ORDER)}


def _at_or_beyond(status_value: str) -> set[str]:
    """Statuses whose pipeline index is >= the given status's index."""
    threshold = _ORDER_INDEX[status_value]
    return {s.value for s in PIPELINE_ORDER if _ORDER_INDEX[s.value] >= threshold}


def _resolve_range(from_: date | None, to: date | None) -> tuple[date, date]:
    to = to or date.today()
    from_ = from_ or (to - timedelta(days=30))
    return from_, to


@router.get("/sources", response_model=list[SourceEffectiveness])
def source_effectiveness(
    session: Session = Depends(get_session),
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
) -> list[SourceEffectiveness]:
    start, end = _resolve_range(from_, to)
    positions = session.scalars(
        select(Position).where(
            Position.date_discovered.is_not(None),
            Position.date_discovered >= start,
            Position.date_discovered <= end,
        )
    ).all()

    applied = _at_or_beyond(PositionStatus.APPLIED.value)
    interview = _at_or_beyond(PositionStatus.INTERVIEW_SCHEDULED.value)
    offers = _at_or_beyond(PositionStatus.OFFER_RECEIVED.value)

    agg: dict[str, dict] = {}
    for p in positions:
        bucket = agg.setdefault(
            p.source or "(none)",
            {"discovered": 0, "scores": [], "applied": 0, "interviews": 0, "offers": 0},
        )
        bucket["discovered"] += 1
        if p.score is not None:
            bucket["scores"].append(p.score)
        if p.status in applied:
            bucket["applied"] += 1
        if p.status in interview:
            bucket["interviews"] += 1
        if p.status in offers:
            bucket["offers"] += 1

    result = [
        SourceEffectiveness(
            source=source,
            discovered=b["discovered"],
            avg_score=round(sum(b["scores"]) / len(b["scores"]), 2) if b["scores"] else None,
            applied=b["applied"],
            interviews=b["interviews"],
            offers=b["offers"],
        )
        for source, b in agg.items()
    ]
    result.sort(key=lambda r: (-r.discovered, r.source))
    return result


@router.get("/funnel", response_model=Funnel)
def funnel(
    session: Session = Depends(get_session),
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
) -> Funnel:
    start, end = _resolve_range(from_, to)

    def count_at(status_value: str) -> int:
        return session.scalar(
            select(func.count())
            .select_from(Position)
            .where(
                Position.date_discovered.is_not(None),
                Position.date_discovered >= start,
                Position.date_discovered <= end,
                Position.status.in_(_at_or_beyond(status_value)),
            )
        ) or 0

    discovered = session.scalar(
        select(func.count())
        .select_from(Position)
        .where(
            Position.date_discovered.is_not(None),
            Position.date_discovered >= start,
            Position.date_discovered <= end,
        )
    ) or 0
    accepted = session.scalar(
        select(func.count())
        .select_from(Position)
        .where(
            Position.date_discovered.is_not(None),
            Position.date_discovered >= start,
            Position.date_discovered <= end,
            Position.status == PositionStatus.ACCEPTED.value,
        )
    ) or 0

    return Funnel(
        discovered=discovered,
        applied=count_at(PositionStatus.APPLIED.value),
        responded=count_at(PositionStatus.ACKNOWLEDGED.value),
        interviews=count_at(PositionStatus.INTERVIEW_SCHEDULED.value),
        offers=count_at(PositionStatus.OFFER_RECEIVED.value),
        accepted=accepted,
    )


# Statuses that are "waiting on the employer" and can go stale.
_WAITING = {
    PositionStatus.APPLIED.value,
    PositionStatus.ACKNOWLEDGED.value,
    PositionStatus.INTERVIEW_SCHEDULED.value,
    PositionStatus.INTERVIEWING.value,
}


@router.get("/stale", response_model=list[StaleItem])
def stale(
    session: Session = Depends(get_session),
    days: int = Query(14, ge=1),
) -> list[StaleItem]:
    """Waiting-on-employer positions with no activity for `days`+ days."""
    today = date.today()
    positions = session.scalars(
        select(Position)
        .options(selectinload(Position.company))
        .where(Position.status.in_(_WAITING))
    ).all()

    items: list[StaleItem] = []
    for p in positions:
        last_activity = (p.updated_at.date() if p.updated_at else p.date_discovered) or today
        days_stale = (today - last_activity).days
        if days_stale < days:
            continue
        # Long silence after applying → likely ghosted; otherwise nudge.
        ghosted = (
            p.status in {PositionStatus.APPLIED.value, PositionStatus.ACKNOWLEDGED.value}
            and days_stale >= days * 2
        )
        items.append(
            StaleItem(
                position=PositionCard.model_validate(p),
                days_stale=days_stale,
                suggested_action="mark_ghosted" if ghosted else "follow_up",
            )
        )
    items.sort(key=lambda i: i.days_stale, reverse=True)
    return items
