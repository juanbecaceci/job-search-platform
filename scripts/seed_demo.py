#!/usr/bin/env python3
"""Seed a throwaway database with a fully synthetic demo dataset.

This exists so the UI can be *seen* — in screenshots, or by anyone evaluating
the repo — without a real job search behind it. Every company, position, person
and document below is invented; the domains are all under ``.example``
(RFC 2606), so nothing here points at a real employer or posting.

It is **not** part of the normal setup path. ``seed_defaults.py`` seeds the
config a real install needs; this one seeds *content*, and you only want it in a
database you're happy to throw away.

Run it against a separate file, never your own DB::

    DB_PATH=data/app-demo.db python scripts/seed_demo.py

    # PowerShell
    $env:DB_PATH = "data/app-demo.db"; python scripts/seed_demo.py

Safety: the script refuses to touch a database that already holds positions or
profile data, because the obvious mistake here is running it with ``DB_PATH``
unset and burying a real search under demo rows. ``--force`` overrides the
refusal and is destructive — it deletes the demo-owned tables first.

Assumes ``alembic upgrade head`` and ``seed_defaults.py`` have already run
against the same target.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Repo root on the path so `import api...` resolves when run as a script.
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import delete, func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from api.config import DATABASE_URL  # noqa: E402
from api.db.engine import session_scope  # noqa: E402
from api.models import (  # noqa: E402
    Application,
    ChatMessage,
    ChatThread,
    Company,
    Document,
    ModuleMemory,
    PendingChange,
    Position,
    PositionEvent,
    ProfileBasics,
    ProfileSection,
    Search,
    SearchRun,
    SearchRunPosition,
)
from api.models.enums import (  # noqa: E402
    Actor,
    ChangeType,
    DocumentKind,
    MessageRole,
    Module,
    PendingChangeStatus,
    PositionEventType,
    PositionStatus,
    SalaryGate,
    ScoreCategory,
    SearchStatus,
    Source,
    Track,
)

TODAY = date.today()
NOW = datetime.now()


def _ago(days: int) -> date:
    return TODAY - timedelta(days=days)


def _slug(text: str) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in text]
    return "-".join(filter(None, "".join(keep).split("-")))


def _position_id(company: str, role: str) -> str:
    """Mirror the real slug shape: company + trimmed role + short hash."""
    digest = hashlib.sha1(f"{company}|{role}".encode()).hexdigest()[:6]
    role_part = "-".join(_slug(role).split("-")[:4])
    return f"{_slug(company)}-{role_part}-{digest}"


# ── The invented world ───────────────────────────────────────────────────────

COMPANIES = [
    ("Meridian Labs", "AI Infrastructure", "Series B (~120)", "https://meridianlabs.example"),
    ("Northwind Analytics", "Data & BI", "Series A (~60)", "https://northwind-analytics.example"),
    ("Kestrel Robotics", "Industrial Robotics", "200–500", "https://kestrelrobotics.example"),
    ("Lumen Health", "Digital Health", "Series A (~45)", "https://lumenhealth.example"),
    ("Tidewater Logistics", "Supply Chain SaaS", "Public", "https://tidewaterlogistics.example"),
    ("Beacon Payments", "Fintech", "Series C (~400)", "https://beaconpayments.example"),
    ("Cobalt Grid", "Energy / Cleantech", "Seed (~25)", "https://cobaltgrid.example"),
    ("Foxglove Studio", "Creative Technology", "20–50", "https://foxglovestudio.example"),
    ("Harbor Signal", "Cybersecurity", "Series A (~80)", "https://harborsignal.example"),
    ("Quill & Co", "E-commerce", "50–200", "https://quillandco.example"),
]

# (company, role, source, status, score, salary_raw, min, max, remote, posted_days_ago)
POSITIONS = [
    # ── Terminal / late pipeline ──
    ("Meridian Labs", "Senior Platform Engineer", Source.LINKEDIN, PositionStatus.OFFER_RECEIVED, 94.0, "USD 7,000–9,000 / month", 7000, 9000, "Remote (Global)", 34),
    ("Beacon Payments", "Backend Engineer, Payments Core", Source.REMOTIVE, PositionStatus.INTERVIEWING, 88.0, "USD 6,500–8,000 / month", 6500, 8000, "Remote (Americas)", 28),
    ("Harbor Signal", "Senior Software Engineer, Detection", Source.HIMALAYAS, PositionStatus.INTERVIEW_SCHEDULED, 86.0, "USD 6,000–7,500 / month", 6000, 7500, "Remote (Global)", 25),
    ("Northwind Analytics", "Data Platform Engineer", Source.REMOTIVE, PositionStatus.ACKNOWLEDGED, 81.0, "USD 5,500–7,000 / month", 5500, 7000, "Remote (Global)", 30),
    ("Tidewater Logistics", "Senior Backend Engineer", Source.LINKEDIN, PositionStatus.APPLIED, 84.0, "USD 6,000–7,200 / month", 6000, 7200, "Remote (Americas)", 21),
    ("Lumen Health", "Full-Stack Engineer (Python/React)", Source.JOBICY, PositionStatus.APPLIED, 78.0, "USD 5,000–6,200 / month", 5000, 6200, "Remote (Global)", 19),
    # ── Mid pipeline ──
    ("Cobalt Grid", "Founding Backend Engineer", Source.REMOTEOK, PositionStatus.READY_TO_APPLY, 82.0, "USD 5,800–7,000 / month", 5800, 7000, "Remote (Global)", 12),
    ("Quill & Co", "Senior Engineer, Order Systems", Source.ARBEITNOW, PositionStatus.CV_DRAFT, 76.0, "USD 5,200–6,400 / month", 5200, 6400, "Remote (EU/LATAM)", 14),
    ("Kestrel Robotics", "Backend Engineer, Fleet Services", Source.HIMALAYAS, PositionStatus.SHORTLISTED, 79.0, "USD 5,400–6,800 / month", 5400, 6800, "Remote (Global)", 11),
    ("Meridian Labs", "Developer Experience Engineer", Source.LINKEDIN, PositionStatus.SHORTLISTED, 74.0, "USD 5,000–6,500 / month", 5000, 6500, "Remote (Global)", 9),
    ("Foxglove Studio", "Senior Full-Stack Developer", Source.REMOTIVE, PositionStatus.EVALUATING, 71.0, "USD 4,800–6,000 / month", 4800, 6000, "Remote (Americas)", 8),
    ("Northwind Analytics", "Analytics Engineer", Source.JOBICY, PositionStatus.EVALUATING, 68.0, "USD 4,500–5,800 / month", 4500, 5800, "Remote (Global)", 7),
    # ── Terminal negatives (a real pipeline has them) ──
    ("Beacon Payments", "Staff Engineer, Risk", Source.LINKEDIN, PositionStatus.REJECTED, 83.0, "USD 7,500–9,500 / month", 7500, 9500, "Remote (Americas)", 45),
    ("Kestrel Robotics", "Principal Systems Engineer", Source.REMOTIVE, PositionStatus.GHOSTED, 72.0, "USD 6,800–8,500 / month", 6800, 8500, "Hybrid (Berlin)", 52),
    ("Tidewater Logistics", "Engineering Manager, Platform", Source.LINKEDIN, PositionStatus.WITHDRAWN, 66.0, "USD 7,000–8,800 / month", 7000, 8800, "Remote (US only)", 40),
    # ── Fresh, unevaluated ──
    ("Lumen Health", "Backend Engineer, Integrations", Source.ARBEITNOW, PositionStatus.DISCOVERED, None, "USD 4,800–6,000 / month", 4800, 6000, "Remote (Global)", 3),
    ("Harbor Signal", "Platform Engineer", Source.REMOTEOK, PositionStatus.DISCOVERED, None, None, None, None, "Remote (Global)", 2),
    ("Cobalt Grid", "Senior Data Engineer", Source.HIMALAYAS, PositionStatus.DISCOVERED, None, "USD 5,000–6,500 / month", 5000, 6500, "Remote (Global)", 4),
    ("Quill & Co", "Backend Engineer, Catalog", Source.JOBICY, PositionStatus.DISCOVERED, None, "USD 4,200–5,400 / month", 4200, 5400, "Remote (EU/LATAM)", 1),
    ("Foxglove Studio", "Node.js Engineer (Contract)", Source.REMOTEOK, PositionStatus.DISCOVERED, None, "USD 45–60 / hour", 4500, 6000, "Remote (Global)", 5),
    ("Meridian Labs", "Site Reliability Engineer", Source.REMOTIVE, PositionStatus.DISCOVERED, None, "USD 6,000–7,500 / month", 6000, 7500, "Remote (Global)", 2),
    ("Northwind Analytics", "Senior Python Engineer", Source.LINKEDIN, PositionStatus.DISCOVERED, None, None, None, None, "Remote (Americas)", 6),
    ("Beacon Payments", "Senior Backend Engineer, Ledger", Source.LINKEDIN, PositionStatus.DISCOVERED, None, "USD 6,200–7,800 / month", 6200, 7800, "Remote (Americas)", 3),
    ("Tidewater Logistics", "API Platform Engineer", Source.REMOTIVE, PositionStatus.DISCOVERED, None, "USD 5,600–7,000 / month", 5600, 7000, "Remote (Global)", 1),
    ("Kestrel Robotics", "Backend Engineer, Telemetry", Source.ARBEITNOW, PositionStatus.DISCOVERED, None, "USD 5,000–6,300 / month", 5000, 6300, "Remote (EU)", 4),
    ("Harbor Signal", "Senior Backend Engineer, Ingest", Source.HIMALAYAS, PositionStatus.DISCOVERED, None, "USD 5,800–7,200 / month", 5800, 7200, "Remote (Global)", 2),
    ("Lumen Health", "Data Engineer, Clinical Records", Source.JOBICY, PositionStatus.DISCOVERED, None, "USD 4,600–5,900 / month", 4600, 5900, "Remote (Global)", 5),
    ("Quill & Co", "Platform Engineer, Checkout", Source.REMOTEOK, PositionStatus.DISCOVERED, None, "USD 4,900–6,100 / month", 4900, 6100, "Remote (EU/LATAM)", 3),
]

# How long ago a position was *discovered*, by pipeline depth. Discovery is
# independent of when the role was posted — a run surfaces old and new postings
# alike — but it can't postdate the application, so late-stage rows are older.
#
# Both analytics windows are anchored here: the dashboard summarises the last
# 7 days (so the shallow end feeds it) and the funnel the last 30 (so every
# value below, plus the `idx % 4` jitter, stays under 30 — otherwise the
# late-stage rows fall out and the funnel reports zero offers).
DISCOVERY_DAYS = {
    PositionStatus.GHOSTED: 27,
    PositionStatus.REJECTED: 26,
    PositionStatus.OFFER_RECEIVED: 26,
    PositionStatus.WITHDRAWN: 25,
    PositionStatus.INTERVIEWING: 24,
    PositionStatus.INTERVIEW_SCHEDULED: 22,
    PositionStatus.ACKNOWLEDGED: 24,
    PositionStatus.APPLIED: 21,
    PositionStatus.CV_DRAFT: 14,
    PositionStatus.READY_TO_APPLY: 13,
    PositionStatus.SHORTLISTED: 5,
    PositionStatus.EVALUATING: 4,
    PositionStatus.DISCOVERED: 2,
}

# Days between discovery and the position's most recent activity. `updated_at`
# is what the stale detector reads (`GET /analytics/stale`), so leaving it at
# insert-time would make every application look freshly touched and the stale
# list come back empty.
# The chain of dates hanging off discovery: apply a couple of days later, hear
# back about a week after that, interview a few days after the reply.
APPLY_LAG, RESPONSE_LAG, INTERVIEW_LAG = 2, 7, 5

APPLIED_STATES = {
    PositionStatus.APPLIED, PositionStatus.ACKNOWLEDGED,
    PositionStatus.INTERVIEW_SCHEDULED, PositionStatus.INTERVIEWING,
    PositionStatus.OFFER_RECEIVED, PositionStatus.REJECTED,
    PositionStatus.GHOSTED, PositionStatus.WITHDRAWN,
}
# Ghosted is the point: applied, never heard back.
_GOT_RESPONSE = APPLIED_STATES - {PositionStatus.APPLIED, PositionStatus.GHOSTED}
_GOT_INTERVIEW = {
    PositionStatus.INTERVIEW_SCHEDULED, PositionStatus.INTERVIEWING,
    PositionStatus.OFFER_RECEIVED,
}


def _timeline(status: PositionStatus, discovered: int) -> dict[str, int | None]:
    """Days-ago for each milestone a position at this status has reached."""
    applied = max(1, discovered - APPLY_LAG)
    response = max(1, applied - RESPONSE_LAG) if status in _GOT_RESPONSE else None
    interview = (
        max(1, response - INTERVIEW_LAG)
        if response is not None and status in _GOT_INTERVIEW
        else None
    )
    return {"applied": applied, "response": response, "interview": interview}


def _last_activity(status: PositionStatus, discovered: int) -> datetime:
    """Timestamp of the newest real event on a position (default: discovery)."""
    if status not in APPLIED_STATES:
        return NOW - timedelta(days=discovered)
    t = _timeline(status, discovered)
    newest = t["interview"] or t["response"] or t["applied"]
    return NOW - timedelta(days=newest)


CRITERION_RATIONALES = {
    "profile_alignment": (
        "Core responsibilities map directly onto the target role: distributed "
        "backend services, API design and data-heavy workloads."
    ),
    "remote_modality": (
        "Advertised as remote with an overlap window that works from the "
        "profile's timezone; no relocation implied."
    ),
    "seniority_growth": (
        "Senior scope with explicit ownership of a service area, and a stated "
        "path toward technical leadership."
    ),
    "company_stability": (
        "Funded, with public traction signals and a verifiable engineering "
        "presence."
    ),
}


def _evaluation(score: float) -> dict:
    """Build a plausible per-criterion breakdown that averages near `score`."""
    base = score / 20.0  # 0–100 → 0–5
    tilt = {"profile_alignment": 0.4, "remote_modality": 0.2, "seniority_growth": -0.2, "company_stability": -0.4}
    weights = {"profile_alignment": 0.4, "remote_modality": 0.25, "seniority_growth": 0.2, "company_stability": 0.15}
    out = {}
    for cid, weight in weights.items():
        raw = max(1.0, min(5.0, round(base + tilt[cid], 1)))
        out[cid] = {"score": raw, "weight": weight, "rationale": CRITERION_RATIONALES[cid]}
    return out


def _category(score: float) -> str:
    if score >= 80:
        return ScoreCategory.EXCELLENT.value
    if score >= 60:
        return ScoreCategory.GOOD.value
    if score >= 45:
        return ScoreCategory.ACCEPTABLE.value
    return ScoreCategory.DISCARD.value


PROFILE_SECTIONS = [
    ("summary", "Professional summary", """Backend-leaning full-stack engineer with 8 years building and operating
distributed services in Python and TypeScript. Comfortable owning a service
end to end: schema, API, deployment and the on-call that follows.

Looking for a senior individual-contributor role on a remote-first team,
ideally on data-heavy or platform work."""),
    ("experience", "Experience", """### Senior Backend Engineer — Ridgeline Software *(2022 – present)*
- Owns the billing and entitlements services behind a multi-tenant SaaS product.
- Led the migration from a single Postgres instance to per-tenant schemas,
  cutting the p95 of the heaviest report from 4.2s to 600ms.
- Mentors two mid-level engineers; runs the team's design-review rotation.

### Backend Engineer — Halcyon Data *(2019 – 2022)*
- Built the ingestion pipeline that normalised third-party feeds into a single
  event schema; it still carries ~40M events/day.
- Introduced contract tests between services, which removed the class of
  breakage that had caused most of the team's rollbacks.

### Software Developer — Atlas Interactive *(2018 – 2019)*
- Full-stack feature work on a customer-facing dashboard (Django + React)."""),
    ("skills", "Skills", """**Languages** — Python, TypeScript, SQL, Go (working knowledge)
**Backend** — FastAPI, Django, PostgreSQL, Redis, SQLAlchemy, Alembic
**Frontend** — React, Vite, TanStack Query
**Infra** — Docker, GitHub Actions, Terraform (basic), AWS (ECS, RDS, S3)
**Practices** — trunk-based development, contract testing, observability-first"""),
    ("education", "Education", """**BSc, Computer Science** — Universidad Nacional del Litoral, 2017"""),
    ("preferences", "Search preferences", """- **Target roles:** Senior Backend Engineer, Platform Engineer, Data Platform Engineer
- **Modality:** remote-first; open to quarterly travel
- **Compensation floor:** USD 5,000 / month
- **Avoid:** mandatory on-site, rotating night on-call, agency staffing with
  undisclosed end clients"""),
]

MODULE_MEMORY = {
    Module.SCORING.value: """- The user consistently down-ranks roles that advertise "remote" but restrict
  hiring to a single country. Treat an explicit country lock as a 2 on
  `remote_modality`, not a 3.
- Agency/staffing listings that never name the end client have been rejected
  every time they reached shortlist. Cap `company_stability` at 2 for those.""",
    Module.POSITIONS.value: """- The user prefers the summary to lead with what the team actually owns, not
  with the company's marketing line.
- Do not mark a position `Ready to Apply` until both the CV and the cover
  letter exist — the user has corrected this twice.""",
    Module.PROFILE.value: """- Never invent metrics. If a bullet needs a number the profile doesn't have,
  write the bullet without one and flag it instead.
- The user writes impact-first bullets ("cut p95 from 4.2s to 600ms by …"),
  not responsibility-first ("responsible for performance").""",
    Module.SEARCHES.value: """- Keyword sets that include "engineer" alone return too much noise; the user
  prefers pairing it with a domain word ("platform", "data", "backend").
- Runs on Friday afternoons return mostly reposts. Prefer Monday/Tuesday.""",
}


def _wipe(session: Session) -> None:
    """Delete only the tables this script owns. Used by --force."""
    for model in (
        SearchRunPosition, SearchRun, PendingChange, ChatMessage, ChatThread,
        Application, Document, PositionEvent, Position, Search, Company,
        ProfileSection, ProfileBasics,
    ):
        session.execute(delete(model))


def _looks_occupied(session: Session) -> str | None:
    """Return a human reason if the target DB already holds real content."""
    positions = session.scalar(select(func.count()).select_from(Position)) or 0
    sections = session.scalar(select(func.count()).select_from(ProfileSection)) or 0
    if positions or sections:
        return f"{positions} position(s) and {sections} profile section(s) already present"
    return None


def seed(session: Session) -> list[str]:
    out: list[str] = []

    # ── Companies ──
    companies: dict[str, Company] = {}
    for name, industry, size, website in COMPANIES:
        company = Company(name=name, industry=industry, size=size, website=website)
        session.add(company)
        companies[name] = company
    session.flush()
    out.append(f"companies: {len(companies)}")

    # ── The search that found them ──
    search = Search(
        name="Senior Backend / Platform — remote",
        keywords=["backend engineer", "platform engineer", "python"],
        sources=[Source.REMOTIVE.value, Source.REMOTEOK.value, Source.HIMALAYAS.value,
                 Source.ARBEITNOW.value, Source.JOBICY.value, Source.LINKEDIN.value],
        posted_within_days=30,
        markets=["worldwide"],
        status=SearchStatus.ANALYZED.value,
        total_found=len(POSITIONS),
        total_new=len(POSITIONS),
        total_evaluated=sum(1 for p in POSITIONS if p[4] is not None),
        avg_score=round(
            sum(p[4] for p in POSITIONS if p[4] is not None)
            / max(1, sum(1 for p in POSITIONS if p[4] is not None)), 1
        ),
        last_run_at=NOW - timedelta(days=1),
    )
    session.add(search)
    session.flush()

    run = SearchRun(
        search_id=search.id,
        started_at=NOW - timedelta(days=1, minutes=4),
        finished_at=NOW - timedelta(days=1),
        stats={
            "remotive": {"fetched": 41, "new": 4, "duplicates": 37, "errors": 0},
            "remoteok": {"fetched": 28, "new": 3, "duplicates": 25, "errors": 0},
            "himalayas": {"fetched": 33, "new": 3, "duplicates": 30, "errors": 0},
            "arbeitnow": {"fetched": 19, "new": 2, "duplicates": 17, "errors": 0},
            "jobicy": {"fetched": 22, "new": 3, "duplicates": 19, "errors": 0},
            "linkedin": {"fetched": 60, "new": 7, "duplicates": 53, "errors": 0},
        },
    )
    session.add(run)
    session.flush()

    # ── Positions ──
    ranked = sorted(
        [p for p in POSITIONS if p[4] is not None], key=lambda p: p[4], reverse=True
    )
    rank_of = {(p[0], p[1]): i + 1 for i, p in enumerate(ranked)}

    created: dict[str, Position] = {}
    for idx, (company_name, role, source, status, score, salary_raw, smin, smax, remote, posted) in enumerate(POSITIONS):
        pid = _position_id(company_name, role)
        # Never earlier than the posting itself; `+ idx % 4` just spreads the
        # dates so the timeline doesn't look generated.
        discovered = min(DISCOVERY_DAYS[status] + idx % 4, posted)
        gate = (
            SalaryGate.NEEDS_VALIDATION.value if smin is None
            else SalaryGate.PASS.value if smin >= 3500
            else SalaryGate.FAIL.value
        )
        position = Position(
            id=pid,
            company_id=companies[company_name].id,
            search_id=search.id,
            source=source.value,
            sources=[source.value],
            dedupe_key=f"{_slug(company_name)}|{_slug(role)}",
            tipo="full-time",
            track=Track.FULL_TIME.value,
            role=role,
            url=f"{companies[company_name].website}/careers/{_slug(role)}",
            location=remote,
            remote=remote,
            salary_raw=salary_raw,
            salary_min_usd_month=smin,
            salary_max_usd_month=smax,
            salary_gate=gate,
            date_posted=_ago(posted),
            date_discovered=_ago(discovered),
            score=score,
            score_category=_category(score) if score is not None else None,
            rank=rank_of.get((company_name, role)),
            scoring_config_version=1 if score is not None else None,
            evaluation=_evaluation(score) if score is not None else None,
            summary=(
                f"{company_name} is hiring a {role.lower()}. The posting emphasises "
                "ownership of a service area end to end, with the team running what "
                "it builds. Stack overlaps the profile closely on the backend side."
            ) if score is not None else None,
            recommended_action=(
                "Apply immediately, prioritize over the rest." if (score or 0) >= 80
                else "Apply, preparing the submission well." if (score or 0) >= 60
                else "Apply only if no better options are in progress."
            ) if score is not None else None,
            status=status.value,
            # Plain text on purpose: the detail view renders this with
            # `white-space: pre-wrap` and no markdown pass, so headings would
            # show up as literal `###`.
            description=(
                f"About the role\n\n{company_name} is looking for a {role} to join a "
                "remote-first engineering team. You'll join a group that owns its "
                "services end to end and keeps the on-call for them.\n\n"
                "What you'll do\n\n"
                "  • Own one or more backend services end to end, from schema to on-call.\n"
                "  • Design APIs consumed by internal teams and external partners.\n"
                "  • Improve the reliability and cost profile of data-heavy workloads.\n\n"
                "What we're looking for\n\n"
                "  • 5+ years building production backend systems.\n"
                "  • Strong Python or TypeScript, and comfort with SQL and schema design.\n"
                "  • Experience operating what you ship.\n\n"
                "We're remote-first, asynchronous by default, and we review design "
                "documents rather than run interviews on a whiteboard."
            ),
            tags=["python", "remote", "backend"],
            # Explicit, so the row lands in the past: `server_default=now()` only
            # fires when the column is omitted from the INSERT.
            created_at=NOW - timedelta(days=discovered),
            updated_at=_last_activity(status, discovered),
        )
        session.add(position)
        created[pid] = position

        session.add(PositionEvent(
            position_id=pid, event_type=PositionEventType.CREATED.value,
            to_value=PositionStatus.DISCOVERED.value, actor=Actor.SYSTEM.value,
        ))
        if score is not None:
            session.add(PositionEvent(
                position_id=pid, event_type=PositionEventType.SCORE_CHANGE.value,
                from_value=None, to_value=str(score), actor=Actor.AGENT.value,
                payload={"category": _category(score)},
            ))
        if status is not PositionStatus.DISCOVERED:
            session.add(PositionEvent(
                position_id=pid, event_type=PositionEventType.STATUS_CHANGE.value,
                from_value=PositionStatus.DISCOVERED.value, to_value=status.value,
                actor=Actor.USER.value,
            ))
        session.add(SearchRunPosition(
            search_run_id=run.id, position_id=pid, source=source.value, is_new=True,
        ))
    session.flush()
    out.append(f"positions: {len(created)} across {len({p[3] for p in POSITIONS})} statuses")

    # ── Documents + applications for anything that got that far ──
    doc_states = APPLIED_STATES | {PositionStatus.CV_DRAFT, PositionStatus.READY_TO_APPLY}

    docs = apps = 0
    for idx, (company_name, role, _s, status, _sc, *_rest) in enumerate(POSITIONS):
        if status not in doc_states:
            continue
        pid = _position_id(company_name, role)
        posted = _rest[-1]
        discovered = min(DISCOVERY_DAYS[status] + idx % 4, posted)
        cv = Document(
            position_id=pid, kind=DocumentKind.CV.value, version=1,
            content_md=(
                f"# Alex Doe\n\n*Senior Backend Engineer — tailored for {role} at "
                f"{company_name}*\n\n## Summary\n\nBackend-leaning full-stack engineer "
                "with 8 years building distributed services in Python and TypeScript…\n\n"
                "## Selected experience\n\n**Ridgeline Software — Senior Backend Engineer**\n"
                "- Cut the p95 of the heaviest reporting query from 4.2s to 600ms by moving "
                "to per-tenant schemas.\n"
            ),
            status="final", created_by=Actor.AGENT.value,
        )
        cl = Document(
            position_id=pid, kind=DocumentKind.COVER_LETTER.value, version=1,
            content_md=(
                f"Dear {company_name} hiring team,\n\nYour {role} posting describes a team "
                "that owns its services end to end — schema, API and the on-call that "
                "follows. That is the shape of the work I've been doing for the last four "
                "years…\n"
            ),
            status="final", created_by=Actor.AGENT.value,
        )
        session.add_all([cv, cl])
        session.flush()
        docs += 2

        if status in APPLIED_STATES:
            # Same chain `_last_activity` reads, so the dates on the position
            # detail agree with the timestamp the stale detector sees.
            t = _timeline(status, discovered)
            session.add(Application(
                position_id=pid,
                cv_document_id=cv.id,
                cover_letter_document_id=cl.id,
                date_applied=_ago(t["applied"]),
                applied_via="Company careers page",
                response_date=_ago(t["response"]) if t["response"] else None,
                interview_date=_ago(t["interview"]) if t["interview"] else None,
                outcome=(
                    "Offer received — pending decision" if status is PositionStatus.OFFER_RECEIVED
                    else "Rejected after the technical screen" if status is PositionStatus.REJECTED
                    else "No response after two follow-ups" if status is PositionStatus.GHOSTED
                    else "Withdrew — on-site requirement surfaced late" if status is PositionStatus.WITHDRAWN
                    else None
                ),
                follow_up_due=_ago(-4) if status is PositionStatus.APPLIED else None,
                notes="Referred by a former colleague." if status is PositionStatus.INTERVIEWING else None,
            ))
            apps += 1
    out.append(f"documents: {docs}, applications: {apps}")

    # ── Profile ──
    session.add(ProfileBasics(
        id=1,
        full_name="Alex Doe",
        headline="Senior Backend Engineer — distributed systems, Python & TypeScript",
        email="alex.doe@example.com",
        phone="+00 000 000 0000",
        location="Remote — UTC-3",
        linkedin_url="https://www.linkedin.com/in/example-alex-doe",
        portfolio_url="https://alexdoe.example",
    ))
    for order, (slug, title, content) in enumerate(PROFILE_SECTIONS):
        session.add(ProfileSection(
            slug=slug, title=title, content_md=content,
            sort_order=order, updated_by=Actor.USER.value,
        ))
    out.append(f"profile: basics + {len(PROFILE_SECTIONS)} sections")

    # ── A chat thread with pending proposals (the HITL tray) ──
    thread = ChatThread(title="Tighten the scoring weights", module=Module.SCORING.value)
    session.add(thread)
    session.flush()

    session.add_all([
        ChatMessage(
            thread_id=thread.id, role=MessageRole.USER.value,
            content="Remote-only roles that are actually locked to one country keep "
                    "scoring too high. Can you fix that?",
        ),
        ChatMessage(
            thread_id=thread.id, role=MessageRole.ASSISTANT.value,
            content="Agreed — three of the last five shortlisted roles turned out to be "
                    "country-locked. I'd raise the weight of `remote_modality` from 0.25 "
                    "to 0.30 (taking 0.05 off `company_stability`), and add an explicit "
                    "hint so a single-country lock scores a 2 rather than a 3.\n\n"
                    "I've proposed both changes for your approval.",
            pending_change_ids=[1, 2],
        ),
    ])

    session.add_all([
        PendingChange(
            thread_id=thread.id, module=Module.SCORING.value,
            change_type=ChangeType.UPDATE.value, target_table="scoring_configs", target_id="1",
            summary="Raise the weight of `remote_modality` to 0.30, offset against `company_stability`.",
            diff=[
                {"field": "criteria[remote_modality].weight", "from": 0.25, "to": 0.30},
                {"field": "criteria[company_stability].weight", "from": 0.15, "to": 0.10},
            ],
            status=PendingChangeStatus.PENDING.value,
        ),
        PendingChange(
            thread_id=thread.id, module=Module.SCORING.value,
            change_type=ChangeType.UPDATE.value, target_table="scoring_configs", target_id="1",
            summary="Score a single-country hiring lock as a 2 on `remote_modality`.",
            diff=[{
                "field": "criteria[remote_modality].hints.2",
                "from": "Demanding hybrid, unclear remote policy, or frequent presence required.",
                "to": "Demanding hybrid, unclear remote policy, frequent presence required, "
                      "or 'remote' restricted to a single country the user can't be hired in.",
            }],
            status=PendingChangeStatus.PENDING.value,
        ),
        PendingChange(
            module=Module.PROFILE.value,
            change_type=ChangeType.UPDATE.value, target_table="profile_sections", target_id="3",
            summary="Add Terraform and GitHub Actions to the infra line in Skills.",
            diff=[{
                "field": "content_md",
                "from": "**Infra** — Docker, AWS (ECS, RDS, S3)",
                "to": "**Infra** — Docker, GitHub Actions, Terraform (basic), AWS (ECS, RDS, S3)",
            }],
            status=PendingChangeStatus.PENDING.value,
        ),
    ])
    out.append("chat: 1 thread, 2 messages, 3 pending changes")

    # ── Module memory (what the agent has learned) ──
    touched = 0
    for module, content in MODULE_MEMORY.items():
        memory = session.get(ModuleMemory, module)
        if memory is None:
            memory = ModuleMemory(module=module)
            session.add(memory)
        memory.content_md = content
        memory.updated_by = Actor.AGENT.value
        touched += 1
    out.append(f"module memories: {touched} populated")

    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--force", action="store_true",
        help="delete existing demo content first (DESTRUCTIVE — never point this at real data)",
    )
    args = parser.parse_args()

    print(f"Target: {DATABASE_URL}")
    if "app-demo" not in DATABASE_URL and not args.force:
        print(
            "\n  Refusing to run: the target doesn't look like a demo database.\n"
            "  Set DB_PATH to a throwaway file whose name contains 'app-demo', e.g.\n"
            "      DB_PATH=data/app-demo.db python scripts/seed_demo.py\n"
            "  (--force overrides this, and will delete existing rows.)",
            file=sys.stderr,
        )
        return 1

    with session_scope() as session:
        occupied = _looks_occupied(session)
        if occupied and not args.force:
            print(
                f"\n  Refusing to run: {occupied}.\n"
                "  Seed a fresh database, or pass --force to delete what's there first.",
                file=sys.stderr,
            )
            return 1
        if args.force:
            _wipe(session)
            print("  --force: cleared existing demo content")
        outcomes = seed(session)

    print("Demo seed complete:")
    for line in outcomes:
        print(f"  - {line}")
    print("\nStart the API against it with the same DB_PATH, e.g.")
    print("  DB_PATH=data/app-demo.db python -m uvicorn api.main:app --port 8000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
