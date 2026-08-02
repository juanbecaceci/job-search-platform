# Workflow 02 - Configure a Job Search Session

## Objective
Define a search session with clear parameters before running discovery. Each
session has a name, keywords, target markets and a source selection, and is
saved as a `searches` row that can be re-run.

## When to Use
- Starting a new round of job search
- Targeting a specific niche or geography
- Right after first-run setup (**Workflow 00**) hands off the first search

---

## Inputs

Ask the user to confirm:

| Parameter | Options | Default |
|---|---|---|
| Search name | Any descriptive name | e.g., `automation_remote_jul26` |
| Keywords | Comma-separated list | See `config/job_sites.json` -> `search_keywords_by_role` |
| Markets | Whatever the user's `TARGET_REGION` allows: `worldwide` / `latam` / `north-america` / `europe` / `apac` | `TARGET_REGION` from their `.env` (`worldwide` = unfiltered) |
| Sources | Any of the ids in the table below | The 5 free APIs; add `linkedin`/`indeed` on request |
| Type | full-time / gig / freelance | full-time |
| Min score threshold | 0-100 | From the **active scoring config** (`GET /scoring/config`), not a file — the seeded default is generic and meant to be tuned |

---

## Steps

### 1. Confirm keywords

Use `config/job_sites.json` -> `search_keywords_by_role` as starting point:
- `automation_engineer`: automation engineer, automation consultant, process automation, workflow automation
- `product_ops`: product operations, product ops, product engineer, technical product manager
- `ai_ops`: AI operations, AI ops, conversational AI, chatbot operations, LLM operations
- `operations`: operations automation, digital operations, business automation, operations specialist
- `freelance_automation`: automation specialist, workflow automation, process automation consultant

Ask the user if he wants to customize or add keywords.

### 2. Confirm sources

The sources the runner can actually fetch (this is the whole list — it mirrors
the `Source` enum, and anything else is rejected):

| id | Kind | Setup needed |
|---|---|---|
| `remotive` | Free public API | None |
| `remoteok` | Free public API | None |
| `himalayas` | Free public API | None |
| `arbeitnow` | Free public API | None |
| `jobicy` | Free public API | None |
| `linkedin` | Public guest-endpoint scraper | None, but slow and rate-limits |
| `indeed` | MCP connector, costs an agent turn | One-time interactive authorization |
| `manual` | Positions the user adds by hand | Not queried automatically |

Important notes:
- The 5 free APIs are the default discovery track: no auth, no rate limits, fast.
- `linkedin` needs no account but paginates with 3-6s delays and returns HTTP
  429 after roughly 10 pages per IP.
- `indeed` is reached through the user's own agent CLI. If its connector was
  never authorized, the run records it as **skipped**, not as an error.
- `manual` is for roles the user finds outside the system; they go through the
  same scoring flow once added.

### 3. Save the search

The search is a row in the `searches` table, created through the UI's
new-search wizard or `POST /searches`. SQLite is authoritative — Google Sheets
is an optional one-way export mirror and is never read back (DECISIONS #2), so
there is nothing to log there by hand.

You can propose edits to an existing search's configuration (`name`, `keywords`,
`sources`, `posted_within_days`, `markets`) but never to its metrics, and never
while it is running.

### 4. Run it

`POST /searches/{id}/run` returns `202` with a job id and streams per-source
progress over SSE. Unsupported or unauthorized sources are recorded as
`skipped` with the rest of the run continuing.

---

## Source Decision Guide

| Source | Best for | Notes |
|---|---|---|
| `remotive` | Remote-first SaaS roles | Free, no auth |
| `remoteok` | Remote tech roles | Free, no auth |
| `himalayas` | Remote-first tech roles | Paged feed; local keyword filtering |
| `arbeitnow` | Remote roles with EU/DACH bias | Filters remote + keyword locally |
| `jobicy` | Highest yield of the free APIs | The only one with real server-side filtering |
| `linkedin` | Volume | Public `jobs-guest` endpoint, no login. Slow; HTTP 429 after ~10 pages per IP. Descriptions cached under `data/cache/`, so re-runs are cheap |
| `indeed` | High volume, global coverage | MCP connector authorized with the user's **own** Indeed account; costs an agent turn. Unauthorized → the run records it as `skipped`. Its URLs are not permalinks — positions are identified by company + role |
| `manual` | Startups / one-off finds | Added by hand, same scoring flow |

---

## Recommended Presets

- **Remote full-time search:** Remotive, Remote OK, Himalayas, Arbeitnow, Jobicy, plus LinkedIn and Indeed if they're set up
- **Fast first run:** the five free APIs only — no auth, no rate limits, quick
- **Startup or external finds:** manual

If the user does not specify otherwise, use:
- `type = full-time`
- `markets` = whatever their `TARGET_REGION` is; never assume a country
- `sources = Remotive, Remote OK, Himalayas, Arbeitnow, Jobicy` (add LinkedIn
  and Indeed once the user confirms they want the slower/authorized sources)

---

## Output

- A `searches` row saved with its keywords, sources and market
- Ready to run, and re-runnable — discovery dedupes against everything already
  stored, so re-running finds what's new rather than duplicating

---

## Next Step

-> Run **Workflow 03 - Discover Jobs**
