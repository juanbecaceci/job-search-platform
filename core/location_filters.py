"""Location filters for the user's job search.

Given a job's advertised location, decide whether someone based in the user's
region could actually take it. Global remote roles are always allowed; roles
locked to a *different* region are filtered out.

The region is configuration, not a constant: set `TARGET_REGION` in
`data/credentials/.env` (see `.env.example`). The default is `worldwide`, which
filters nothing — a new user sees every remote role their keywords match until
they say where they are.

This module is pure: `region` is always an explicit argument with a default
resolved from env at call time, so callers can filter for any region without
touching the environment.
"""

import re
import sys

from env_config import target_region


# Region key -> location terms that mean "someone in this region can take it".
# Keys are what `TARGET_REGION` accepts. Matching is plain substring matching
# on a normalized (lowercased, punctuation-stripped) location string.
REGIONS: dict[str, list[str]] = {
    "latam": [
        "argentina",
        "latin america",
        "latam",
        "south america",
        "central america",
        "americas",
    ],
    "north-america": [
        "united states",
        "usa",
        "u.s.",
        "us only",
        "canada",
    ],
    "europe": [
        "united kingdom",
        "uk",
        "england",
        "london",
        "europe",
        "emea",
        "european union",
        "eu",
        "spain",
        "germany",
        "france",
        "netherlands",
    ],
    "apac": [
        "australia",
        "new zealand",
        "apac",
        "asia",
        "india",
    ],
}

# Region keys that mean "do not filter by geography at all".
WORLDWIDE_KEYS = {"worldwide", "global", "any", "all", ""}

# Values that predate the configurable region. The CLIs took a `--market` flag
# with exactly two values, and `.env.example` shipped `TARGET_REGION=
# Argentina-LATAM` — so anyone who copied it before this change has that string
# in their env. Map them all rather than silently ignoring them.
LEGACY_REGION_ALIASES = {
    "latam-argentina": "latam",
    "argentina-latam": "latam",
    "all": "worldwide",
}

# Everything `--region` accepts, in help-text order.
REGION_CHOICES = ["worldwide", *REGIONS, *LEGACY_REGION_ALIASES]


def normalize_region(value: object) -> str:
    """Lowercase, trim, and resolve legacy `--market` values to region keys."""
    key = str(value or "").strip().lower()
    return LEGACY_REGION_ALIASES.get(key, key)


_warned_regions: set[str] = set()


def _warn_unknown_region(region: str) -> None:
    """Say something once per bad key, on stderr.

    An unrecognized region falls back to no filtering rather than dropping
    every result — a typo in `.env` should not silently empty a search — but
    failing that quietly would hide the typo, so it gets one warning.
    """
    if region in _warned_regions:
        return
    _warned_regions.add(region)
    print(
        f"[Geo] TARGET_REGION={region!r} no reconocida; no se filtra por geografía. "
        f"Valores válidos: {', '.join(['worldwide', *REGIONS])}.",
        file=sys.stderr,
    )

GLOBAL_REMOTE_TERMS = [
    "worldwide",
    "anywhere",
    "global",
    "globally",
    "all regions",
]

REMOTE_ONLY_TERMS = [
    "remote",
    "remoto",
    "remote only",
]


def _normalize_location(location: object) -> str:
    if isinstance(location, list):
        location = " ".join(str(item) for item in location)
    text = str(location or "").lower()
    text = re.sub(r"[^a-z0-9áéíóúüñ.\s/-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _other_region_terms(region: str) -> list[str]:
    """Terms belonging to every region *except* the caller's."""
    return [
        term
        for key, terms in REGIONS.items()
        if key != region
        for term in terms
    ]


def is_region_eligible(location: object, remote: bool = True,
                       region: str | None = None) -> bool:
    """Return True if `location` is compatible with `region` remote work.

    An unknown region key is treated as `worldwide` (permissive) rather than
    filtering everything out — a typo in `.env` should not silently empty a
    search.
    """
    if not remote:
        return False

    region = normalize_region(region if region is not None else target_region())
    if region in WORLDWIDE_KEYS:
        return True
    if region not in REGIONS:
        _warn_unknown_region(region)
        return True

    loc = _normalize_location(location)
    if not loc:
        return True

    if _contains_any(loc, REGIONS[region]) or _contains_any(loc, GLOBAL_REMOTE_TERMS):
        return True

    if _contains_any(loc, _other_region_terms(region)):
        return False

    # Sources sometimes return only "Remote" after already applying a remote
    # filter. Keep those rather than losing potentially valid global roles.
    return loc in REMOTE_ONLY_TERMS


def filter_by_region(positions: list[dict], region: str | None = None) -> list[dict]:
    """Drop positions whose location is incompatible with `region`."""
    return [
        pos for pos in positions
        if is_region_eligible(pos.get("location", ""), pos.get("remote", True), region)
    ]


# --- Multi-region filtering (union) ------------------------------------------
# `searches.markets` is a list: a search can target several regions at once, and
# a position survives if ANY of them could take it. Single-region callers (the
# CLIs) keep using `filter_by_region` above.

def effective_regions(regions: object = None) -> list[str]:
    """Normalize a list of region keys; `[]` means "do not filter at all".

    An empty/absent list falls back to `TARGET_REGION`, so a search that says
    nothing about geography behaves like the rest of the tools. A `worldwide`
    (or unknown) member collapses the whole union to "no filtering": in a union,
    the most permissive member wins, and an unrecognized key must never be the
    reason a search comes back empty.
    """
    keys = [normalize_region(r) for r in (regions or []) if str(r or "").strip()]
    if not keys:
        keys = [normalize_region(target_region())]

    out: list[str] = []
    for key in keys:
        if key in WORLDWIDE_KEYS:
            return []
        if key not in REGIONS:
            _warn_unknown_region(key)
            return []
        if key not in out:
            out.append(key)
    return out


def filter_by_regions(positions: list[dict], regions: object = None) -> list[dict]:
    """Drop positions no listed region could take. Union across `regions`.

    Note the deliberate difference from `filter_by_region`: when this resolves
    to "no filtering" it returns the list untouched, so **non-remote positions
    survive**. `is_region_eligible` rejects those up front, which is right for
    the remote-focused CLIs but would make a `worldwide` default silently drop
    on-site roles — and `worldwide` is documented everywhere as filtering
    nothing. Filtering only starts once a real region is named.
    """
    keys = effective_regions(regions)
    if not keys:
        return list(positions)
    return [
        pos for pos in positions
        if any(
            is_region_eligible(pos.get("location", ""), pos.get("remote", True), key)
            for key in keys
        )
    ]


# --- Backwards-compatible LATAM helpers --------------------------------------
# The tools shipped with a LATAM-only filter before the region became
# configurable. These keep that exact behaviour available by name.

def is_latam_remote_eligible(location: object, remote: bool = True) -> bool:
    """Return True if the location is compatible with Argentina/LATAM remote."""
    return is_region_eligible(location, remote, region="latam")


def filter_latam_remote(positions: list[dict]) -> list[dict]:
    return filter_by_region(positions, region="latam")
