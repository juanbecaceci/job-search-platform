#!/usr/bin/env python3
"""One-time migration: Google Sheets Job Tracker -> SQLite.

Reads the four tabs exposed by ``core/sheets_manager.py`` (Positions,
Applications, Search Configs, Companies) and upserts them into the SQLite
schema. Going forward SQLite is authoritative — this never reads Sheets again
(DECISIONS #2). Sheets stays only as an optional one-way export mirror.

Mapping highlights (Sheets column -> SQLite):
  Positions.company            -> companies (get-or-create by name) + positions.company_id
  Positions.search_name        -> searches.id (resolved by name)
  Positions.salary             -> positions.salary_raw (single free-text field)
  Positions.evaluation_notes   -> positions.summary
  Applications.*_drive_url      -> documents (kind cv/cover_letter, drive_url) + FK on application
  Companies.research_drive_url -> documents (kind company_research, drive_url)
  Companies.notes              -> companies.research_md

Synthesized history: each newly-inserted position gets a ``created`` event, plus
one ``status_change`` (Discovered -> current) when its status isn't Discovered.
All synthesized events use ``actor='system'``. Search aggregate metrics
(total_found / total_evaluated / avg_score / last_run_at) are computed from the
migrated positions.

Idempotent: rows are upserted by natural key (position id, company name, search
name, application position_id); events are synthesized only for positions that
have none, so re-running won't duplicate history.

Prerequisites: ``GOOGLE_SHEETS_JOB_TRACKER_ID`` set (+ Google OAuth
``credentials.json`` / ``token.json``, per core/sheets_manager.py), schema
migrated (``alembic upgrade head``), and ideally defaults seeded
(``scripts/seed_defaults.py``, so score_category can be derived).

Run (from repo root):
    python scripts/migrate_from_sheets.py            # writes to the DB
    python scripts/migrate_from_sheets.py --dry-run  # reports, writes nothing
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import UTC, date, datetime, time
from pathlib import Path

# Repo root on the path so `import api...` / `import core...` resolve.
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from api.db.engine import SessionLocal  # noqa: E402
from api.models import (  # noqa: E402
    Application,
    Company,
    Document,
    Position,
    PositionEvent,
    ScoringConfig,
    Search,
)
from api.models.enums import (  # noqa: E402
    Actor,
    DocumentKind,
    PositionEventType,
    PositionStatus,
    SearchStatus,
)
from core import sheets_manager as sm  # noqa: E402

# ─── parsing helpers ─────────────────────────────────────────


def _clean(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _parse_date(value: object) -> date | None:
    text = _clean(value)
    if not text:
        return None
    # Accept ISO (YYYY-MM-DD) and a couple of common alternates.
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_float(value: object) -> float | None:
    text = _clean(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_int(value: object) -> int | None:
    f = _parse_float(value)
    return int(f) if f is not None else None


def _split_list(value: object) -> list[str]:
    """Split a comma-separated cell into a clean, de-duplicated list."""
    text = _clean(value)
    if not text:
        return []
    seen: dict[str, None] = {}
    for part in text.split(","):
        item = part.strip()
        if item and item not in seen:
            seen[item] = None
    return list(seen)


def _as_datetime(d: date | None) -> datetime | None:
    return datetime.combine(d, time.min, tzinfo=UTC) if d else None


def _rows_as_dicts(values: list[list[str]]) -> list[dict[str, str]]:
    """Turn a raw sheet (list of rows) into dicts keyed by its own header row.

    Using the sheet's actual header row (not a hardcoded constant) keeps the
    migration resilient to column reordering.
    """
    if not values or len(values) < 2:
        return []
    headers = [_clean(h) for h in values[0]]
    rows: list[dict[str, str]] = []
    for row in values[1:]:
        if not any(_clean(c) for c in row):
            continue  # skip fully blank rows
        padded = list(row) + [""] * (len(headers) - len(row))
        rows.append({h: _clean(v) for h, v in zip(headers, padded)})
    return rows


# ─── migration steps ─────────────────────────────────────────


class _CompanyCache:
    """Get-or-create companies by case-insensitive name, within one session."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._by_name: dict[str, Company] = {
            (c.name or "").strip().lower(): c
            for c in session.scalars(select(Company)).all()
        }

    def get_or_create(self, name: str) -> Company | None:
        key = name.strip().lower()
        if not key:
            return None
        company = self._by_name.get(key)
        if company is None:
            company = Company(name=name.strip())
            self._session.add(company)
            self._session.flush()  # assign id
            self._by_name[key] = company
        return company


def _category_resolver(session: Session):
    """Return score->category-id function from the active scoring config.

    Returns ``None`` if no active config exists (defaults not seeded yet), in
    which case score_category is left null.
    """
    config = session.scalar(
        select(ScoringConfig).where(ScoringConfig.is_active.is_(True))
    )
    if config is None or not config.categories:
        return None

    bands = [
        (float(c["min_score"]), float(c["max_score"]), c["id"])
        for c in config.categories
    ]

    def resolve(score: float | None) -> str | None:
        if score is None:
            return None
        for low, high, cid in bands:
            if low <= score <= high:
                return cid
        return None

    return resolve


def migrate_searches(session: Session) -> tuple[dict[str, int], int]:
    """Upsert Search Configs. Returns (name_lower -> search.id, count)."""
    service = sm.get_sheets_service()
    rows = _rows_as_dicts(sm.get_all_values(service, sm.SEARCHES_SHEET))

    existing = {(s.name or "").strip().lower(): s for s in session.scalars(select(Search)).all()}
    name_to_id: dict[str, int] = {}
    count = 0
    for r in rows:
        name = r.get("name", "")
        if not name:
            continue
        key = name.strip().lower()
        search = existing.get(key)
        if search is None:
            search = Search(name=name.strip())
            session.add(search)
            existing[key] = search
        search.keywords = _split_list(r.get("keywords"))
        search.markets = _split_list(r.get("markets"))
        search.sources = _split_list(r.get("sources"))
        # Migrated searches carry historical evaluated positions -> "analyzed".
        search.status = SearchStatus.ANALYZED.value
        created = _parse_date(r.get("date_created"))
        if created:
            search.created_at = _as_datetime(created)
        session.flush()
        name_to_id[key] = search.id
        count += 1
    return name_to_id, count


def migrate_companies(session: Session, companies: _CompanyCache) -> int:
    """Upsert Companies and attach a company_research doc when a Drive URL exists."""
    service = sm.get_sheets_service()
    rows = _rows_as_dicts(sm.get_all_values(service, sm.COMPANIES_SHEET))

    count = 0
    for r in rows:
        name = r.get("company", "")
        if not name:
            continue
        company = companies.get_or_create(name)
        if company is None:
            continue
        company.industry = r.get("industry") or company.industry
        company.size = r.get("size") or company.size
        company.website = r.get("website") or company.website
        # The research text itself lives in Drive; the sheet's free-text notes
        # are the best local stand-in for research_md.
        if r.get("notes"):
            company.research_md = r["notes"]
        researched = _parse_date(r.get("date_researched"))
        if researched:
            company.created_at = _as_datetime(researched)
        session.flush()

        drive_url = r.get("research_drive_url")
        if drive_url and not _has_doc(session, company_id=company.id,
                                      kind=DocumentKind.COMPANY_RESEARCH.value):
            session.add(
                Document(
                    company_id=company.id,
                    kind=DocumentKind.COMPANY_RESEARCH.value,
                    version=1,
                    drive_url=drive_url,
                    status="final",
                    created_by=Actor.USER.value,
                )
            )
        count += 1
    return count


def _has_doc(session: Session, *, kind: str,
            position_id: str | None = None, company_id: int | None = None) -> bool:
    stmt = select(func.count()).select_from(Document).where(Document.kind == kind)
    if position_id is not None:
        stmt = stmt.where(Document.position_id == position_id)
    if company_id is not None:
        stmt = stmt.where(Document.company_id == company_id)
    return bool(session.scalar(stmt))


def migrate_positions(
    session: Session,
    companies: _CompanyCache,
    search_ids: dict[str, int],
) -> tuple[int, int, Counter, Counter]:
    """Upsert Positions (+ synthesized events). Returns (total, new, by_status, by_source)."""
    service = sm.get_sheets_service()
    rows = _rows_as_dicts(sm.get_all_values(service, sm.POSITIONS_SHEET))
    resolve_category = _category_resolver(session)

    by_status: Counter = Counter()
    by_source: Counter = Counter()
    total = new = 0

    valid_status = {s.value for s in PositionStatus}

    for r in rows:
        pid = r.get("id")
        if not pid:
            continue

        position = session.get(Position, pid)
        is_new = position is None
        if is_new:
            position = Position(id=pid, source=r.get("source", "manual"), role=r.get("role", ""))
            session.add(position)

        company = companies.get_or_create(r.get("company", ""))
        position.company_id = company.id if company else None

        search_name = r.get("search_name", "").strip().lower()
        position.search_id = search_ids.get(search_name)

        position.source = r.get("source") or position.source
        sources = _split_list(r.get("sources")) or ([position.source] if position.source else [])
        position.sources = sources
        position.tipo = r.get("tipo") or None
        position.role = r.get("role") or position.role
        position.url = r.get("url") or None
        position.location = r.get("location") or None
        position.remote = r.get("remote") or None
        position.salary_raw = r.get("salary") or None
        position.date_discovered = _parse_date(r.get("date_discovered"))
        position.score = _parse_float(r.get("score"))
        position.rank = _parse_int(r.get("rank"))
        if resolve_category:
            position.score_category = resolve_category(position.score)
        status = r.get("status") or PositionStatus.DISCOVERED.value
        if status not in valid_status:
            status = PositionStatus.DISCOVERED.value
        position.status = status
        position.summary = r.get("evaluation_notes") or None
        position.notes = r.get("notes") or None
        position.description = r.get("description") or None
        position.tags = _split_list(r.get("tags"))
        session.flush()

        if is_new:
            _synthesize_events(session, position)

        total += 1
        new += int(is_new)
        by_status[status] += 1
        for s in sources or ["(none)"]:
            by_source[s] += 1

    return total, new, by_status, by_source


def _synthesize_events(session: Session, position: Position) -> None:
    """Create a `created` event (+ a `status_change` if not Discovered)."""
    if position.events:  # idempotency guard
        return
    discovered_at = _as_datetime(position.date_discovered) or datetime.now(UTC)
    session.add(
        PositionEvent(
            position_id=position.id,
            event_type=PositionEventType.CREATED.value,
            to_value=PositionStatus.DISCOVERED.value,
            payload={"source": position.source, "migrated": True},
            actor=Actor.SYSTEM.value,
            created_at=discovered_at,
        )
    )
    if position.status != PositionStatus.DISCOVERED.value:
        session.add(
            PositionEvent(
                position_id=position.id,
                event_type=PositionEventType.STATUS_CHANGE.value,
                from_value=PositionStatus.DISCOVERED.value,
                to_value=position.status,
                payload={"migrated": True, "synthesized": True},
                actor=Actor.SYSTEM.value,
                created_at=discovered_at,
            )
        )


def migrate_applications(session: Session) -> int:
    """Upsert Applications; materialize CV/cover-letter Drive URLs as documents."""
    service = sm.get_sheets_service()
    rows = _rows_as_dicts(sm.get_all_values(service, sm.APPLICATIONS_SHEET))

    count = 0
    for r in rows:
        pid = r.get("position_id")
        if not pid or session.get(Position, pid) is None:
            continue  # orphan application row — skip

        application = session.scalar(
            select(Application).where(Application.position_id == pid)
        )
        if application is None:
            application = Application(position_id=pid)
            session.add(application)

        application.date_applied = _parse_date(r.get("date_applied"))
        application.contact = r.get("contact") or None
        application.response_date = _parse_date(r.get("response_date"))
        application.interview_date = _parse_date(r.get("interview_date"))
        application.outcome = r.get("outcome") or None
        application.notes = r.get("notes") or None

        version = _parse_int(r.get("cv_version")) or 1
        application.cv_document_id = _ensure_doc(
            session, pid, DocumentKind.CV.value, r.get("cv_drive_url"), version
        )
        application.cover_letter_document_id = _ensure_doc(
            session, pid, DocumentKind.COVER_LETTER.value, r.get("cover_letter_drive_url"), version
        )
        session.flush()
        count += 1
    return count


def _ensure_doc(session: Session, position_id: str, kind: str,
               drive_url: str | None, version: int) -> int | None:
    """Get-or-create a document for a position's Drive URL; return its id."""
    if not drive_url:
        return None
    existing = session.scalar(
        select(Document).where(
            Document.position_id == position_id, Document.kind == kind
        )
    )
    if existing is not None:
        existing.drive_url = drive_url
        session.flush()
        return existing.id
    doc = Document(
        position_id=position_id,
        kind=kind,
        version=version,
        drive_url=drive_url,
        status="final",
        created_by=Actor.USER.value,
    )
    session.add(doc)
    session.flush()
    return doc.id


def compute_search_metrics(session: Session) -> int:
    """Recompute per-search aggregate metrics from migrated positions."""
    searches = session.scalars(select(Search)).all()
    updated = 0
    for search in searches:
        positions = session.scalars(
            select(Position).where(Position.search_id == search.id)
        ).all()
        if not positions:
            continue
        scored = [p.score for p in positions if p.score is not None]
        search.total_found = len(positions)
        search.total_new = len(positions)
        search.total_evaluated = len(scored)
        search.avg_score = round(sum(scored) / len(scored), 2) if scored else None
        discovered = [p.date_discovered for p in positions if p.date_discovered]
        search.last_run_at = _as_datetime(max(discovered)) if discovered else None
        updated += 1
    return updated


# ─── orchestration ───────────────────────────────────────────


def run_migration(session: Session) -> dict[str, object]:
    companies = _CompanyCache(session)
    search_ids, n_searches = migrate_searches(session)
    n_companies = migrate_companies(session, companies)
    n_positions, n_new, by_status, by_source = migrate_positions(
        session, companies, search_ids
    )
    n_apps = migrate_applications(session)
    n_search_metrics = compute_search_metrics(session)
    return {
        "searches": n_searches,
        "companies": n_companies,
        "positions": n_positions,
        "positions_new": n_new,
        "applications": n_apps,
        "search_metrics_updated": n_search_metrics,
        "by_status": by_status,
        "by_source": by_source,
    }


def _print_summary(result: dict[str, object], dry_run: bool) -> None:
    mode = "DRY-RUN (nothing written)" if dry_run else "COMMITTED"
    print(f"\n=== Sheets -> SQLite migration [{mode}] ===")
    print(f"  searches:      {result['searches']}")
    print(f"  companies:     {result['companies']}")
    print(f"  positions:     {result['positions']}  ({result['positions_new']} new)")
    print(f"  applications:  {result['applications']}")
    print(f"  search metrics recomputed: {result['search_metrics_updated']}")

    by_status: Counter = result["by_status"]  # type: ignore[assignment]
    print("\n  positions by status (compare against Sheets):")
    for status in [s.value for s in PositionStatus]:
        if by_status.get(status):
            print(f"    {status:<20} {by_status[status]}")

    by_source: Counter = result["by_source"]  # type: ignore[assignment]
    print("\n  positions by source:")
    for source, n in sorted(by_source.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"    {source:<20} {n}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate Google Sheets Job Tracker -> SQLite")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the full migration in a transaction, then roll back (writes nothing).",
    )
    args = parser.parse_args()

    session = SessionLocal()
    try:
        result = run_migration(session)
        if args.dry_run:
            session.rollback()
        else:
            session.commit()
        _print_summary(result, args.dry_run)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
