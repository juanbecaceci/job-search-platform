"""`generate_document` job: agent drafts a CV or cover-letter Markdown source
for one position (§5 `POST /positions/{id}/documents/generate`).

Only the drafting happens here — rendering to PDF/DOCX is the separate
`export_document` job, matching `core/generate_cv.py`'s own two-step design
(write the .md, `--export` it later) and letting the user edit the draft
in between via `PUT /documents/{id}`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from api.agent.one_shot import run_agent_text
from api.agent.output_parser import extract_fenced_block
from api.agent.task_prompts import build_document_prompt
from api.models import (
    Document,
    Position,
    PositionEvent,
    ProfileBasics,
    ProfileSection,
    Template,
    TemplateVersion,
)
from api.models.enums import Actor, PositionEventType


def handle(session: Session, job, params: dict[str, Any], progress) -> dict[str, Any]:
    position_id = params["position_id"]
    kind = params["kind"]
    instructions = params.get("instructions")

    position = session.get(Position, position_id, options=[selectinload(Position.company)])
    if position is None:
        raise ValueError(f"Position {position_id} not found")

    progress(0.1, "loading profile + template")
    template = session.scalar(select(Template).where(Template.kind == kind))
    active_version = None
    if template is not None:
        active_version = session.scalar(
            select(TemplateVersion).where(
                TemplateVersion.template_id == template.id,
                TemplateVersion.is_active.is_(True),
            )
        )
    basics = session.get(ProfileBasics, 1)
    sections = session.scalars(
        select(ProfileSection).order_by(ProfileSection.sort_order)
    ).all()

    system, user_prompt = build_document_prompt(
        kind=kind,
        position={
            "role": position.role,
            "description": position.description,
        },
        company_name=position.company.name if position.company else None,
        template_content_md=active_version.content_md if active_version else None,
        profile_basics={
            "full_name": basics.full_name if basics else None,
            "headline": basics.headline if basics else None,
            "email": basics.email if basics else None,
            "phone": basics.phone if basics else None,
            "location": basics.location if basics else None,
            "linkedin_url": basics.linkedin_url if basics else None,
            "portfolio_url": basics.portfolio_url if basics else None,
        },
        profile_sections=[
            {"slug": s.slug, "title": s.title, "content_md": s.content_md} for s in sections
        ],
        instructions=instructions,
    )

    progress(0.3, "drafting via agent")
    text = run_agent_text(system, user_prompt)
    content_md = extract_fenced_block(text, "markdown")
    if not content_md:
        raise ValueError("agent returned no draftable content")

    progress(0.9, "saving document")
    existing_versions = session.scalars(
        select(Document.version).where(
            Document.position_id == position_id, Document.kind == kind
        )
    ).all()
    next_version = (max(existing_versions) if existing_versions else 0) + 1

    document = Document(
        position_id=position_id,
        kind=kind,
        version=next_version,
        content_md=content_md,
        status="draft",
        created_by="agent",
    )
    session.add(document)
    session.flush()
    session.add(
        PositionEvent(
            position_id=position_id,
            event_type=PositionEventType.DOCUMENT_GENERATED.value,
            payload={"kind": kind, "document_id": document.id, "version": next_version},
            actor=Actor.AGENT.value,
        )
    )
    session.commit()

    return {"document_id": document.id, "kind": kind, "version": next_version}
