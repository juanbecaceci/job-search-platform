"""MCP-backed job sources for the `search_run` handler.

Why this lives in `api/agent/` and not `core/`: resolving an MCP connector means
invoking the user's agent CLI, which is an LLM call. `core/` is deterministic
only (hard rule #3 / `core/CLAUDE.md`), so an MCP source cannot live there even
though it is, conceptually, "just another fetcher". The deterministic Indeed
path — plain HTTP against a data provider — stays in `core/fetch_jobs_indeed.py`
as the fallback for environments without the connector.

Each function here matches the `_FETCHERS` contract in
`api/jobs/handlers/search_run.py`: `(keywords) -> list[normalized position]`,
using the shape mandated by `core/CLAUDE.md` (`source, tipo, company, role,
url, location, remote, salary, description, tags, date_posted`).

Cost note: unlike the five free HTTP fetchers, one call here spends an agent
turn (seconds to minutes, token cost, non-deterministic). That is the price of
reaching a connector the backend has no direct HTTP credentials for, and it is
why these sources are opt-in per search rather than on by default.

Enrichment note: the Indeed listing view carries no job description, so each
posting needs a second `get_job_details` call. That call MUST happen in the same
agent turn as the search — Indeed re-issues `job_id` per session (the same
posting was `JOBSEARCH_67` and later `JOBSEARCH_117`), so an id cannot be stored
and resolved later. Enabled by default and capped by `INDEED_MAX_DETAILS`,
because it is what makes the turn expensive.

URL caveat: Indeed's `View Job URL` is a per-request redirect token, not a
stable permalink — the same posting yields a different URL on every call. So
URLs are not identity here (we dedupe on company+role, matching
`make_position_id`), and a stored Indeed URL may eventually stop resolving.
"""

from __future__ import annotations

import json
import re
from typing import Any

from api.agent.one_shot import AgentRunError, run_agent_text
from api.agent.output_parser import extract_fenced_block
from api.agent.task_prompts import build_indeed_search_prompt
from api.config import (
    INDEED_FETCH_DESCRIPTIONS,
    INDEED_MAX_DETAILS,
    INDEED_MCP_TOOLS,
    JOB_SEARCH_COUNTRY,
    JOB_SEARCH_LOCATION,
)
from api.models.enums import JobType, Source


class McpSourceUnavailable(RuntimeError):
    """The connector isn't registered/authorized in this environment.

    Distinct from a fetch *error* on purpose: `search_run` records this as a
    skipped source (the same treatment a source with no fetcher gets), because
    "you never connected Indeed" is a setup state, not a failed run.
    """


# Indeed's raw `job_type` strings → our `tipo` enum. Done here rather than in
# the prompt so the mapping is deterministic and reviewable instead of a
# judgment call the model re-makes on every run.
_TIPO_BY_JOB_TYPE = {
    "full-time": JobType.FULL_TIME.value,
    "fulltime": JobType.FULL_TIME.value,
    "permanent": JobType.FULL_TIME.value,
    "part-time": JobType.FULL_TIME.value,
    "parttime": JobType.FULL_TIME.value,
    "contract": JobType.FREELANCE.value,
    "temporary": JobType.FREELANCE.value,
    "internship": JobType.FULL_TIME.value,
}

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Location strings Indeed uses for work-from-home, across its localized sites.
_REMOTE_HINTS = ("remote", "desde casa", "teletrabajo", "home based", "work from home")


def _tipo_for(job_type: str) -> str:
    return _TIPO_BY_JOB_TYPE.get((job_type or "").strip().lower(), JobType.FULL_TIME.value)


def _is_remote(location: str, requested_location: str) -> bool:
    if "remote" in (requested_location or "").strip().lower():
        return True
    loc = (location or "").strip().lower()
    return any(hint in loc for hint in _REMOTE_HINTS)


def _clean_date(value: Any) -> str:
    """Keep only a well-formed ISO date; drop anything else.

    `search_run._parse_date` would return None for a malformed value anyway —
    dropping it here keeps the malformed string out of the normalized dict.
    """
    text = str(value or "").strip()
    return text if _ISO_DATE.match(text) else ""


def _normalize(raw: dict[str, Any], requested_location: str) -> dict[str, Any] | None:
    """One tool result → the normalized position shape, or None if unusable."""
    company = str(raw.get("company") or "").strip()
    role = str(raw.get("role") or "").strip()
    url = str(raw.get("url") or "").strip()
    # Same required trio as core/load_positions_bulk.py: without these a
    # position can neither be identified nor acted on.
    if not (company and role and url):
        return None

    location = str(raw.get("location") or "").strip()
    # `core/CLAUDE.md` caps description at 3000 chars for the normalized shape.
    description = str(raw.get("description") or "").strip()[:3000]
    return {
        "source": Source.INDEED.value,
        "tipo": _tipo_for(str(raw.get("job_type") or "")),
        "company": company,
        "role": role,
        "url": url,
        "location": location or "Remote",
        "remote": _is_remote(location, requested_location),
        "salary": str(raw.get("salary") or "").strip(),
        "description": description,
        "tags": [],
        "date_posted": _clean_date(raw.get("date_posted")),
    }


def fetch_indeed(
    keywords: list[str],
    country_code: str | None = None,
    location: str | None = None,
    timeout: float = 900.0,
    with_descriptions: bool | None = None,
    max_details: int | None = None,
) -> list[dict[str, Any]]:
    """Fetch Indeed postings through the MCP connector via one agent turn.

    Raises `McpSourceUnavailable` when the connector isn't reachable, and
    `AgentRunError` (from `run_agent_text`) when the CLI itself failed — the
    caller needs to tell those apart to report skipped vs errored.

    Descriptions are fetched in this same turn when enabled: Indeed's `job_id`
    is re-issued per session, so it cannot be persisted and resolved later.
    That makes the turn substantially longer, hence the generous timeout.
    """
    keywords = [k.strip() for k in (keywords or []) if k and k.strip()]
    if not keywords:
        return []

    country = (country_code or JOB_SEARCH_COUNTRY).strip().upper()
    loc = (location or JOB_SEARCH_LOCATION).strip()
    want_desc = INDEED_FETCH_DESCRIPTIONS if with_descriptions is None else with_descriptions
    cap = INDEED_MAX_DETAILS if max_details is None else max_details

    system, user = build_indeed_search_prompt(
        keywords, country, loc, with_descriptions=want_desc, max_details=cap
    )
    text = run_agent_text(
        system,
        user,
        timeout=timeout,
        allowed_tools=list(INDEED_MCP_TOOLS),
    )

    block = extract_fenced_block(text, "json")
    if not block:
        raise McpSourceUnavailable("Indeed MCP returned no parseable output")
    try:
        payload = json.loads(block)
    except json.JSONDecodeError as exc:
        raise McpSourceUnavailable(f"Indeed MCP output was not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise McpSourceUnavailable("Indeed MCP output was not a JSON object")

    if not payload.get("available", False):
        reason = str(payload.get("reason") or "connector not available").strip()
        raise McpSourceUnavailable(f"Indeed MCP unavailable: {reason}")

    raw_positions = payload.get("positions")
    if not isinstance(raw_positions, list):
        return []

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_positions:
        if not isinstance(raw, dict):
            continue
        pos = _normalize(raw, loc)
        if pos is None:
            continue
        # Dedupe on company+role, NOT url: Indeed hands out a fresh redirect URL
        # for the same posting on every call, so URLs are useless as identity.
        # This mirrors `make_position_id(company, role)`, the pipeline's key.
        key = (pos["company"].lower(), pos["role"].lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(pos)
    return out


__all__ = ["McpSourceUnavailable", "fetch_indeed", "AgentRunError"]
