"""First-run onboarding: completion status + CV import (§5, §8 `/onboarding`).

`completed` is **derived from the profile data itself** — there is no stored
"onboarding done" flag and no endpoint to set one. The user finishes onboarding
by having a profile, so approving the imported changes is what flips this to
true; nothing can drift out of sync with reality. (The wizard's "skip for now"
escape is deliberately client-side only, for the same reason.)

The upload writes the PDF under `data/uploads/cv/` — hard rule #1, user files
never land outside `data/`.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.config import DATA_DIR
from api.db.engine import get_session
from api.deps import get_runner
from api.jobs.runner import JobRunner
from api.models import ProfileBasics, ProfileSection
from api.models.enums import AsyncJobType
from api.schemas.requests import JobAccepted

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

_UPLOAD_DIR = DATA_DIR / "uploads" / "cv"
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class OnboardingStep(BaseModel):
    id: str
    label: str
    done: bool


class OnboardingStatus(BaseModel):
    completed: bool
    steps: list[OnboardingStep]


@router.get("/status", response_model=OnboardingStatus)
def get_status(session: Session = Depends(get_session)) -> OnboardingStatus:
    """Derived onboarding state — a profile that can actually draft documents.

    Both steps mirror what `generate_document` needs: without a name and at
    least one non-empty section the agent correctly refuses to draft a CV.
    """
    basics = session.get(ProfileBasics, 1)
    has_basics = bool(basics and basics.full_name)
    has_sections = (
        session.scalar(
            select(ProfileSection.id)
            .where(ProfileSection.content_md.is_not(None), ProfileSection.content_md != "")
            .limit(1)
        )
        is not None
    )

    steps = [
        OnboardingStep(id="basics", label="Profile basics", done=has_basics),
        OnboardingStep(id="sections", label="Profile sections", done=has_sections),
    ]
    return OnboardingStatus(completed=all(s.done for s in steps), steps=steps)


@router.post(
    "/import-cv", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED
)
async def import_cv(
    file: UploadFile = File(...),
    runner: JobRunner = Depends(get_runner),
) -> JobAccepted:
    """Upload a CV PDF; a job extracts it and proposes profile changes to approve."""
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Only PDF files are supported")

    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")

    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = _UPLOAD_DIR / f"{stamp}-{_SAFE_NAME.sub('_', filename)}"
    dest.write_bytes(payload)

    job_id = runner.submit(AsyncJobType.IMPORT_CV.value, {"path": str(dest)})
    return JobAccepted(job_id=job_id)
