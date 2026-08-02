"""`search_run` job: fetch jobs from the free public APIs, dedupe, persist.

Wraps the deterministic fetchers in `core/fetch_jobs_api.py` (imported directly
in-process per api/CLAUDE.md — no subprocess). We call the per-source fetchers
individually (not `fetch_all`) so we can report progress and per-source stats as
each source finishes.

Dedup: a position's identity is `make_position_id(company, role)` — the same
slug the Sheets system used, so newly fetched rows dedupe cleanly against
migrated data (whose PK is that slug). A re-found position is linked to this run
(is_new=False) and gets the new source merged into its `sources`; a brand-new
one is inserted (status Discovered) and linked (is_new=True).

Geo/market filtering IS applied here, as of 2026-08-02 (DECISIONS #35). Each
source's results pass through `core.location_filters.filter_by_regions` before
dedupe, using `search.markets` (union: a position survives if ANY listed region
could take it) and falling back to `TARGET_REGION` when the search names none.
The drop is reported per source as `filtered_out` rather than applied silently —
the earlier region default silently emptied CLI searches, and that is exactly
the failure this must not reproduce. With `worldwide` (the default) nothing is
filtered and the runner behaves as it always did.
"""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime, time as dtime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.config import (
    LINKEDIN_FETCH_DESCRIPTIONS,
    LINKEDIN_LOCATION,
    LINKEDIN_MAX_PAGES,
    ROOT_DIR,
)
from api.models import (
    Company,
    Job,
    Position,
    Search,
    SearchRun,
    SearchRunPosition,
)
from api.agent.mcp_sources import McpSourceUnavailable, fetch_indeed
from api.models.enums import PositionStatus, SearchStatus, Source

# core/ uses sibling imports (e.g. `from location_filters import ...`), so it must
# be importable as a top-level package root.
_CORE_DIR = str(ROOT_DIR / "core")
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

from core import fetch_jobs_api as api_fetchers  # noqa: E402
from core import scrape_jobs  # noqa: E402
from core.location_filters import effective_regions, filter_by_regions  # noqa: E402
from core.sheets_manager import make_position_id  # noqa: E402

# Sources this handler can run. The first five are the free, no-auth public
# HTTP APIs. `linkedin` scrapes the public guest endpoint (slow — paginated
# with 3-6s delays, and rate-limited after ~10 pages per IP). `indeed` is
# MCP-backed and costs an agent turn (see `api/agent/mcp_sources.py`). Both of
# the latter are only reached when a search explicitly lists them; `manual` has
# no fetcher by design.
_FETCHERS = {
    Source.REMOTIVE.value: lambda kw: api_fetchers.fetch_remotive(kw, None),
    Source.REMOTEOK.value: lambda kw: api_fetchers.fetch_remoteok(kw),
    Source.HIMALAYAS.value: lambda kw: api_fetchers.fetch_himalayas(kw),
    Source.ARBEITNOW.value: lambda kw: api_fetchers.fetch_arbeitnow(kw),
    Source.JOBICY.value: lambda kw: api_fetchers.fetch_jobicy(kw, geo=""),
    Source.INDEED.value: lambda kw: fetch_indeed(kw),
    # Lambda, not a bare reference: `_fetch_linkedin` is defined below this dict.
    Source.LINKEDIN.value: lambda kw: _fetch_linkedin(kw),
}


def _fetch_linkedin(keywords: list[str]) -> list[dict[str, Any]]:
    """LinkedIn via the public guest endpoint (`core/scrape_jobs.py`).

    Unlike the API fetchers, `scrape_linkedin` takes ONE keyword string per
    call, so we loop and merge. `LINKEDIN_LOCATION` scopes the *query*; the
    region filter is applied afterwards by `handle`, uniformly across sources,
    so this function stays a plain fetcher.

    Descriptions are a second request per posting. `enrich_linkedin_descriptions`
    owns the anti-429 machinery (guest-cookie priming, a job-id cache under
    `data/cache/`, adaptive backoff) and gives up gracefully rather than
    failing the run, so a rate-limited pass still returns card metadata.
    It also strips the internal `_job_id` key — we strip it ourselves on the
    no-descriptions path, since it must never reach the normalized shape.
    """
    positions: list[dict[str, Any]] = []
    for kw in keywords:
        positions.extend(
            scrape_jobs.scrape_linkedin(
                kw,
                max_pages=LINKEDIN_MAX_PAGES,
                linkedin_location=LINKEDIN_LOCATION,
            )
        )
    # Dedupe before enriching so we never spend a detail request on a duplicate.
    positions = scrape_jobs.dedup(positions)

    if LINKEDIN_FETCH_DESCRIPTIONS:
        positions = scrape_jobs.enrich_linkedin_descriptions(positions)
    else:
        for pos in positions:
            pos.pop("_job_id", None)
    return positions


def _parse_date(value: object) -> date | None:
    text = str(value).strip() if value else ""
    if not text:
        return None
    text = text[:10]  # tolerate ISO datetimes / trailing time
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _get_or_create_company(session: Session, name: str, cache: dict[str, Company]) -> Company | None:
    key = (name or "").strip().lower()
    if not key:
        return None
    company = cache.get(key)
    if company is None:
        company = session.scalar(select(Company).where(func.lower(Company.name) == key))
        if company is None:
            company = Company(name=name.strip())
            session.add(company)
            session.flush()
        cache[key] = company
    return company


def handle(session: Session, job: Job, params: dict[str, Any], progress) -> dict[str, Any]:
    search_id = params["search_id"]
    search = session.get(Search, search_id)
    if search is None:
        raise ValueError(f"Search {search_id} not found")

    keywords = list(search.keywords or [])
    if not keywords:
        raise ValueError("Search has no keywords")

    # The SearchRun row is pre-created by the route (so POST /run can return its
    # id synchronously); we just attach this job and stamp the start time.
    run = session.get(SearchRun, params["search_run_id"])
    if run is None:
        raise ValueError(f"SearchRun {params['search_run_id']} not found")
    run.job_id = job.id
    run.started_at = datetime.now(UTC)

    # Only run sources this handler supports; skip others (recorded as skipped).
    requested = list(search.sources or [])
    runnable = [s for s in requested if s in _FETCHERS]
    skipped = [s for s in requested if s not in _FETCHERS]

    search.status = SearchStatus.RUNNING.value
    session.flush()

    stats: dict[str, dict[str, Any]] = {}
    for s in skipped:
        stats[s] = {"fetched": 0, "new": 0, "duplicates": 0, "errors": 0, "skipped": 1}

    # Geography: the search's own markets, else TARGET_REGION. Resolved once so
    # the run reports one consistent answer even if the env changes mid-run.
    regions = list(search.markets or [])
    active_regions = effective_regions(regions)

    company_cache: dict[str, Company] = {}
    # pids already linked to THIS run — a position surfaced by two sources (or
    # twice in one feed) must be linked once (composite PK is unique per run).
    linked: set[str] = set()
    total_sources = max(len(runnable), 1)
    today = date.today()
    total_new = 0

    try:
        for idx, source in enumerate(runnable):
            progress(idx / total_sources, f"{source}: fetching", stats=stats)
            source_stats: dict[str, Any] = {
                "fetched": 0, "new": 0, "duplicates": 0, "errors": 0,
                "filtered_out": 0,
            }
            try:
                fetched = _FETCHERS[source](keywords)
            except McpSourceUnavailable as exc:
                # Not an error: the connector just isn't set up in this
                # environment. Report it like any other unsupported source so
                # the run still reads as successful.
                source_stats["skipped"] = 1
                source_stats["reason"] = str(exc)
                stats[source] = source_stats
                skipped.append(source)
                progress((idx + 1) / total_sources, f"{source}: skipped ({exc})", stats=stats)
                continue
            except Exception as exc:  # noqa: BLE001 — one source failing must not kill the run
                source_stats["errors"] = 1
                stats[source] = source_stats
                progress((idx + 1) / total_sources, f"{source}: error ({exc})", stats=stats)
                continue

            # `fetched` stays the raw source count; the region drop is reported
            # next to it instead of being folded into it, so the funnel reads
            # "the source returned N, geography removed M".
            source_stats["fetched"] = len(fetched)
            if active_regions:
                eligible = filter_by_regions(fetched, regions)
                source_stats["filtered_out"] = len(fetched) - len(eligible)
                fetched = eligible

            for raw in fetched:
                role = raw.get("role", "")
                if not role:
                    continue
                company_name = raw.get("company", "")
                pid = make_position_id(company_name or "unknown", role)
                existing = session.get(Position, pid)

                if existing is not None:
                    # Known position (prior run / migration / earlier source this
                    # run): merge the source, count as duplicate, link once.
                    srcs = list(existing.sources or [])
                    if source not in srcs:
                        srcs.append(source)
                        existing.sources = srcs
                    source_stats["duplicates"] += 1
                    if pid not in linked:
                        _link(session, run.id, pid, source, is_new=False)
                        linked.add(pid)
                    continue

                company = _get_or_create_company(session, company_name, company_cache)
                position = Position(
                    id=pid,
                    company_id=company.id if company else None,
                    search_id=search.id,
                    source=source,
                    sources=[source],
                    dedupe_key=pid,
                    tipo=raw.get("tipo") or None,
                    role=role,
                    url=raw.get("url") or None,
                    location=raw.get("location") or None,
                    remote="Yes" if raw.get("remote") else None,
                    salary_raw=raw.get("salary") or None,
                    date_posted=_parse_date(raw.get("date_posted")),
                    date_discovered=today,
                    status=PositionStatus.DISCOVERED.value,
                    description=(raw.get("description") or None),
                    tags=list(raw.get("tags") or []),
                )
                session.add(position)
                session.flush()
                _synthesize_created_event(session, position)
                _link(session, run.id, pid, source, is_new=True)
                linked.add(pid)
                source_stats["new"] += 1
                total_new += 1

            stats[source] = source_stats
            # persist incrementally so partial results survive a later failure.
            run.stats = dict(stats)
            session.commit()
            dropped = source_stats["filtered_out"]
            note = f" ({dropped} outside {'/'.join(active_regions)})" if dropped else ""
            progress(
                (idx + 1) / total_sources,
                f"{source}: {source_stats['new']} new{note}",
                stats=stats,
            )
    except Exception:
        # Mark the search failed (its own committed state) before the runner
        # rolls back and records the job failure.
        session.rollback()
        failed = session.get(Search, search_id)
        if failed is not None:
            failed.status = SearchStatus.FAILED.value
            session.commit()
        raise

    # finalize
    run.finished_at = datetime.now(UTC)
    run.stats = dict(stats)
    total_found = sum(s.get("fetched", 0) for s in stats.values())
    search.status = SearchStatus.FINISHED.value
    search.total_found = (search.total_found or 0) + total_found
    search.total_new = (search.total_new or 0) + total_new
    search.last_run_at = datetime.now(UTC)
    session.flush()

    return {
        "search_run_id": run.id,
        "search_id": search.id,
        "total_new": total_new,
        "total_found": total_found,
        "total_filtered_out": sum(s.get("filtered_out", 0) for s in stats.values()),
        "regions": active_regions,
        "stats": stats,
        "skipped_sources": skipped,
    }


def _link(session: Session, run_id: int, position_id: str, source: str, is_new: bool) -> None:
    session.add(
        SearchRunPosition(
            search_run_id=run_id, position_id=position_id, source=source, is_new=is_new
        )
    )


def _synthesize_created_event(session: Session, position: Position) -> None:
    from api.models import PositionEvent
    from api.models.enums import Actor, PositionEventType

    session.add(
        PositionEvent(
            position_id=position.id,
            event_type=PositionEventType.CREATED.value,
            to_value=PositionStatus.DISCOVERED.value,
            payload={"source": position.source, "via": "search_run"},
            actor=Actor.SYSTEM.value,
            created_at=datetime.combine(position.date_discovered or date.today(), dtime.min, tzinfo=UTC),
        )
    )
