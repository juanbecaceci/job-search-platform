"""`import_cv` job: turn an uploaded CV (PDF) into proposed profile changes
(§5 `POST /onboarding/import-cv`).

Pipeline: deterministic text extraction (pypdf) → agent structures it into
basics + sections → **`pending_changes` rows**, not direct writes.

That last step is the important one and it differs from this package's other
agent-calling handlers (`evaluate_batch`, `generate_document`,
`research_company`), which write straight to the entity. DECISIONS #14 draws
the line explicitly: those three produce *draft work products*, while the
profile is *state the user debates and approves*, so anything a job handler
wants to put into `profile_basics`/`profile_sections` goes through the same
HITL gate chat uses. The wizard then shows these rows for approval, and
`ChangeApplier` is what actually writes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.agent.one_shot import run_agent_text
from api.agent.output_parser import extract_fenced_block
from api.agent.task_prompts import build_cv_import_prompt
from api.models import PendingChange, ProfileBasics, ProfileSection

# A CV that extracts to less than this is almost certainly a scanned image —
# worth failing loudly rather than sending the agent an empty page.
_MIN_CV_CHARS = 200

_BASICS_FIELDS = (
    "full_name", "headline", "email", "phone", "location", "linkedin_url", "portfolio_url",
)


def _extract_pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(p for p in pages if p).strip()


def handle(session: Session, job, params: dict[str, Any], progress) -> dict[str, Any]:
    path = Path(params["path"])
    if not path.exists():
        raise ValueError(f"Uploaded CV not found at {path}")

    progress(0.1, f"reading {path.name}")
    cv_text = _extract_pdf_text(path)
    if len(cv_text) < _MIN_CV_CHARS:
        raise ValueError(
            "Could not extract usable text from the PDF "
            f"({len(cv_text)} chars). If it's a scanned image, export a text-based PDF."
        )

    progress(0.3, "structuring profile via agent")
    system, user_prompt = build_cv_import_prompt(cv_text)
    text = run_agent_text(system, user_prompt, timeout=900.0)
    block = extract_fenced_block(text, "json")
    if not block:
        raise ValueError("agent returned no structured profile block")
    try:
        parsed = json.loads(block)
    except json.JSONDecodeError as exc:
        raise ValueError(f"agent returned invalid JSON: {exc}") from exc

    progress(0.8, "preparing changes for approval")
    change_ids = _propose(session, parsed)
    if not change_ids:
        raise ValueError("agent extracted nothing from the CV worth proposing")
    session.commit()

    return {"pending_change_ids": change_ids, "source_file": path.name}


def _propose(session: Session, parsed: dict[str, Any]) -> list[int]:
    """Turn the agent's extraction into pending_changes rows.

    Basics become one `update` (the applier upserts the single row); each
    section becomes its own `create` so the user can approve/reject them
    individually rather than all-or-nothing.
    """
    change_ids: list[int] = []

    basics_in = parsed.get("basics")
    if isinstance(basics_in, dict):
        current = session.get(ProfileBasics, 1)
        diff = [
            {
                "field": field,
                "old": getattr(current, field, None) if current else None,
                "new": basics_in[field],
            }
            for field in _BASICS_FIELDS
            if basics_in.get(field)
        ]
        if diff:
            change_ids.append(_add(session, PendingChange(
                module="profile",
                change_type="update",
                target_table="profile_basics",
                target_id="1",
                summary=f"Set profile basics from CV ({len(diff)} fields)",
                diff=diff,
                status="pending",
            )))

    sections_in = parsed.get("sections")
    if isinstance(sections_in, list):
        # Don't propose a section whose slug already exists — a re-import
        # shouldn't silently duplicate the user's profile.
        existing = set(session.scalars(select(ProfileSection.slug)).all())
        for index, section in enumerate(sections_in):
            if not isinstance(section, dict):
                continue
            slug = (section.get("slug") or "").strip()
            content = section.get("content_md")
            if not slug or not content or slug in existing:
                continue
            existing.add(slug)
            title = section.get("title") or slug.replace("_", " ").title()
            sort_order = section.get("sort_order")
            change_ids.append(_add(session, PendingChange(
                module="profile",
                change_type="create",
                target_table="profile_sections",
                target_id=None,
                summary=f"Add profile section: {title}",
                diff=[
                    {"field": "slug", "old": None, "new": slug},
                    {"field": "title", "old": None, "new": title},
                    {"field": "content_md", "old": None, "new": content},
                    {
                        "field": "sort_order",
                        "old": None,
                        "new": sort_order if isinstance(sort_order, int) else index,
                    },
                ],
                status="pending",
            )))

    return change_ids


def _add(session: Session, row: PendingChange) -> int:
    session.add(row)
    session.flush()
    return row.id
