"""`research_company` job: scrape a company's public presence, then have the
agent synthesize a structured research brief (§5 `POST /companies/{id}/research`).

Scraping (`core/research_company.py:scrape_company_data`) is reused as-is —
pure network I/O, no side effects. The brief itself is agent-authored; it's
written to `Company.research_md` AND mirrored into a `company_research`
`Document` (per the model's docstring), never to `output/companies/...`
(hard rule #1 — bypasses `research_company.py`'s own `save_research()`, which
hardcodes that path).
"""

from __future__ import annotations

import sys
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.agent.one_shot import run_agent_text
from api.agent.output_parser import extract_fenced_block
from api.agent.task_prompts import build_research_prompt
from api.config import ROOT_DIR
from api.models import Company, Document

_CORE_DIR = str(ROOT_DIR / "core")
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

from core.research_company import scrape_company_data  # noqa: E402


def handle(session: Session, job, params: dict[str, Any], progress) -> dict[str, Any]:
    company_id = params["company_id"]
    company = session.get(Company, company_id)
    if company is None:
        raise ValueError(f"Company {company_id} not found")
    if not company.website:
        raise ValueError("Company has no website on file to research")

    progress(0.1, f"scraping {company.website}")
    raw_sections = scrape_company_data(company.name, company.website)
    if not raw_sections:
        raise ValueError("Could not scrape any content from the company's site")

    progress(0.5, "synthesizing research via agent")
    system, user_prompt = build_research_prompt(company.name, company.website, raw_sections)
    text = run_agent_text(system, user_prompt, timeout=900.0)
    brief = extract_fenced_block(text, "markdown")
    if not brief:
        raise ValueError("agent returned no research brief")

    progress(0.9, "saving research")
    company.research_md = brief

    existing_versions = session.scalars(
        select(Document.version).where(
            Document.company_id == company_id, Document.kind == "company_research"
        )
    ).all()
    next_version = (max(existing_versions) if existing_versions else 0) + 1

    document = Document(
        position_id=None,
        company_id=company_id,
        kind="company_research",
        version=next_version,
        content_md=brief,
        status="draft",
        created_by="agent",
    )
    session.add(document)
    session.flush()
    session.commit()

    return {"company_id": company_id, "document_id": document.id}
