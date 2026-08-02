"""Shared env loading + market settings for the `core/` tools.

Two problems this solves, both of which only bite a *cloner*:

1. **Where env lives.** `.env.example` tells users to copy their config to
   `data/credentials/.env`, and `sheets_manager.py` / `google_auth.py` read it
   from there — but the fetchers used to call a bare `load_dotenv()`, which
   only reads a root `.env`. A user who followed the README got fetcher
   defaults instead of their own settings, silently.
2. **Whose market.** The search geography used to be baked into these tools as
   Argentina / `AR` literals. It now comes from env, with neutral defaults, so
   nobody inherits someone else's market by accident.

Paths resolve against the repo root, never the CWD: these modules are imported
in-process by `api/jobs/handlers/*`, where the CWD is wherever uvicorn started
(the same trap as the CWD-relative paths fixed in DECISIONS #31). `repo_path()`
is the same rule for any other relative path a tool needs to open.

`api/config.py` reads the same variable names for the API side, so the two
halves of the system agree on one configuration.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Repo root = one level up from core/.
_ROOT = Path(__file__).resolve().parent.parent

_loaded = False


def load_env() -> None:
    """Load `data/credentials/.env`, then a root `.env`, then leave the
    process environment alone. Idempotent, and non-fatal if either is absent.

    Order matters only in that already-set variables win: `load_dotenv` does
    not override existing keys, so an explicitly exported var beats both files.
    """
    global _loaded
    if _loaded:
        return
    load_dotenv(_ROOT / "data" / "credentials" / ".env")
    load_dotenv(_ROOT / ".env")
    _loaded = True


load_env()


def repo_path(value: str | os.PathLike[str]) -> Path:
    """Resolve a relative path against the repo root; leave absolute ones alone.

    For the same reason `load_env` resolves its own files that way: a default
    like `data/credentials/token.json` is relative to the *repo*, not to
    wherever the process happened to start. An env override may be absolute, so
    only relative values are rebased.
    """
    path = Path(value)
    return path if path.is_absolute() else _ROOT / path


# --- Market / geography ------------------------------------------------------
# Every default here is deliberately neutral. "worldwide" means "do not filter
# by geography" — a new user sees everything their keywords match until they
# tell the system where they are.

def target_region() -> str:
    """Region key used to filter discovered jobs by location eligibility.

    See `location_filters.REGIONS` for the accepted values. Read through a
    function rather than a module constant so tests and the CLIs can change the
    environment without re-importing.
    """
    return os.getenv("TARGET_REGION", "worldwide").strip().lower()


def linkedin_location() -> str:
    """Geography NAME for LinkedIn's guest endpoint (not a country code).

    "Worldwide" is LinkedIn's own neutral value, so it is the default rather
    than any one country.
    """
    return os.getenv("LINKEDIN_LOCATION", "Worldwide").strip()


def job_search_country() -> str:
    """ISO 3166 two-letter country code for Indeed, which has no global value."""
    return os.getenv("JOB_SEARCH_COUNTRY", "US").strip().upper()


def job_search_location() -> str:
    """City/state string for Indeed, or the literal "remote"."""
    return os.getenv("JOB_SEARCH_LOCATION", "remote").strip()
