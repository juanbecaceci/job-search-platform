"""The score formula and the salary gate — `core/evaluate_position.py`.

This is the reference implementation `api/jobs/handlers/evaluate_batch.py`
reuses (see core/CLAUDE.md), so a change here silently changes every ranking.
Band boundaries get explicit tests because they're inclusive lower bounds, which
is the kind of thing a refactor flips by one.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.evaluate_position import (
    CATEGORY_BELOW_FLOOR,
    CATEGORY_NEEDS_VALIDATION,
    SALARY_FAIL,
    SALARY_PASS,
    SALARY_UNKNOWN,
    category_for_score,
    compute_weighted_score,
    normalize_salary_gate,
)

DEFAULTS = Path(__file__).resolve().parent.parent / "config" / "defaults" / "scoring_criteria.default.json"


@pytest.fixture(scope="module")
def criteria() -> dict:
    """The shipped default config — tests run against what users actually get."""
    return json.loads(DEFAULTS.read_text("utf-8"))


# ── The weighted score ──────────────────────────────────────────────────────


def test_all_fives_is_one_hundred(criteria):
    scores = {c["id"]: 5 for c in criteria["criteria"]}
    assert compute_weighted_score(scores, criteria) == 100.0


def test_all_ones_is_twenty(criteria):
    """1/5 of the scale, not 0 — the scale starts at 1."""
    scores = {c["id"]: 1 for c in criteria["criteria"]}
    assert compute_weighted_score(scores, criteria) == 20.0


def test_weights_are_applied(criteria):
    """A 5 on the 40%-weighted criterion beats a 5 on the 15% one."""
    heavy = compute_weighted_score({"profile_alignment": 5}, criteria)
    light = compute_weighted_score({"company_stability": 5}, criteria)
    assert heavy > light
    assert heavy == pytest.approx(40.0)
    assert light == pytest.approx(15.0)


def test_missing_criterion_scores_zero(criteria):
    """A criterion the agent omitted must not be silently treated as full marks."""
    partial = compute_weighted_score({"profile_alignment": 5}, criteria)
    full = compute_weighted_score({c["id"]: 5 for c in criteria["criteria"]}, criteria)
    assert partial < full


def test_accepts_the_dict_form_the_agent_emits(criteria):
    """Scores arrive as `{"score": n, "rationale": …}`, not bare numbers."""
    as_dicts = {c["id"]: {"score": 4, "rationale": "…"} for c in criteria["criteria"]}
    as_numbers = {c["id"]: 4 for c in criteria["criteria"]}
    assert compute_weighted_score(as_dicts, criteria) == compute_weighted_score(
        as_numbers, criteria
    )


def test_default_weights_sum_to_one(criteria):
    """The invariant change_applier enforces on edits must hold for the default."""
    assert sum(c["weight"] for c in criteria["criteria"]) == pytest.approx(1.0)


# ── Bands ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (100, "EXCELLENT"),
        (80, "EXCELLENT"),   # inclusive lower bound
        (79.9, "GOOD"),
        (60, "GOOD"),
        (59.9, "ACCEPTABLE"),
        (45, "ACCEPTABLE"),
        (44.9, "DISCARD"),
        (0, "DISCARD"),
    ],
)
def test_band_boundaries(criteria, score, expected):
    assert category_for_score(score, criteria)["id"] == expected


def test_bands_are_english(criteria):
    """Regression guard for DECISIONS #37 — these strings render in the UI."""
    assert [c["id"] for c in criteria["categories"]] == [
        "EXCELLENT", "GOOD", "ACCEPTABLE", "DISCARD",
    ]
    assert criteria["salary_gate"]["unpublished_status"] == "NEEDS VALIDATION"
    assert CATEGORY_NEEDS_VALIDATION == "NEEDS VALIDATION"
    assert CATEGORY_BELOW_FLOOR == "BELOW SALARY FLOOR"


def test_every_band_carries_a_recommended_action(criteria):
    for category in criteria["categories"]:
        assert category["recommended_action"].strip()


# ── The salary gate ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("PASS", SALARY_PASS),
        ("FAIL", SALARY_FAIL),
        ("UNKNOWN", SALARY_UNKNOWN),
        ("NEEDS VALIDATION", SALARY_UNKNOWN),
        ("BELOW_FLOOR", SALARY_FAIL),
        # Legacy Spanish spellings stay accepted as *input*: the workflow prompts
        # the agent in its own vocabulary and old evaluations used these
        # (DECISIONS #37).
        ("A VALIDAR", SALARY_UNKNOWN),
        ("A_VALIDAR", SALARY_UNKNOWN),
        ("NO_PUBLICADO", SALARY_UNKNOWN),
        ("DESCARTAR", SALARY_FAIL),
        ("NO_PASA", SALARY_FAIL),
        ("PASA", SALARY_PASS),
        # Anything unrecognized is UNKNOWN, never a silent PASS.
        ("something else", SALARY_UNKNOWN),
        ("", SALARY_UNKNOWN),
    ],
)
def test_gate_status_normalization(criteria, raw, expected):
    assert normalize_salary_gate({"salary_gate": {"status": raw}}, criteria)["status"] == expected


def test_gate_accepts_a_bare_string(criteria):
    assert normalize_salary_gate({"salary_gate": "PASS"}, criteria)["status"] == SALARY_PASS


def test_passes_floor_boolean_wins_over_status(criteria):
    """The explicit boolean is the stronger signal when both are present."""
    entry = {"salary_gate": {"passes_floor": False, "status": "PASS"}}
    assert normalize_salary_gate(entry, criteria)["status"] == SALARY_FAIL


def test_gate_defaults_the_floor_from_the_config(criteria):
    gate = normalize_salary_gate({"salary_gate": {"status": "PASS"}}, criteria)
    assert gate["floor_usd_month"] == criteria["salary_gate"]["floor_usd_month"]


def test_missing_gate_is_unknown_not_pass(criteria):
    """An evaluation with no salary_gate must not sail through the filter."""
    assert normalize_salary_gate({}, criteria)["status"] == SALARY_UNKNOWN


def test_garbage_gate_type_is_unknown(criteria):
    assert normalize_salary_gate({"salary_gate": 42}, criteria)["status"] == SALARY_UNKNOWN
