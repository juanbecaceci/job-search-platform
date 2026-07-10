"""Read endpoints for templates (GET only in Stage 2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from api.db.engine import get_session
from api.models import Template, TemplateVersion
from api.schemas.content import TemplateOut, TemplateVersionOut

router = APIRouter(prefix="/templates", tags=["templates"])


def _active_version(template: Template) -> TemplateVersion | None:
    return next((v for v in template.versions if v.is_active), None)


def _to_out(template: Template) -> TemplateOut:
    active = _active_version(template)
    return TemplateOut(
        id=template.id,
        kind=template.kind,
        name=template.name,
        active_version=TemplateVersionOut.model_validate(active) if active else None,
    )


@router.get("", response_model=list[TemplateOut])
def list_templates(session: Session = Depends(get_session)) -> list[TemplateOut]:
    stmt = select(Template).options(selectinload(Template.versions)).order_by(Template.id)
    return [_to_out(t) for t in session.scalars(stmt).all()]


@router.get("/{template_id}/versions", response_model=list[TemplateVersionOut])
def list_versions(
    template_id: int, session: Session = Depends(get_session)
) -> list[TemplateVersionOut]:
    template = session.get(
        Template, template_id, options=[selectinload(Template.versions)]
    )
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    versions = sorted(template.versions, key=lambda v: v.version, reverse=True)
    return [TemplateVersionOut.model_validate(v) for v in versions]
