# Workflow 04 - Evaluate & Rank Positions

## Objective

Evaluate every `Discovered` position with the current opportunity evaluation system:

1. Apply the salary gate first.
2. Score only eligible or salary-unpublished positions across 4 weighted criteria.
3. Assign a final score (0-100), category, recommended action, and rank.

The goal is to spend application effort only on roles that combine salary, profile fit, remote feasibility, growth, and company stability.

## When to Use

After Workflow 03 (discovery complete). Run in batch or individually on demand.

---

## Inputs

| Input | Source |
|---|---|
| Positions with status `Discovered` | Google Sheets |
| Candidate profile | `context/professional_profile.md` |
| Evaluation system + weights | `config/scoring_criteria.json` |

---

## Salary Gate

Salary is eliminatory, not part of the weighted average.

- Floor: **USD 3.500/month equivalent**.
- If a range is published, evaluate the **lower bound**.
- If the published lower bound is below USD 3.500/month, mark the position as **DESCARTADA POR SALARIO** and do not calculate a score.
- If salary is not published, do not discard. Mark as **A VALIDAR**, estimate market fit if possible, calculate the weighted score, and validate compensation before advancing.

Contract type does not affect score. Relationship, contractor, freelance, and contract roles are all acceptable; record contract type as informational only.

---

## Weighted Criteria

Use a 1-5 scale for each criterion.

| Criterion | Weight | What it measures |
|---|---:|---|
| `profile_alignment` | 40% | Closeness to Automation Engineer / AI Operations / Product Engineer / WhatsApp-Conversational AI. |
| `remote_modality` | 25% | Real remote level and timezone compatibility with US/Europe overlap. |
| `seniority_growth` | 20% | Real possibility to grow in responsibility and career. |
| `company_stability` | 15% | Reputation, funding, trajectory, and verifiable company stability. |

Formula:

```text
Score = (profile_alignment*0.40 + remote_modality*0.25 + seniority_growth*0.20 + company_stability*0.15) / 5 * 100
```

---

## Categories

| Category | Score | Recommended action |
|---|---:|---|
| EXCELENTE | 80-100 | Apply immediately, prioritize over the rest. |
| BUENA | 60-79 | Apply with a well-prepared application. |
| ACEPTABLE | 45-59 | Apply only if there are no better options in progress. |
| DESCARTAR | <45 | Do not spend time applying. |

Additional marks:

- **DESCARTADA POR SALARIO**: below USD 3.500/month floor. No score.
- **A VALIDAR**: salary not published. Score is calculated, but compensation must be confirmed before moving forward.

Auto-discard threshold: **score < 45** -> status set to `Rejected`.

---

## Execution

The evaluation is split in two steps: **the agent reasons** through salary/profile/company fit, and **the tool writes deterministically** to Sheets. No paid LLM API is used by this workflow.

### Step 1 - List Positions To Evaluate

```bash
python core/evaluate_position.py --list-pending --status Discovered > .tmp/pending.json
```

This exports `Discovered` positions with id, company, role, salary, URL, location, type, and saved JD/notes.

### Step 2 - Evaluate Salary Gate + Criteria

Read each JD and create `.tmp/scores.json` using this structure:

```json
[
  {
    "position_id": "acme-automation-engineer-a1b2c3",
    "salary_gate": {
      "status": "PASS",
      "evaluated_usd_month": 4200,
      "salary_text": "USD 4.2k-5.5k/month",
      "note": "Lower bound is above the USD 3.500/month floor."
    },
    "scores": {
      "profile_alignment": {
        "score": 5,
        "note": "Automation role with APIs, process automation, and AI workflow ownership."
      },
      "remote_modality": {
        "score": 4,
        "note": "Remote LATAM with US timezone overlap."
      },
      "seniority_growth": {
        "score": 4,
        "note": "Mid-level responsibilities with clear growth into AI operations."
      },
      "company_stability": {
        "score": 3,
        "note": "Company looks valid, but funding and trajectory need more research."
      }
    },
    "summary": "Strong automation/product-ops fit; company stability should be researched before applying.",
    "action": ""
  }
]
```

Salary gate values:

- `PASS`: published lower bound meets or exceeds USD 3.500/month.
- `FAIL`: published lower bound is below USD 3.500/month.
- `UNKNOWN`: salary is not published; mark as A VALIDAR.

### Step 3 - Write Scores + Ranking

```bash
python core/evaluate_position.py --write-scores --data-file .tmp/scores.json
```

The tool:

- Rejects salary failures without calculating score.
- Computes weighted score 0-100 for salary-pass and salary-unknown roles.
- Writes score, category, salary mark, criterion notes, and recommended action to `evaluation_notes`.
- Sets `Rejected` for score <45.
- Sets `Evaluating` for scored positions.
- Re-ranks full-time and gig/freelance tracks separately.

### View Ranking

```bash
python core/evaluate_position.py --show-ranking --min-score 45
python core/evaluate_position.py --show-ranking --tipo gig
python core/evaluate_position.py --rerank
```

Or check Google Sheets directly - "Positions" sheet, sorted by `score` descending.

---

## Reviewing The Ranking With The User

After batch evaluation, present the top 10-15 positions:

```text
# | Score | Company             | Role                        | Status
---------------------------------------------------------------------------
1 | 86    | Acme SaaS           | Automation Engineer         | Evaluating
2 | 74    | Beta FinTech        | Product Operations Manager  | Evaluating
```

For each top position, the user decides:

- **Shortlist** -> status updated to `Shortlisted` -> proceed to Workflow 05.
- **Skip** -> status updated to `Rejected`.
- **More info** -> fetch full JD/company details and re-evaluate.
- **Validate salary** -> required before advancing any `A VALIDAR` position.

To update status:

```bash
python core/sheets_manager.py --action update_status --id <position_id> --status Shortlisted
```

---

## Gig / Freelance Track

Positions with `tipo: gig` or `tipo: freelance` are ranked separately. Contract type does not change the score.

```bash
python core/evaluate_position.py --show-ranking --tipo gig --min-score 45
```

`--write-scores` automatically re-ranks both tracks separately.

---

## Edge Cases

**Position has no description:** Fetch the full JD from the source URL before evaluating when possible. Without a JD, score conservatively and explain uncertainty in notes.

**Salary range uses annual or hourly compensation:** Convert to monthly USD equivalent and evaluate the conservative lower bound. Document the conversion in `salary_gate.note`.

**Salary is not published:** Use `salary_gate.status = "UNKNOWN"` and mark the role A VALIDAR. Do not move to document generation until compensation is confirmed or the user explicitly approves the risk.

**Selector changes in scrapers:** If LinkedIn or another scraper returns empty descriptions or incomplete cards, check `.tmp/scraped_jobs.json` to verify the description field is populated.

---

## Output

- Google Sheets: score, rank, evaluation_notes, status updated.
- Console: evaluation summary and updated ranking.

---

## Next Step

For each confirmed `Shortlisted` position: **Workflow 05 - Generate Documents**
