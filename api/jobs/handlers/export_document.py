"""`export_document` job: render a Document's `content_md` to PDF + DOCX.

Reuses only the pure Markdown→PDF/DOCX renderers from `core/generate_cv.py`
and `core/generate_cover_letter.py` (`markdown_to_pdf`, `markdown_to_docx`,
`doc_basename`, `safe_id`) — NOT their `export()`/`OUTPUT_DIR`-coupled
wrappers, which hardcode `output/...` at the repo root. Hard rule #1 requires
generated content (a candidate's tailored CV, cover letter) to live under
`data/`, so this handler writes to `DATA_DIR / "documents" / ...` itself.
"""

from __future__ import annotations

import sys
from typing import Any

from sqlalchemy.orm import Session, selectinload

from api.config import DATA_DIR, ROOT_DIR
from api.models import Document, Position, ProfileBasics

_CORE_DIR = str(ROOT_DIR / "core")
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

from core import generate_cover_letter, generate_cv  # noqa: E402

_RENDERERS = {"cv": generate_cv, "cover_letter": generate_cover_letter}
_DOC_LABEL = {"cv": "CV", "cover_letter": "CoverLetter"}


def handle(session: Session, job, params: dict[str, Any], progress) -> dict[str, Any]:
    document_id = params["document_id"]
    document = session.get(Document, document_id, options=[selectinload(Document.position)])
    if document is None:
        raise ValueError(f"Document {document_id} not found")
    if document.kind not in _RENDERERS:
        raise ValueError(f"Export not supported for document kind {document.kind!r}")
    if not (document.content_md or "").strip():
        raise ValueError("Document has no content to export")

    renderer = _RENDERERS[document.kind]
    scope_id = document.position_id or f"company-{document.company_id}"
    safe = renderer.safe_id(scope_id)

    candidate = "Candidate"
    role = ""
    if document.position_id:
        position = session.get(Position, document.position_id, options=[selectinload(Position.company)])
        role = position.role if position else ""
    basics = session.get(ProfileBasics, 1)
    if basics and basics.full_name:
        candidate = basics.full_name

    out_dir = DATA_DIR / "documents" / safe
    out_dir.mkdir(parents=True, exist_ok=True)
    base = renderer.doc_basename(candidate, _DOC_LABEL[document.kind], role) if role else document.kind
    pdf_path = out_dir / f"{base}-v{document.version}.pdf"
    docx_path = out_dir / f"{base}-v{document.version}.docx"

    progress(0.3, "rendering PDF")
    pdf_ok = renderer.markdown_to_pdf(document.content_md, pdf_path)
    progress(0.7, "rendering DOCX")
    docx_ok = renderer.markdown_to_docx(document.content_md, docx_path)

    document.pdf_available = pdf_ok
    document.docx_available = docx_ok
    document.pdf_path = str(pdf_path.relative_to(DATA_DIR)) if pdf_ok else None
    document.docx_path = str(docx_path.relative_to(DATA_DIR)) if docx_ok else None
    session.commit()

    if not pdf_ok and not docx_ok:
        raise ValueError("Export failed for both PDF and DOCX (see server logs)")

    return {
        "document_id": document.id,
        "pdf_available": pdf_ok,
        "docx_available": docx_ok,
    }
