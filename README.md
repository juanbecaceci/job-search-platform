# Job Search Platform

A **self-hosted, AI-powered job search platform**. Discover jobs from multiple sources, evaluate and score them against *your* profile, generate tailored ATS-ready CVs and cover letters, and manage your application pipeline — all running locally, with the AI reasoning powered by **your own agent CLI subscription** (Claude Code in v1). No API keys, no cloud backend, your data never leaves your machine.

> **Status: feature-complete, pre-release.** The database, API, agent integration and web UI are all built and running against real data. Search geography is now fully configurable (see "Set your market"). Remaining before a public release: first-run onboarding docs and a final secrets sweep — see the roadmap below.

## How it works

```
Web UI (React)  ◄──►  Local API (FastAPI)  ◄──►  SQLite (your data)
                            │
                            ├── core/       deterministic Python tools (scrapers, scoring math, PDF/DOCX export)
                            └── agent/      your local agent CLI (claude -p) does the reasoning:
                                            evaluating jobs, drafting documents, editing config via chat
```

Three principles:

1. **Human-in-the-loop.** The agent never applies changes directly — it proposes diffs you approve or reject in the UI.
2. **Bring your own agent.** The AI runs through the agent CLI you're already subscribed to. v1 supports Claude Code; the adapter interface is ready for other CLIs.
3. **Publishable by construction.** Everything personal (profile, database, documents, credentials) lives in `data/`, which is fully gitignored.

## What it does

- **Discover** — searches Remotive, Remote OK, Himalayas, Arbeitnow and Jobicy (free APIs), plus **LinkedIn** (public guest endpoint, no login) and **Indeed** (optional connector, see below), all deduped into one pipeline.
- **Evaluate** — a salary gate plus weighted criteria you control produce a 0–100 score per job; low scores are auto-discarded.
- **Manage** — a 15-state application pipeline (Discovered → … → Accepted) with kanban view, full history and analytics (source effectiveness, conversion funnel, stale-application detection).
- **Generate** — tailored CV + cover letter per position (Markdown → PDF/DOCX), driven by your profile's content rules (never inventing metrics).
- **Learn** — per-module feedback memory: your corrections make future runs better, and you can see and edit everything it learned.

## Repository layout

```
api/          FastAPI backend: routers, Pydantic schemas, SQLAlchemy models,
              async job runner (SSE progress), agent adapter
core/         deterministic Python tools (scraping, scoring, export, Google)
workflows/    markdown SOPs the agent follows for each pipeline stage
frontend/     React + TypeScript SPA (Vite) — 14 screens, light/dark
config/       source catalog + default scoring criteria and templates
scripts/      setup, migration, Google authorization and safety scripts
data/         ── gitignored ── ALL your personal data: SQLite DB,
              profile, documents, attachments, credentials, .env
PLATFORM_SPEC.md   the full platform contract (data model, API, views)
```

## Getting started

**Prerequisites:** Python 3.11+, Node 18+, and an agent CLI you're subscribed to (Claude Code).

```bash
# 1. Install
pip install -r requirements.txt
playwright install chromium        # only needed for PDF export
cd frontend && npm install && cd ..

# 2. Configure
cp .env.example data/credentials/.env
#    Set AGENT_CLI_PATH if `claude` isn't on your PATH — e.g. when you use
#    Claude Code via the VSCode extension, which bundles the binary but
#    doesn't expose it on PATH.

# 3. Create the database
alembic upgrade head              # builds all 19 tables
python scripts/seed_defaults.py   # scoring criteria, CV/cover-letter templates

# 4. Run both servers
python -m uvicorn api.main:app --port 8000     # API + Swagger at /docs
cd frontend && npm run dev                     # SPA
```

Then open **http://localhost:5173** and the first-run wizard will walk you through importing your CV. Google Sheets/Drive are optional — run `python scripts/authorize_google.py` once if you want the export mirror and document upload.

### Set your market

Where you're looking is configuration, not something baked into the code. Every
default is neutral, so nothing searches someone else's country by accident — but
that also means the defaults are almost certainly not *your* market. Set these in
`data/credentials/.env` before your first search:

```bash
# Where to search — each site wants a different format, hence two settings
JOB_SEARCH_COUNTRY=US        # Indeed: ISO 3166 two-letter code, e.g. AR, ES, DE
JOB_SEARCH_LOCATION=remote   # Indeed: a city/state string, or "remote"
LINKEDIN_LOCATION=Worldwide  # LinkedIn: a geography NAME, e.g. Argentina, Spain

# Which results you can actually take
TARGET_REGION=worldwide      # worldwide | latam | north-america | europe | apac
```

`TARGET_REGION` is the filter, not the search. Job boards happily return roles
locked to a region you can't work from — "US only", "EMEA", "Remote (India)" —
and this drops those while keeping anything advertised as global or anywhere.
The default `worldwide` filters nothing, which is the right place to start;
narrow it once you see how many results you can't legally take. Region term
lists live in [`core/location_filters.py`](core/location_filters.py) — add a
region there if yours isn't covered, it's a plain list of strings.

The same settings drive the standalone `core/` CLIs, which also accept
`--region`, `--linkedin-location`, `--location` and `--country` to override them
per run.

LinkedIn needs no account, key or setup beyond that — it reads the public guest
endpoint. It is slower than the API sources (pages are fetched with 3-6s delays
and it rate-limits after ~10 pages per IP), and each posting costs a second
request for its description. Those are cached by job id under `data/cache/`, so
re-running a search is nearly free — measured 27s cold, 1s warm for 10 postings.
Tune with `LINKEDIN_MAX_PAGES` and `LINKEDIN_FETCH_DESCRIPTIONS`.

### Optional: enable the Indeed source

The five sources above need no setup. **Indeed** is optional and needs a one-time
authorization with *your own* Indeed account — nothing is shared with anyone else,
and no API key is involved.

**If your agent CLI account already has an Indeed connector**, you're done —
nothing to install. Skip to the market settings below.

**Otherwise**, register it once and authorize in your browser:

```bash
claude mcp add --transport http indeed https://mcp.indeed.com/claude/mcp
claude           # run once inside the repo
/mcp             # authorize — opens your browser to sign in to Indeed
```

> Deliberately **not** shipped as a committed `.mcp.json`. A project-scoped
> server sits in "pending approval" until you accept it, and while pending it
> suppresses an already-working account connector — so shipping the file would
> break the setup of anyone who already had Indeed connected. Registering it
> yourself only when you need it avoids that.

Set your market in `data/credentials/.env` (Indeed requires a country — there is
no "global" option):

```bash
JOB_SEARCH_COUNTRY=US        # ISO 3166 two-letter code, e.g. AR, ES, DE
JOB_SEARCH_LOCATION=remote   # or a city/state string
```

Then tick **indeed** among the sources when you create a search.

Two things worth knowing:

- **If you skip this, nothing breaks.** Searches run on the other five sources and
  Indeed is reported as *skipped*, not as an error.
- **It costs an agent turn**, unlike the other sources which are plain HTTP calls,
  because the connector is reached through your agent CLI. Indeed listings carry
  no job description either, so each posting needs a second call to fetch one
  (~11s each, capped by `INDEED_MAX_DETAILS`, default 25). Measured: ~25s for 10
  postings without descriptions, ~135s with them. Set
  `INDEED_FETCH_DESCRIPTIONS=false` to skip them, at the cost of much weaker
  scoring — the description is what the evaluator reads.
- **Indeed URLs are not permalinks.** Every call returns a fresh redirect token
  for the same posting, so a stored Indeed link may stop resolving over time.
  Positions are identified by company + role, never by URL.

Prefer not to use the connector? `core/fetch_jobs_indeed.py` fetches Indeed over
plain HTTP through a data provider instead — deterministic and agent-free, but it
needs a `SCRAPPA_API_KEY`.

See `PLATFORM_SPEC.md` for the complete design contract.

## Roadmap

- [x] **Stage 0** — Platform spec (`PLATFORM_SPEC.md`)
- [x] **Stage 1** — Repo skeleton, genericized core tools and workflows
- [x] **Stage 2** — SQLite schema + read API (dashboard, positions, searches)
- [x] **Stage 3** — Write operations + async job runner (searches with live progress)
- [x] **Stage 4** — Agent adapter (chat, proposed-change approval flow, per-module memory)
- [x] **Stage 5** — Web UI integration + onboarding wizard
- [x] **Pre-release** — configurable search geography (no region baked into the code)
- [ ] **Pre-release** — first-run onboarding docs, scoped MCP config, final secrets sweep

## Privacy & safety

- `data/` is the only place user data lives and it is never committed.
- `scripts/check_no_secrets.py` runs as a pre-commit hook and blocks commits containing credentials, tokens, or database files.
- Job-board sources are used within their ToS (attribution links preserved; no redistribution to third-party platforms).

## License

MIT — see [LICENSE](LICENSE).
