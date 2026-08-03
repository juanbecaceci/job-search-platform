"""ChangeApplier is the only code that writes agent-proposed changes (DECISIONS
#6), so its whitelists are the security boundary, not a convenience.

The tests below are grouped by the invariant they defend:
  - a field outside a table's whitelist is refused, per table
  - versioned tables (scoring, templates) get a NEW active version, never an
    in-place edit
  - position edits leave an audit trail
  - a proposal the user rewrote is attributed to the user, not the agent
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import select

from api.models import (
    Application,
    Company,
    Document,
    ModuleMemory,
    PositionEvent,
    ProfileBasics,
    ProfileSection,
    ScoringConfig,
    Search,
    TemplateVersion,
)
from api.models.enums import Actor, PositionEventType, PositionStatus, SearchStatus
from api.services.change_applier import ChangeApplyError, apply, is_supported


def diff(field: str, new, old=None) -> list[dict]:
    return [{"field": field, "old": old, "new": new}]


# ── The whitelist boundary ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("table", "field", "fixture_name"),
    [
        # `id` is never editable anywhere.
        ("positions", "id", "position"),
        # Scores are computed by the evaluator; the agent proposing one would be
        # writing its own grade straight into the ranking.
        ("positions", "score", "position"),
        ("positions", "score_category", "position"),
        # A company rename splits its position history — it's the dedupe key.
        ("companies", "name", "company_row"),
        # Search metrics are derived from runs; proposing them invents history.
        ("searches", "total_found", "search_row"),
        ("searches", "avg_score", "search_row"),
        ("searches", "status", "search_row"),
        # Export paths/flags belong to the export job.
        ("documents", "pdf_path", "document_row"),
        ("documents", "drive_url", "document_row"),
        ("profile_basics", "id", None),
    ],
)
def test_rejects_field_outside_whitelist(
    session, make_change, request, table, field, fixture_name
):
    target_id = None
    if fixture_name:
        row = request.getfixturevalue(fixture_name)
        target_id = str(row.id)
    elif table == "profile_basics":
        target_id = "1"

    change = make_change(table, diff(field, "anything"), target_id=target_id)
    with pytest.raises(ChangeApplyError, match="not editable"):
        apply(session, change)


def test_unsupported_target_table_raises(session, make_change):
    change = make_change("jobs", diff("status", "succeeded"), target_id="1")
    with pytest.raises(ChangeApplyError, match="Unsupported target_table"):
        apply(session, change)


def test_is_supported_matches_what_apply_accepts():
    assert is_supported("positions", "update")
    assert not is_supported("positions", "delete")
    assert not is_supported("jobs", "update")
    assert not is_supported(None, "update")
    # `action` carries no table — it's validated by name inside _apply_action.
    assert is_supported(None, "action")


# ── Scoring config: versioned, and the weight invariant ──────────────────────


def test_scoring_edit_creates_new_active_version(session, make_change, scoring_config):
    change = make_change(
        "scoring_configs",
        [
            {"field": "criteria.remote_modality.weight", "old": 0.25, "new": 0.30},
            {"field": "criteria.company_stability.weight", "old": 0.15, "new": 0.10},
        ],
        target_id=str(scoring_config.id),
        module="scoring",
    )
    result = apply(session, change)

    assert result["scoring_config_version"] == 2
    # The old version is kept, deactivated — scoring history stays auditable.
    session.refresh(scoring_config)
    assert scoring_config.is_active is False

    active = session.scalar(select(ScoringConfig).where(ScoringConfig.is_active.is_(True)))
    assert active.version == 2
    assert active.created_by == Actor.AGENT.value
    weights = {c["id"]: c["weight"] for c in active.criteria}
    assert weights["remote_modality"] == 0.30
    assert weights["company_stability"] == 0.10
    # Untouched criteria carry over unchanged.
    assert weights["profile_alignment"] == 0.40


def test_scoring_rejects_weights_that_do_not_sum_to_one(session, make_change, scoring_config):
    change = make_change(
        "scoring_configs",
        diff("criteria.remote_modality.weight", 0.50),  # 0.40+0.50+0.20+0.15 = 1.25
        target_id=str(scoring_config.id),
        module="scoring",
    )
    with pytest.raises(ChangeApplyError, match="must sum to 1.0"):
        apply(session, change)

    # And nothing was versioned on the way to failing.
    assert session.scalar(select(ScoringConfig).where(ScoringConfig.version == 2)) is None


def test_scoring_rejects_unknown_criterion_id(session, make_change, scoring_config):
    change = make_change(
        "scoring_configs",
        diff("criteria.does_not_exist.weight", 0.1),
        target_id=str(scoring_config.id),
        module="scoring",
    )
    with pytest.raises(ChangeApplyError, match="id not found"):
        apply(session, change)


def test_scoring_supports_nested_and_top_level_paths(session, make_change, scoring_config):
    change = make_change(
        "scoring_configs",
        [
            {"field": "salary_gate.floor_usd_month", "old": 3500, "new": 4200},
            {"field": "score_threshold_auto_discard", "old": 45, "new": 50},
            {"field": "categories.EXCELLENT.min_score", "old": 80, "new": 85},
        ],
        target_id=str(scoring_config.id),
        module="scoring",
    )
    apply(session, change)

    active = session.scalar(select(ScoringConfig).where(ScoringConfig.is_active.is_(True)))
    assert active.salary_gate["floor_usd_month"] == 4200
    assert active.score_threshold_auto_discard == 50
    assert {c["id"]: c["min_score"] for c in active.categories}["EXCELLENT"] == 85


def test_scoring_without_an_active_config_raises(session, make_change):
    change = make_change("scoring_configs", diff("scale_max", 10), target_id="1", module="scoring")
    with pytest.raises(ChangeApplyError, match="No active scoring config"):
        apply(session, change)


# ── Templates: a new active version, never an in-place edit ─────────────────


def test_template_edit_writes_a_new_active_version(session, make_change, template):
    change = make_change(
        "templates",
        [
            {"field": "content_md", "old": "# v1", "new": "# v2"},
            {"field": "change_note", "old": None, "new": "tightened the summary"},
        ],
        target_id=str(template.id),
        module="templates",
    )
    apply(session, change)

    versions = session.scalars(
        select(TemplateVersion).where(TemplateVersion.template_id == template.id)
    ).all()
    assert len(versions) == 2
    v1 = next(v for v in versions if v.version == 1)
    v2 = next(v for v in versions if v.version == 2)
    # v1's content is intact — the whole point of versioning.
    assert v1.content_md == "# v1"
    assert v1.is_active is False
    assert v2.content_md == "# v2"
    assert v2.is_active is True
    assert v2.change_note == "tightened the summary"


# ── Positions: whitelisted edits, and an audit trail ────────────────────────


def test_position_status_change_logs_a_status_event(session, make_change, position):
    change = make_change(
        "positions",
        diff("status", PositionStatus.SHORTLISTED.value, PositionStatus.DISCOVERED.value),
        target_id=position.id,
    )
    result = apply(session, change)

    assert result["changed"] == ["status"]
    session.refresh(position)
    assert position.status == PositionStatus.SHORTLISTED.value

    events = session.scalars(
        select(PositionEvent).where(PositionEvent.position_id == position.id)
    ).all()
    assert len(events) == 1
    assert events[0].event_type == PositionEventType.STATUS_CHANGE.value
    assert events[0].from_value == PositionStatus.DISCOVERED.value
    assert events[0].to_value == PositionStatus.SHORTLISTED.value
    assert events[0].actor == Actor.AGENT.value


def test_position_field_edit_logs_a_field_update_event(session, make_change, position):
    change = make_change(
        "positions",
        [
            {"field": "notes", "old": None, "new": "Referred by a former colleague."},
            {"field": "tags", "old": [], "new": ["python", "remote"]},
        ],
        target_id=position.id,
    )
    apply(session, change)

    events = session.scalars(
        select(PositionEvent).where(PositionEvent.position_id == position.id)
    ).all()
    assert len(events) == 1
    assert events[0].event_type == PositionEventType.FIELD_UPDATE.value
    assert set(events[0].payload["fields"]) == {"notes", "tags"}


def test_position_status_and_fields_log_separate_events(session, make_change, position):
    change = make_change(
        "positions",
        [
            {"field": "status", "old": "Discovered", "new": "Shortlisted"},
            {"field": "notes", "old": None, "new": "worth a look"},
        ],
        target_id=position.id,
    )
    apply(session, change)

    kinds = {
        e.event_type
        for e in session.scalars(
            select(PositionEvent).where(PositionEvent.position_id == position.id)
        ).all()
    }
    assert kinds == {
        PositionEventType.STATUS_CHANGE.value,
        PositionEventType.FIELD_UPDATE.value,
    }


def test_position_no_op_edit_logs_nothing(session, make_change, position):
    change = make_change(
        "positions", diff("role", "Platform Engineer"), target_id=position.id
    )
    result = apply(session, change)

    assert result["changed"] == []
    assert session.scalars(select(PositionEvent)).all() == []


def test_position_rejects_invalid_status(session, make_change, position):
    change = make_change("positions", diff("status", "Pending Vibes"), target_id=position.id)
    with pytest.raises(ChangeApplyError, match="Invalid status"):
        apply(session, change)


def test_position_not_found_raises(session, make_change):
    change = make_change("positions", diff("notes", "x"), target_id="nope-000000")
    with pytest.raises(ChangeApplyError, match="Position not found"):
        apply(session, change)


# ── Profile sections: create / update / delete ──────────────────────────────


def test_profile_section_create_then_update_then_delete(session, make_change):
    create = make_change(
        "profile_sections",
        [
            {"field": "slug", "old": None, "new": "skills"},
            {"field": "title", "old": None, "new": "Skills"},
            {"field": "content_md", "old": None, "new": "Python, TypeScript"},
        ],
        change_type="create",
        module="profile",
    )
    result = apply(session, create)
    section_id = result.get("section_id") or session.scalar(select(ProfileSection.id))
    assert section_id is not None

    update = make_change(
        "profile_sections",
        diff("content_md", "Python, TypeScript, Go"),
        target_id=str(section_id),
        module="profile",
    )
    apply(session, update)
    section = session.get(ProfileSection, section_id)
    assert section.content_md == "Python, TypeScript, Go"

    delete = make_change(
        "profile_sections", [], change_type="delete", target_id=str(section_id), module="profile"
    )
    apply(session, delete)
    assert session.get(ProfileSection, section_id) is None


def test_profile_basics_creates_the_singleton_row_if_missing(session, make_change):
    change = make_change(
        "profile_basics",
        diff("headline", "Senior Backend Engineer"),
        target_id="1",
        module="profile",
    )
    apply(session, change)

    basics = session.get(ProfileBasics, 1)
    assert basics is not None
    assert basics.headline == "Senior Backend Engineer"


# ── Authorship: a rewritten proposal is the user's content ──────────────────


def test_edited_proposal_is_attributed_to_the_user(session, make_change):
    change = make_change(
        "profile_sections",
        [
            {"field": "slug", "old": None, "new": "summary"},
            {"field": "title", "old": None, "new": "Summary"},
            {"field": "content_md", "old": None, "new": "Rewritten by the user."},
        ],
        change_type="create",
        module="profile",
        edited_at=datetime(2026, 8, 2, 12, 0, 0),
    )
    apply(session, change)

    section = session.scalar(select(ProfileSection))
    assert section.updated_by == Actor.USER.value


def test_unedited_proposal_is_attributed_to_the_agent(session, make_change):
    change = make_change(
        "profile_sections",
        [
            {"field": "slug", "old": None, "new": "summary"},
            {"field": "title", "old": None, "new": "Summary"},
            {"field": "content_md", "old": None, "new": "Drafted by the agent."},
        ],
        change_type="create",
        module="profile",
    )
    apply(session, change)

    section = session.scalar(select(ProfileSection))
    assert section.updated_by == Actor.AGENT.value


# ── Module memory ───────────────────────────────────────────────────────────


def test_module_memory_creates_the_row_when_absent(session, make_change):
    change = make_change(
        "module_memories",
        diff("content_md", "- Prefer Monday runs."),
        target_id="searches",
        module="searches",
    )
    apply(session, change)

    memory = session.get(ModuleMemory, "searches")
    assert memory.content_md == "- Prefer Monday runs."
    assert memory.updated_by == Actor.AGENT.value


def test_module_memory_without_target_id_raises(session, make_change):
    change = make_change("module_memories", diff("content_md", "x"), module="searches")
    with pytest.raises(ChangeApplyError, match="needs target_id"):
        apply(session, change)


# ── Applications: ISO date coercion ─────────────────────────────────────────


def test_application_dates_accept_iso_strings(session, make_change, position):
    app_row = Application(position_id=position.id)
    session.add(app_row)
    session.flush()

    change = make_change(
        "applications",
        [
            {"field": "date_applied", "old": None, "new": "2026-07-15"},
            {"field": "outcome", "old": None, "new": "Offer received"},
        ],
        target_id=str(app_row.id),
        module="positions",
    )
    apply(session, change)

    session.refresh(app_row)
    assert app_row.date_applied == date(2026, 7, 15)
    assert app_row.outcome == "Offer received"


def test_application_rejects_a_malformed_date(session, make_change, position):
    app_row = Application(position_id=position.id)
    session.add(app_row)
    session.flush()

    change = make_change(
        "applications",
        diff("date_applied", "15/07/2026"),
        target_id=str(app_row.id),
        module="positions",
    )
    with pytest.raises(ChangeApplyError, match="Invalid date"):
        apply(session, change)


# ── Documents ───────────────────────────────────────────────────────────────


def test_document_rejects_an_unknown_status(session, make_change, document_row):
    change = make_change(
        "documents", diff("status", "published"), target_id=str(document_row.id), module="documents"
    )
    with pytest.raises(ChangeApplyError, match="Invalid document status"):
        apply(session, change)


def test_editing_document_text_invalidates_its_exports(session, make_change, document_row):
    """A stale PDF is worse than no PDF — it's the file that gets sent."""
    document_row.pdf_available = True
    document_row.docx_available = True
    session.flush()

    change = make_change(
        "documents",
        diff("content_md", "# CV (revised)"),
        target_id=str(document_row.id),
        module="documents",
    )
    apply(session, change)

    session.refresh(document_row)
    assert document_row.content_md == "# CV (revised)"
    assert document_row.pdf_available is False
    assert document_row.docx_available is False


def test_editing_only_document_status_leaves_exports_alone(session, make_change, document_row):
    document_row.pdf_available = True
    session.flush()

    change = make_change(
        "documents", diff("status", "final"), target_id=str(document_row.id), module="documents"
    )
    apply(session, change)

    session.refresh(document_row)
    assert document_row.pdf_available is True


# ── Fixtures local to this module ───────────────────────────────────────────


@pytest.fixture
def company_row(session) -> Company:
    row = Company(name="Northwind Analytics")
    session.add(row)
    session.flush()
    return row


@pytest.fixture
def search_row(session) -> Search:
    row = Search(
        name="Backend — remote",
        keywords=["backend"],
        sources=["remotive"],
        markets=[],
        status=SearchStatus.DRAFT.value,
    )
    session.add(row)
    session.flush()
    return row


@pytest.fixture
def document_row(session, position) -> Document:
    row = Document(position_id=position.id, kind="cv", version=1, content_md="# CV")
    session.add(row)
    session.flush()
    return row
