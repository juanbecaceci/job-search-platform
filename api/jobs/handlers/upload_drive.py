"""`upload_drive` job: push a document's exported PDF/DOCX to Google Drive
(§5 `POST /documents/{id}/upload-drive`).

Uploads whatever binaries the export job produced into a per-position
subfolder (`Company - Role`) of the configured Drive folder — matching the
foldering convention users already keep by hand — and records the resulting
Drive link on the document. Nothing is generated here — if the document was
never exported there's nothing to upload, and the job says so instead of
silently succeeding.

Auth goes through `core/google_auth.py` with `interactive=False`: a server must
never open a browser OAuth prompt.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from api.config import DATA_DIR, ROOT_DIR
from api.models import Company, Document, Position

_CORE_DIR = str(ROOT_DIR / "core")
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

from core.upload_to_drive import ensure_folder, get_drive_service, upload_file  # noqa: E402


def _folder_id(params: dict[str, Any]) -> str:
    folder = params.get("folder_id") or os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not folder:
        raise ValueError(
            "No Drive folder configured — set GOOGLE_DRIVE_FOLDER_ID in "
            "data/credentials/.env (or pass folder_id)."
        )
    return folder


def _title(document: Document, path: Path) -> str:
    """Keep the exported filename.

    `export_document` already builds something a recruiter should see
    (`<Name>-CV-<Role>-v1.pdf`); renaming it to `cv-v1.pdf` here would strip
    that the moment the file is downloaded or forwarded.
    """
    return path.name


def _folder_name(session: Session, document: Document) -> str:
    """`Company - Role` for a position's documents, company name for research.

    Mirrors the folder convention the user's own Drive already uses, so
    platform-generated documents sit alongside the ones they filed by hand
    instead of piling up loose in the parent folder.
    """
    if document.position_id:
        position = session.get(Position, document.position_id)
        if position is not None:
            company = position.company.name if position.company else None
            name = f"{company} - {position.role}" if company else position.role
            return _sanitize(name)
    if document.company_id:
        company = session.get(Company, document.company_id)
        if company is not None:
            return _sanitize(company.name)
    return "Unfiled"


def _sanitize(name: str) -> str:
    """Drive tolerates most characters; slashes still read as path separators."""
    cleaned = name.replace("/", "-").replace("\\", "-").strip()
    return cleaned[:120] or "Unfiled"


def handle(session: Session, job, params: dict[str, Any], progress) -> dict[str, Any]:
    document_id = params["document_id"]
    document = session.get(Document, document_id)
    if document is None:
        raise ValueError(f"Document {document_id} not found")

    # Stored paths are relative to data/ (see the Document model).
    candidates: list[Path] = []
    for rel in (document.pdf_path, document.docx_path):
        if rel:
            path = DATA_DIR / rel
            if path.exists():
                candidates.append(path)
    if not candidates:
        raise ValueError(
            "This document has no exported file yet — run Export (PDF/DOCX) first."
        )

    parent = _folder_id(params)
    progress(0.1, "connecting to Google Drive")
    service = get_drive_service(interactive=False)

    subfolder_name = _folder_name(session, document)
    progress(0.15, f"filing under '{subfolder_name}'")
    folder = ensure_folder(service, subfolder_name, parent)

    uploaded: list[dict[str, Any]] = []
    for index, path in enumerate(candidates):
        progress(0.2 + 0.7 * index / len(candidates), f"uploading {path.name}")
        created = upload_file(
            service, str(path), _title(document, path), folder, replace_existing=True
        )
        if created:
            uploaded.append({
                "name": created.get("name"),
                "url": created.get("webViewLink"),
                "id": created.get("id"),
            })

    if not uploaded:
        raise ValueError("Drive accepted no files")

    # Prefer the PDF's link as the canonical one shown in the UI.
    pdf_link = next((u["url"] for u in uploaded if str(u["name"]).endswith(".pdf")), None)
    document.drive_url = pdf_link or uploaded[0]["url"]
    session.commit()

    progress(1.0, "upload complete")
    return {"document_id": document.id, "drive_url": document.drive_url, "files": uploaded}
