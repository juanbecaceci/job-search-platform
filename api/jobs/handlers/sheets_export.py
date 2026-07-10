"""`sheets_export` job: mirror SQLite into the Google Sheets tracker
(§5 `POST /export/sheets`).

One-way only (DECISIONS #2): each tab is truncated and rewritten from the DB,
so the sheet always reflects current state — including deletions. Nothing is
ever read back; `migrate_from_sheets.py` was the one-time import and SQLite has
been authoritative since.

The column layouts mirror `core/sheets_manager.py`'s `*_HEADERS`, which is what
the original tracker used, so an exported sheet stays readable by the same
formulas/filters the user already had.
"""

from __future__ import annotations

import sys
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from api.config import ROOT_DIR
from api.models import Application, Company, Document, Position, Search

_CORE_DIR = str(ROOT_DIR / "core")
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

from core import sheets_manager as sm  # noqa: E402


def _text(value: Any) -> str:
    """Sheets cells are strings; None becomes empty, lists become 'a, b'."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value if v not in (None, ""))
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value)


def _position_rows(session: Session) -> list[list[str]]:
    positions = session.scalars(
        select(Position)
        .options(selectinload(Position.company), selectinload(Position.search))
        .order_by(Position.date_discovered.desc(), Position.id)
    ).all()
    return [
        [
            _text(p.id),
            _text(p.search.name if p.search else None),
            _text(p.source),
            _text(p.sources),
            _text(p.tipo),
            _text(p.company.name if p.company else None),
            _text(p.role),
            _text(p.url),
            _text(p.location),
            _text(p.remote),
            _text(p.salary_raw),
            _text(p.date_discovered),
            _text(p.score),
            _text(p.rank),
            _text(p.status),
            _text(p.summary),  # evaluation_notes column (see migration mapping)
            _text(p.notes),
            _text(p.description),
            _text(p.tags),
        ]
        for p in positions
    ]


def _application_rows(session: Session) -> list[list[str]]:
    applications = session.scalars(
        select(Application).order_by(Application.position_id)
    ).all()
    # Drive URLs live on the linked documents, not the application row.
    doc_ids = {
        d
        for a in applications
        for d in (a.cv_document_id, a.cover_letter_document_id)
        if d is not None
    }
    drive_urls: dict[int, str | None] = {}
    if doc_ids:
        drive_urls = {
            d.id: d.drive_url
            for d in session.scalars(select(Document).where(Document.id.in_(doc_ids))).all()
        }

    rows = []
    for a in applications:
        cv_doc = session.get(Document, a.cv_document_id) if a.cv_document_id else None
        rows.append([
            _text(a.position_id),
            _text(cv_doc.version if cv_doc else None),
            _text(drive_urls.get(a.cv_document_id)),
            _text(drive_urls.get(a.cover_letter_document_id)),
            _text(a.date_applied),
            _text(a.contact),
            _text(a.response_date),
            _text(a.interview_date),
            _text(a.outcome),
            _text(a.notes),
        ])
    return rows


def _search_rows(session: Session) -> list[list[str]]:
    searches = session.scalars(select(Search).order_by(Search.id)).all()
    return [
        [
            _text(s.id),
            _text(s.name),
            _text(s.keywords),
            _text(s.markets),
            _text(s.sources),
            _text(s.created_at.date() if s.created_at else None),
            _text(s.status != "archived"),
        ]
        for s in searches
    ]


def _company_rows(session: Session) -> list[list[str]]:
    companies = session.scalars(select(Company).order_by(Company.name)).all()
    research_docs = {
        d.company_id: d
        for d in session.scalars(
            select(Document)
            .where(Document.kind == "company_research")
            .order_by(Document.version)
        ).all()
        if d.company_id is not None
    }
    rows = []
    for c in companies:
        doc = research_docs.get(c.id)
        rows.append([
            _text(c.name),
            _text(c.industry),
            _text(c.size),
            _text(c.website),
            _text(doc.drive_url if doc else None),
            "",  # notes: no company-notes column in the model
            _text(doc.updated_at.date() if doc and doc.updated_at else None),
        ])
    return rows


def handle(session: Session, job, params: dict[str, Any], progress) -> dict[str, Any]:
    if not sm.SPREADSHEET_ID:
        raise ValueError(
            "No spreadsheet configured — set SPREADSHEET_ID (or "
            "GOOGLE_SHEETS_JOB_TRACKER_ID) in data/credentials/.env"
        )

    progress(0.05, "connecting to Google Sheets")
    # interactive=False: a server must never block on a browser OAuth prompt.
    service = sm.get_sheets_service(interactive=False)

    tabs = [
        (sm.POSITIONS_SHEET, sm.POSITIONS_HEADERS, _position_rows),
        (sm.APPLICATIONS_SHEET, sm.APPLICATIONS_HEADERS, _application_rows),
        (sm.SEARCHES_SHEET, sm.SEARCHES_HEADERS, _search_rows),
        (sm.COMPANIES_SHEET, sm.COMPANIES_HEADERS, _company_rows),
    ]
    sm.ensure_sheets_exist(service, [name for name, _, _ in tabs])

    written: dict[str, int] = {}
    for index, (name, headers, build_rows) in enumerate(tabs):
        progress(0.1 + 0.85 * index / len(tabs), f"writing {name}")
        rows = build_rows(session)
        written[name] = sm.replace_sheet(service, name, headers, rows)

    progress(1.0, "export complete")
    return {"spreadsheet_id": sm.SPREADSHEET_ID, "rows_written": written}
