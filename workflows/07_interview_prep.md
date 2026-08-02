# Workflow 07 — Interview Preparation

## Objective
Produce personalized interview prep when a position reaches
`Interview Scheduled`: probable questions, STAR answers built from the user's
*real* experience, questions for them to ask, and what not to say.

## When to Use
As soon as an interview is confirmed. Prep written the night before is worth
much less than prep the user has time to sit with.

---

## Inputs

| Input | Source |
|---|---|
| `position_id` | The `positions` row |
| Interview date/time, format, interviewer | The user confirms in chat |
| Company research | `company.research_md` (Workflow 06) |
| CV actually sent | The `cv` `Document` for this position |
| Job description | `position.description` |
| Profile | `profile_basics` + `profile_sections` |

The CV that was **sent** matters more than the profile here: the interviewer is
reading that document, and the user needs to be ready to defend what's on it.
If it was edited before sending, use the final version.

---

## Steps

### Step 1: Confirm the status

Interview scheduling is a pipeline transition — `POST /positions/{id}/status`
with `Interview Scheduled`. Propose it if the position isn't there yet; don't
assume it moved.

The full pipeline: `Discovered → Evaluating → Shortlisted → CV Draft →
Ready to Apply → Applied → Acknowledged → Interview Scheduled → Interviewing →
Offer Received → Negotiating → Accepted`, plus the terminal states `Rejected`,
`Withdrawn`, `Ghosted`.

Interview date, interviewer and format belong on the `applications` row
(`PATCH /applications/{id}` — `interview_date`, `contact`, `notes`), not in a
free-text note.

### Step 2: Read the context in this order

1. The profile — what the user actually did
2. The company research — what they care about
3. **The CV that was sent** — what has been claimed
4. The job description — what they're hiring for

### Step 3: Generate the prep

**Section A — Probable questions**

- Behavioral (5-7): "Tell me about a time when…"
- Technical / functional (4-6): drawn from the JD's actual requirements
- Culture fit (3-4): remote work, collaboration, autonomy
- Role-specific (3-5): from JD specifics

**Section B — STAR answers**

For each behavioral question, draft an answer from the user's real cases in the
profile. **Never invent details** — not the situation, not the numbers, not the
outcome. If the profile doesn't have a case that fits a likely question, say so
and suggest the user think of one, rather than manufacturing it.

- **Situation** — the context and business problem as documented
- **Task** — the user's specific responsibility
- **Action** — what they actually did
- **Result** — the metrics as recorded, verbatim

Spread the answers across *different* cases. Rotating through their strongest
achievements is what stops every answer sounding like the same story.

**Section C — Questions for the user to ask**

Start from the research's "Preguntas Estratégicas", plus reliable ones:
- "What does success look like in the first 90 days?"
- "What's the biggest challenge the team is trying to solve right now?"
- "How does the team decide build vs. buy vs. configure?"

A question that shows they read something specific about the company beats a
generic good question.

**Section D — Key points to land**

3-5 talking points tailored to this role + company, from the JD and research.

**Section E — What not to say**

- Don't present weaker skills as core strengths — respect the declared levels
- Don't center the narrative on work the user is moving away from
- Don't undersell the strongest achievement; lead with its real metrics
- Don't say "I'm still learning" about tools they use in production
- Don't claim anything the sent CV doesn't support

### Step 4: Calendar (optional)

If the user has the Google Calendar connector, offer an event: title
"Interview — <Role> @ <Company>", the confirmed time, interviewer and format in
the description, reminders 24h and 1h before. This is a convenience, not a step
the platform depends on — skip it without ceremony if the connector isn't there.

---

## After the interview

The user reports the outcome; propose the matching transition:

| Outcome | Status |
|---|---|
| Moving forward, more rounds | `Interviewing` |
| Offer | `Offer Received` → `Negotiating` → `Accepted` |
| Rejected | `Rejected` (terminal) |
| No response after ~7 days | `Ghosted` (terminal) |
| The user pulls out | `Withdrawn` (terminal) |

Record the substance on the `applications` row — `response_date`, `outcome`,
`follow_up_due`, `notes`. The status says where it is; the application row says
what happened.

Worth capturing while it's fresh: which questions actually came up. That's the
kind of thing that belongs in module memory, and it makes the next prep better.

---

## Output

- Prep delivered in chat (and saved as a document if the user wants it)
- `applications` row updated with interview details
- Position status reflecting reality
