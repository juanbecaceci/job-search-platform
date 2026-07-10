"""Dashboard summary endpoint (§5). Default window: last 7 days."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from api.db.engine import get_session
from api.models import Position, Search
from api.models.enums import TERMINAL_STATUSES
from api.schemas.misc import DashboardSummary, SourceSummary
from api.schemas.position import PositionCard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_TERMINAL = {s.value for s in TERMINAL_STATUSES}


def _resolve_range(from_: date | None, to: date | None) -> tuple[date, date]:
    to = to or date.today()
    from_ = from_ or (to - timedelta(days=7))
    return from_, to


@router.get("/summary", response_model=DashboardSummary)
def summary(
    session: Session = Depends(get_session),
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
) -> DashboardSummary:
    # `from` is a Python keyword, so the param is aliased from `from_`.
    start, end = _resolve_range(from_, to)
    in_range = (
        Position.date_discovered.is_not(None),
        Position.date_discovered >= start,
        Position.date_discovered <= end,
    )

    positions_found = session.scalar(
        select(func.count()).select_from(Position).where(*in_range)
    ) or 0
    positions_evaluated = session.scalar(
        select(func.count())
        .select_from(Position)
        .where(*in_range, Position.score.is_not(None))
    ) or 0
    avg_score = session.scalar(
        select(func.avg(Position.score)).where(*in_range, Position.score.is_not(None))
    )
    searches_run = session.scalar(
        select(func.count())
        .select_from(Search)
        .where(
            Search.last_run_at.is_not(None),
            func.date(Search.last_run_at) >= start,
            func.date(Search.last_run_at) <= end,
        )
    ) or 0

    by_source_rows = session.execute(
        select(
            Position.source,
            func.count().label("found"),
            func.avg(Position.score).label("avg_score"),
        )
        .where(*in_range)
        .group_by(Position.source)
        .order_by(func.count().desc())
    ).all()
    by_source = [
        SourceSummary(
            source=row.source or "(none)",
            found=row.found,
            avg_score=round(row.avg_score, 2) if row.avg_score is not None else None,
        )
        for row in by_source_rows
    ]

    top = session.scalars(
        select(Position)
        .options(selectinload(Position.company))
        .where(Position.status.not_in(_TERMINAL), Position.score.is_not(None))
        .order_by(Position.score.desc(), Position.rank.asc())
        .limit(5)
    ).all()

    return DashboardSummary(
        positions_found=positions_found,
        positions_evaluated=positions_evaluated,
        avg_score=round(avg_score, 2) if avg_score is not None else None,
        searches_run=searches_run,
        by_source=by_source,
        top_positions=[PositionCard.model_validate(p) for p in top],
    )
