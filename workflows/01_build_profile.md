# Workflow 01 — Build / Update the Professional Profile

## Objective
Maintain the user's professional profile as the source of truth every other
workflow reads: evaluation scores positions against it, document generation
drafts CVs and cover letters from it, and interview prep works off it.

The profile lives in the **database**, not in a file:

| Where | What |
|---|---|
| `profile_basics` (one row, `target_id` `"1"`) | `full_name`, `headline`, `email`, `phone`, `location`, `linkedin_url`, `portfolio_url` |
| `profile_sections` (many rows) | `slug`, `title`, `content_md`, `sort_order` — one per section (experience, skills, achievements, education, …) |

## When to Use
- First-time setup (see **Workflow 00 — First Run** for the whole path)
- The user has a newer CV, a new role, a new certification
- The user corrects or adds something in conversation

---

## Three ways the profile changes — know which one you're in

1. **CV import** — `POST /onboarding/import-cv` runs a job that extracts a PDF
   and *proposes* basics + sections. The user approves them in the tray.
2. **Chat (you)** — you propose edits with `proposed_changes`. You have no write
   access; nothing you say changes the profile until it is approved.
3. **The user's own form** — `/profile` writes directly, no approval step
   (DECISIONS #19). The gate exists for *your* writes, not theirs.

So never say "I've updated your profile". Say what you're proposing, and that it
is waiting in the changes tray.

---

## Inputs

| Input | Source | Required |
|---|---|---|
| Current profile | The entity snapshot in this prompt — carries basics and every section **with its `id`** | Always |
| A CV | A text-based PDF, uploaded in the wizard | For import-based updates |
| Conversation | The user's corrections and additions | For chat-based updates |

---

## Steps

### A. Import-based update

1. The user uploads a PDF in the wizard. The job proposes the changes; you don't
   run it.
2. Help them read the proposals: what each section would add, and whether the
   extraction misread anything (dates and job titles are the usual casualties).
3. Re-import is idempotent — a section whose `slug` already exists is not
   proposed again, so a second import cannot duplicate their profile.

### B. Chat-based update

1. Read the current profile from the entity snapshot, never from memory of an
   earlier turn.
2. Propose one change per section you're touching:
   - rewrite a section → `update` on `profile_sections`, `target_id` = its id
   - add a section → `create` on `profile_sections`, `target_id` null, `diff`
     including at least a `slug` that doesn't collide with an existing one
   - remove a section → `delete` on `profile_sections`, `target_id` = its id
   - contact details / headline → `update` on `profile_basics`, `target_id` `"1"`
3. Quote the existing text in `old` so the user sees a real diff.

---

## Content rules (these are the point of the workflow)

- **Never invent experience.** If the CV and the profile don't support a claim,
  it doesn't go in — not even to match a job description better. A profile that
  wins an interview it can't survive is worse than one that doesn't.
- **Never inflate skill levels.** Use the level the user declared.
- **Keep quantified achievements verbatim.** Don't round figures up, don't
  restate "18%" as "nearly 20%", don't turn a specific result into a vaguer,
  grander one.
- **Prefer specific over impressive.** A concrete responsibility beats a
  superlative.
- **Write the professional summary and any ATS-keyword section in English**,
  which is what the document templates and most parsers expect — regardless of
  the language the rest of the conversation is in.
- **Preserve the user's own wording** where it is already good. Rewriting
  everything into one voice loses the detail that makes a profile credible.

---

## Validation checklist

Before treating the profile as ready for document generation:

- [ ] `full_name` is set and at least one section has real content — this is
      literally what `GET /onboarding/status` derives `completed` from
- [ ] Quantified achievements appear with their original figures
- [ ] Skill levels match what the user declared — no inflation
- [ ] Nothing present that the CV or the user didn't provide
- [ ] Sections ordered sensibly via `sort_order`
- [ ] Professional summary / ATS keywords in English
- [ ] Salary expectation, if the user set one, matches the salary gate in the
      active scoring config

---

## Edge cases

**Scanned PDF.** Extraction returns almost nothing, and the import job fails on
purpose rather than sending the agent a blank page. Ask for a text-based export.

**Very large CV.** Long documents are fine — prompts go over stdin, not argv, so
there is no command-line length limit to hit (DECISIONS #17).

**Profile older than a few months.** Before a serious search round, ask the user
to confirm it is still accurate. A stale profile quietly degrades every score.

**The user wants a profile file.** There isn't one — the profile is database
state. If they want a document out of it, that's document generation
(**Workflow 05**), not this workflow.

---

## Output

- `profile_basics` + `profile_sections` updated, through approved changes
- Onboarding reads as complete once a name and one section with content exist

## Next Step

→ **Workflow 02 — Configure a Job Search Session**
