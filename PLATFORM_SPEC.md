# Job Search Platform — Platform Specification (v1)

> **Purpose of this document:** single source of truth for the platform's data model, API contract, and view map. It is the contract between the backend (FastAPI + SQLite + agent adapter) and the frontend (React SPA). A UI designer can build every screen against this spec without reading backend code.

---

## 1. What this platform is

A **self-hosted, single-user job search platform**. It automates the full pipeline: discover jobs from multiple sources → evaluate & score them against the user's profile → manage applications through a status pipeline → generate tailored CVs/cover letters → analyze what's working.

The AI reasoning (evaluating jobs, drafting documents, editing configuration through chat) is performed by a **local agent CLI** (Claude Code in v1, agent-agnostic adapter) running under the **user's own subscription** — no API keys, no cloud backend. Deterministic work (scraping, scoring arithmetic, PDF/DOCX export, DB access) is plain Python.

### Core principles the UI must reflect

1. **Human-in-the-loop, always.** The agent never applies a change directly. It proposes changes as structured diffs (`pending_changes`). The user reviews and approves/rejects each one in the UI. Every screen that shows agent output must make the "proposed vs. applied" distinction visually unmistakable.
2. **Chat everywhere.** A global chat drawer is available on every route. It knows which module/entity the user is looking at and can propose changes to any module.
3. **Everything is editable** — manually (forms/editors) or via chat. Manual edits apply immediately; chat edits go through the approval flow.
4. **The system learns.** Each module has a "memory" (lessons learned) the agent updates from user feedback — visible and editable in the UI.
5. **Long work is asynchronous.** Searches, batch evaluations, document generation run as background jobs with live progress (SSE). The UI never blocks.

---

## 2. Architecture (context for the designer)

```
React SPA  ◄── HTTP + SSE ──►  FastAPI (localhost)
                                ├─ SQLite (source of truth)
                                ├─ Job runner (async jobs + progress events)
                                ├─ Change applier (approved diffs → DB)
                                ├─ core/ Python tools (scrapers, exporters)
                                └─ Agent adapter → `claude -p` (user's subscription)
```

- Single user, no auth/login screens.
- All URLs below are prefixed `/api/v1`.
- Paginated lists return `{"items": [...], "total": n, "page": p, "page_size": s}`.
- Errors return `{"error": {"code": "position_not_found", "message": "..."}}`.
- Dates are ISO-8601 strings (UTC).

---

## 3. Enums

### Position status (the application pipeline — 15 states, in order)
```
Discovered → Evaluating → Shortlisted → CV Draft → Ready to Apply → Applied
→ Acknowledged → Interview Scheduled → Interviewing → Offer Received
→ Negotiating → Accepted
Terminal: Rejected · Withdrawn · Ghosted
```

### Other enums
| Enum | Values |
|---|---|
| `source` | `remotive`, `remoteok`, `himalayas`, `arbeitnow`, `jobicy`, `linkedin`, `indeed`, `manual` |
| `tipo` (job type) | `full-time`, `gig`, `freelance` |
| `track` (ranking track) | `full-time`, `gig-freelance` |
| `salary_gate` | `PASS`, `FAIL`, `NEEDS VALIDATION` (unpublished salary) |
| `score_category` | `EXCELLENT` (80–100), `GOOD` (60–79), `ACCEPTABLE` (45–59), `DISCARD` (0–44). Plus two markers written when the salary gate, not the score, decides: `NEEDS VALIDATION` and `BELOW SALARY FLOOR` |
| `search.status` | `draft`, `running`, `finished`, `analyzed`, `failed` |
| `job.status` | `queued`, `running`, `succeeded`, `failed`, `cancelled` |
| `job.type` | `search_run`, `evaluate_batch`, `generate_document`, `export_document`, `upload_drive`, `research_company`, `agent_chat`, `import_cv`, `sheets_export` |
| `pending_change.status` | `pending`, `approved`, `rejected`, `applied`, `failed`, `expired` |
| `change_type` | `update`, `create`, `delete`, `action` |
| `module` | `profile`, `templates`, `scoring`, `searches`, `positions`, `documents`, `analytics`, `onboarding` |
| `document.kind` | `cv`, `cover_letter`, `company_research` |
| `actor` | `user`, `agent`, `system` |

---

## 4. Entities (JSON shapes as returned by the API)

### 4.1 Position (central entity)

```json
{
  "id": "acme-automation-engineer-a1b2c3",
  "company": { "id": 12, "name": "Acme Corp", "industry": "SaaS", "size": "51-200", "website": "https://acme.com" },
  "search_id": 3,
  "source": "remotive",
  "sources": ["remotive", "linkedin"],
  "tipo": "full-time",
  "track": "full-time",
  "role": "Automation Engineer",
  "url": "https://remotive.com/jobs/12345",
  "location": "Remote (LATAM)",
  "remote": "Yes",
  "salary_raw": "USD 4,000–5,500/month",
  "salary_min_usd_month": 4000,
  "salary_max_usd_month": 5500,
  "salary_gate": "PASS",
  "date_posted": "2026-07-02",
  "date_discovered": "2026-07-08",
  "score": 82.5,
  "score_category": "EXCELLENT",
  "rank": 1,
  "scoring_config_version": 3,
  "evaluation": {
    "profile_alignment":  { "score": 5, "weight": 0.40, "rationale": "Exact match for automation engineering..." },
    "remote_modality":    { "score": 4, "weight": 0.25, "rationale": "Remote LATAM with US overlap..." },
    "seniority_growth":   { "score": 4, "weight": 0.20, "rationale": "..." },
    "company_stability":  { "score": 3, "weight": 0.15, "rationale": "..." }
  },
  "summary": "Strong fit: automation-first role at funded SaaS...",
  "recommended_action": "Apply immediately, prioritize over the rest.",
  "status": "Shortlisted",
  "description": "…(job description, max 3000 chars)…",
  "tags": ["python", "automation", "APIs"],
  "notes": "…free-form notes…",
  "created_at": "2026-07-08T14:02:11Z",
  "updated_at": "2026-07-09T09:30:00Z"
}
```

### 4.2 Position event (history timeline)

```json
{
  "id": 981,
  "position_id": "acme-automation-engineer-a1b2c3",
  "event_type": "status_change",
  "from_value": "Evaluating",
  "to_value": "Shortlisted",
  "payload": { "note": "Great fit, prioritize" },
  "actor": "user",
  "created_at": "2026-07-09T09:30:00Z"
}
```
`event_type`: `created` · `status_change` · `score_change` · `field_update` · `note` · `document_generated` · `application_update`.

### 4.3 Application (1:1 with position)

```json
{
  "id": 44,
  "position_id": "acme-automation-engineer-a1b2c3",
  "cv_document_id": 210,
  "cover_letter_document_id": 211,
  "date_applied": "2026-07-09",
  "applied_via": "Company site",
  "contact": "jane@acme.com",
  "response_date": null,
  "interview_date": null,
  "outcome": null,
  "follow_up_due": "2026-07-16",
  "notes": ""
}
```

### 4.4 Search

```json
{
  "id": 3,
  "name": "AI Ops July",
  "keywords": ["AI operations", "automation engineer", "workflow automation"],
  "sources": ["remotive", "jobicy", "linkedin", "indeed"],
  "posted_within_days": 7,
  "markets": ["latam", "europe"],
  "status": "analyzed",
  "total_found": 143,
  "total_new": 37,
  "total_evaluated": 37,
  "avg_score": 58.2,
  "last_run_at": "2026-07-08T13:00:00Z",
  "runs": [
    {
      "id": 7,
      "job_id": "d3adb33f-...",
      "started_at": "2026-07-08T12:55:00Z",
      "finished_at": "2026-07-08T13:00:00Z",
      "stats": {
        "remotive":  { "fetched": 50, "new": 12, "duplicates": 8, "errors": 0, "filtered_out": 30 },
        "linkedin":  { "fetched": 75, "new": 20, "duplicates": 30, "errors": 0, "filtered_out": 25 },
        "jobicy":    { "fetched": 18, "new": 5,  "duplicates": 2,  "errors": 0, "filtered_out": 11 }
      }
    }
  ]
}
```

**`markets` is the search's geography, and it is applied** (DECISIONS #35).
Values are region keys from `core/location_filters.py`'s `REGIONS` table
(`latam`, `north-america`, `europe`, `apac`), served to the UI by
`GET /searches/defaults` so no client keeps its own copy. Semantics:

- **Union** — a position survives if *any* listed market could take it.
- **Empty falls back to `TARGET_REGION`**, so a search that says nothing about
  geography behaves like the CLIs. The shipped default is `worldwide`, which
  filters nothing.
- A `worldwide` or unrecognized member collapses the union to no filtering. An
  unknown key must never be the reason a search comes back empty.
- The drop is **reported, never silent**: `filtered_out` per source in
  `stats`, plus `total_filtered_out` and the resolved `regions` on the job
  result. `fetched` stays the raw source count, so the funnel reads "the source
  returned N, geography removed M".
- Filtering only starts once a real region is named; while it is off,
  **non-remote roles are kept**. Once a region is named, remote eligibility is
  part of the test (`is_region_eligible` rejects non-remote roles outright).

### 4.5 Job (async work)

```json
{
  "id": "d3adb33f-1234-...",
  "type": "search_run",
  "status": "running",
  "progress": 0.66,
  "progress_message": "linkedin: page 2/3",
  "result": null,
  "error": null,
  "created_at": "2026-07-08T12:55:00Z",
  "started_at": "2026-07-08T12:55:02Z",
  "finished_at": null
}
```

### 4.6 Pending change (the HITL diff)

```json
{
  "id": 55,
  "thread_id": 9,
  "module": "scoring",
  "change_type": "update",
  "target_table": "scoring_configs",
  "target_id": null,
  "summary": "Raise remote_modality weight to 0.30, lower company_stability to 0.10",
  "diff": [
    { "field": "criteria.remote_modality.weight",  "old": 0.25, "new": 0.30 },
    { "field": "criteria.company_stability.weight","old": 0.15, "new": 0.10 }
  ],
  "status": "pending",
  "created_at": "2026-07-09T10:11:00Z"
}
```
For `change_type: "action"`, `diff` is `{"action": "create_and_run_search", "payload": {...}}` — approving dispatches a job instead of writing rows.

### 4.7 Chat thread & message

```json
{ "id": 9, "title": "Scoring tweak", "module": "scoring", "entity_type": null, "entity_id": null, "archived": false }
```
```json
{
  "id": 301, "thread_id": 9, "role": "assistant",
  "content": "I suggest raising the remote weight because...",
  "attachments": [ { "filename": "jd.pdf", "mime": "application/pdf" } ],
  "status": "complete",
  "pending_change_ids": [55],
  "created_at": "2026-07-09T10:11:00Z"
}
```

### 4.8 Profile

```json
// GET /profile/basics
{ "full_name": "…", "headline": "…", "email": "…", "phone": "…",
  "location": "…", "linkedin_url": "…", "portfolio_url": "…" }

// GET /profile/sections → ordered array
[ { "id": 1, "slug": "experience", "title": "Experience", "content_md": "…", "sort_order": 0, "updated_by": "user", "updated_at": "…" } ]
```

### 4.9 Template (versioned)

```json
{
  "id": 1, "kind": "cv", "name": "CV default",
  "active_version": { "id": 14, "version": 5, "content_md": "…", "change_note": "Tightened summary", "created_by": "agent", "created_at": "…" }
}
```

### 4.10 Scoring config (versioned)

```json
{
  "version": 3,
  "is_active": true,
  "salary_gate": { "floor_usd_month": 3500, "evaluation_basis": "lower_bound", "unpublished_status": "NEEDS VALIDATION" },
  "score_threshold_auto_discard": 45,
  "scale_max": 5,
  "categories": [
    { "id": "EXCELLENT",  "min_score": 80, "max_score": 100, "recommended_action": "Apply immediately, prioritize." },
    { "id": "GOOD",       "min_score": 60, "max_score": 79,  "recommended_action": "Apply with a well-prepared submission." },
    { "id": "ACCEPTABLE", "min_score": 45, "max_score": 59,  "recommended_action": "Apply only if nothing better is in progress." },
    { "id": "DISCARD",    "min_score": 0,  "max_score": 44,  "recommended_action": "Do not invest time." }
  ],
  "criteria": [
    { "id": "profile_alignment", "name": "Profile alignment", "weight": 0.40, "scale": "1-5", "description": "…", "hints": { "5": "…", "1": "…" } },
    { "id": "remote_modality",   "name": "Remote modality",   "weight": 0.25, "scale": "1-5", "description": "…", "hints": {} },
    { "id": "seniority_growth",  "name": "Seniority & growth","weight": 0.20, "scale": "1-5", "description": "…", "hints": {} },
    { "id": "company_stability", "name": "Company stability", "weight": 0.15, "scale": "1-5", "description": "…", "hints": {} }
  ]
}
```
Validation the UI should enforce live: **criterion weights must sum to 1.0**; category ranges must cover 0–100 without gaps/overlaps. Score formula: `Σ(criterion_score × weight) / scale_max × 100`. Salary gate is eliminatory: `FAIL` → auto-Rejected without score.

### 4.11 Document

```json
{
  "id": 210, "position_id": "acme-automation-engineer-a1b2c3",
  "kind": "cv", "version": 2,
  "content_md": "…markdown source…",
  "pdf_available": true, "docx_available": true,
  "drive_url": null,
  "status": "draft",
  "created_by": "agent", "created_at": "…"
}
```

### 4.12 Module memory

```json
{ "module": "documents", "content_md": "- Never exceed one page.\n- Lead with the flagship project…", "updated_by": "agent", "updated_at": "…" }
```

---

## 5. API reference

### Dashboard & analytics
| Method | Path | Returns |
|---|---|---|
| GET | `/dashboard/summary?from&to` | `{ positions_found, positions_evaluated, avg_score, searches_run, by_source: [{source, found, avg_score}] }` — default last 7 days |
| GET | `/analytics/sources?from&to` | `[{ source, discovered, avg_score, applied, interviews, offers }]` |
| GET | `/analytics/funnel?from&to` | `{ discovered, applied, responded, interviews, offers, accepted }` |
| GET | `/analytics/stale?days=14` | `[{ position: {…}, days_stale, suggested_action: "follow_up" \| "mark_ghosted" }]` |

### Searches
| Method | Path | Notes |
|---|---|---|
| GET | `/searches?status&page` | list with persisted metrics |
| GET | `/searches/defaults` | `{ sources: [{id, label, enabled_default}], keyword_groups: {automation_engineer: [...], ai_ops: [...], ...}, regions: [{id, label}], default_region }` |
| POST | `/searches` | `{ name, sources, keywords, posted_within_days, markets }` → created as `draft` |
| GET | `/searches/{id}` | full detail incl. `runs` and `positions_by_source` |
| POST | `/searches/{id}/run` | `202 → { job_id, search_run_id }`; search status → `running` |
| DELETE | `/searches/{id}` | drafts only |

### Positions & applications
| Method | Path | Notes |
|---|---|---|
| GET | `/positions?status&source&search_id&track&min_score&q&sort&page` | filterable table |
| GET | `/positions/top?limit=5` | best-ranked, excludes Rejected/Withdrawn/Ghosted |
| GET | `/positions/board` | `{ columns: [{ status, count, positions: [compact cards] }] }`. A compact card carries `id, role, company, source, status, score, score_category, rank, salary_raw, url, track, date_discovered` |
| POST | `/positions` | manual intake |
| GET | `/positions/{id}` | full detail: position + company + evaluation + events + application + documents |
| PATCH | `/positions/{id}` | field edits (logs `field_update` event) |
| POST | `/positions/{id}/status` | `{ status, note? }` — validates pipeline enum, logs event |
| POST | `/positions/{id}/evaluate` | `202` re-evaluate with active scoring config |
| POST | `/positions/evaluate` | `{ position_ids: string[] }` → `202`, one job scores all of them (bulk re-evaluate — new search results, or existing positions after a scoring change) |
| POST | `/positions/{id}/application` · PATCH `/applications/{id}` | create/update application record |
| POST | `/positions/{id}/documents/generate` | `{ kind, instructions? }` → `202` agent drafts markdown |
| GET/PUT | `/documents/{id}` | read / edit markdown source |
| POST | `/documents/{id}/export` | `202` → PDF + DOCX |
| POST | `/documents/{id}/upload-drive` | `202` optional Google Drive upload; `409` unless the document was exported to PDF/DOCX first |
| GET | `/documents/{id}/file?format=pdf\|docx` | binary download |

### Profile, templates, scoring, memories, settings
| Method | Path | Notes |
|---|---|---|
| GET | `/profile/basics` | single record |
| PUT | `/profile/basics` | direct edit; only the fields sent are touched (upserts the row) |
| GET | `/profile/sections` | ordered list |
| POST | `/profile/sections` | `{ slug, title, content_md?, sort_order? }` → `201`; slug normalized + must be free |
| PUT | `/profile/sections/{id}` | direct edit (all fields optional) |
| DELETE | `/profile/sections/{id}` | `204` |
| POST | `/profile/sections/reorder` | `{ section_ids: number[] }` — full ordered list, rewrites `sort_order` |
| GET | `/templates` · `/templates/{id}/versions` | |
| GET | `/scoring/config` | |
| GET | `/scoring/config/versions` | history |
| GET | `/memories` · `/memories/{module}` | lessons learned per module |
| GET | `/settings` | key-value bag (sheets export on/off, agent adapter, paths) |
| PUT | `/settings` | `{ values: {...} }` — **whitelisted keys only** (`WRITABLE_KEYS` in `api/routers/settings.py`); unknown or mistyped keys `422` |
| POST | `/export/sheets` | `202` one-way mirror to Google Sheets; `409` if the export toggle is off |

> **PUT `/memories/{module}` is not built** (GET only — see
> `api/routers/memories.py`). `PUT /settings` exists but is **whitelisted**:
> only keys in `WRITABLE_KEYS` can be set, and each is type-checked. The bag
> also holds runtime facts (paths, adapter identity) that are not user
> preferences, so a blanket write endpoint would turn a settings form into a
> way to reconfigure the backend. Add a key when a real control needs it.

> **Onboarding `completed` is derived, never stored.** `GET /onboarding/status`
> computes it from the profile itself — `profile_basics.full_name` present AND
> at least one `profile_sections` row with non-empty `content_md` (exactly what
> `generate_document` needs before it will draft anything). There is no stored
> "onboarding done" flag and deliberately no endpoint to set one, so the status
> can't drift from reality: approving the imported changes is what completes
> onboarding. The wizard's "skip for now" is therefore a **client-side**
> escape only (`frontend/src/lib/onboarding.ts`, localStorage), suppressing the
> §7.5 guard on that browser without inventing server state.

> **`POST /onboarding/import-cv` proposes, it does not write.** The `import_cv`
> job extracts the PDF text (pypdf), has the agent structure it, and creates
> `pending_changes` rows — one `update` for `profile_basics`, one `create` per
> `profile_sections` entry — which the wizard shows for approval. This is
> DECISIONS #14's stated boundary: unlike `generate_document`/`research_company`
> (draft work products, written directly), the profile is user-approved state,
> so it goes through the HITL gate. Sections whose slug already exists are not
> re-proposed, so a re-import can't fork the profile into duplicates.

> **Profile is directly editable; templates and scoring are still chat-only.**
> The profile write endpoints above were added on an explicit UI decision
> (2026-07-29) — the user edits their own profile in a form, in both
> `Profile.tsx` and the onboarding wizard. This does **not** loosen DECISIONS
> #6: that gate is for the *agent's* writes, and agent-proposed profile changes
> still go through `pending_changes` exactly as before (see DECISIONS #19).
> `Scoring.tsx` and `Templates.tsx` remain chat-only, so `PUT /templates/{id}`,
> `PUT /scoring/config` and their version-activate siblings are still
> intentionally unbuilt — don't add them without the same explicit decision.

### Companies
| Method | Path |
|---|---|
| GET | `/companies` · GET/PATCH `/companies/{id}` |
| POST | `/companies/{id}/research` → `202` (agent researches, result to `research_md` + document) |

### Jobs, changes, chat, onboarding
| Method | Path | Notes |
|---|---|---|
| GET | `/jobs?status&type` · `/jobs/{id}` | |
| POST | `/jobs/{id}/cancel` | best-effort |
| **GET (SSE)** | `/jobs/{id}/events` | see §6 |
| GET | `/changes?status=pending` · `/changes/{id}` | the approval tray |
| PATCH | `/changes/{id}` | `{ diff, summary? }` — rewrite a still-**pending** proposal before approving (stamps `edited_at`; `409` if not pending, `422` for `action` changes). The applier's whitelists still police the edited diff |
| POST | `/changes/{id}/approve` | applies transactionally → `{ status: "applied" }` |
| POST | `/changes/{id}/reject` | `{ reason? }` — reason offered as feedback to module memory |
| GET | `/chat/threads?module&entity_type&entity_id` · POST `/chat/threads` | |
| GET | `/chat/threads/{id}/messages` | history |
| **POST (SSE)** | `/chat/threads/{id}/messages` | multipart `content` + `files[]`; response is a live event stream (§6) |
| GET | `/onboarding/status` | `{ completed, steps: [{ id, label, done }] }` — **derived**, see note |
| POST | `/onboarding/import-cv` | multipart `file` (PDF) → `202 { job_id }` (`import_cv` job) |

---

## 6. SSE event streams

### Job progress — `GET /jobs/{id}/events`
```
event: progress   data: { "progress": 0.66, "message": "linkedin: page 2/3", "stats": {…} }
event: done       data: { "result": {…} }
event: failed     data: { "error": "…" }
```

### Chat — response stream of `POST /chat/threads/{id}/messages`
```
event: message_created  data: { "user_message_id": 300, "assistant_message_id": 301 }
event: token            data: { "text": "I suggest raising " }
event: tool_use         data: { "name": "Read", "summary": "Reading scoring config" }
event: pending_change   data: { "change_id": 55, "module": "scoring", "summary": "…", "diff": [...] }
event: job_started      data: { "job_id": "…", "type": "search_run" }
event: done             data: { "message_id": 301 }
event: error            data: { "message": "…" }
```

---

## 7. Global UI shell (present on every route)

1. **Sidebar** — module navigation: Dashboard, Searches, Positions, Analytics, Profile, Templates, Scoring, Memories, Settings.
2. **ChatDrawer** — collapsible right panel. Derives `module` + `entity` from the active route (e.g. on `/positions/abc123` the thread is scoped to that position). Renders streaming tokens, tool-use indicators, attachments (file upload), and **PendingChangeCard**: summary + expandable field-level diff (old → new) + Approve / Reject buttons. Approve shows applied confirmation; Reject offers optional reason ("save as lesson for this module?").
3. **JobsIndicator** — badge with count of running jobs; popover lists them with progress bars (live via SSE).
4. **ChangesTray** — global inbox of pending changes across all modules (badge count). Same PendingChangeCard component.
5. **Onboarding guard** — if `GET /onboarding/status → completed: false`, redirect to `/onboarding` (implemented in `AppShell.tsx`; held until the status query resolves so a cold load doesn't bounce, and suppressed by the client-side "skip for now" flag — see the §5 note).

---

## 8. View map

| Route | View |
|---|---|
| `/onboarding` | First-run wizard: welcome → drop CV PDF (`POST /onboarding/import-cv`, live job progress) → **review**: approve/reject each proposed change inline (basics + one card per section) → done (derived checklist). Further refinement happens in the ChatDrawer, which is scoped to the `profile` module on this route |
| `/` | **Dashboard**: date-range picker (default 7 days) · stat tiles (positions found, evaluated, avg score, searches run) · by-source breakdown chart · Top 5 positions (score + status chip) · recent searches list |
| `/searches` | Table: name, date, status chip, avg score, sources; row click → detail |
| `/searches/new` | **3-step wizard**: ① name → ② sources (toggle cards, all on by default) → ③ keywords (chips, pre-filled from system defaults, add/remove) + posted-within selector (7 / 30 / 180 days) + **markets** (toggle chips from `defaults.regions`; none selected states the `TARGET_REGION` fallback and whether it filters) → Create & Run |
| `/searches/:id` | Header (status, metrics) · **live run progress panel** (per-source progress via SSE) · per-source stats table (fetched/new/duplicates/errors/filtered_out) · keywords used · found positions table · **Evaluate all found** button (`POST /positions/evaluate` with this run's position ids, live job progress) |
| `/positions` | Filterable/sortable table (status, source, search, track, min score, text search) + totals; quick status change per row; row checkboxes + **select all (filtered)** + bulk **Evaluate selected** action (`POST /positions/evaluate`, live job progress) |
| `/positions/board` | **Kanban**: one column per pipeline status, drag & drop card → `POST /{id}/status`; terminal states collapsed to the right |
| `/positions/:id` | Detail with tabs: **Info** (all fields, edit) · **Evaluation** (score dial 0-100, category badge, per-criterion breakdown bars with rationale, salary gate result, config version used, re-evaluate button) · **History** (timeline of position_events) · **Documents** (markdown drafts, edit, export PDF/DOCX, Drive upload) · **Company** (info + research) · **Application** (dates, contact, outcome, follow-up). Status changer in header |
| `/analytics` | Source effectiveness (discovered/avg score/applied/interviews per source) · conversion funnel (discovered→applied→responded→interviews→offers) · stale applications list with one-click actions (follow up / mark Ghosted) |
| `/profile` | Basics form + section editor (markdown, reorder, add/delete) |
| `/templates` | Per-template markdown editor + version history panel with diff & rollback |
| `/scoring` | Salary gate form · criteria weight editor (live Σ=1.0 validation, sliders + numeric) · categories editor · version history with rollback |
| `/memories` | Per-module markdown editor of lessons learned |
| `/settings` | Sheets export toggle + spreadsheet ID · agent adapter selector (Claude v1; Codex reserved) · paths · CLI health check (`claude --version` status) |

---

## 9. UX rules

- **Language:** English UI. All strings centralized (i18n-ready).
- **Optimistic UI** for manual edits (status drag & drop, notes); **explicit confirmation** for agent-proposed changes — these are two visually distinct interaction families.
- **Empty states matter** (fresh install has zero data): every list/dashboard needs a friendly empty state pointing to the next action (run onboarding → create first search).
- Long-running actions always show: job started toast → progress in JobsIndicator → completion toast with link to result.
- Score is always displayed 0–100 with its category color: EXCELLENT / GOOD / ACCEPTABLE / DISCARD (4 stable semantic colors + neutral for unevaluated).
- Positions in terminal states (Rejected/Withdrawn/Ghosted) are visually muted everywhere.
- Destructive actions (delete section, reject change, mark Ghosted) need confirmation.
- Desktop-first (self-hosted tool), but dashboard and kanban should degrade gracefully to tablet width.
