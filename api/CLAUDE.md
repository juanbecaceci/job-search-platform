# api/ — FastAPI backend

Built through Stage 5 (frontend integration); see root `PROGRESS.md` for the
exact resume point. This file is the on-ramp for whoever picks up work here —
read it before writing code in this directory.

## Before writing code

Load only the `PLATFORM_SPEC.md` sections you need for the layer you're
building — don't re-read the whole file per session:
- §2 "Architecture" — component diagram, what talks to what
- §3 "Enums" — exact allowed values (status, source, job.type, etc.)
- §4 "Entities" — JSON shapes each endpoint returns
- §5 "API reference" — literal paths/verbs/params
- §6 "SSE event streams" — event names and payloads for jobs/chat

## Actual layout (as built)

```
api/
├── main.py            # app factory, CORS, /health, lifespan (starts EventBus,
│                       # JobRunner, registers job handlers, ClaudeAdapter)
├── config.py           # DATABASE_URL/DB_PATH resolution, WORKFLOWS_DIR, etc.
├── deps.py             # FastAPI deps for app.state singletons (runner, bus, adapter)
├── db/                 # base.py (Base + TimestampMixin), engine.py (SQLite +
│                       # WAL/FK/busy_timeout, SessionLocal, session_scope,
│                       # get_session dep), alembic/ (env.py, versions/)
├── models/             # SQLAlchemy models, one file per aggregate (company,
│                       # position, search, profile, content, scoring, agent,
│                       # settings) + enums.py mirroring PLATFORM_SPEC.md §3.
│                       # No `repos/` layer — routers/services query via
│                       # SQLAlchemy Session directly.
├── schemas/             # Pydantic request/response schemas (separate from
│                       # models/ — chat.py, common.py, content.py, misc.py,
│                       # position.py, profile.py, requests.py,
│                       # requests_profile.py, search.py)
├── services/           # change_applier.py — the only DB write path for
│                       # agent-proposed changes (DECISIONS #6)
├── routers/            # analytics, changes, chat, companies, dashboard,
│                       # documents (also owns /applications/{id} PATCH — see
│                       # its module docstring), export, jobs, memories,
│                       # onboarding, positions, profile, scoring, searches,
│                       # settings, templates.
├── jobs/               # runner.py (JobRunner, ThreadPoolExecutor(2)),
│                       # event_bus.py (SSE pub/sub), handlers/ — one file per
│                       # job type: search_run, evaluate_batch,
│                       # generate_document, export_document, research_company,
│                       # sheets_export, upload_drive, and import_cv (the only
│                       # agent-calling handler that PROPOSES instead of
│                       # writing — see its docstring)
└── agent/              # adapter.py (AgentAdapter ABC + event types),
                        # claude_adapter.py (subprocess to the CLI, NDJSON
                        # parser), fake.py (ScriptedAdapter for tests),
                        # prompt_builder.py (chat system prompt: brief +
                        # workflow SOP + module memory + entity snapshot +
                        # proposed_changes protocol), change_parser.py
                        # (chat-only HITL parse), task_prompts.py +
                        # output_parser.py (one-shot job-handler agent calls —
                        # see DECISIONS #14, these bypass proposed_changes),
                        # one_shot.py (run_agent_text — the ONLY way a job
                        # handler should invoke the agent; it raises on
                        # ErrorEvent, see DECISIONS #18), mcp_sources.py
                        # (MCP-backed job sources, e.g. Indeed — they live here
                        # rather than core/ because resolving a connector is an
                        # LLM call, see DECISIONS #27)
```

As of 2026-07-29 Stage 5 is complete: `POST /export/sheets`,
`POST /documents/{id}/upload-drive` and a **whitelisted** `PUT /settings` all
exist. `PUT /memories/{module}` is still deliberately unbuilt.

**Profile is directly editable** as of 2026-07-29 (DECISIONS #19):
`PUT /profile/basics`, `POST/PUT/DELETE /profile/sections`, and
`POST /profile/sections/reorder` write straight from the UI, bypassing the
changes tray — that gate is for the agent's writes, not the user's own form.
**Templates and scoring stay chat-only**: `PUT /templates/{id}`,
`PUT /scoring/config` and their version-activate siblings are still
intentionally unbuilt (see `PLATFORM_SPEC.md` §5 note). A still-pending
proposal can also be rewritten before approval via `PATCH /changes/{id}`
(DECISIONS #20).

## Non-negotiable conventions (see root `DECISIONS.md` for rationale)

- SQLite engine: `PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;
  PRAGMA busy_timeout=5000` (decision #1).
- Async work goes through `jobs/runner.py` (`ThreadPoolExecutor(2)` + the
  `jobs` table), not a new queue system (decision #4).
- Job progress and chat responses stream via SSE, not WebSocket (decision #3).
- Job handlers import `core/*` directly in-process — no subprocess calls to
  the Python tools (subprocess is reserved for invoking the agent CLI itself).
- The agent (`agent/claude_adapter.py`) never writes to the DB. Its only
  write path is emitting a `proposed_changes` JSON block, parsed into
  `pending_changes` rows. Only `services/change_applier.py`, triggered by an
  explicit `POST /changes/{id}/approve`, writes to domain tables (decision #6).
  Its write surface is a per-field catalog: adding a table means a whitelisted
  `_apply_*`, an entry in `SUPPORTED_TARGETS`, **and** a row in
  `prompt_builder`'s protocol table — a test asserts no advertised target is
  unreachable (decisions #21/#22).
- Job handlers invoke the agent only via `agent/one_shot.py:run_agent_text`,
  which raises `AgentRunError`. Never write a local runner that collects
  `DoneEvent` and drops `ErrorEvent` — that made a launch failure look like a
  parse failure (decision #18). Prompts go over **stdin**, never argv
  (decision #17).
- A headless run **auto-denies any tool not in `AgentTask.allowed_tools`**. If
  an agent call must reach a tool (an MCP connector, say), name it there or it
  will come back empty with no error to explain why (decision #27).
- Every new endpoint should map to one already listed in `PLATFORM_SPEC.md`
  §5 — if you need one that isn't there, update the spec first, then build it
  (keeps the spec authoritative for the frontend built in Claude Design).

## When you finish a milestone

Update `PROGRESS.md` at the repo root (tick the item, move the resume point) and
append one line to `PROGRESS_LOG.md`. Those files are what let the next session
start in seconds instead of re-deriving state from the codebase.
