"""Enumerations from PLATFORM_SPEC.md §3.

These are `str, Enum` so they serialize as their string value and compare
equal to plain strings. Columns store them as ``String`` (SQLite doesn't
enforce native enums and the value set may evolve); these classes are the
single source of truth for validation at the Pydantic/service layer and for
documenting the allowed values next to the models.
"""

from __future__ import annotations

from enum import Enum


class PositionStatus(str, Enum):
    """The 15-state application pipeline (ordered), incl. 3 terminal states."""

    DISCOVERED = "Discovered"
    EVALUATING = "Evaluating"
    SHORTLISTED = "Shortlisted"
    CV_DRAFT = "CV Draft"
    READY_TO_APPLY = "Ready to Apply"
    APPLIED = "Applied"
    ACKNOWLEDGED = "Acknowledged"
    INTERVIEW_SCHEDULED = "Interview Scheduled"
    INTERVIEWING = "Interviewing"
    OFFER_RECEIVED = "Offer Received"
    NEGOTIATING = "Negotiating"
    ACCEPTED = "Accepted"
    # Terminal
    REJECTED = "Rejected"
    WITHDRAWN = "Withdrawn"
    GHOSTED = "Ghosted"


# Ordered forward pipeline (excludes terminal states) — used for validating
# status transitions and rendering the board columns in order.
PIPELINE_ORDER: tuple[PositionStatus, ...] = (
    PositionStatus.DISCOVERED,
    PositionStatus.EVALUATING,
    PositionStatus.SHORTLISTED,
    PositionStatus.CV_DRAFT,
    PositionStatus.READY_TO_APPLY,
    PositionStatus.APPLIED,
    PositionStatus.ACKNOWLEDGED,
    PositionStatus.INTERVIEW_SCHEDULED,
    PositionStatus.INTERVIEWING,
    PositionStatus.OFFER_RECEIVED,
    PositionStatus.NEGOTIATING,
    PositionStatus.ACCEPTED,
)

TERMINAL_STATUSES: frozenset[PositionStatus] = frozenset(
    {PositionStatus.REJECTED, PositionStatus.WITHDRAWN, PositionStatus.GHOSTED}
)


class Source(str, Enum):
    REMOTIVE = "remotive"
    REMOTEOK = "remoteok"
    HIMALAYAS = "himalayas"
    ARBEITNOW = "arbeitnow"
    JOBICY = "jobicy"
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    MANUAL = "manual"


class JobType(str, Enum):
    """`tipo` — the kind of engagement a position is."""

    FULL_TIME = "full-time"
    GIG = "gig"
    FREELANCE = "freelance"


class Track(str, Enum):
    """Ranking track a position competes in."""

    FULL_TIME = "full-time"
    GIG_FREELANCE = "gig-freelance"


class SalaryGate(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NEEDS_VALIDATION = "NEEDS VALIDATION"  # unpublished salary


class ScoreCategory(str, Enum):
    """The four bands a score falls into.

    Note these do **not** exhaust `positions.score_category`: the evaluator also
    writes two outcome markers that aren't score bands — `NEEDS VALIDATION`
    (scored, but the salary was unpublished) and `BELOW SALARY FLOOR` (failed
    the eliminatory gate). See `SCORE_CATEGORY_MARKERS` below and
    `api/jobs/handlers/evaluate_batch.py`.
    """

    EXCELLENT = "EXCELLENT"  # 80–100
    GOOD = "GOOD"  # 60–79
    ACCEPTABLE = "ACCEPTABLE"  # 45–59
    DISCARD = "DISCARD"  # 0–44


# Written into `positions.score_category` in place of a band when the salary
# gate decides the outcome. Kept next to the enum because the UI colors and the
# spec's value list have to account for them.
SCORE_CATEGORY_NEEDS_VALIDATION = "NEEDS VALIDATION"
SCORE_CATEGORY_BELOW_FLOOR = "BELOW SALARY FLOOR"
SCORE_CATEGORY_MARKERS: frozenset[str] = frozenset(
    {SCORE_CATEGORY_NEEDS_VALIDATION, SCORE_CATEGORY_BELOW_FLOOR}
)


class SearchStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    FINISHED = "finished"
    ANALYZED = "analyzed"
    FAILED = "failed"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AsyncJobType(str, Enum):
    """`job.type` — the async work catalog run by the JobRunner."""

    SEARCH_RUN = "search_run"
    EVALUATE_BATCH = "evaluate_batch"
    GENERATE_DOCUMENT = "generate_document"
    EXPORT_DOCUMENT = "export_document"
    UPLOAD_DRIVE = "upload_drive"
    RESEARCH_COMPANY = "research_company"
    AGENT_CHAT = "agent_chat"
    IMPORT_CV = "import_cv"
    SHEETS_EXPORT = "sheets_export"


class PendingChangeStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    FAILED = "failed"
    EXPIRED = "expired"


class ChangeType(str, Enum):
    UPDATE = "update"
    CREATE = "create"
    DELETE = "delete"
    ACTION = "action"


class Module(str, Enum):
    PROFILE = "profile"
    TEMPLATES = "templates"
    SCORING = "scoring"
    SEARCHES = "searches"
    POSITIONS = "positions"
    DOCUMENTS = "documents"
    ANALYTICS = "analytics"
    ONBOARDING = "onboarding"


class DocumentKind(str, Enum):
    CV = "cv"
    COVER_LETTER = "cover_letter"
    COMPANY_RESEARCH = "company_research"


class Actor(str, Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class PositionEventType(str, Enum):
    """`position_event.event_type` (PLATFORM_SPEC.md §4.2)."""

    CREATED = "created"
    STATUS_CHANGE = "status_change"
    SCORE_CHANGE = "score_change"
    FIELD_UPDATE = "field_update"
    NOTE = "note"
    DOCUMENT_GENERATED = "document_generated"
    APPLICATION_UPDATE = "application_update"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
