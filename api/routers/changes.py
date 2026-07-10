"""The approval tray: list, inspect, approve, reject pending changes (§5).

Approve is the only path that mutates domain tables (via ChangeApplier), inside
one transaction (DECISIONS #6).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db.engine import get_session
from api.deps import get_runner
from api.jobs import JobRunner
from api.models import PendingChange
from api.models.enums import PendingChangeStatus
from api.schemas.chat import ChangeEdit, PendingChangeOut, RejectBody
from api.services import change_applier

router = APIRouter(prefix="/changes", tags=["changes"])


@router.get("", response_model=list[PendingChangeOut])
def list_changes(
    session: Session = Depends(get_session),
    status: str | None = "pending",
) -> list[PendingChangeOut]:
    stmt = select(PendingChange)
    if status:
        stmt = stmt.where(PendingChange.status == status)
    stmt = stmt.order_by(PendingChange.created_at.desc())
    return [PendingChangeOut.model_validate(c) for c in session.scalars(stmt).all()]


@router.get("/{change_id}", response_model=PendingChangeOut)
def get_change(change_id: int, session: Session = Depends(get_session)) -> PendingChangeOut:
    change = session.get(PendingChange, change_id)
    if change is None:
        raise HTTPException(status_code=404, detail="Change not found")
    return PendingChangeOut.model_validate(change)


@router.patch("/{change_id}", response_model=PendingChangeOut)
def edit_change(
    change_id: int,
    body: ChangeEdit,
    session: Session = Depends(get_session),
) -> PendingChangeOut:
    """Rewrite a still-pending proposal before approving it.

    The user correcting what the agent extracted (a mangled CV section, a wrong
    job title) shouldn't have to reject, re-prompt, and hope. This edits the
    proposal in place; approving it afterwards runs the same `ChangeApplier`
    path with the same whitelists, so an edit can't widen what the change is
    allowed to touch. `edited_at` records that the applied text was the user's,
    not the agent's.
    """
    change = session.get(PendingChange, change_id)
    if change is None:
        raise HTTPException(status_code=404, detail="Change not found")
    if change.status != PendingChangeStatus.PENDING.value:
        raise HTTPException(status_code=409, detail=f"Change is {change.status}, not pending")
    if change.change_type == "action":
        # An `action` diff dispatches a job; letting the tray rewrite its
        # payload is a different (and much sharper) tool than fixing text.
        raise HTTPException(status_code=422, detail="Action changes can't be edited")

    change.diff = body.diff
    if body.summary is not None:
        change.summary = body.summary
    change.edited_at = datetime.now(UTC)
    session.commit()
    session.refresh(change)
    return PendingChangeOut.model_validate(change)


@router.post("/{change_id}/approve", response_model=PendingChangeOut)
def approve_change(
    change_id: int,
    session: Session = Depends(get_session),
    runner: JobRunner = Depends(get_runner),
) -> PendingChangeOut:
    """Apply the change transactionally. On failure the change is marked failed."""
    change = session.get(PendingChange, change_id)
    if change is None:
        raise HTTPException(status_code=404, detail="Change not found")
    if change.status != PendingChangeStatus.PENDING.value:
        raise HTTPException(status_code=409, detail=f"Change is {change.status}, not pending")

    try:
        change_applier.apply(session, change, runner=runner)
        change.status = PendingChangeStatus.APPLIED.value
        change.applied_at = datetime.now(UTC)
        change.apply_error = None
        session.commit()
    except Exception as exc:  # noqa: BLE001 — surface any apply failure on the row
        session.rollback()
        change = session.get(PendingChange, change_id)
        change.status = PendingChangeStatus.FAILED.value
        change.apply_error = str(exc)
        session.commit()
        raise HTTPException(status_code=422, detail=f"Apply failed: {exc}") from exc

    session.refresh(change)
    return PendingChangeOut.model_validate(change)


@router.post("/{change_id}/reject", response_model=PendingChangeOut)
def reject_change(
    change_id: int,
    body: RejectBody | None = None,
    session: Session = Depends(get_session),
) -> PendingChangeOut:
    """Reject a pending change; the optional reason is kept for context."""
    change = session.get(PendingChange, change_id)
    if change is None:
        raise HTTPException(status_code=404, detail="Change not found")
    if change.status != PendingChangeStatus.PENDING.value:
        raise HTTPException(status_code=409, detail=f"Change is {change.status}, not pending")
    change.status = PendingChangeStatus.REJECTED.value
    if body and body.reason:
        change.apply_error = f"rejected: {body.reason}"
    session.commit()
    session.refresh(change)
    return PendingChangeOut.model_validate(change)
