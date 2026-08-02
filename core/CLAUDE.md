# core/ — deterministic tools

12 of these files were ported verbatim from a private production job-search
tracker on 2026-07-10, then genericized (all personal names, employers, metrics,
and past-run details removed or replaced — verified via `git grep` before the
first commit, see repo root commit `cd2ee06`). `google_auth.py` is the one
module written here rather than ported (added 2026-07-29, DECISIONS #23).

`api/jobs/handlers/*` imports these modules **directly, in-process** — no
subprocess calls to the Python tools (subprocess is reserved for invoking the
agent CLI itself). Anything you change here can break a live job handler.

## Rules for this directory

- **No LLM/API calls here.** These are deterministic Python: scraping,
  arithmetic, file I/O, PDF/DOCX export, Sheets/Drive access. Reasoning (job
  evaluation sub-scores, document drafting, chat) belongs in `api/agent/` via
  the `AgentAdapter`, not here. See root `DECISIONS.md` #9.
- **Preserve the normalized position shape** used across `fetch_jobs_api.py`,
  `scrape_jobs.py`, `fetch_jobs_indeed.py`, `load_positions_bulk.py`:
  `source, tipo, company, role, url, location, remote, salary, description
  (≤3000 chars), tags, date_posted`. `PLATFORM_SPEC.md` §4.1 depends on this
  shape mapping cleanly into the `positions` table — don't change field names
  without updating both.
- **Keep functions importable, not just CLI-callable.** Each fetch/scrape
  function must be callable with plain arguments and return data, independent of
  its `argparse` CLI wrapper — that's how the job handlers report per-source
  progress.
- **`evaluate_position.py`'s arithmetic (`compute_weighted_score`,
  `category_for_score`, salary gate normalization) is the reference
  implementation** for the score formula documented in `PLATFORM_SPEC.md`
  §4.10. `api/jobs/handlers/evaluate_batch.py` reuses these functions rather
  than reimplementing the math — keep it that way.
- **Reuse the pure renderers, not the `export()` wrappers.** `generate_cv.py` /
  `generate_cover_letter.py` expose pure `markdown_to_pdf` / `markdown_to_docx`
  plus `export()` wrappers that hardcode an `output/` path at the repo root.
  Callers in `api/` use the pure renderers and write under
  `data/documents/…` — going through the wrappers would violate hard rule #1.
- **Google access goes through `google_auth.py`, and never prompts.** One token
  at `data/credentials/token.json` carries both Sheets and Drive scopes. Server
  code calls `get_credentials(interactive=False)`, which raises
  `GoogleAuthError` with a re-auth hint; only `scripts/authorize_google.py` runs
  the interactive browser flow. Don't reintroduce a `flow.run_local_server()`
  reachable from an API request — inside a job handler that blocks a server
  thread on a prompt nobody will see (DECISIONS #23).
- **Env loading goes through `env_config.load_env()`** (added 2026-07-31,
  completed 2026-08-02): it loads `data/credentials/.env` then a root `.env`,
  resolved from the repo root rather than the CWD, and is idempotent. Every
  module that needs env now gets it that way — `fetch_jobs_api.py`,
  `scrape_jobs.py`, `fetch_jobs_indeed.py` and `load_positions_bulk.py` by
  importing `env_config`, `sheets_manager.py` and `google_auth.py` by calling
  `load_env()`. Don't add a bare `load_dotenv()` anywhere: it reads only a root
  `.env`, so a user who followed the README gets defaults instead of their
  settings.
- **Any other relative path goes through `env_config.repo_path()`**, for the
  same reason: it rebases a relative value on the repo root and passes an
  absolute one through untouched. `google_auth.py`'s `CREDENTIALS_FILE` /
  `TOKEN_FILE` use it, so a job handler under uvicorn reads the same token the
  CLI wrote. A default like `data/credentials/token.json` written bare is a bug
  waiting for a process that starts somewhere else (DECISIONS #31).
- **Two import shapes, and modules must survive both.** `core/` files use
  sibling imports (`from location_filters import …`), so an importer from `api/`
  puts `ROOT/core` on `sys.path` (see `api/jobs/handlers/search_run.py`).
  `google_auth.py`, `sheets_manager.py` and `upload_to_drive.py` need the
  reverse as well — they import `core.*` — so each puts the **repo root** on
  `sys.path` itself rather than relying on its caller. That is why
  `python core/sheets_manager.py` works even though `api/routers/positions.py`
  imports the same module with no path fixup.
- **Search geography is configuration, never a literal.** `TARGET_REGION`,
  `LINKEDIN_LOCATION`, `JOB_SEARCH_COUNTRY` and `JOB_SEARCH_LOCATION` are read
  through `env_config`, and `api/config.py` reads the same names so both halves
  of the system agree. `location_filters.py` is region-driven off `REGIONS`;
  its default is `worldwide`, which filters nothing. Never reintroduce a country
  or region as a default value (DECISIONS #32).
- If you find yourself wanting to add a new personal detail (a real API key,
  a real spreadsheet ID, a real name) to any file here — stop, that belongs in
  `data/`, never in `core/`.
