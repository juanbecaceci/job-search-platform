"""Profile basics and sections — read + direct user edits (§4.8, §5).

The write endpoints here are the user editing their own profile through the UI.
They deliberately do NOT go through `pending_changes`/`ChangeApplier`: that gate
exists for the *agent's* writes (DECISIONS #6), and making someone approve their
own form submission would be ceremony, not safety. Agent-proposed profile
changes still land in the tray exactly as before.

Sections are ordered by `sort_order`; `POST /sections/reorder` rewrites the
whole order in one call so drag-and-drop can't leave a half-applied sequence.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db.engine import get_session
from api.models import ProfileBasics, ProfileSection
from api.schemas.profile import ProfileBasicsOut, ProfileSectionOut
from api.schemas.requests_profile import (
    ProfileBasicsUpdate,
    ProfileSectionCreate,
    ProfileSectionReorder,
    ProfileSectionUpdate,
)

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/basics", response_model=ProfileBasicsOut)
def get_basics(session: Session = Depends(get_session)) -> ProfileBasicsOut:
    row = session.get(ProfileBasics, 1)
    # Empty (unonboarded) profile returns an all-null record rather than 404.
    return ProfileBasicsOut.model_validate(row) if row else ProfileBasicsOut()


@router.put("/basics", response_model=ProfileBasicsOut)
def update_basics(
    body: ProfileBasicsUpdate,
    session: Session = Depends(get_session),
) -> ProfileBasicsOut:
    """Upsert the single basics row. Only the fields sent are touched."""
    row = session.get(ProfileBasics, 1)
    if row is None:
        row = ProfileBasics(id=1)
        session.add(row)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    session.commit()
    session.refresh(row)
    return ProfileBasicsOut.model_validate(row)


@router.get("/sections", response_model=list[ProfileSectionOut])
def list_sections(session: Session = Depends(get_session)) -> list[ProfileSectionOut]:
    stmt = select(ProfileSection).order_by(
        ProfileSection.sort_order, ProfileSection.id
    )
    return [ProfileSectionOut.model_validate(s) for s in session.scalars(stmt).all()]


@router.post("/sections", response_model=ProfileSectionOut, status_code=status.HTTP_201_CREATED)
def create_section(
    body: ProfileSectionCreate,
    session: Session = Depends(get_session),
) -> ProfileSectionOut:
    if session.scalar(select(ProfileSection).where(ProfileSection.slug == body.slug)):
        raise HTTPException(status_code=409, detail=f"Section already exists: {body.slug}")

    sort_order = body.sort_order
    if sort_order is None:
        # Append: one past the current maximum.
        highest = session.scalar(select(ProfileSection.sort_order).order_by(ProfileSection.sort_order.desc()))
        sort_order = (highest + 1) if highest is not None else 0

    section = ProfileSection(
        slug=body.slug,
        title=body.title,
        content_md=body.content_md,
        sort_order=sort_order,
        updated_by="user",
    )
    session.add(section)
    session.commit()
    session.refresh(section)
    return ProfileSectionOut.model_validate(section)


@router.put("/sections/{section_id}", response_model=ProfileSectionOut)
def update_section(
    section_id: int,
    body: ProfileSectionUpdate,
    session: Session = Depends(get_session),
) -> ProfileSectionOut:
    section = session.get(ProfileSection, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="Section not found")

    updates = body.model_dump(exclude_unset=True)
    new_slug = updates.get("slug")
    if new_slug and new_slug != section.slug:
        clash = session.scalar(
            select(ProfileSection).where(
                ProfileSection.slug == new_slug, ProfileSection.id != section_id
            )
        )
        if clash:
            raise HTTPException(status_code=409, detail=f"Section already exists: {new_slug}")

    for field, value in updates.items():
        setattr(section, field, value)
    section.updated_by = "user"
    session.commit()
    session.refresh(section)
    return ProfileSectionOut.model_validate(section)


@router.delete("/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_section(section_id: int, session: Session = Depends(get_session)) -> Response:
    section = session.get(ProfileSection, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="Section not found")
    session.delete(section)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sections/reorder", response_model=list[ProfileSectionOut])
def reorder_sections(
    body: ProfileSectionReorder,
    session: Session = Depends(get_session),
) -> list[ProfileSectionOut]:
    """Rewrite `sort_order` from the given id sequence (0-based, in order)."""
    sections = {s.id: s for s in session.scalars(select(ProfileSection)).all()}
    unknown = [i for i in body.section_ids if i not in sections]
    if unknown:
        raise HTTPException(status_code=404, detail=f"Unknown section ids: {unknown}")
    if len(body.section_ids) != len(sections):
        raise HTTPException(
            status_code=422,
            detail=f"Expected all {len(sections)} section ids, got {len(body.section_ids)}",
        )

    for position, section_id in enumerate(body.section_ids):
        sections[section_id].sort_order = position
    session.commit()

    stmt = select(ProfileSection).order_by(ProfileSection.sort_order, ProfileSection.id)
    return [ProfileSectionOut.model_validate(s) for s in session.scalars(stmt).all()]
