# Progress

> Read this first, every session. Update it last, every session. This file
> exists so a new session (or a compacted context) never has to reconstruct
> status from `git log` or by re-reading the whole spec.
>
> Session-by-session history lives in [PROGRESS_LOG.md](PROGRESS_LOG.md) — append
> one line there when you finish, but don't read it to get oriented; everything
> a resuming session needs is below.

**Current stage: 5 — frontend integration ✅ COMPLETE (2026-07-29)**
**Resume point:** every Stage 5 item is done and verified — onboarding wizard,
profile editing (direct + chat), the widened agent write surface, Sheets export,
Drive upload, and the visual pass (14 screens x light/dark, 28/28 clean).
A harness/docs pass ran 2026-07-29 (see `PROGRESS_LOG.md`): the session log moved
to `PROGRESS_LOG.md`, root `CLAUDE.md` gained a file-routing table, and
`frontend/CLAUDE.md` now exists.
**The `indeed` MCP source was wired on 2026-07-30** (live-verified, 20 real
positions) — see the item at the end of Stage 5 and DECISIONS #27/#28.
**The regional-defaults pre-publish item was closed on 2026-07-31** — search
geography is now configuration end to end (`TARGET_REGION` +
`LINKEDIN_LOCATION` + `JOB_SEARCH_*`), with `worldwide` as a filter-nothing
default. See that item below and DECISIONS #32.
**Next: the remaining Pre-publish checklist items below** — the two that need a
decision from Juan are `--strict-mcp-config` and `frontend/design-reference/`.

✅ Google is authorized (2026-07-29): one token with Sheets+Drive scopes in
`data/credentials/token.json`, and `GOOGLE_DRIVE_FOLDER_ID` set in that folder's
`.env` (the dedicated Drive folder). **Drive upload is verified end-to-end
against live Drive**; test artifacts were deleted afterwards and the folder is
back to its original 5 items.

✅ **Sheets export run and verified live (2026-07-29)**: 539 positions /
4 applications / 4 searches / 306 companies written, headers intact. Both
Google features are now proven end-to-end. `sheets_export_enabled` is ON in
settings, so the "Export now" button in Settings works from the UI.

Git state: the whole Stage 2–5 build is committed (branch `stage5-complete`,
through `ce4c31a`). **No remote is configured** — nothing has been pushed to
GitHub, pending Juan's go-ahead and the Pre-publish checklist below. The only
untracked path is `frontend/design-reference/` (the design prototype; decide at
pre-publish whether to ship it).

⚠️ Routes and job handlers are registered at **startup** — restart uvicorn after
any change under `api/routers/` or `api/jobs/handlers/`, or a long-lived server
404s on the new ones.

Known follow-ups (not blockers): the runner skips geo/market filtering
entirely. `core/location_filters.py` now offers `filter_by_region(positions,
region)` driven by `TARGET_REGION` (DECISIONS #32) and the standalone CLIs use
it, but `search_run` deliberately does not — wiring it in (and finally using the
unused `searches.markets` column) is a real feature, not a cleanup.

Env / how to run (both servers, then open http://localhost:5173):
- backend: `.venv\Scripts\python -m uvicorn api.main:app --port 8000` (Swagger `/docs`)
- frontend: `cd frontend && npm run dev` (Vite binds `localhost`/IPv6 — use
  http://localhost:5173, not 127.0.0.1)
- `.venv/` has all Python deps; `frontend/node_modules` installed. `data/app.db`
  = REAL data. `data/credentials/` has Juan's Google creds + `.env` (gitignored).

⚠️ REAL-DATA STATE (important):
- **Scoring is at v2, active** (`profile_alignment 0.50 · remote_modality 0.20 ·
  seniority_growth 0.20 · company_stability 0.10`, Σ=1.0, created_by=agent).
  This is JUAN'S OWN change — he used the chat + approved it via the HITL tray.
  v1 (0.40/0.25/0.20/0.15) is retained but inactive. Do NOT revert without asking.
- Agent CLI: no standalone `claude` was installable (the 244MB native binary
  download from downloads.claude.ai stalls here — region/network). Workaround in
  place: the VSCode extension's self-contained `claude.exe` was COPIED to a
  stable path `%LOCALAPPDATA%\claude-cli\claude.exe` (also on USER PATH), and
  `AGENT_CLI_PATH` in `data/credentials/.env` points there. Chat works. Re-run
  `irm https://claude.ai/install.ps1 | iex` later (when network allows) for the
  auto-updating install.
- ⚠️ DATA LOSS I caused: while fixing the chat I ran a cleanup that cleared the
  `chat_threads`/`chat_messages`/`pending_changes` tables, ASSUMING they were all
  my test artifacts — but they included Juan's real conversation that produced
  scoring v2. The scoring config itself survived; the chat history + the approved
  change's audit row were deleted. Lesson: never bulk-clear those tables; they
  hold real user data.

How to run alembic: from repo root, `alembic upgrade head` (config in
`alembic.ini`, env in `api/db/alembic/env.py` — it pulls `Base.metadata` and the
engine/URL from the app, so the CLI needs no `sqlalchemy.url`). DB path defaults
to `data/app.db`; override with `DATABASE_URL` or `DB_PATH` env vars.

Note: ORM models live in `api/models/` (per `api/CLAUDE.md`'s "approved plan"
layout), not `api/db/models.py` as an earlier resume point read. `api/db/` holds
`base.py` (Base + TimestampMixin), `engine.py` (sessions + PRAGMAs), `alembic/`.

---

## Stage 0 — Platform spec ✅ done (2026-07-10)
- `PLATFORM_SPEC.md` written: data model, API contract, SSE events, view map, UX rules.
- `DESIGN_BRIEF.md` written: prompt for the Claude Design UI session.

## Stage 1 — Repo skeleton ✅ done (2026-07-10)
- Folder structure created (`api/ core/ workflows/ frontend/ config/ scripts/ data/`).
- Fresh git history (`git init`, no connection to the private `Copilot` repo).
- 12 tools ported to `core/`, 7 workflows ported to `workflows/` — genericized
  (verified zero personal references: names, employers, metrics, past-run
  companies/dates all removed or replaced with generic placeholders).
- `config/defaults/` (scoring criteria, CV/cover-letter templates) genericized.
- `README.md`, `LICENSE` (MIT), `.env.example`, `.gitignore` (`data/` fully
  ignored), `scripts/check_no_secrets.py` installed as pre-commit hook.
- Commits: `cd2ee06` (initial), `5c21590` (scoring defaults genericized),
  `c3bece6` (design brief).
- Not yet pushed to GitHub — pending Juan's go-ahead.

## Stage 2 — SQLite schema + read API ✅ DONE (real-data verified 2026-07-18)
Target: schema live, migration script working against Juan's real Sheets data
(run locally, never committed), GET endpoints returning real data.

- [x] SQLAlchemy models (in `api/models/`, one file per aggregate: company,
      position, search, profile, content, scoring, agent, settings) covering all
      19 tables (positions, position_events, applications, companies, documents,
      searches, search_runs, search_run_positions, jobs, profile_basics,
      profile_sections, templates, template_versions, scoring_configs,
      chat_threads, chat_messages, pending_changes, module_memories, settings).
      `api/models/enums.py` mirrors PLATFORM_SPEC.md §3. Verified via in-memory
      `create_all`. Templates/scoring use an `is_active` flag (no circular FK) —
      see DECISIONS #11.
- [x] `api/db/engine.py` — SQLite engine, WAL + `foreign_keys=ON` +
      `busy_timeout=5000` via a `connect` event, `SessionLocal`, `session_scope()`
      context manager, `get_session()` FastAPI dep. `api/config.py` resolves
      `DATABASE_URL` (defaults to `data/app.db`).
- [x] Alembic init + first migration (`api/db/alembic/`, `alembic.ini` at root).
      `env.py` wired to `api.models.Base.metadata` + the app engine,
      `render_as_batch=True` (SQLite-safe ALTERs), `compare_type=True`. Initial
      revision `c416b77fadf6`; verified `upgrade head` builds all 19 tables clean.
- [x] `scripts/seed_defaults.py` — loads `config/defaults/*` into `scoring_configs`
      (v1, active), `templates` cv + cover_letter (v1, active), one empty
      `module_memories` row per module. Idempotent (skips what exists). Verified:
      clean migrate → seed → re-seed; scoring weight sum = 1.0, 8 memories.
- [x] `scripts/migrate_from_sheets.py` — reads the 4 Sheets tabs via
      `core/sheets_manager.py`, upserts into SQLite, synthesizes `position_events`
      (`created` + `status_change` per position, actor=`system`). Has `--dry-run`;
      prints by-status/by-source counts for comparison. Idempotent (upsert by
      natural key; events only for positions with none). Mapping notes: company
      get-or-create by name (auto-creates ones absent from the Companies tab);
      Positions.salary → `salary_raw`; evaluation_notes → `summary`; Drive URLs
      (cv/cover_letter/company_research) materialized as `documents` + FK links;
      score_category derived from the active scoring config. Logic verified with
      synthetic data (26 assertions). ⚠️ NOT yet run against real Sheets.
- [x] `api/main.py` app factory (CORS for localhost SPA, `/health`, wires all
      routers via `api/routers/all_routers`; lifespan hook left for Stage 3/4).
- [x] Read routers (all GET): `/dashboard/summary`, `/analytics/{sources,funnel,
      stale}`, `/searches`+`/searches/defaults`+`/searches/{id}`, `/positions`+
      `/top`+`/board`+`/{id}`, `/profile/{basics,sections}`, `/templates`+
      `/{id}/versions`, `/scoring/config`+`/versions`, `/companies`+`/{id}`,
      `/memories`+`/{module}`, `/settings`. Pydantic response schemas in
      `api/schemas/`. Verified with a TestClient smoke test (28 endpoints +
      15 payload spot-checks; analytics/funnel/dashboard aggregates checked).
- [x] Real-data verification DONE (2026-07-18, run by Juan's creds locally).
      Migrated: 327 positions, 211 companies (6 from Companies tab + 205
      auto-created from positions), 3 applications, 12 documents (6
      company_research + 6 cv/cl from Drive URLs), 654 events (327 created +
      327 status_change). Status: Evaluating 278 / Applied 5 / Rejected 44.
      Categories: EXCELENTE 28 / BUENA 119 / ACEPTABLE 137 / DESCARTAR 30 /
      unscored 13. API serves it correctly (verified live via uvicorn:
      /positions total=327, /companies total=211, funnel discovered=327).
      FINDINGS worth remembering:
      · 231/327 positions have `search_id=null` — their Sheets `search_name`
        doesn't match any of the 3 Search Configs `name`s (dated run-names never
        saved to that tab). Faithful, not a bug; those show in /positions but not
        in any /searches/{id} detail. Juan to confirm this is expected.
      · Dashboard default window is last 7 days; migrated positions are dated
        ~Jul 5–10 so `/dashboard/summary` (default, "today"=Jul 18) shows 0 —
        widen the range to see data. Frontend/onboarding must handle a
        historical-data default range (see Stage 5 / pre-publish).
      · Migration summary's "companies: N" line counts only Companies-tab rows,
        not auto-created ones — minor polish: report total instead.

## Stage 3 — Write ops + async jobs ✅ DONE (E2E-verified 2026-07-18)
- [x] `api/jobs/event_bus.py` — in-process pub/sub, per-job buffer + backlog
      replay + `Last-Event-ID` resume. `api/jobs/runner.py` — JobRunner
      (`ThreadPoolExecutor(2)`), state machine (queued→running→succeeded/failed/
      cancelled) persisted to `jobs`, `progress(fraction, message, stats)`
      callback that persists + emits SSE + supports cooperative cancel. Wired
      into app lifespan (`api/main.py`) + `api/deps.py`. Verified standalone
      (14 checks: happy/fail/cancel/late-subscriber replay/resume).
- [x] `api/jobs/handlers/search_run.py` — wraps the 5 free API fetchers in
      `core/fetch_jobs_api.py` (called per-source for progress + per-source
      stats), dedupes by `make_position_id(company, role)` against existing rows
      (so it dedupes vs migrated data), writes `search_runs` + linked
      `search_run_positions`, synthesizes `created` events, sets `position.
      search_id`. Unsupported sources (linkedin scraper, indeed MCP, manual)
      recorded as `skipped`. NOTE: linkedin/indeed fetchers NOT yet wired into
      the runner — follow-up (wrap `core/scrape_jobs.py` + the Indeed MCP path).
- [x] `POST /positions` (manual intake), `PATCH /positions/{id}` (field_update
      event), `POST /positions/{id}/status` (validated, status_change event).
- [x] `POST /searches` (draft), `POST /searches/{id}/run` (202 → {job_id,
      search_run_id}), `DELETE /searches/{id}` (drafts only). `GET /jobs`,
      `GET /jobs/{id}`, `POST /jobs/{id}/cancel`, `GET /jobs/{id}/events` (SSE).
- [x] Verification: E2E against a COPY of the real DB + LIVE remotive+jobicy —
      created search, ran it, consumed live SSE progress, 101 new positions
      persisted & linked, 11 dedupe hits vs migrated data, linkedin skipped,
      search→finished. 10/10 checks. Real `data/app.db` untouched (used a copy).

## Stage 4 — Agent adapter ✅ DONE (HITL loop verified 2026-07-18)
- [x] `api/agent/adapter.py` — `AgentAdapter` ABC + `AgentTask` / event types
      (Token/ToolUse/Done/Error). `claude_adapter.py` — subprocess to
      `claude -p --output-format stream-json --verbose --include-partial-messages`
      (+ `--append-system-prompt`, `--resume`), with a PURE NDJSON parser
      (`iter_events_from_lines`) unit-tested (14 checks: token deltas, tool_use,
      fallback text, error/missing-result, garbage tolerance, single-terminal
      contract). `api/agent/fake.py` = `ScriptedAdapter` for tests. Binary path
      via `AGENT_CLI_PATH`. ✅ The stream-json format was VERIFIED against the
      real CLI (v2.1.215) — matches the parser exactly (system/init→session_id,
      content_block_delta→token, result→done; extra event types ignored). See the
      Stage 5 real-CLI chat item for the fixes (`_clean_env`, UTF-8 stdout).
- [x] `api/agent/prompt_builder.py` — base brief + module→workflow SOP injection
      + module_memory + entity JSON snapshot + the strict `proposed_changes`
      output protocol (the HITL contract).
- [x] `api/agent/change_parser.py` — pure parser: fenced ```json blocks with a
      top-level `proposed_changes` array → validated `ProposedChange` objects.
- [x] `api/services/change_applier.py` — the ONLY apply path (DECISIONS #6):
      scoring_configs (new active version via dotted-path edits, weight-sum
      invariant enforced), module_memories, positions (+ history events),
      profile_basics/sections, and `action` (dispatch a job, e.g.
      create_and_run_search). Chat router (SSE: message_created/token/tool_use/
      pending_change/done/error, persists messages, stores resume_id, parses
      proposed_changes → pending_changes) + `/changes/*` (list/get/approve/reject;
      approve applies transactionally). Adapter wired into app lifespan.
- [x] Verification: full HITL loop with the fake adapter (20 checks) — chat turn
      → SSE sequence → pending_change row → approve → new active scoring v2
      (remote 0.30 / company 0.10, Σ=1.0, v1 deactivated); invariant guard
      rejects a sum≠1.0 apply. HTTP wiring smoke-tested over uvicorn.

## Stage 5 — Frontend integration ✅ DONE (2026-07-29)
Design imported from Juan's Claude Design project (`DesignSync` MCP, project
c76fb8d1…): the brand design system (dark/executive, Carbon Black + cyan accent,
Space Grotesk/Inter) + a full interactive React prototype of all 19 screens.
A browsable copy is at `frontend/design-reference/design.html` (static reference,
currently untracked; decide at pre-publish whether to keep it). Approach: real Vite+React+TS app, brand
tokens ported 1:1, inline-styles+CSS-vars (NOT Tailwind — matches the delivered
design), typed API client + React Query + SSE, screens rebuilt from the
prototype and wired to the live API.

- [x] Foundation: Vite+React+TS scaffold (`frontend/`, proxy `/api`→:8000),
      tokens (`src/styles/tokens.css`), typed API client + TS types (`src/lib/`),
      SSE helpers (jobs via EventSource, chat via fetch-stream), theme context.
- [x] App shell: Sidebar (nav), Topbar (JobsIndicator polling /jobs, ChangesTray
      = HITL inbox with approve/reject + old→new diffs, theme toggle), ChatDrawer
      (token streaming + tool-use chips + proposed-change cards), router (§8 view
      map) with per-route topbar-slot context.
- [x] Dashboard wired to /dashboard/summary (stat tiles, by-source bars, recent
      searches, top-5, empty state). VERIFIED live: npm install + tsc clean +
      dev server proxies to backend, dashboard shows real data (327 found / 314
      evaluated / avg 60.31 / by-source). NOTE: Vite binds `localhost` (IPv6 ::1),
      not 127.0.0.1 — open http://localhost:5173.
- [x] All 13 screens built + wired to the live API: Dashboard, Positions table,
      Board (kanban drag→status), Position detail (6 tabs: Info+notes edit,
      Evaluation with score dial + criteria bars, History timeline, Documents,
      Company, Application), Searches list, New-search 3-step wizard (→create+run
      →live SSE), Search detail (live per-source run progress via SSE), Analytics
      (funnel + source effectiveness + stale list), Profile, Templates, Scoring
      (read + version history), Memories, Settings. ChatDrawer streams tokens +
      tool-use chips + proposed-change handoff. VERIFIED: tsc clean, `vite build`
      clean (101 modules), dev server + backend — all 20 data endpoints + a
      position detail return 200 through the proxy against real data (0 failures).
- [x] **Position Detail action cluster DONE** (2026-07-21, real-CLI-verified):
      `POST /positions/{id}/evaluate`, `POST /positions/{id}/documents/generate`,
      `GET/PUT /documents/{id}`, `POST /documents/{id}/export`,
      `GET /documents/{id}/file`, `POST /positions/{id}/application` +
      `PATCH /applications/{id}`, `POST /companies/{id}/research` — plus the
      four new job handlers (`evaluate_batch`, `generate_document`,
      `export_document`, `research_company`) and the buttons/forms in
      `PositionDetail.tsx` that call them. New pattern: job handlers call the
      agent CLI directly (one-shot, via `ClaudeAdapter().run()`, NOT through a
      chat thread/`proposed_changes` — these are direct work-product writes,
      not HITL-gated decisions) using new prompt builders in
      `api/agent/task_prompts.py` + `api/agent/output_parser.py`
      (`extract_fenced_block`). Reused `core/evaluate_position.py`'s pure
      scoring math and `core/generate_cv.py`/`generate_cover_letter.py`'s pure
      `markdown_to_pdf`/`markdown_to_docx` renderers directly — NOT their
      `export()`/`OUTPUT_DIR`-coupled wrappers, which hardcode `output/...` at
      the repo root (would've violated hard rule #1); PDF/DOCX now land under
      `data/documents/<position-or-company>/`. Direct-edit PUTs for
      profile/scoring/templates were explicitly dropped from scope (see
      resume-point note above + `PLATFORM_SPEC.md` §5).
      NOT built: `POST /documents/{id}/upload-drive`, onboarding
      (`import-cv`/`status`), `POST /export/sheets` — see resume point.
- [x] **Bulk (re-)evaluate DONE** (2026-07-23): added `POST /positions/evaluate`
      (`{ position_ids: string[] }` → `202`, one job) in `api/routers/positions.py`
      + `EvaluateBatchRequest` schema — thin wrapper, zero changes to the
      `evaluate_batch` job handler, which already looped over a `position_ids`
      list (the single-id `POST /positions/{id}/evaluate` was always just
      calling it with a 1-item list). Frontend: extracted the job-progress
      hook out of `PositionDetail.tsx` into a shared
      `frontend/src/lib/useJobAction.ts`; added an "Evaluate all found" button
      to `SearchDetail.tsx` (evaluates every position from that search run)
      and row checkboxes + a bulk "Evaluate selected" action bar to
      `Positions.tsx` (the filterable table). `PLATFORM_SPEC.md` §5/§8
      updated. Verified: `tsc --noEmit` clean, OpenAPI schema confirms no
      route collision with `/positions/{position_id}`, `EvaluateBatchRequest`
      rejects an empty list. Did NOT submit a real job against `data/app.db`
      during verification (would've triggered the live agent CLI and
      overwritten real scores) — the job-submission code path is identical to
      the already-verified single-position endpoint. Prompted by Juan hitting
      this gap: after running a new search, there was no way to evaluate the
      results in bulk from the front end, only one position at a time.
- [x] Real `claude` CLI chat VERIFIED end-to-end (was Stage 4's owed test). The
      chat "didn't work" because the backend couldn't find `claude` — Juan runs
      Claude Code via the VSCode extension (CLAUDE_CODE_ENTRYPOINT=claude-vscode),
      which bundles the binary but puts no `claude` on PATH. Fixes:
      · `AGENT_CLI_PATH` in `data/credentials/.env` → a STABLE standalone copy
        at `%LOCALAPPDATA%\claude-cli\claude.exe` (also added to USER PATH).
        The official installer (`irm https://claude.ai/install.ps1 | iex`) and
        `claude install` both STALL here downloading the 244MB native binary from
        downloads.claude.ai (metadata `/latest` works, the big file transfer
        times out — likely region/network). Workaround: the extension's bundled
        `claude.exe` is a self-contained 244MB binary — copied it to the stable
        path (survives extension updates). To get auto-updates later, re-run the
        official installer when the network cooperates.
      · `claude_adapter.py`: strip the parent's `CLAUDE_CODE*`/`CLAUDECODE`
        nested-session env vars for the subprocess (`_clean_env`), and read
        stdout as UTF-8 (`encoding="utf-8"`) — Windows text mode defaulted to
        cp1252 and mangled accents ("día"→"dÃ­a").
      Verified: streams tokens, and a scoring-reweight request produced a proper
      `proposed_changes` block → pending_change (diff correct, weights sum 1.0) →
      SSE message_created/pending_change/done. The stream-json format matches the
      parser exactly. Test threads/pending-change cleaned from the real DB.
- [x] **Onboarding wizard DONE** (2026-07-28, browser-verified 14/14). New:
      `api/routers/onboarding.py` (`GET /status` derived + `POST /import-cv`
      multipart→`202`), `api/jobs/handlers/import_cv.py`, `build_cv_import_prompt`
      in `task_prompts.py`, `profile_sections` **`create`** support in
      `change_applier.py` (it only did update-by-id — the import had nowhere to
      land), `frontend/src/screens/Onboarding.tsx` (welcome→upload→live job
      progress→inline approve/reject→derived done), `lib/onboarding.ts` (the
      client-side skip flag), the §7.5 redirect guard in `AppShell.tsx`, and a
      `/onboarding` route. Two calls recorded as DECISIONS #15/#16: `completed`
      is **derived from profile data, never stored** (Juan chose the literal
      spec redirect guard + purely-derived status), and `import_cv` **proposes
      `pending_changes` rather than writing** — the DECISIONS #14 boundary, since
      the profile is user-approved state, not a draft work product. Re-import is
      idempotent (existing slugs aren't re-proposed). Also made the Vite proxy
      target env-overridable (`API_PROXY_TARGET`/`VITE_DEV_PORT`, defaults
      unchanged) so a second dev server can point at a throwaway-DB backend.
- [x] **Visual/pixel pass DONE** (2026-07-29): 14 screens x light+dark,
      28/28 with no console errors, no horizontal overflow, all rendering
      real content. Screenshots reviewed by eye, both themes.
- [x] **Sheets export + Drive upload DONE** (2026-07-29), and both **verified
      against live Google** after Juan ran `scripts/authorize_google.py` —
      export wrote 539/4/4/306 rows, Drive upload passed 11/11 on a DB copy.
      See `PROGRESS_LOG.md` (2026-07-29 entries) for the two bugs the live run
      caught. Gating: export needs `sheets_export_enabled`, upload needs the
      document already exported.

- [x] **`indeed` source wired via MCP DONE** (2026-07-30, live-verified).
      New `api/agent/mcp_sources.py` (`fetch_indeed`) — lives in `api/agent/`,
      not `core/`, because resolving an MCP connector invokes the agent CLI
      (hard rule #3). It matches the existing `_FETCHERS` contract, so
      `search_run` needed only a dict entry + one `except` clause. Supporting
      changes: `AgentTask.allowed_tools` + `--allowedTools` in
      `claude_adapter._build_command` (headless auto-DENIES un-allowlisted
      tools, so without this an MCP call silently returns nothing),
      `run_agent_text(allowed_tools=…)`, `build_indeed_search_prompt` in
      `task_prompts.py`, and `JOB_SEARCH_COUNTRY`/`JOB_SEARCH_LOCATION` +
      `INDEED_MCP_TOOLS` in `api/config.py`. Region is config-driven with
      neutral defaults (`US`/`remote`) — deliberately NOT hardcoded to AR, per
      the first pre-publish item. Both MCP namespaces are allowlisted
      (`mcp__claude_ai_Indeed__*` for an account connector,
      `mcp__indeed__*` for a committed `.mcp.json`) so it works either way.
      An unregistered connector raises `McpSourceUnavailable` → recorded as a
      **skipped** source, not an error (DECISIONS #27).
      VERIFIED: pure-logic unit checks (normalize/dedupe/required-field drop/
      non-ISO date drop/4 failure modes); 4 handler scenarios against a
      throwaway DB (unavailable→skipped, real error→errors=1, happy path
      persists, pre-existing skip path unregressed); and a LIVE end-to-end run
      through the real CLI + Indeed MCP — 20 positions in 40s, all matching the
      normalized shape, incl. LATAM-relevant hits (Backblaze "AI Workflow
      Engineer | LATAM", "AI Engineer - LATAM"). Real `data/app.db` untouched
      throughout. Also corrected a stale note in `core/fetch_jobs_indeed.py`
      that claimed Indeed's MCP was Claude-Connector-only (DECISIONS #28).
      NOT done: `--strict-mcp-config` on the agent subprocess (see pre-publish).
- [x] **Cloner onboarding for the `indeed` source DONE** (2026-07-30). README
      now has an "Optional: enable the Indeed source" section: account-connector
      users need nothing, everyone else runs one `claude mcp add` + `/mcp` to
      authorize with their OWN Indeed account (no key, nothing shared). Also
      documents the market env vars, the graceful skip, the agent-turn cost, the
      empty-description caveat, and the Scrappa alternative.
      ⚠️ A committed `.mcp.json` was tried and **rejected** — it broke the
      working account connector (DECISIONS #29). Don't re-add it without
      re-reading that entry.
- [x] **Indeed job descriptions DONE** (2026-07-30, live-verified 10/10).
      `get_job_details` is now called inside the SAME agent turn as the search
      — Indeed re-issues `job_id` per session, so ids can't be stored and
      resolved by a later job (DECISIONS #30). Gated by
      `INDEED_FETCH_DESCRIPTIONS` (default on) + `INDEED_MAX_DETAILS`
      (default 25); `fetch_indeed` timeout raised to 900s. Measured: 10
      postings took ~25s without descriptions, ~136s with (~11s each), all
      3000-char-capped per `core/CLAUDE.md`.
      Fixed alongside it: **dedupe was keyed on URL, which is wrong** — Indeed
      hands out a fresh redirect token per call, so the same posting appears
      under different URLs and duplicates slipped through. Now keyed on
      company+role, matching `make_position_id`. Same reason a stored Indeed
      URL is perishable.

- [x] **`linkedin` source wired DONE** (2026-07-31, live-verified). Closed the
      biggest discovery gap: linkedin was 219 of 539 positions in the real DB
      yet unreachable from the runner. `_fetch_linkedin` in `search_run.py`
      loops `core/scrape_jobs.scrape_linkedin` per keyword (it takes one
      keyword string, not a list), dedupes, then enriches descriptions. Plain
      in-process HTTP — no agent turn, unlike `indeed`. Config:
      `LINKEDIN_LOCATION` (neutral default `Worldwide`, NOT `Argentina`),
      `LINKEDIN_MAX_PAGES`, `LINKEDIN_FETCH_DESCRIPTIONS`.
      ⚠️ Fixed two latent bugs in `core/scrape_jobs.py` (DECISIONS #31):
      `CONFIG_PATH` and `LI_DESC_CACHE_PATH` were **CWD-relative**, so
      in-process they resolved against uvicorn's start directory — and the
      description cache (scraped job text = user data) wrote to `.tmp/`
      OUTSIDE `data/`, breaking hard rule #1. Both now resolve from the repo
      root; cache moved to `data/cache/` (already gitignored, verified).
      VERIFIED: `Worldwide` and `Argentina` both return results (10 each);
      full fetcher 10/10 with descriptions in 27s cold / 1s warm from cache;
      normalized shape exact and no `_job_id` leak; 2 handler scenarios on a
      throwaway DB (persists correctly; a 429 is an error that doesn't kill the
      run); the 4 Indeed handler scenarios still pass.

## Pre-publish checklist ⬜ (do AFTER the system is fully built, BEFORE going public)
Goal: publish as a public GitHub repo anyone can clone and run in *their own*
professional context. Juan's data must never ship; the repo must be genuinely
region/role-agnostic and easy to onboard.
- [x] **Genericize regional defaults DONE** (2026-07-31, 49 logic checks +
      CLI/API import checks). Search geography is configuration end to end;
      no region is a default anywhere. See DECISIONS #32.
      · **The literals**: `config/job_sites.json` now carries `${JOB_SEARCH_*}` /
        `${LINKEDIN_LOCATION}` placeholders plus a top-level note that it is a
        source catalog, not where you set your market (nothing reads those keys
        from it); `.env.example` ships `TARGET_REGION=worldwide` in a rewritten
        "where you're looking for work" block; `PLATFORM_SPEC.md` §4.4's sample
        `markets` value is neutral.
      · **The real find**: `core/location_filters.py` could only filter for
        LATAM, and all four standalone CLIs called it **by default**
        (`--market latam-argentina`) — so a cloner running them silently dropped
        every non-LATAM-eligible job. It is now a `REGIONS` table (`latam`,
        `north-america`, `europe`, `apac`) selected by `TARGET_REGION`,
        defaulting to `worldwide` = no filtering. `filter_latam_remote` stays as
        an alias; `--market` stays as an alias of the new `--region`; legacy
        values (incl. the `Argentina-LATAM` string the old `.env.example`
        shipped) are mapped, not ignored; an unknown key warns once on stderr
        and filters nothing rather than emptying the search.
      · **Also neutralized**: `scrape_jobs.scrape_linkedin`'s
        `linkedin_location="Argentina"` default, `fetch_jobs_indeed`'s
        `--location Argentina` / `--country ar`, and `fetch_jobs_api`'s
        `--jobicy-geo latam`. All now fall back to env.
      · ⚠️ `data/credentials/.env` still has `TARGET_REGION=Argentina-LATAM`
        (copied from the old `.env.example`). It is aliased to `latam`, so it
        keeps working — change it to a current key when convenient.
      · `search_run` is untouched and still never geo-filters (see its
        docstring), so app behaviour is unchanged; this affects the CLIs.
- [ ] **Decide `--strict-mcp-config` for the agent subprocess.** Without it,
      every MCP server the *cloner* has registered — Gmail, Drive, anything —
      loads into the tool space of the agent this platform spawns. For a
      public repo that's a real surprise and a privacy question, not just a
      reproducibility one. Passing it (plus `--mcp-config` naming only the
      servers the platform needs) makes cloner behaviour deterministic and
      scoped. Deferred from the 2026-07-30 Indeed work as a separate call.
- [ ] **Onboarding assets for cloners.** Author the workflow / skills / globals
      that walk a new user through first run (env + Google creds optional, CV
      import, first search). Ties into the Stage 5 onboarding wizard.
- [ ] **Reconcile core dotenv loading.** ↳ MOSTLY DONE 2026-07-31, as a
      prerequisite of the item above: without it `TARGET_REGION` would have been
      genericized but inert (the fetchers never read `data/credentials/.env`,
      which is where the README tells users to put it). New `core/env_config.py`
      exposes `load_env()` — `data/credentials/.env` then a root `.env`, both
      resolved from the repo root, idempotent — and `fetch_jobs_api.py`,
      `scrape_jobs.py`, `fetch_jobs_indeed.py` and `load_positions_bulk.py` now
      get it by importing `env_config`. WHAT REMAINS: `sheets_manager.py` and
      `google_auth.py` still do their own two-line load with **CWD-relative**
      paths (`load_dotenv("data/credentials/.env")`) — correct only when the
      process starts at the repo root, the same trap as DECISIONS #31. Point
      them at `env_config.load_env()`.
- [ ] **Decide on `frontend/design-reference/`.** The Claude Design prototype
      (`design.html`, 220K) is the only untracked path left. Either commit it as
      the design source of record (it's what DECISIONS #12 points at) or drop it
      and remove the reference.
      ↳ INSPECTED 2026-07-30, and it can't be committed as-is: it carries
      personal data — renders the author's full name in the sidebar and
      references `_ds/<author-name>-design-system-<uuid>/…` stylesheets 55
      times (grep the file for the name to see them). It is
      also broken standalone (those `_ds/` assets and `./support.js` aren't in
      the repo, so it won't render). So the real choice is: genericize the
      name + vendor the missing assets, or drop it and point DECISIONS #12 at
      `frontend/src/styles/tokens.css` as the design source of record.
      ⚠️ `scripts/check_no_secrets.py` did NOT flag this — it looks for
      credentials/tokens/DB files, not personal names. Hard rule #6 (grep for
      names/employers before committing) is a manual step; don't treat a green
      hook as proof the content is genericized.
- [ ] **Final secrets sweep.** `git ls-files | grep -i data` empty; run
      `python scripts/check_no_secrets.py`; `git status --ignored` shows `data/`
      ignored; skim tracked files for personal data (only `LICENSE` should name
      the author).
      ↳ CODE/UI IS CLEAN as of 2026-07-31. Both previously-found files are
      fixed, and the mechanical checks all pass (no tracked file under `data/`,
      `check_no_secrets.py` exit 0, `data/` shows ignored, no tracked
      `.env`/credential/DB file):
      · `Sidebar.tsx` now reads `full_name` from `profile_basics` via React
        Query on the same `["profile","basics"]` key the Profile screen uses —
        so editing your name there updates the sidebar immediately (that screen
        invalidates the whole `["profile"]` prefix). Renders nothing when the
        profile has no name yet, e.g. before onboarding. Verified: `tsc -b
        --noEmit` clean, `vite build` clean (104 modules).
      · `tokens.css` header now describes the file as the design source of
        record (and points at `DESIGN_BRIEF.md` + DECISIONS #12) instead of
        crediting a person.
      Reproduce the name sweep with:
      `git ls-files | while read f; do grep -ilE "<your-surname>" "$f"; done`
      Note `check_no_secrets.py` will NOT catch names — it looks for
      credentials/tokens/DB files.
      ↳ HARNESS DOCS SCRUBBED 2026-07-31. The sweep surfaced what the original
      item didn't anticipate: the docs carried real job-search detail, not just
      the author's name (which is fine and expected in `LICENSE`). Juan chose to
      scrub the specifics and keep the docs. Removed: the named employer he
      applied to plus its position slug and application date, the stale Sheets
      position id, the ATS vendor name, the Drive folder name, and the CV's
      page/char count (that last one also in `DECISIONS.md` #17 and twice in
      `api/agent/claude_adapter.py`, where it justified the stdin decision — now
      "a long CV can extract to ~63k"). Every engineering lesson is intact; only
      the identifying particulars are gone. "Juan" remains where it's plain
      authorship ("Juan chose", "pending Juan's go-ahead"), which is what a
      repo owner's notes normally read like.
      Verify with:
      `git ls-files | while read f; do grep -ilE "<employer>|<folder>|<cv-size>" "$f"; done`
      → only `LICENSE` should match a personal identifier.
      ⚠️ **The name is also already in committed history** (`cd2ee06` 1 file,
      `3948e07` 3, `ce4c31a` 4 — incl. an earlier `PROGRESS.md`). Cleaning the
      working tree is therefore NOT enough: since no remote exists yet, decide
      before adding one whether to squash the branch into a single clean commit
      or accept the name in history. DECISIONS #7 kept this history free of the
      *private repo's* data, but not of the author's own name.
