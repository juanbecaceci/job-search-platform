"""Read endpoints for positions (GET only in Stage 2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from api.db.engine import get_session
from api.deps import get_runner
from api.jobs import JobRunner
from api.models import Application, Company, Position, PositionEvent
from api.models.enums import (
    PIPELINE_ORDER,
    TERMINAL_STATUSES,
    Actor,
    AsyncJobType,
    PositionEventType,
    PositionStatus,
)
from api.schemas.common import Page
from api.schemas.position import (
    ApplicationOut,
    DocumentOut,
    PositionCard,
    PositionDetail,
    PositionEventOut,
    PositionOut,
)
from api.schemas.requests import (
    ApplicationCreate,
    DocumentGenerateRequest,
    EvaluateBatchRequest,
    JobAccepted,
    PositionCreate,
    PositionPatch,
    StatusChange,
)
from core.sheets_manager import make_position_id

router = APIRouter(prefix="/positions", tags=["positions"])
_VALID_DOC_KINDS = {"cv", "cover_letter"}

_TERMINAL = {s.value for s in TERMINAL_STATUSES}
_VALID_STATUS = {s.value for s in PositionStatus}


def _get_or_create_company(session: Session, name: str | None) -> Company | None:
    if not name or not name.strip():
        return None
    key = name.strip().lower()
    company = session.scalar(select(Company).where(func.lower(Company.name) == key))
    if company is None:
        company = Company(name=name.strip())
        session.add(company)
        session.flush()
    return company

_SORTS = {
    "score": (Position.score.desc(), Position.rank.asc()),
    "-score": (Position.score.asc(),),
    "rank": (Position.rank.asc(),),
    "date": (Position.date_discovered.desc(),),
    "-date": (Position.date_discovered.asc(),),
}


def _card(position: Position) -> PositionCard:
    return PositionCard.model_validate(position)


@router.get("", response_model=Page[PositionCard])
def list_positions(
    session: Session = Depends(get_session),
    status: str | None = None,
    source: str | None = None,
    search_id: int | None = None,
    track: str | None = None,
    min_score: float | None = None,
    q: str | None = None,
    sort: str = "score",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Page[PositionCard]:
    stmt = select(Position).options(selectinload(Position.company))

    if status:
        stmt = stmt.where(Position.status == status)
    if source:
        # match either the primary source or membership in the sources list.
        stmt = stmt.where(
            or_(Position.source == source, Position.sources.contains([source]))
        )
    if search_id is not None:
        stmt = stmt.where(Position.search_id == search_id)
    if track:
        stmt = stmt.where(Position.track == track)
    if min_score is not None:
        stmt = stmt.where(Position.score >= min_score)
    if q:
        like = f"%{q}%"
        stmt = stmt.outerjoin(Company).where(
            or_(Position.role.ilike(like), Company.name.ilike(like))
        )

    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    for clause in _SORTS.get(sort, _SORTS["score"]):
        stmt = stmt.order_by(clause)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    items = [_card(p) for p in session.scalars(stmt).unique().all()]
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/top", response_model=list[PositionCard])
def top_positions(
    session: Session = Depends(get_session),
    limit: int = Query(5, ge=1, le=50),
) -> list[PositionCard]:
    """Best-ranked positions, excluding terminal states."""
    stmt = (
        select(Position)
        .options(selectinload(Position.company))
        .where(Position.status.not_in(_TERMINAL))
        .where(Position.score.is_not(None))
        .order_by(Position.score.desc(), Position.rank.asc())
        .limit(limit)
    )
    return [_card(p) for p in session.scalars(stmt).unique().all()]


@router.get("/board")
def board(session: Session = Depends(get_session)) -> dict:
    """Kanban board: one column per pipeline status (terminal states last)."""
    stmt = select(Position).options(selectinload(Position.company))
    positions = session.scalars(stmt).unique().all()

    grouped: dict[str, list[PositionCard]] = {}
    for p in positions:
        grouped.setdefault(p.status, []).append(_card(p))

    ordered_statuses = [s.value for s in PIPELINE_ORDER] + [
        s.value for s in PositionStatus if s.value not in {x.value for x in PIPELINE_ORDER}
    ]
    columns = [
        {"status": st, "count": len(grouped.get(st, [])), "positions": grouped.get(st, [])}
        for st in ordered_statuses
    ]
    return {"columns": columns}


@router.get("/{position_id}", response_model=PositionDetail)
def get_position(position_id: str, session: Session = Depends(get_session)) -> PositionDetail:
    position = session.get(
        Position,
        position_id,
        options=[
            selectinload(Position.company),
            selectinload(Position.events),
            selectinload(Position.application),
            selectinload(Position.documents),
        ],
    )
    if position is None:
        raise HTTPException(status_code=404, detail="Position not found")

    return PositionDetail(
        position=PositionOut.model_validate(position),
        events=[PositionEventOut.model_validate(e) for e in position.events],
        application=(
            ApplicationOut.model_validate(position.application)
            if position.application
            else None
        ),
        documents=[DocumentOut.model_validate(d) for d in position.documents],
    )


@router.post("", response_model=PositionOut, status_code=status.HTTP_201_CREATED)
def create_position(
    body: PositionCreate, session: Session = Depends(get_session)
) -> PositionOut:
    """Manual position intake. Id is the company+role slug (dedupe-consistent)."""
    pid = make_position_id(body.company or "manual", body.role)
    if session.get(Position, pid) is not None:
        raise HTTPException(status_code=409, detail="A position with this company+role already exists")

    company = _get_or_create_company(session, body.company)
    position = Position(
        id=pid,
        company_id=company.id if company else None,
        source=body.source or "manual",
        sources=[body.source or "manual"],
        dedupe_key=pid,
        role=body.role,
        url=body.url,
        location=body.location,
        remote=body.remote,
        tipo=body.tipo,
        track=body.track,
        salary_raw=body.salary_raw,
        description=body.description,
        tags=body.tags,
        notes=body.notes,
        status=PositionStatus.DISCOVERED.value,
    )
    session.add(position)
    session.flush()
    session.add(
        PositionEvent(
            position_id=pid,
            event_type=PositionEventType.CREATED.value,
            to_value=PositionStatus.DISCOVERED.value,
            payload={"source": position.source, "via": "manual"},
            actor=Actor.USER.value,
        )
    )
    session.commit()
    session.refresh(position)
    return PositionOut.model_validate(position)


@router.patch("/{position_id}", response_model=PositionOut)
def patch_position(
    position_id: str, body: PositionPatch, session: Session = Depends(get_session)
) -> PositionOut:
    """Edit fields; logs a `field_update` event with the before/after values."""
    position = session.get(Position, position_id, options=[selectinload(Position.company)])
    if position is None:
        raise HTTPException(status_code=404, detail="Position not found")

    changes: dict[str, dict] = {}
    for field, new_value in body.model_dump(exclude_unset=True).items():
        old_value = getattr(position, field)
        if old_value != new_value:
            setattr(position, field, new_value)
            changes[field] = {"old": old_value, "new": new_value}

    if changes:
        session.add(
            PositionEvent(
                position_id=position_id,
                event_type=PositionEventType.FIELD_UPDATE.value,
                payload={"fields": changes},
                actor=Actor.USER.value,
            )
        )
    session.commit()
    session.refresh(position)
    return PositionOut.model_validate(position)


@router.post("/{position_id}/evaluate", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED)
def evaluate_position(
    position_id: str,
    session: Session = Depends(get_session),
    runner: JobRunner = Depends(get_runner),
) -> JobAccepted:
    """Re-evaluate one position against the active scoring config."""
    if session.get(Position, position_id) is None:
        raise HTTPException(status_code=404, detail="Position not found")
    job_id = runner.submit(AsyncJobType.EVALUATE_BATCH.value, {"position_ids": [position_id]})
    return JobAccepted(job_id=job_id)


@router.post("/evaluate", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED)
def evaluate_positions(
    body: EvaluateBatchRequest,
    session: Session = Depends(get_session),
    runner: JobRunner = Depends(get_runner),
) -> JobAccepted:
    """Bulk (re-)evaluate: one job scores every listed position against the
    active scoring config. Used for newly-found search results and for
    re-scoring existing positions after a scoring criteria change."""
    known = set(session.scalars(select(Position.id).where(Position.id.in_(body.position_ids))))
    if not known:
        raise HTTPException(status_code=404, detail="None of the given position_ids exist")
    job_id = runner.submit(AsyncJobType.EVALUATE_BATCH.value, {"position_ids": body.position_ids})
    return JobAccepted(job_id=job_id)


@router.post(
    "/{position_id}/documents/generate",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_document(
    position_id: str,
    body: DocumentGenerateRequest,
    session: Session = Depends(get_session),
    runner: JobRunner = Depends(get_runner),
) -> JobAccepted:
    """Agent drafts a CV/cover-letter Markdown source for this position."""
    if session.get(Position, position_id) is None:
        raise HTTPException(status_code=404, detail="Position not found")
    if body.kind not in _VALID_DOC_KINDS:
        raise HTTPException(status_code=422, detail=f"Invalid kind: {body.kind}")
    job_id = runner.submit(
        AsyncJobType.GENERATE_DOCUMENT.value,
        {"position_id": position_id, "kind": body.kind, "instructions": body.instructions},
    )
    return JobAccepted(job_id=job_id)


@router.post(
    "/{position_id}/application", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED
)
def create_application(
    position_id: str, body: ApplicationCreate, session: Session = Depends(get_session)
) -> ApplicationOut:
    """Log an application for this position (1:1 — 409 if one already exists)."""
    if session.get(Position, position_id) is None:
        raise HTTPException(status_code=404, detail="Position not found")
    if session.scalar(select(Application).where(Application.position_id == position_id)):
        raise HTTPException(status_code=409, detail="An application already exists for this position")

    application = Application(position_id=position_id, **body.model_dump())
    session.add(application)
    session.add(
        PositionEvent(
            position_id=position_id,
            event_type=PositionEventType.APPLICATION_UPDATE.value,
            payload={"action": "created"},
            actor=Actor.USER.value,
        )
    )
    session.commit()
    session.refresh(application)
    return ApplicationOut.model_validate(application)


@router.post("/{position_id}/status", response_model=PositionOut)
def change_status(
    position_id: str, body: StatusChange, session: Session = Depends(get_session)
) -> PositionOut:
    """Change pipeline status (validated); logs a `status_change` event."""
    if body.status not in _VALID_STATUS:
        raise HTTPException(status_code=422, detail=f"Invalid status: {body.status}")

    position = session.get(Position, position_id, options=[selectinload(Position.company)])
    if position is None:
        raise HTTPException(status_code=404, detail="Position not found")

    old_status = position.status
    if old_status != body.status:
        position.status = body.status
        payload: dict = {}
        if body.note:
            payload["note"] = body.note
        session.add(
            PositionEvent(
                position_id=position_id,
                event_type=PositionEventType.STATUS_CHANGE.value,
                from_value=old_status,
                to_value=body.status,
                payload=payload or None,
                actor=Actor.USER.value,
            )
        )
    session.commit()
    session.refresh(position)
    return PositionOut.model_validate(position)
