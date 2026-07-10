"""One-way export of the SQLite tracker to Google Sheets (§5 `POST /export/sheets`).

Sheets is a mirror, never a source (DECISIONS #2) — the job truncates and
rewrites each tab from the DB. Requires Google credentials under
`data/credentials/` and a configured spreadsheet id; both are the same ones the
one-time `migrate_from_sheets.py` import used.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.db.engine import get_session
from api.deps import get_runner
from api.jobs.runner import JobRunner
from api.models import Setting
from api.models.enums import AsyncJobType
from api.schemas.requests import JobAccepted

router = APIRouter(prefix="/export", tags=["export"])

SHEETS_ENABLED_KEY = "sheets_export_enabled"


@router.post("/sheets", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED)
def export_to_sheets(
    session: Session = Depends(get_session),
    runner: JobRunner = Depends(get_runner),
) -> JobAccepted:
    """Mirror every tracked entity into the configured spreadsheet."""
    setting = session.get(Setting, SHEETS_ENABLED_KEY)
    if setting is None or not setting.value:
        raise HTTPException(
            status_code=409,
            detail="Sheets export is turned off — enable it in Settings first.",
        )
    job_id = runner.submit(AsyncJobType.SHEETS_EXPORT.value, {})
    return JobAccepted(job_id=job_id)
