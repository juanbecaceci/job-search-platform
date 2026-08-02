# Workflow 05 — Generate Application Documents

## Objective
For a shortlisted position: research the company, draft a tailored ATS-friendly
CV and a personalized cover letter, let the user edit them, render to PDF/DOCX,
and optionally upload to Google Drive.

## When to Use
After the user shortlists a position in Workflow 04.

---

## Inputs

| Input | Source |
|---|---|
| `position_id` | The `positions` row |
| Job description | `position.description` — persisted at discovery |
| Candidate profile | `profile_basics` + `profile_sections` |
| Template | The **active version** of the `cv` / `cover_letter` template |
| Company research | `company.research_md` (Workflow 06) |
| Tone | The user's choice: formal / startup / consulting |

> **Architecture note.** Drafting is reasoning and runs through the user's own
> agent CLI — no Anthropic API, no key (DECISIONS #10). Rendering to PDF/DOCX is
> deterministic and happens in `core/`.

---

## The pipeline is two jobs, not one

This mirrors `core/generate_cv.py`'s own design: write the Markdown, export it
later. The gap between them is where the user edits.

1. **Draft** — `POST /positions/{id}/documents/generate` → `202`. The agent
   writes Markdown into a `Document` row. Nothing is rendered yet.
2. **Edit** — `GET /documents/{id}` / `PUT /documents/{id}`. The user (or you,
   at their request) revises the Markdown. Repeat as needed.
3. **Export** — `POST /documents/{id}/export` → `202`. Renders PDF + DOCX to
   `data/documents/<position>/` and records the paths on the row.
   `GET /documents/{id}/file` downloads.
4. **Upload (optional)** — `POST /documents/{id}/upload-drive`. Requires the
   document to have been exported first.

⚠️ Documents are written under `data/`, never to an `output/` directory at the
repo root — everything user-generated lives under `data/` (hard rule #1). The
`export()` wrappers in `core/generate_cv.py` hardcode a repo-root path and are
**not** what the platform calls; it uses the pure `markdown_to_pdf` /
`markdown_to_docx` renderers directly.

---

## Steps

### Step 1: Research the company first

Always. The research is what makes the summary and the cover letter specific
rather than generic. See **Workflow 06**; the short version is
`POST /companies/{id}/research`, which fills `company.research_md`.

### Step 2: Draft the CV

The draft is built from the profile + the job description + the research +
the active CV template. Content rules, which matter more than format:

- Lead with the strongest **relevant** achievement, with its metrics as the
  profile states them — never rounded up, never embellished.
- Skill levels exactly as declared in the profile. No inflation.
- **No invented metrics, ever.** If the profile doesn't support a claim, it
  doesn't go in, however well it would match the JD.
- Mirror the JD's vocabulary where it's honest to do so — that's what ATS
  keyword matching reads.
- Tailor the summary to this role and company specifically.
- ATS-safe layout: no tables, no multi-column, no text in images.

**Validation before moving on:**
- [ ] Lead achievement is relevant to *this* role, with metrics intact
- [ ] Skill levels match the profile
- [ ] No invented metrics
- [ ] Summary is specific to this role/company
- [ ] JD keywords appear naturally, not stuffed
- [ ] No tables or multi-column layout

### Step 3: Edit

The user asks for changes in chat; you rewrite the Markdown via
`PUT /documents/{id}` and re-export. Typical requests:

- "Add SQL to the technical skills section"
- "The summary is too generic, focus it on the role's domain"
- "Drop the teaching bullet, it's not relevant here"

Re-exporting overwrites the rendered files for that document. Iterate until the
user is satisfied — editing the Markdown is cheap, re-drafting from scratch
costs another agent turn.

### Step 4: Draft the cover letter

Same pipeline, `kind: cover_letter`. Keep it **under 350 words**.

**Tone guide:**
- **formal** — banks, large corporations, traditional enterprise
- **startup** — seed to Series B, product companies
- **consulting** — consulting firms, agencies, professional services

**Validation:**
- [ ] Under 350 words
- [ ] Opens with the achievement most relevant to this role
- [ ] References the company specifically — something from the research, not a
      line lifted off their homepage
- [ ] No clichés ("I believe I am a perfect fit")
- [ ] Clear call to action

### Step 5: Export and (optionally) upload

Export both documents, then upload to Drive if the user has authorized Google.
Upload requires a prior export — there is no file to send otherwise. If they
haven't set up Google, that's fine: the files are on disk under `data/documents/`
and downloadable through the API.

### Step 6: Move the position forward

Status changes are **not** part of this workflow's jobs. When the user is ready,
`POST /positions/{id}/status`. Recording an actual application is
`POST /positions/{id}/application`, which creates the `applications` row —
that's the record of what was sent and when.

---

## Edge cases

**No description on the position.** The CV would be tailored to a job title.
Fetch the description first, or tell the user the draft is generic and why.

**Profile too thin.** If the profile has only basics and no sections, drafting
produces something hollow. Send them back to Workflow 01 rather than inventing
substance.

**PDF export fails.** Rendering needs the Playwright Chromium download
(`playwright install chromium`). DOCX doesn't. A failed PDF with a working DOCX
usually means that step was skipped at install.

---

## Output

- `Document` rows (`cv`, `cover_letter`) with Markdown, status `draft`/`final`
- Rendered PDF + DOCX under `data/documents/<position>/`
- Drive URLs recorded, if uploaded
- An `applications` row once the user actually applies

---

## Next Step

→ If an interview is scheduled: **Workflow 07 — Interview Prep**
