"""Read endpoints for searches (GET only in Stage 2)."""

from __future__ import annotations

import json
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from api.config import CONFIG_DIR
from api.db.engine import get_session
from api.deps import get_runner
from api.jobs import JobRunner
from api.models import Position, Search, SearchRun
from api.models.enums import AsyncJobType, SearchStatus
from api.schemas.common import Page
from api.schemas.position import PositionCard
from api.schemas.requests import SearchCreate, SearchRunAccepted
from api.schemas.search import (
    SearchDefaults,
    SearchDetail,
    SearchOut,
    SearchRunOut,
    SourceBucket,
    SourceDefault,
)

router = APIRouter(prefix="/searches", tags=["searches"])


@lru_cache(maxsize=1)
def _job_sites() -> dict:
    path = CONFIG_DIR / "job_sites.json"
    return json.loads(path.read_text("utf-8")) if path.exists() else {}


@router.get("", response_model=Page[SearchOut])
def list_searches(
    session: Session = Depends(get_session),
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Page[SearchOut]:
    stmt = select(Search)
    if status:
        stmt = stmt.where(Search.status == status)
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(Search.last_run_at.desc().nulls_last(), Search.id.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    items = [SearchOut.model_validate(s) for s in session.scalars(stmt).all()]
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=SearchOut, status_code=status.HTTP_201_CREATED)
def create_search(
    body: SearchCreate, session: Session = Depends(get_session)
) -> SearchOut:
    """Create a search as a draft (run it later with POST /searches/{id}/run)."""
    search = Search(
        name=body.name,
        sources=body.sources,
        keywords=body.keywords,
        posted_within_days=body.posted_within_days,
        markets=body.markets,
        status=SearchStatus.DRAFT.value,
    )
    session.add(search)
    session.commit()
    return SearchOut.model_validate(search)


@router.post(
    "/{search_id}/run",
    response_model=SearchRunAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def run_search(
    search_id: int,
    session: Session = Depends(get_session),
    runner: JobRunner = Depends(get_runner),
) -> SearchRunAccepted:
    """Dispatch an async search_run job; returns the job + pre-created run id."""
    search = session.get(Search, search_id)
    if search is None:
        raise HTTPException(status_code=404, detail="Search not found")
    if not search.keywords:
        raise HTTPException(status_code=422, detail="Search has no keywords")

    # Pre-create the run row so we can return its id synchronously; the job
    # attaches to it and fills in stats/started_at.
    run = SearchRun(search_id=search.id, stats={})
    session.add(run)
    session.commit()

    job_id = runner.submit(
        AsyncJobType.SEARCH_RUN.value,
        {"search_id": search.id, "search_run_id": run.id},
    )
    return SearchRunAccepted(job_id=job_id, search_run_id=run.id)


@router.delete("/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_search(search_id: int, session: Session = Depends(get_session)) -> Response:
    """Delete a search — drafts only."""
    search = session.get(Search, search_id)
    if search is None:
        raise HTTPException(status_code=404, detail="Search not found")
    if search.status != SearchStatus.DRAFT.value:
        raise HTTPException(status_code=409, detail="Only draft searches can be deleted")
    session.delete(search)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/defaults", response_model=SearchDefaults)
def search_defaults() -> SearchDefaults:
    """Source toggles + keyword groups for the new-search wizard."""
    data = _job_sites()
    sources = [
        SourceDefault(
            id=key,
            label=key.replace("_", " ").title(),
            enabled_default=bool(site.get("enabled", True)),
        )
        for key, site in data.get("sites", {}).items()
    ]
    keyword_groups = data.get("search_keywords_by_role", {})
    return SearchDefaults(sources=sources, keyword_groups=keyword_groups)


@router.get("/{search_id}", response_model=SearchDetail)
def get_search(search_id: int, session: Session = Depends(get_session)) -> SearchDetail:
    search = session.get(Search, search_id, options=[selectinload(Search.runs)])
    if search is None:
        raise HTTPException(status_code=404, detail="Search not found")

    positions = session.scalars(
        select(Position)
        .options(selectinload(Position.company))
        .where(Position.search_id == search_id)
    ).all()

    buckets: dict[str, list[PositionCard]] = {}
    for p in positions:
        buckets.setdefault(p.source, []).append(PositionCard.model_validate(p))

    base = SearchOut.model_validate(search).model_dump()
    return SearchDetail(
        **base,
        runs=[SearchRunOut.model_validate(r) for r in search.runs],
        positions_by_source=[
            SourceBucket(source=src, positions=cards) for src, cards in buckets.items()
        ],
    )
