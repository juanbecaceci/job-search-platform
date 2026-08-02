# Workflow 00 — First Run (fresh clone)

## Objective
Take a freshly-cloned install from "nothing configured" to its first scored
search results. This is the SOP you follow when the person you're talking to is
new to the platform — they cloned a public repo, they are not the author, and
nothing here is set up for them yet.

## When to Use
- Chat scoped to the `onboarding` module
- The profile is empty or partial (`GET /onboarding/status` → `completed: false`)
- The user says a first search returned nothing, or that setup "isn't working"

---

## What you can and cannot do here

You have **no write access to the database**. Everything you want to change is
*proposed* and the user approves it in the changes tray (see the output protocol
at the end of this prompt). Two things follow from that:

- Never say "I've set that up" or "I've imported your CV". Say what you are
  proposing and that it is waiting for their approval.
- Configuration that lives in files (`.env`, `config/job_sites.json`) is **not**
  proposable at all. For those, tell the user the exact line to edit and where
  the file lives. Do not pretend to edit it.

The CV import is the one place this gets confusing: `POST /onboarding/import-cv`
runs a job that reads their document and *proposes* profile sections. The user
still has to approve them. That is deliberate — the profile is user-approved
state, not a draft work product.

---

## Inputs

| Input | Source | Required |
|---|---|---|
| A CV / résumé | **A text-based PDF** uploaded in the wizard | Yes — nothing else works well without a profile |
| Market settings | `data/credentials/.env` | Yes, or they silently search the wrong place |
| Agent CLI path | `AGENT_CLI_PATH` in the same `.env` | Only if `claude` isn't on PATH |
| Google OAuth credentials | `data/credentials/credentials.json` | No — Sheets/Drive are optional |

---

## Steps

### 1. Confirm the install is actually running

Both servers must be up. If the user can see the UI at all, the frontend is
fine; what usually breaks is the API or the database.

- API health: `GET /health`
- Database: if `alembic upgrade head` and `python scripts/seed_defaults.py`
  were never run, the app will render but every list is empty and scoring has
  no active config.

If scoring looks unconfigured, `seed_defaults.py` is idempotent — it is always
safe to suggest re-running it.

### 2. Set their market before anything is fetched

This is the single most common way a first run disappoints someone: the
defaults are deliberately neutral, so they are almost certainly not the user's
market. Ask where they are looking, then tell them to set these in
`data/credentials/.env`:

| Variable | What it means | Neutral default |
|---|---|---|
| `JOB_SEARCH_COUNTRY` | Indeed: ISO 3166 two-letter code | `US` |
| `JOB_SEARCH_LOCATION` | Indeed: city/state, or `remote` | `remote` |
| `LINKEDIN_LOCATION` | LinkedIn: a geography **name**, not a code | `Worldwide` |
| `TARGET_REGION` | Which results they can actually take | `worldwide` (filters nothing) |

`TARGET_REGION` is a filter, not a search: it drops roles locked to a region
they can't work from ("US only", "EMEA") while keeping anything global. Accepted
values are `worldwide`, `latam`, `north-america`, `europe`, `apac` — the term
lists live in `core/location_filters.py` and a region can be added there. Start
at `worldwide` and narrow only if their results are full of roles they can't
legally take.

The API must be restarted for `.env` changes to take effect.

### 3. Check the agent CLI is reachable

Every reasoning step — CV import, evaluation, document drafting, this
conversation — shells out to the user's own agent CLI. No API key is involved
(DECISIONS #10). If chat works, this is already fine.

If it doesn't: the usual cause is that they run Claude Code through the VSCode
extension, which bundles the binary but puts no `claude` on PATH. The fix is to
point `AGENT_CLI_PATH` in `data/credentials/.env` at a real binary path.

### 4. Import their CV

Send them to the first-run wizard (`/onboarding`) and have them upload their CV.
The job extracts text, then proposes `profile_basics` plus one
`profile_sections` row per section it identifies.

**The upload accepts PDF only** — anything else is rejected with a 422 before
the job starts. If their CV is a DOCX or a Google Doc, have them export it to
PDF first. It also has to be a *text* PDF: a scanned image extracts almost no
characters and the job fails deliberately rather than sending the agent a blank
page.

Then walk them through the proposals rather than leaving them to guess:

- Sections come back as *proposals* — they approve or reject each one.
- Re-importing is safe: a section whose `slug` already exists is not proposed
  again, so a second import can't duplicate their profile.
- The profile is also directly editable at `/profile` (DECISIONS #19) — their
  own form writes straight through, no approval needed. That asymmetry is
  intentional: the gate is for *your* writes, not theirs.

Onboarding is considered complete when `full_name` is set and at least one
section has content. That status is **derived**, never stored — there is no
"mark complete" button to look for.

### 5. Offer Google Sheets/Drive, and make clear it's optional

Nothing requires it. If they want the export mirror and document upload:
`python scripts/authorize_google.py` once, with their own OAuth credentials at
`data/credentials/credentials.json`. Sheets export is one-way and truncates the
tabs it owns (DECISIONS #2), so it should never point at a spreadsheet holding
anything they care about.

If they skip it, say so plainly and move on — do not treat it as a missing step.

### 6. Run the first search

Hand off to **Workflow 02** for the parameters. For a first run specifically:

- Start with the five free public APIs (`remotive`, `remoteok`, `himalayas`,
  `arbeitnow`, `jobicy`). They need no auth and return quickly.
- `linkedin` works with no account but is slow (paginated with 3-6s delays, and
  it rate-limits after ~10 pages per IP).
- `indeed` needs a one-time interactive authorization of the MCP connector. If
  they haven't done it, the source is recorded as **skipped**, not as an error —
  that is expected behaviour, not a failure to debug.
- Keep the keyword list short for the first run. It is faster to see whether the
  pipeline works end to end than to tune recall on day one.

### 7. Evaluate, and set expectations about scoring

Discovered positions arrive unscored. Evaluation is a separate job — "Evaluate
all found" on the search, or the bulk action on the positions table.

Scoring uses the seeded default criteria, which are generic on purpose. Their
first results will rank *something*, but the ranking only becomes meaningful
once the weights reflect what they actually care about. Offer to adjust the
scoring config in a `scoring` chat — that is a proposal like everything else,
and the criteria weights must still sum to 1.0.

---

## Troubleshooting — the traps a first run actually hits

| Symptom | Cause | Fix |
|---|---|---|
| CV upload rejected immediately (422) | The endpoint accepts PDF only | Export the CV to PDF |
| CV job fails with "could not extract usable text" | Scanned/image PDF — almost no extractable characters | Export a text-based PDF |
| Dashboard shows 0 of everything, but positions exist | The dashboard window defaults to the last 7 days; freshly imported or migrated data may be older | Widen the range |
| A source silently returns nothing | Its connector was never authorized | Check the run's per-source stats — an unavailable MCP source is recorded as `skipped` |
| Indeed results have no descriptions | `INDEED_FETCH_DESCRIPTIONS=false`, or the per-run cap was hit | Raise `INDEED_MAX_DETAILS`; descriptions matter a lot for scoring |
| LinkedIn stops returning results mid-run | HTTP 429 after ~10 pages per IP | Lower `LINKEDIN_MAX_PAGES`, wait, re-run — the description cache makes re-runs cheap |
| A new endpoint 404s after an update | Routes and job handlers are registered at **startup** | Restart the API |
| Search results are all roles they can't take | `TARGET_REGION` is `worldwide` | Narrow it (step 2) |
| Search returns far fewer results than expected | `TARGET_REGION` is too narrow, or an unrecognized value | An unknown key filters nothing and warns once on stderr; check the value against the accepted list |

---

## Output

- A profile with basics + at least one section (onboarding reads as complete)
- Market variables set in `data/credentials/.env`
- One search run with results, evaluated

## Next Step

→ **Workflow 02 — Configure a Job Search Session** for a real, tuned search.
