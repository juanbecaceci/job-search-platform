"""The agent is told exactly what it may propose; this checks that story is true.

DECISIONS #21/#22: adding a writable table means three edits — a `_apply_*`
handler, an entry in `SUPPORTED_TARGETS`, and a row in `prompt_builder`'s
protocol table. Miss the third and the agent never proposes a change it could
have made; miss the second and it proposes one that dies on approve. Both
failures are silent in production and invisible in review, which is why they
get a test rather than a convention.

The protocol table is prose the agent reads, so it's parsed here as prose.
"""

from __future__ import annotations

import re

import pytest

from api.agent import prompt_builder
from api.services import change_applier
from api.services.change_applier import SUPPORTED_TARGETS, is_supported

# `| `table` | update / create | fields… |`
_ROW = re.compile(r"^\|\s*`(?P<table>\w+)`\s*\|(?P<types>[^|]+)\|(?P<fields>.*)\|\s*$", re.M)

# Field whitelists in change_applier, keyed by the table they guard. Tables
# whose editable set isn't a flat module constant are checked by table only.
_EDITABLE_SETS = {
    "positions": change_applier._POSITION_EDITABLE,
    "profile_basics": change_applier._PROFILE_BASICS_EDITABLE,
    "profile_sections": change_applier._PROFILE_SECTION_EDITABLE,
    "searches": change_applier._SEARCH_EDITABLE,
    "companies": change_applier._COMPANY_EDITABLE,
    "applications": change_applier._APPLICATION_EDITABLE,
    "documents": change_applier._DOCUMENT_EDITABLE,
    "templates": change_applier._TEMPLATE_EDITABLE,
}


def advertised() -> dict[str, set[str]]:
    """Parse {table: {change_type}} out of the prompt's protocol table."""
    out: dict[str, set[str]] = {}
    for match in _ROW.finditer(prompt_builder._OUTPUT_PROTOCOL):
        table = match.group("table")
        if table == "target_table":  # the header row
            continue
        types = {t.strip() for t in match.group("types").split("/") if t.strip()}
        out[table] = types
    return out


def advertised_fields(table: str) -> set[str]:
    """The column names a protocol row invites the agent to edit.

    Parenthetical asides are dropped first. They carry backticks too, but for
    prohibitions ("never `name`"), enum values ("`draft`/`final`/`sent`") and
    addressing notes ("`target_id` = template id") — none of which are editable
    fields, and all of which the agent is meant to read.
    """
    for match in _ROW.finditer(prompt_builder._OUTPUT_PROTOCOL):
        if match.group("table") != table:
            continue
        fields = re.sub(r"\([^)]*\)", "", match.group("fields"))
        names = set(re.findall(r"`([a-z_.]+)`", fields))
        # `scoring_configs` advertises dotted paths, not plain columns.
        return {n for n in names if "." not in n} - {"target_id"}
    return set()


def test_the_protocol_table_actually_parses():
    """Guard the parser itself: a reformat that breaks it must not pass silently."""
    parsed = advertised()
    assert len(parsed) >= 8, f"parsed only {len(parsed)} rows — has the table format changed?"
    assert "scoring_configs" in parsed


def test_every_advertised_table_is_writable():
    """Nothing the agent is told it may change is unreachable in the applier."""
    missing = sorted(set(advertised()) - set(SUPPORTED_TARGETS))
    assert not missing, f"advertised to the agent but not in SUPPORTED_TARGETS: {missing}"


def test_every_writable_table_is_advertised():
    """The inverse: no write capability is hidden from the agent."""
    missing = sorted(set(SUPPORTED_TARGETS) - set(advertised()))
    assert not missing, f"writable but never advertised in the prompt: {missing}"


def test_change_types_agree_between_prompt_and_applier():
    for table, types in advertised().items():
        assert types == SUPPORTED_TARGETS[table], (
            f"{table}: prompt says {sorted(types)}, applier supports "
            f"{sorted(SUPPORTED_TARGETS[table])}"
        )


@pytest.mark.parametrize("table", sorted(_EDITABLE_SETS))
def test_advertised_fields_are_in_the_applier_whitelist(table):
    """A field the agent is invited to edit must survive `_checked_updates`."""
    promised = advertised_fields(table)
    assert promised, f"no fields parsed for {table} — check the protocol row"
    extra = sorted(promised - _EDITABLE_SETS[table])
    assert not extra, f"{table}: advertised but not editable: {extra}"


def test_company_name_is_never_advertised():
    """Renaming a company splits its position history — it's the dedupe key."""
    assert "name" not in advertised_fields("companies")
    assert "name" not in change_applier._COMPANY_EDITABLE
    # The prompt should say so, not just omit it: an unexplained gap invites the
    # agent to ask for the capability instead of telling the user why not.
    assert "never `name`" in prompt_builder._OUTPUT_PROTOCOL


def test_every_supported_pair_passes_is_supported():
    for table, types in SUPPORTED_TARGETS.items():
        for change_type in types:
            assert is_supported(table, change_type), f"{table}/{change_type}"
