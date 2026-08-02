"""Builds the system prompt for one chat turn.

Assembles four things into the agent's context:
  1. A base operating brief (who it is, the HITL contract, the strict output
     protocol for proposing changes).
  2. The relevant workflow SOP(s) for the active module (`workflows/*.md`).
  3. The module's accumulated memory (`module_memories.content_md`).
  4. An entity slice — a JSON snapshot of what the chat is scoped to (a position,
     the scoring config, etc.), passed by the caller.

The output protocol is the load-bearing part: the agent NEVER writes to the DB
(DECISIONS #6). To change anything it must end its turn with a fenced ```json
block containing a top-level `proposed_changes` array; `change_parser` turns that
into `pending_changes` rows the user approves.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from sqlalchemy.orm import Session

from api.config import WORKFLOWS_DIR
from api.models import ModuleMemory

# Which workflow SOP(s) inform each module's chat.
_MODULE_WORKFLOWS: dict[str, list[str]] = {
    "profile": ["01_build_profile.md"],
    # Onboarding gets the first-run SOP *before* the profile one: a new cloner's
    # problem is usually setup (market vars, agent CLI, PDF-only upload), not
    # how to phrase an achievement.
    "onboarding": ["00_first_run.md", "01_build_profile.md"],
    "searches": ["02_configure_search.md", "03_discover_jobs.md"],
    "scoring": ["04_evaluate_rank.md"],
    "positions": ["04_evaluate_rank.md"],
    "documents": ["05_generate_documents.md", "06_research_company.md"],
    "analytics": [],
    "templates": ["05_generate_documents.md"],
}

_OUTPUT_PROTOCOL = """\
## How to propose changes (STRICT — this is the only way you may change data)

You do not have write access to the database. When the user agrees to a change,
end your reply with a single fenced code block, tagged `json`, whose content is
an object with a top-level `proposed_changes` array. Each item:

```json
{
  "proposed_changes": [
    {
      "module": "<module>",
      "change_type": "update | create | delete | action",
      "target_table": "<table, e.g. scoring_configs>",
      "target_id": "<id or null>",
      "summary": "<one line the user will see>",
      "diff": [ { "field": "<dotted.path>", "old": <value>, "new": <value> } ]
    }
  ]
}
```

### What you are allowed to change

`target_table` MUST be one of these — anything else is rejected on the spot,
so if what the user wants isn't here, say so plainly instead of proposing it:

| target_table | change_type | editable fields |
|---|---|---|
| `scoring_configs` | update | dotted paths: `criteria.<id>.weight`, `categories.<id>.min_score`, `salary_gate.*`, `scale_max`, `score_threshold_auto_discard` (criteria weights must still sum to 1.0) |
| `profile_basics` | update | `full_name`, `headline`, `email`, `phone`, `location`, `linkedin_url`, `portfolio_url` (`target_id` = "1") |
| `profile_sections` | create / update / delete | `slug`, `title`, `content_md`, `sort_order` |
| `positions` | update | `role`, `url`, `location`, `remote`, `tipo`, `track`, `salary_raw`, `salary_min_usd_month`, `salary_max_usd_month`, `description`, `tags`, `notes`, `status` |
| `templates` | update | `content_md`, `change_note` — writes a NEW active version (`target_id` = template id) |
| `searches` | update | `name`, `keywords`, `sources`, `posted_within_days`, `markets` — config only, never metrics; not while the search is running |
| `companies` | update | `industry`, `size`, `website`, `research_md` (never `name` — it's the dedupe key) |
| `applications` | update | `date_applied`, `applied_via`, `contact`, `response_date`, `interview_date`, `outcome`, `follow_up_due`, `notes` (dates as `YYYY-MM-DD`) |
| `documents` | update | `content_md`, `status` (`draft`/`final`/`sent`) |
| `module_memories` | update | `content_md` (`target_id` = module name) |

Config files in the repo (e.g. `config/job_sites.json`) are NOT writable this
way — per-search settings live in the `searches` row.

Rules:
- Only emit the block when you actually intend a change; a normal answer has no block.
- For `change_type: "action"`, `diff` is instead `{ "action": "<name>", "payload": { ... } }`.
- Keep `summary` short and human; put the precise edits in `diff`.
- Never claim a change was applied — it is only *proposed* until the user approves it.

Editing the profile (module `profile`): the entity snapshot below carries the
current basics and every section with its `id`. Propose one change per section
you're touching:
- rewrite a section → `update` on `profile_sections`, `target_id` = its id,
  `diff` fields from `title`, `content_md`, `sort_order`, `slug`
- add a section → `create` on `profile_sections`, `target_id` null, `diff`
  including at least `slug` (must not collide with an existing one)
- remove a section → `delete` on `profile_sections`, `target_id` = its id
- contact details / headline → `update` on `profile_basics`, `target_id` "1"
Quote the section's existing text in `old` so the user sees a real diff, and
never invent experience the profile and CV don't support.
"""

_BASE_BRIEF = """\
You are the reasoning engine of a single-user, self-hosted job-search platform,
operating inside the "{module}" module. Be concise and concrete. Ground answers
in the provided context (workflow, memory, entity snapshot) and the repository's
tools. Follow the human-in-the-loop contract below exactly.
"""


@lru_cache(maxsize=16)
def _load_workflow(filename: str) -> str:
    path = WORKFLOWS_DIR / filename
    return path.read_text("utf-8") if path.exists() else ""


def _module_memory(session: Session, module: str) -> str:
    row = session.get(ModuleMemory, module)
    return (row.content_md or "").strip() if row else ""


def build_system_prompt(
    session: Session,
    module: str,
    entity: dict[str, Any] | None = None,
) -> str:
    """Compose the system prompt for a chat turn in `module`."""
    parts: list[str] = [_BASE_BRIEF.format(module=module)]

    workflows = _MODULE_WORKFLOWS.get(module, [])
    for wf in workflows:
        content = _load_workflow(wf)
        if content:
            parts.append(f"## Workflow reference — {wf}\n\n{content}")

    memory = _module_memory(session, module)
    if memory:
        parts.append(f"## Module memory (lessons learned)\n\n{memory}")

    if entity:
        parts.append(
            "## Entity in focus (JSON snapshot)\n\n```json\n"
            + json.dumps(entity, ensure_ascii=False, indent=2, default=str)
            + "\n```"
        )

    parts.append(_OUTPUT_PROTOCOL)
    return "\n\n---\n\n".join(parts)
