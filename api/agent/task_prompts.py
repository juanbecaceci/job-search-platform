"""One-shot task prompts for job handlers that call the agent directly.

Unlike `prompt_builder.py` (chat turns, strict `proposed_changes` HITL output),
these are direct work-product jobs (DECISIONS-adjacent but not gated by
approval — the spec describes them as `202` jobs that write straight to the
entity: evaluation scores, a drafted document, a research brief). Each builder
returns `(system_prompt, user_prompt)`; the system prompt's only job is to pin
down a single, strictly-shaped fenced output block that `output_parser.
extract_fenced_block` can pull back out.
"""

from __future__ import annotations

import json
from typing import Any


def _format_hints(hints: Any) -> str:
    """`criteria[].hints` is a `{score: description}` map (e.g. `{"5": "...", "1": "..."}`)."""
    if isinstance(hints, dict):
        return "; ".join(f"{score}={desc}" for score, desc in hints.items())
    return str(hints)


def build_evaluation_prompt(
    position: dict[str, Any],
    company_name: str | None,
    config: dict[str, Any],
) -> tuple[str, str]:
    criteria = config.get("criteria", [])
    criterion_lines = "\n".join(
        f"- `{c['id']}` (weight {c['weight']}, scale 1-{config.get('scale_max', 5)}): "
        f"{c.get('name', c['id'])} — {c.get('description', '')} "
        f"{('Hints: ' + _format_hints(c['hints'])) if c.get('hints') else ''}".strip()
        for c in criteria
    )
    salary_gate_cfg = config.get("salary_gate", {})

    system = f"""\
You are evaluating one job posting against a weighted scoring rubric. Read the
posting and score each criterion below, plus the salary gate. Be concrete and
grounded in the posting text — don't invent details it doesn't contain.

Criteria to score (1-{config.get("scale_max", 5)} each):
{criterion_lines}

Salary floor: USD {salary_gate_cfg.get("floor_usd_month", "unspecified")}/month
({salary_gate_cfg.get("evaluation_basis", "as stated in the posting")}).

Respond with ONLY one fenced ```json block (no text before or after it), shaped:
{{
  {", ".join(f'"{c["id"]}": {{"score": <int>, "rationale": "<1-2 sentences>"}}' for c in criteria)},
  "salary_gate": {{"status": "PASS|FAIL|UNKNOWN", "evaluated_usd_month": <number or null>, "salary_text": "<as posted>", "note": "<why>"}},
  "summary": "<one short paragraph overall assessment>"
}}"""

    user = (
        f"Role: {position.get('role', '')}\n"
        f"Company: {company_name or 'unknown'}\n"
        f"Location: {position.get('location', '—')} · Remote: {position.get('remote', '—')} · "
        f"Type: {position.get('tipo', '—')}\n"
        f"Salary as posted: {position.get('salary_raw', '—')}\n"
        f"Listing URL: {position.get('url', '—')}\n\n"
        f"Job description:\n{position.get('description') or '(no description available)'}"
    )
    return system, user


def build_document_prompt(
    kind: str,
    position: dict[str, Any],
    company_name: str | None,
    template_content_md: str | None,
    profile_basics: dict[str, Any],
    profile_sections: list[dict[str, Any]],
    instructions: str | None,
) -> tuple[str, str]:
    doc_label = "CV" if kind == "cv" else "cover letter"
    sections_md = "\n\n".join(
        f"### {s.get('title', s.get('slug', ''))}\n{s.get('content_md', '')}" for s in profile_sections
    )

    system = f"""\
You are drafting a tailored {doc_label} in Markdown for ONE specific job
application. Adapt content to the job description below (relevant keywords,
ordering, emphasis) without inventing experience the candidate doesn't have.

Follow this template's structure/style as the formatting reference:
---
{template_content_md or "(no template on file — use a clean, ATS-friendly structure)"}
---

Respond with ONLY one fenced ```markdown block containing the final {doc_label}
text — no preamble, no commentary outside the fence."""

    user = (
        f"Candidate: {profile_basics.get('full_name', '—')} · {profile_basics.get('headline', '')}\n"
        f"Contact: {profile_basics.get('email', '—')} · {profile_basics.get('phone', '—')} · "
        f"{profile_basics.get('location', '—')}\n"
        f"LinkedIn: {profile_basics.get('linkedin_url', '—')} · Portfolio: {profile_basics.get('portfolio_url', '—')}\n\n"
        f"Candidate profile sections:\n{sections_md or '(none on file)'}\n\n"
        f"Target role: {position.get('role', '')} at {company_name or 'unknown'}\n"
        f"Job description:\n{position.get('description') or '(no description available)'}\n\n"
        + (f"Extra instructions: {instructions}" if instructions else "")
    )
    return system, user


def build_cv_import_prompt(cv_text: str) -> tuple[str, str]:
    """Structure a CV's raw text into profile basics + sections (§4.8).

    Unlike the other builders here, the output of this one is NOT written
    straight to the entity — `import_cv` turns it into `pending_changes` rows
    for the user to approve (DECISIONS #14: profile writes stay HITL-gated).
    The shape below is therefore an intermediate, not a final work product.
    """
    system = """\
You are extracting a structured professional profile from the raw text of a CV.
Work ONLY from the text provided — never invent employers, dates, degrees, or
contact details that don't appear in it. Leave a basics field null if the CV
doesn't state it.

Split the CV body into coherent sections (typically: summary, experience,
skills, education, certifications, projects, languages). Use lowercase
underscore slugs. Each section's `content_md` is Markdown, preserving the CV's
own wording and detail — condense formatting, not substance. Order sections as
they should appear on a CV (`sort_order` starting at 0).

Respond with ONLY one fenced ```json block (no text before or after it), shaped:
{
  "basics": {
    "full_name": "<or null>", "headline": "<short professional title, or null>",
    "email": "<or null>", "phone": "<or null>", "location": "<or null>",
    "linkedin_url": "<or null>", "portfolio_url": "<or null>"
  },
  "sections": [
    {"slug": "experience", "title": "Experience", "content_md": "...", "sort_order": 0}
  ]
}"""

    user = f"Raw CV text:\n\n{cv_text}"
    return system, user


def build_indeed_search_prompt(
    keywords: list[str],
    country_code: str,
    location: str,
    with_descriptions: bool = False,
    max_details: int = 0,
) -> tuple[str, str]:
    """Prompt for the MCP-backed Indeed source (`api/agent/mcp_sources.py`).

    The agent's whole job here is transcription, not judgment: call the tool
    once per keyword and copy the fields out. The `available` flag exists so a
    missing/unauthorized connector is reported as "source unavailable" (which
    `search_run` records as *skipped*) instead of being indistinguishable from
    "this search legitimately found nothing".
    """
    system = """\
You are a data-collection step in an automated job-search pipeline. Call the
Indeed MCP tool `search_jobs` once per keyword you are given, using the country
code and location supplied, and transcribe the results.

More than one Indeed server may be registered (e.g. an account connector and a
project-level one), so several `search_jobs` tools may be offered. They are
interchangeable. If the first one you try is unauthorized or errors, try the
other(s) before concluding the source is unavailable — one being unapproved
does not mean Indeed is unreachable.

Rules:
- Transcribe ONLY what the tool returns. Never invent, infer, or fill in a
  company, salary, date, or URL that is not in the tool output. Missing values
  are empty strings.
- Keep every result the tool returns. Do not filter, rank, or judge relevance —
  scoring happens later in the pipeline.
- Copy URLs verbatim, including query parameters.
- Normalize `date_posted` to ISO `YYYY-MM-DD`. If the tool gives no date, use
  an empty string.
- `job_type` is the tool's raw value (e.g. "Full-time", "Contract", "N/A").
- De-duplicate by company+role across keywords. Do NOT de-duplicate by URL:
  Indeed re-issues a different redirect URL for the same posting on every call,
  so identical postings will show different URLs.
__DETAILS_BLOCK__

If the Indeed tool is unavailable to you for ANY reason — not registered, not
authorized, permission denied, or every call errors — do not retry in a loop
and do not substitute another source or your own knowledge. Return the envelope
with "available": false and a one-line "reason".

Respond with ONLY one fenced ```json block, no commentary outside it:

```json
{
  "available": true,
  "reason": "",
  "positions": [
    {
      "company": "",
      "role": "",
      "url": "",
      "location": "",
      "salary": "",
      "job_type": "",
      "date_posted": "",
      "description": ""
    }
  ]
}
```"""

    if with_descriptions and max_details > 0:
        details = f"""
After collecting the listings, fetch the full description for each one with the
Indeed MCP tool `get_job_details`, using the `Job Id` from the search result.
Do this for at most {max_details} postings (if there are more, take the first
{max_details} and leave the rest with an empty description).

- `job_id` values are only valid within THIS session — use each one immediately,
  in this same turn. Never carry them anywhere else.
- Put the posting's description text into the `description` field, trimmed to
  about 3000 characters. Copy it as-is; do not summarize, rewrite or translate.
- If a details call fails, leave that posting's `description` empty and move on.
  Never drop the posting itself, and never fabricate a description."""
    else:
        details = """
Leave every `description` field as an empty string — do not call
`get_job_details`."""

    system = system.replace("__DETAILS_BLOCK__", details)

    user = (
        f"country_code: {country_code}\n"
        f"location: {location}\n"
        f"fetch_descriptions: {bool(with_descriptions and max_details > 0)}\n"
        f"max_details: {max_details}\n"
        f"keywords ({len(keywords)}):\n"
        + "\n".join(f"- {k}" for k in keywords)
    )
    return system, user


def build_research_prompt(
    company_name: str,
    website: str | None,
    raw_sections: dict[str, str],
) -> tuple[str, str]:
    system = """\
Synthesize a structured company research brief in Markdown from the raw
scraped text provided (homepage, about/careers/blog pages, recent news search
results). Cover: what the company does, size/stage signals, recent news,
culture/hiring signals, and anything notable for someone evaluating a job
application there. Note where the raw text was too thin to say something with
confidence rather than guessing.

Respond with ONLY one fenced ```markdown block containing the final brief —
no preamble, no commentary outside the fence."""

    user = (
        f"Company: {company_name}\nWebsite: {website or '—'}\n\n"
        f"Raw scraped text by source:\n{json.dumps(raw_sections, ensure_ascii=False, indent=2)}"
    )
    return system, user
