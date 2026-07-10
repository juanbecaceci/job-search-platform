"""ChangeApplier — the ONLY code that applies agent-proposed changes to domain
tables, and only when a user approves (DECISIONS #6).

`apply(session, change, runner)` dispatches on `target_table` / `change_type`,
mutates the DB inside the caller's transaction, and returns a small result dict.
Anything it doesn't explicitly support raises — the change is never applied
"loosely". The agent's output reached here only as a `pending_changes` row; this
is the human-approved gate.

Supported in v1:
  scoring_configs (update)  → new active version with dotted-path edits applied
  module_memories (update)  → set content_md (target_id = module)
  positions       (update)  → whitelisted field edits (+ history event)
  profile_basics  (update)  → single-row field edits
  profile_sections(update)  → field edits by id
  profile_sections(create)  → new section (the onboarding CV import path)
  profile_sections(delete)  → drop a section by id
  templates       (update)  → new ACTIVE version (never edits one in place)
  searches        (update)  → config only (name/keywords/sources/markets/recency)
  companies       (update)  → industry/size/website/research_md (not `name`)
  applications    (update)  → dates, contact, outcome, notes
  documents       (update)  → content_md/status (invalidates stale exports)
  <any>           (action)  → dispatch a job (e.g. create_and_run_search)

`SUPPORTED_TARGETS` / `is_supported()` expose that catalog so the chat layer can
reject an unsupported proposal when it's parsed, instead of letting it sit in
the tray and fail on approve.

Note on authorship: a proposal the user rewrote before approving
(`PATCH /changes/{id}` sets `edited_at`) is applied as `updated_by="user"` —
see `_authorship`. Direct form edits don't come through here at all; the
profile router writes those straight (DECISIONS #19).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.models import (
    Application,
    Company,
    Document,
    ModuleMemory,
    PendingChange,
    Position,
    PositionEvent,
    ProfileBasics,
    ProfileSection,
    ScoringConfig,
    Search,
    Template,
    TemplateVersion,
)
from api.models.enums import (
    Actor,
    AsyncJobType,
    PositionEventType,
    PositionStatus,
    SearchStatus,
    Source,
)


class ChangeApplyError(Exception):
    """Raised when a change can't be applied (unsupported/invalid)."""


_POSITION_EDITABLE = {
    "role", "url", "location", "remote", "tipo", "track", "salary_raw",
    "salary_min_usd_month", "salary_max_usd_month", "description", "tags",
    "notes", "status",
}
_PROFILE_BASICS_EDITABLE = {
    "full_name", "headline", "email", "phone", "location", "linkedin_url", "portfolio_url",
}
_PROFILE_SECTION_EDITABLE = {"title", "content_md", "sort_order", "slug"}
# Search *config* only. Metrics (total_found, avg_score, …) and `status` are
# derived from runs — the agent proposing those would be inventing history.
_SEARCH_EDITABLE = {"name", "keywords", "sources", "posted_within_days", "markets"}
# `name` is deliberately excluded: the Sheets migration and the fetchers dedupe
# companies by name, so renaming one splits its position history.
_COMPANY_EDITABLE = {"industry", "size", "website", "research_md"}
_APPLICATION_EDITABLE = {
    "date_applied", "applied_via", "contact", "response_date",
    "interview_date", "outcome", "follow_up_due", "notes",
}
_APPLICATION_DATES = {"date_applied", "response_date", "interview_date", "follow_up_due"}
# Binary paths/flags are set by the export job, never proposed.
_DOCUMENT_EDITABLE = {"content_md", "status"}
_TEMPLATE_EDITABLE = {"content_md", "change_note"}

_DOCUMENT_STATUSES = {"draft", "final", "sent"}

# What `apply` can actually write, as (target_table -> {change_types}). The chat
# layer checks this when a proposal is parsed so an unsupported target is caught
# on the spot instead of at approve time (which is how a reasonable-looking
# proposal used to sit in the tray and then fail).
SUPPORTED_TARGETS: dict[str, set[str]] = {
    "scoring_configs": {"update"},
    "module_memories": {"update"},
    "positions": {"update"},
    "profile_basics": {"update"},
    "profile_sections": {"create", "update", "delete"},
    "templates": {"update"},
    "searches": {"update"},
    "companies": {"update"},
    "applications": {"update"},
    "documents": {"update"},
}


def is_supported(target_table: str | None, change_type: str) -> bool:
    """Can `apply` handle this (table, change_type) pair?

    `action` changes carry no target table — they're validated by name inside
    `_apply_action` instead.
    """
    if change_type == "action":
        return True
    return change_type in SUPPORTED_TARGETS.get(target_table or "", set())


def _as_date(value: Any) -> Any:
    """Accept an ISO date string (what the agent emits) for a Date column."""
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError as exc:
            raise ChangeApplyError(f"Invalid date: {value!r}") from exc
    return value


def _checked_updates(
    change: PendingChange, editable: set[str], table_label: str
) -> dict[str, Any]:
    """Flatten a diff and reject anything outside the table's whitelist."""
    updates = _flat_updates(change.diff)
    for field in updates:
        if field not in editable:
            raise ChangeApplyError(f"Field not editable on {table_label}: {field}")
    return updates


def _flat_updates(diff: Any) -> dict[str, Any]:
    """Turn a list of {field, old, new} into {field: new}."""
    updates: dict[str, Any] = {}
    if isinstance(diff, list):
        for entry in diff:
            if isinstance(entry, dict) and "field" in entry:
                updates[entry["field"]] = entry.get("new")
    elif isinstance(diff, dict):
        updates.update(diff)
    return updates


def apply(session: Session, change: PendingChange, runner: Any | None = None) -> dict[str, Any]:
    if change.change_type == "action":
        return _apply_action(session, change, runner)

    table = change.target_table
    if table == "scoring_configs":
        return _apply_scoring(session, change)
    if table == "module_memories":
        return _apply_module_memory(session, change)
    if table == "positions":
        return _apply_position(session, change)
    if table == "profile_basics":
        return _apply_profile_basics(session, change)
    if table == "profile_sections":
        if change.change_type == "create":
            return _create_profile_section(session, change)
        if change.change_type == "delete":
            return _delete_profile_section(session, change)
        return _apply_profile_section(session, change)
    if table == "templates":
        return _apply_template(session, change)
    if table == "searches":
        return _apply_search(session, change)
    if table == "companies":
        return _apply_company(session, change)
    if table == "applications":
        return _apply_application(session, change)
    if table == "documents":
        return _apply_document(session, change)
    raise ChangeApplyError(f"Unsupported target_table for apply: {table!r}")


# ── scoring (versioned) ──────────────────────────────────────


def _set_dotted(config: dict[str, Any], path: str, value: Any) -> None:
    """Apply a dotted path into the config dict.

    Supports: top-level scalars (`scale_max`), nested dict
    (`salary_gate.floor_usd_month`), and list-by-id
    (`criteria.<id>.weight`, `categories.<id>.min_score`).
    """
    parts = path.split(".")
    if len(parts) == 1:
        config[parts[0]] = value
        return
    head = parts[0]
    if head in ("criteria", "categories"):
        item_id, field = parts[1], parts[2]
        for item in config.get(head, []):
            if item.get("id") == item_id:
                item[field] = value
                return
        raise ChangeApplyError(f"{head} id not found: {item_id}")
    # nested dict (e.g. salary_gate.*)
    node = config
    for key in parts[:-1]:
        node = node.setdefault(key, {})
    node[parts[-1]] = value


def _apply_scoring(session: Session, change: PendingChange) -> dict[str, Any]:
    active = session.scalar(select(ScoringConfig).where(ScoringConfig.is_active.is_(True)))
    if active is None:
        raise ChangeApplyError("No active scoring config to update")

    # Work on a fresh copy of the config's data, apply the edits, then version it.
    config = {
        "salary_gate": dict(active.salary_gate or {}),
        "score_threshold_auto_discard": active.score_threshold_auto_discard,
        "scale_max": active.scale_max,
        "categories": [dict(c) for c in (active.categories or [])],
        "criteria": [dict(c) for c in (active.criteria or [])],
    }
    for field, new_value in _flat_updates(change.diff).items():
        _set_dotted(config, field, new_value)

    # Safety: criterion weights must sum to 1.0 (the eliminatory invariant).
    weight_sum = sum(float(c.get("weight", 0)) for c in config["criteria"])
    if abs(weight_sum - 1.0) > 1e-6:
        raise ChangeApplyError(f"criteria weights must sum to 1.0 (got {weight_sum})")

    next_version = (session.scalar(select(ScoringConfig.version).order_by(ScoringConfig.version.desc())) or 0) + 1
    active.is_active = False
    new_config = ScoringConfig(
        version=next_version,
        is_active=True,
        salary_gate=config["salary_gate"],
        score_threshold_auto_discard=config["score_threshold_auto_discard"],
        scale_max=config["scale_max"],
        categories=config["categories"],
        criteria=config["criteria"],
        created_by=Actor.AGENT.value,
    )
    session.add(new_config)
    session.flush()
    return {"scoring_config_version": next_version}


# ── module memory ────────────────────────────────────────────


def _apply_module_memory(session: Session, change: PendingChange) -> dict[str, Any]:
    module = change.target_id
    if not module:
        raise ChangeApplyError("module_memory change needs target_id (module)")
    memory = session.get(ModuleMemory, module)
    if memory is None:
        memory = ModuleMemory(module=module)
        session.add(memory)
    updates = _flat_updates(change.diff)
    if "content_md" in updates:
        memory.content_md = updates["content_md"]
    memory.updated_by = Actor.AGENT.value
    session.flush()
    return {"module": module}


# ── positions ────────────────────────────────────────────────


def _apply_position(session: Session, change: PendingChange) -> dict[str, Any]:
    position = session.get(Position, change.target_id)
    if position is None:
        raise ChangeApplyError(f"Position not found: {change.target_id}")
    updates = _flat_updates(change.diff)

    field_changes: dict[str, dict] = {}
    for field, new_value in updates.items():
        if field not in _POSITION_EDITABLE:
            raise ChangeApplyError(f"Field not editable on positions: {field}")
        if field == "status" and new_value not in {s.value for s in PositionStatus}:
            raise ChangeApplyError(f"Invalid status: {new_value}")
        old = getattr(position, field)
        if old != new_value:
            setattr(position, field, new_value)
            field_changes[field] = {"old": old, "new": new_value}

    if "status" in field_changes:
        session.add(PositionEvent(
            position_id=position.id,
            event_type=PositionEventType.STATUS_CHANGE.value,
            from_value=field_changes["status"]["old"],
            to_value=field_changes["status"]["new"],
            payload={"via": "agent_change"},
            actor=Actor.AGENT.value,
        ))
    other = {k: v for k, v in field_changes.items() if k != "status"}
    if other:
        session.add(PositionEvent(
            position_id=position.id,
            event_type=PositionEventType.FIELD_UPDATE.value,
            payload={"fields": other, "via": "agent_change"},
            actor=Actor.AGENT.value,
        ))
    session.flush()
    return {"position_id": position.id, "changed": list(field_changes)}


# ── profile ──────────────────────────────────────────────────


def _apply_profile_basics(session: Session, change: PendingChange) -> dict[str, Any]:
    basics = session.get(ProfileBasics, 1)
    if basics is None:
        basics = ProfileBasics(id=1)
        session.add(basics)
    for field, new_value in _flat_updates(change.diff).items():
        if field not in _PROFILE_BASICS_EDITABLE:
            raise ChangeApplyError(f"Field not editable on profile_basics: {field}")
        setattr(basics, field, new_value)
    session.flush()
    return {"profile": "basics"}


def _authorship(change: PendingChange) -> str:
    """Who wrote the text being applied.

    A proposal the user rewrote before approving (`PATCH /changes/{id}`) is
    their content, not the agent's — recording it as `agent` would misattribute
    every correction they made.
    """
    return Actor.USER.value if change.edited_at else Actor.AGENT.value


def _delete_profile_section(session: Session, change: PendingChange) -> dict[str, Any]:
    """Remove a section the agent proposed dropping (target_id = section id)."""
    section = session.get(ProfileSection, int(change.target_id)) if change.target_id else None
    if section is None:
        raise ChangeApplyError(f"Profile section not found: {change.target_id}")
    slug = section.slug
    session.delete(section)
    session.flush()
    return {"section_id": change.target_id, "slug": slug, "deleted": True}


def _create_profile_section(session: Session, change: PendingChange) -> dict[str, Any]:
    """Add a new profile section (onboarding's CV import proposes one per section).

    Slug is required and must be free — approving the same proposal twice, or
    two imports of the same CV, must not fork a section into duplicates.
    """
    values = _flat_updates(change.diff)
    for field in values:
        if field not in _PROFILE_SECTION_EDITABLE:
            raise ChangeApplyError(f"Field not editable on profile_sections: {field}")

    slug = (values.get("slug") or "").strip()
    if not slug:
        raise ChangeApplyError("profile_sections create needs a slug")
    if session.scalar(select(ProfileSection).where(ProfileSection.slug == slug)) is not None:
        raise ChangeApplyError(f"Profile section already exists: {slug}")

    section = ProfileSection(
        slug=slug,
        title=values.get("title") or slug.replace("_", " ").title(),
        content_md=values.get("content_md"),
        sort_order=values.get("sort_order") if isinstance(values.get("sort_order"), int) else 0,
        updated_by=_authorship(change),
    )
    session.add(section)
    session.flush()
    return {"section_id": section.id, "created": True}


def _apply_profile_section(session: Session, change: PendingChange) -> dict[str, Any]:
    section = session.get(ProfileSection, int(change.target_id)) if change.target_id else None
    if section is None:
        raise ChangeApplyError(f"Profile section not found: {change.target_id}")
    for field, new_value in _flat_updates(change.diff).items():
        if field not in _PROFILE_SECTION_EDITABLE:
            raise ChangeApplyError(f"Field not editable on profile_sections: {field}")
        setattr(section, field, new_value)
    section.updated_by = _authorship(change)
    session.flush()
    return {"section_id": section.id}


# ── templates (versioned, like scoring) ──────────────────────


def _apply_template(session: Session, change: PendingChange) -> dict[str, Any]:
    """Write a new ACTIVE template version; never mutate the existing one.

    Templates are versioned for the same reason scoring is: you must be able to
    see what a document was generated from, and roll back. Editing the active
    version in place would rewrite that history.
    """
    template = session.get(Template, int(change.target_id)) if change.target_id else None
    if template is None:
        raise ChangeApplyError(f"Template not found: {change.target_id}")

    updates = _checked_updates(change, _TEMPLATE_EDITABLE, "templates")
    content = updates.get("content_md")
    if not content or not str(content).strip():
        raise ChangeApplyError("templates update needs non-empty content_md")

    current = session.scalar(
        select(TemplateVersion).where(
            TemplateVersion.template_id == template.id,
            TemplateVersion.is_active.is_(True),
        )
    )
    highest = session.scalar(
        select(TemplateVersion.version)
        .where(TemplateVersion.template_id == template.id)
        .order_by(TemplateVersion.version.desc())
    )
    if current is not None:
        current.is_active = False

    version = TemplateVersion(
        template_id=template.id,
        version=(highest or 0) + 1,
        is_active=True,
        content_md=content,
        change_note=updates.get("change_note") or change.summary,
        created_by=_authorship(change),
    )
    session.add(version)
    session.flush()
    return {"template_id": template.id, "version": version.version}


# ── searches / companies / applications / documents ──────────


def _apply_search(session: Session, change: PendingChange) -> dict[str, Any]:
    """Edit a search's configuration (not its results or metrics)."""
    search = session.get(Search, int(change.target_id)) if change.target_id else None
    if search is None:
        raise ChangeApplyError(f"Search not found: {change.target_id}")
    if search.status == SearchStatus.RUNNING.value:
        raise ChangeApplyError("Can't edit a search while it's running")

    updates = _checked_updates(change, _SEARCH_EDITABLE, "searches")

    if "sources" in updates:
        value = updates["sources"]
        if not isinstance(value, list) or not value:
            raise ChangeApplyError("searches.sources must be a non-empty list")
        valid = {s.value for s in Source}
        unknown = [s for s in value if s not in valid]
        if unknown:
            raise ChangeApplyError(f"Unknown sources: {unknown} (valid: {sorted(valid)})")
    if "keywords" in updates and not isinstance(updates["keywords"], list):
        raise ChangeApplyError("searches.keywords must be a list")
    if "markets" in updates and not isinstance(updates["markets"], list):
        raise ChangeApplyError("searches.markets must be a list")
    if "posted_within_days" in updates and updates["posted_within_days"] is not None:
        try:
            updates["posted_within_days"] = int(updates["posted_within_days"])
        except (TypeError, ValueError) as exc:
            raise ChangeApplyError("searches.posted_within_days must be a number") from exc

    for field, value in updates.items():
        setattr(search, field, value)
    session.flush()
    return {"search_id": search.id, "changed": sorted(updates)}


def _apply_company(session: Session, change: PendingChange) -> dict[str, Any]:
    company = session.get(Company, int(change.target_id)) if change.target_id else None
    if company is None:
        raise ChangeApplyError(f"Company not found: {change.target_id}")
    for field, value in _checked_updates(change, _COMPANY_EDITABLE, "companies").items():
        setattr(company, field, value)
    session.flush()
    return {"company_id": company.id}


def _apply_application(session: Session, change: PendingChange) -> dict[str, Any]:
    application = session.get(Application, int(change.target_id)) if change.target_id else None
    if application is None:
        raise ChangeApplyError(f"Application not found: {change.target_id}")
    for field, value in _checked_updates(change, _APPLICATION_EDITABLE, "applications").items():
        setattr(application, field, _as_date(value) if field in _APPLICATION_DATES else value)
    session.flush()
    return {"application_id": application.id, "position_id": application.position_id}


def _apply_document(session: Session, change: PendingChange) -> dict[str, Any]:
    document = session.get(Document, int(change.target_id)) if change.target_id else None
    if document is None:
        raise ChangeApplyError(f"Document not found: {change.target_id}")

    updates = _checked_updates(change, _DOCUMENT_EDITABLE, "documents")
    if "status" in updates and updates["status"] not in _DOCUMENT_STATUSES:
        raise ChangeApplyError(
            f"Invalid document status: {updates['status']!r} (valid: {sorted(_DOCUMENT_STATUSES)})"
        )

    for field, value in updates.items():
        setattr(document, field, value)

    if "content_md" in updates:
        # The exported PDF/DOCX no longer match the source — mark them stale so
        # nobody sends a file whose text was edited out from under it.
        document.pdf_available = False
        document.docx_available = False
    session.flush()
    return {"document_id": document.id}


# ── actions (dispatch a job) ─────────────────────────────────


def _apply_action(session: Session, change: PendingChange, runner: Any | None) -> dict[str, Any]:
    if runner is None:
        raise ChangeApplyError("action changes require a job runner")
    diff = change.diff if isinstance(change.diff, dict) else {}
    action = diff.get("action")
    payload = diff.get("payload", {}) or {}

    if action == "create_and_run_search":
        search = Search(
            name=payload.get("name", "Agent search"),
            sources=payload.get("sources", []),
            keywords=payload.get("keywords", []),
            posted_within_days=payload.get("posted_within_days"),
            markets=payload.get("markets", []),
            status=SearchStatus.DRAFT.value,
        )
        session.add(search)
        session.flush()
        from api.models import SearchRun
        run = SearchRun(search_id=search.id, stats={})
        session.add(run)
        session.flush()
        # commit here so the worker (separate session) sees the search + run
        session.commit()
        job_id = runner.submit(
            AsyncJobType.SEARCH_RUN.value,
            {"search_id": search.id, "search_run_id": run.id},
        )
        return {"action": action, "search_id": search.id, "job_id": job_id, "search_run_id": run.id}

    raise ChangeApplyError(f"Unsupported action: {action!r}")
