"""Job status endpoints + the SSE progress stream (§5, §6)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.db.engine import get_session
from api.deps import get_bus
from api.jobs import EventBus
from api.models import Job
from api.models.enums import JobStatus
from api.schemas.common import Page
from api.schemas.misc import JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])

_ACTIVE = {JobStatus.QUEUED.value, JobStatus.RUNNING.value}


@router.get("", response_model=Page[JobOut])
def list_jobs(
    session: Session = Depends(get_session),
    status: str | None = None,
    type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Page[JobOut]:
    stmt = select(Job)
    if status:
        stmt = stmt.where(Job.status == status)
    if type:
        stmt = stmt.where(Job.type == type)
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(Job.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = [JobOut.model_validate(j) for j in session.scalars(stmt).all()]
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, session: Session = Depends(get_session)) -> JobOut:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobOut.model_validate(job)


@router.post("/{job_id}/cancel", response_model=JobOut)
def cancel_job(
    job_id: str,
    request: Request,
    session: Session = Depends(get_session),
) -> JobOut:
    """Best-effort cooperative cancel (only queued/running jobs)."""
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in _ACTIVE:
        request.app.state.job_runner.request_cancel(job_id)
    return JobOut.model_validate(job)


def _sse(seq: int, event: str, data: dict) -> str:
    return f"id: {seq}\nevent: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/{job_id}/events")
def job_events(
    job_id: str,
    request: Request,
    session: Session = Depends(get_session),
    bus: EventBus = Depends(get_bus),
) -> StreamingResponse:
    """SSE stream of a job's progress/done/failed events (§6).

    Replays buffered events (and resumes from `Last-Event-ID`) so a client that
    connects late or reconnects still sees everything up to the terminal event.
    """
    if session.get(Job, job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")

    last = request.headers.get("Last-Event-ID")
    last_id = int(last) if last and last.lstrip("-").isdigit() else None

    def stream():
        for seq, event, data in bus.subscribe(job_id, last_event_id=last_id):
            yield _sse(seq, event, data)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
