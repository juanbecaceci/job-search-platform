# Workflow 04 — Evaluate & Rank Positions

## Objective

Score positions against the **active scoring config**:

1. Apply the salary gate first — it is eliminatory, not a weighted criterion.
2. Score eligible (and salary-unpublished) positions across the configured
   criteria.
3. Produce a final score (0-100), a category, and a recommended action.

The goal is to spend application effort only on roles that combine salary,
profile fit, remote feasibility, growth, and company stability.

## When to Use

After Workflow 03 (discovery complete). One position or in bulk.

---

## Inputs

| Input | Source |
|---|---|
| Positions to score | `positions` rows — usually `status = Discovered` |
| Candidate profile | `profile_basics` + `profile_sections` (Workflow 01) |
| Criteria, weights, thresholds | The **active** row in `scoring_configs` (`GET /scoring/config`) |

> **Read the weights, don't assume them.** The numbers below are the *seeded
> default*. The active config is versioned and the user can change it in a
> `scoring` chat, so a running install may well differ. Always score against
> what `GET /scoring/config` returns.

---

## Salary gate

Salary is eliminatory and sits outside the weighted average.

- Floor: `salary_gate.floor_usd_month` in the active config (seeded default:
  **USD 3.500/month** equivalent).
- If a range is published, evaluate the **lower bound**.
- Below the floor → **DESCARTADA POR SALARIO**, no score calculated.
- Not published → do **not** discard. Mark **A VALIDAR**, calculate the
  weighted score anyway, and confirm compensation before advancing.

Contract type does not affect the score. Employment, contractor, freelance and
contract roles are all acceptable; record the type as informational only.

---

## Weighted criteria (seeded default — verify against the active config)

Each criterion is scored 1-5.

| Criterion | Default weight | What it measures |
|---|---:|---|
| `profile_alignment` | 40% | Closeness of the role to the user's target roles, as defined in their profile |
| `remote_modality` | 25% | Real remote level and timezone compatibility |
| `seniority_growth` | 20% | Real room to grow in responsibility and career |
| `company_stability` | 15% | Reputation, funding, trajectory, verifiable stability |

```text
Score = Σ(criterion_score × weight) / scale_max × 100
```

Weights must sum to 1.0 — the change applier enforces that invariant, so a
proposal that breaks it is rejected rather than applied.

## Categories (seeded default)

| Category | Score | Recommended action |
|---|---:|---|
| EXCELENTE | 80-100 | Apply immediately, prioritize over the rest |
| BUENA | 60-79 | Apply with a well-prepared application |
| ACEPTABLE | 45-59 | Apply only if nothing better is in progress |
| DESCARTAR | <45 | Don't spend time applying |

Additional marks:
- **DESCARTADA POR SALARIO** — below the floor. No score.
- **A VALIDAR** — salary not published. Scored, but compensation must be
  confirmed before moving forward.

---

## Execution

Evaluation is a **job**, not a chat turn:

- One position: `POST /positions/{id}/evaluate`
- Many: `POST /positions/evaluate` with `{ "position_ids": [...] }`
- From the UI: "Evaluate all found" on a search, or the bulk action on the
  positions table

Both return `202` with a job id and stream progress over SSE.

### How the work is split

The `evaluate_batch` handler calls the agent **once per position**, one-shot —
no chat thread, no `proposed_changes` gate. Reading a job description and
judging fit is reasoning; it writes the result straight onto the position
(DECISIONS #14).

The agent supplies **only the judgement**: a 1-5 score per criterion with a
short note, plus the salary-gate verdict. The arithmetic — weighted score,
category, salary normalization — is done by
`core/evaluate_position.py`'s pure functions, which are the reference
implementation. Don't recompute the score yourself and don't round it.

Expected shape from the agent, per position:

```json
{
  "salary_gate": {
    "status": "PASS",
    "evaluated_usd_month": 4200,
    "salary_text": "USD 4.2k-5.5k/month",
    "note": "Lower bound is above the configured floor."
  },
  "scores": {
    "profile_alignment": { "score": 5, "note": "Automation role with APIs and AI workflow ownership." },
    "remote_modality":   { "score": 4, "note": "Fully remote with workable timezone overlap." },
    "seniority_growth":  { "score": 4, "note": "Mid-level scope with a clear path up." },
    "company_stability": { "score": 3, "note": "Looks legitimate; funding and trajectory need research." }
  },
  "summary": "Strong automation/product-ops fit; research company stability before applying."
}
```

Salary-gate values: `PASS` (published lower bound meets the floor), `FAIL`
(below it), `UNKNOWN` (not published → A VALIDAR).

### ⚠️ Evaluation does not change status

The handler writes the evaluation and appends a history event. It deliberately
does **not** move the position through the pipeline — `Discovered` stays
`Discovered` even at score 12. Status transitions happen only through
`POST /positions/{id}/status`, so the user is always the one moving a position
forward or rejecting it.

So `score_threshold_auto_discard` (default 45) is a **recommendation** you
surface, not something the system acts on. Say "this scores below the discard
threshold, want me to reject it?" — never report it as already rejected.

---

## Reviewing the ranking with the user

`GET /positions/top` returns the ranked list; the UI shows it on the dashboard
and the positions table. Present the top 10-15:

```text
# | Score | Company             | Role                        | Status
---------------------------------------------------------------------------
1 | 86    | Acme SaaS           | Automation Engineer         | Discovered
2 | 74    | Beta FinTech        | Product Operations Manager  | Discovered
```

For each, the user decides:

- **Shortlist** → status update → proceed to Workflow 05
- **Skip** → status update to `Rejected`
- **More info** → research the company (Workflow 06), then re-evaluate
- **Validate salary** → required before advancing any **A VALIDAR** position

Re-evaluating is safe and idempotent: it overwrites the evaluation on that
position. It costs an agent turn per position, so don't re-run a whole batch to
fix one.

---

## Edge cases

**Position has no description.** This is the big one — the description is what
you actually read. Without it you're scoring a job title. Score conservatively,
say so explicitly in the notes, and prefer fetching the description first
(Indeed and LinkedIn both fetch descriptions by default for this reason).

**Annual or hourly compensation.** Convert to a monthly USD equivalent and
evaluate the conservative lower bound. Document the conversion in
`salary_gate.note`.

**Salary not published.** `status: "UNKNOWN"`, mark A VALIDAR. Don't advance to
document generation until compensation is confirmed or the user explicitly
accepts the risk.

**The user changed the weights.** Old evaluations were computed under the old
config and are not recomputed automatically. If a comparison looks off, check
whether the positions were scored under different versions before concluding
the ranking is wrong.

---

## Output

- `position.evaluation` — per-criterion scores with notes, salary gate, final
  score, category, summary
- A `position_events` row recording the evaluation
- Status unchanged (see the warning above)

---

## Next Step

For each position the user shortlists → **Workflow 05 — Generate Documents**
