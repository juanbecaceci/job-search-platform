"""Document read/edit/export/download (§5) + the top-level Application PATCH.

`PATCH /applications/{id}` lives here (not under `positions.py`) because it's
a top-level resource path per PLATFORM_SPEC.md §5 — `POST /positions/{id}/application`
(create) stays in `positions.py` since it's nested under a position.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.config import DATA_DIR
from api.db.engine import get_session
from api.deps import get_runner
from api.jobs import JobRunner
from api.models import Application, Document, PositionEvent
from api.models.enums import Actor, AsyncJobType, PositionEventType
from api.schemas.position import ApplicationOut, DocumentOut
from api.schemas.requests import ApplicationPatch, DocumentUpdate, JobAccepted

router = APIRouter(prefix="/documents", tags=["documents"])
applications_router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: int, session: Session = Depends(get_session)) -> DocumentOut:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentOut.model_validate(document)


@router.put("/{document_id}", response_model=DocumentOut)
def update_document(
    document_id: int, body: DocumentUpdate, session: Session = Depends(get_session)
) -> DocumentOut:
    """Edit the Markdown source (a draft refinement — no version bump)."""
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    document.content_md = body.content_md
    session.commit()
    session.refresh(document)
    return DocumentOut.model_validate(document)


@router.post("/{document_id}/export", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED)
def export_document(
    document_id: int,
    session: Session = Depends(get_session),
    runner: JobRunner = Depends(get_runner),
) -> JobAccepted:
    if session.get(Document, document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found")
    job_id = runner.submit(AsyncJobType.EXPORT_DOCUMENT.value, {"document_id": document_id})
    return JobAccepted(job_id=job_id)


@router.post(
    "/{document_id}/upload-drive", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED
)
def upload_document_to_drive(
    document_id: int,
    session: Session = Depends(get_session),
    runner: JobRunner = Depends(get_runner),
) -> JobAccepted:
    """Push this document's exported PDF/DOCX to the configured Drive folder."""
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if not (document.pdf_available or document.docx_available):
        raise HTTPException(
            status_code=409, detail="Export this document to PDF/DOCX before uploading it."
        )
    job_id = runner.submit(AsyncJobType.UPLOAD_DRIVE.value, {"document_id": document_id})
    return JobAccepted(job_id=job_id)


@router.get("/{document_id}/file")
def download_document(
    document_id: int,
    format: str = Query(..., pattern="^(pdf|docx)$"),
    session: Session = Depends(get_session),
) -> FileResponse:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    rel_path = document.pdf_path if format == "pdf" else document.docx_path
    if not rel_path:
        raise HTTPException(status_code=404, detail=f"No {format} exported for this document yet")
    path = DATA_DIR / Path(rel_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Exported file is missing on disk")
    media_type = "application/pdf" if format == "pdf" else (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    return FileResponse(path, media_type=media_type, filename=path.name)


@applications_router.patch("/{application_id}", response_model=ApplicationOut)
def patch_application(
    application_id: int, body: ApplicationPatch, session: Session = Depends(get_session)
) -> ApplicationOut:
    """Edit fields on an existing application record."""
    application = session.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    changes: dict[str, dict] = {}
    for field, new_value in body.model_dump(exclude_unset=True).items():
        old_value = getattr(application, field)
        if old_value != new_value:
            setattr(application, field, new_value)
            changes[field] = {"old": str(old_value), "new": str(new_value)}

    if changes:
        session.add(
            PositionEvent(
                position_id=application.position_id,
                event_type=PositionEventType.APPLICATION_UPDATE.value,
                payload={"fields": changes},
                actor=Actor.USER.value,
            )
        )
    session.commit()
    session.refresh(application)
    return ApplicationOut.model_validate(application)
