"""Runtime paths and settings for the API.

Everything user-generated lives under ``data/`` (hard rule #1 in CLAUDE.md).
The SQLite DB defaults to ``data/app.db``; override with ``DATABASE_URL`` (full
SQLAlchemy URL) or ``DB_PATH`` (a filesystem path) if needed — e.g. tests point
these at a temp file or ``sqlite://`` in memory.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Repo root = two levels up from this file (api/config.py -> api/ -> root).
ROOT_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = ROOT_DIR / "data"
CONFIG_DIR: Path = ROOT_DIR / "config"
WORKFLOWS_DIR: Path = ROOT_DIR / "workflows"

# Load env from the conventional location (data/credentials/.env), falling back
# to a plain .env / process env. Non-fatal if absent.
load_dotenv(DATA_DIR / "credentials" / ".env")
load_dotenv()  # also pick up a root .env / already-exported vars


def _database_url() -> str:
    """Resolve the SQLAlchemy database URL.

    Precedence: ``DATABASE_URL`` (verbatim) > ``DB_PATH`` (wrapped) >
    ``data/app.db``. The parent directory is created for file-backed URLs so
    first run doesn't fail on a missing ``data/``.
    """
    explicit = os.getenv("DATABASE_URL")
    if explicit:
        return explicit

    db_path = Path(os.getenv("DB_PATH", str(DATA_DIR / "app.db")))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # as_posix keeps the URL clean on Windows (forward slashes).
    return f"sqlite:///{db_path.as_posix()}"


DATABASE_URL: str = _database_url()

# The user's own agent CLI, invoked headless (no API key — DECISIONS #10).
# Override with AGENT_CLI_PATH if `claude` isn't on PATH when the server runs.
AGENT_CLI_PATH: str = os.getenv("AGENT_CLI_PATH", "claude")

# --- MCP-backed job sources -------------------------------------------------
# Indeed's connector requires a country; there is no "global" value. Both of
# these are config-driven on purpose: hardcoding a region is exactly the
# personalization the pre-publish checklist removes, so a cloner sets their own
# rather than silently inheriting someone else's market.
JOB_SEARCH_COUNTRY: str = os.getenv("JOB_SEARCH_COUNTRY", "US").strip().upper()
JOB_SEARCH_LOCATION: str = os.getenv("JOB_SEARCH_LOCATION", "remote").strip()

# The same MCP server is namespaced differently depending on how it was
# registered: `mcp__claude_ai_Indeed__*` when added as a claude.ai account
# connector, `mcp__indeed__*` when added from a committed `.mcp.json`. We
# allowlist both so the source works either way without per-user config.
INDEED_MCP_TOOLS: tuple[str, ...] = (
    "mcp__claude_ai_Indeed__search_jobs",
    "mcp__indeed__search_jobs",
    "mcp__claude_ai_Indeed__get_job_details",
    "mcp__indeed__get_job_details",
)

# Indeed's listing view carries no job description; fetching one costs an extra
# tool call per posting, in the SAME agent turn (its `job_id` is ephemeral —
# ids are re-issued per session, so they cannot be stored and resolved later).
# Descriptions matter a lot for scoring, so this defaults on but is capped.
INDEED_FETCH_DESCRIPTIONS: bool = os.getenv(
    "INDEED_FETCH_DESCRIPTIONS", "true"
).strip().lower() not in {"0", "false", "no"}
INDEED_MAX_DETAILS: int = int(os.getenv("INDEED_MAX_DETAILS", "25"))

# --- LinkedIn (public guest endpoint, scraped over plain HTTP) ---------------
# LinkedIn wants a geography name, not a country code — "Worldwide" is its own
# neutral value, so it is the default rather than any one country.
LINKEDIN_LOCATION: str = os.getenv("LINKEDIN_LOCATION", "Worldwide").strip()
# The guest endpoint rate-limits (HTTP 429) after roughly 10 pages per IP, and
# each page costs a 3-6s delay, so this stays low by default.
LINKEDIN_MAX_PAGES: int = int(os.getenv("LINKEDIN_MAX_PAGES", "3"))
# Search cards carry no description; fetching one is a second request per
# posting (cached by job id, so re-runs are cheap). Descriptions drive scoring.
LINKEDIN_FETCH_DESCRIPTIONS: bool = os.getenv(
    "LINKEDIN_FETCH_DESCRIPTIONS", "true"
).strip().lower() not in {"0", "false", "no"}
