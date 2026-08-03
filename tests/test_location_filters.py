"""Region filtering — `core/location_filters.py`.

Two promises are load-bearing here and both are easy to regress:

  1. `worldwide` filters nothing. It is the default, and `.env.example`,
     `core/CLAUDE.md`, the README and DECISIONS #32 all say so. A filter that
     quietly drops rows under the default returns an empty search to a new user
     with no explanation.
  2. `filter_by_regions` and `filter_by_region` treat non-remote roles
     differently *on purpose* (DECISIONS #35). The single-region CLI path
     rejects them up front; the multi-region path used by the runner leaves the
     list untouched when it resolves to "no filtering", so on-site roles
     survive the `worldwide` default.

An unknown region key is permissive everywhere: a typo in `.env` must not empty
a search.
"""

from __future__ import annotations

import pytest

from core.location_filters import (
    REGIONS,
    effective_regions,
    filter_by_region,
    filter_by_regions,
    is_region_eligible,
)


@pytest.fixture(autouse=True)
def neutral_env(monkeypatch):
    """Pin TARGET_REGION so the developer's own .env can't steer these tests."""
    monkeypatch.setenv("TARGET_REGION", "worldwide")


def pos(location: str, remote: bool = True) -> dict:
    return {"location": location, "remote": remote, "role": "Engineer"}


# ── worldwide filters nothing ───────────────────────────────────────────────


@pytest.mark.parametrize("key", ["worldwide", "global", "all", "any", ""])
def test_worldwide_keys_accept_everything(key):
    assert is_region_eligible("Berlin, Germany", True, key)
    assert is_region_eligible("US only", True, key)


def test_effective_regions_collapses_to_no_filtering_on_worldwide():
    assert effective_regions(["worldwide"]) == []
    assert effective_regions(["latam", "worldwide"]) == []


def test_effective_regions_falls_back_to_the_env_default(monkeypatch):
    monkeypatch.setenv("TARGET_REGION", "latam")
    assert effective_regions([]) == ["latam"]
    assert effective_regions(None) == ["latam"]


def test_effective_regions_dedupes():
    assert effective_regions(["latam", "latam", "europe"]) == ["latam", "europe"]


def test_unknown_region_is_permissive_not_empty():
    """A typo in .env must not silently return zero results."""
    assert effective_regions(["atlantis"]) == []
    assert is_region_eligible("Buenos Aires, Argentina", True, "atlantis")


# ── The documented asymmetry (DECISIONS #35) ────────────────────────────────


def test_filter_by_regions_keeps_non_remote_when_not_filtering():
    """The runner's path: `worldwide` must not drop on-site roles."""
    positions = [pos("Berlin, Germany", remote=False), pos("Remote (Global)")]
    assert filter_by_regions(positions, ["worldwide"]) == positions
    assert filter_by_regions(positions, []) == positions


def test_filter_by_region_drops_non_remote_even_when_permissive():
    """The CLI path is remote-focused and rejects on-site up front."""
    positions = [pos("Berlin, Germany", remote=False)]
    assert filter_by_region(positions, "worldwide") == []


def test_the_two_paths_disagree_only_about_remoteness():
    """Same input, same region — the difference is exactly the `remote` flag."""
    remote_role = [pos("Remote (Global)")]
    assert filter_by_regions(remote_role, ["worldwide"]) == remote_role
    assert filter_by_region(remote_role, "worldwide") == remote_role


# ── Real filtering, once a region is named ──────────────────────────────────


def test_named_region_keeps_its_own_and_drops_the_others():
    positions = [
        pos("Remote (LATAM)"),
        pos("Remote (Europe)"),
        pos("Buenos Aires, Argentina"),
    ]
    kept = {p["location"] for p in filter_by_regions(positions, ["latam"])}
    assert "Remote (LATAM)" in kept
    assert "Buenos Aires, Argentina" in kept
    assert "Remote (Europe)" not in kept


def test_globally_advertised_roles_survive_any_region():
    for location in ("Worldwide", "Anywhere", "Remote - Global"):
        assert is_region_eligible(location, True, "latam"), location


def test_bare_remote_is_kept_rather_than_guessed_away():
    """Some boards return only "Remote" after applying their own filter."""
    assert is_region_eligible("Remote", True, "latam")


def test_a_blank_location_is_kept():
    assert is_region_eligible("", True, "latam")
    assert is_region_eligible(None, True, "latam")


def test_union_keeps_a_role_any_listed_region_could_take():
    positions = [pos("Remote (Europe)"), pos("Remote (LATAM)"), pos("Tokyo, Japan")]
    kept = {p["location"] for p in filter_by_regions(positions, ["latam", "europe"])}
    assert kept == {"Remote (Europe)", "Remote (LATAM)"}


def test_non_remote_is_dropped_once_a_real_region_is_named():
    """Filtering resumes in full as soon as the union isn't empty."""
    positions = [pos("Buenos Aires, Argentina", remote=False)]
    assert filter_by_regions(positions, ["latam"]) == []


@pytest.mark.parametrize("region", sorted(REGIONS))
def test_every_region_has_terms_and_matches_one(region):
    """Guard against an empty region entry, which would filter everything out."""
    terms = REGIONS[region]
    assert terms, region
    assert is_region_eligible(terms[0], True, region)
