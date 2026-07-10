# Workflow 07 — Interview Preparation

## Objective
Generate comprehensive, personalized interview prep for the user when a position reaches `Interview Scheduled` status. Includes probable questions, STAR answers from the user's real experience, questions to ask, and a calendar event.

## When to Use
When a position moves to `Interview Scheduled` status. Run as soon as the interview is confirmed.

---

## Inputs

| Input | Source |
|---|---|
| position_id | Google Sheets |
| Interview date/time | The user confirms |
| Interview format | Phone / Video / Technical / Panel |
| Interviewer name/role | If known |
| Company research | `output/companies/<company>/research.md` |
| CV sent | `output/cvs/<position_id>/cv.md` |
| Job description | Sheets → `description` |
| Profile | `context/professional_profile.md` |

---

## Steps

### Step 1: Update status

```bash
python core/sheets_manager.py --action update_status \
  --id <position_id> \
  --status "Interview Scheduled"
```

### Step 2: Read all context

Load in this order:
1. `context/professional_profile.md`
2. `output/companies/<company>/research.md`
3. `output/cvs/<position_id>/cv.md`
4. Job description from Sheets

### Step 3: Generate prep materials

As the agent, generate the following directly in chat (or save to `output/interviews/<position_id>/prep.md`):

**Section A — Probable Questions**

Categorized:
- Behavioral (5-7 questions): "Tell me about a time when..."
- Technical/functional (4-6 questions): Automation approach, tool selection, project methodology
- Culture fit (3-4 questions): Remote work, team collaboration, autonomy
- Role-specific (3-5 questions): Based on JD specifics

**Section B — Suggested STAR Answers**

For each behavioral question, draft a STAR answer using the user's real cases, taken from
`context/professional_profile.md` (never invent details):

Primary case: the profile's **flagship project** —
- Situation: context and business problem, as documented in the profile
- Task: the user's specific responsibility
- Action: what the user actually did (led, designed, implemented, iterated)
- Result: the validated metrics, verbatim, plus any awards or recognition

Secondary cases: the other quantified achievements in the profile (each with its own
situation → metric mapping), used to avoid repeating the flagship case in every answer.

**Section C — Questions the user Should Ask**

Pull from company research "Preguntas Estratégicas" section, plus:
- "What does success look like in the first 90 days?"
- "What's the biggest challenge the team is trying to solve right now?"
- "How does the team approach automation decisions — build vs. buy vs. configure?"

**Section D — Key Points to Highlight**

3-5 talking points specifically tailored to this role+company, based on the JD and research.

**Section E — What NOT to Say**

Reminders derived from the user's profile positioning rules:
- Don't position weaker skills as core strengths (respect declared skill levels)
- Don't center the narrative on roles the user is moving away from
- Don't undersell the flagship case — lead with its validated metrics
- Don't say "I'm still learning" about tools the user actively uses at work

---

### Step 4: Create calendar event

```
mcp__claude_ai_Google_Calendar__create_event
```

Parameters:
- Title: "Interview — <Role> @ <Company>"
- Date/time: as provided by the user
- Description: Include interviewer name, format, and link to prep doc
- Reminder: 24h before + 1h before

---

## Output

- `output/interviews/<position_id>/prep.md` — full prep document (optional save)
- Google Calendar event created
- Sheets: status → `Interview Scheduled`

---

## After the Interview

The user reports the outcome:
- **Positive:** status → `Interviewing` or `Offer Received`
- **Rejected:** status → `Rejected`
- **No response after 7 days:** status → `Ghosted`

Update via:
```bash
python core/sheets_manager.py --action update_status \
  --id <position_id> \
  --status "<new_status>"
```
