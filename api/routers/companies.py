"""Read endpoints for companies (GET only in Stage 2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.db.engine import get_session
from api.deps import get_runner
from api.jobs import JobRunner
from api.models import Company
from api.models.enums import AsyncJobType
from api.schemas.common import Page
from api.schemas.misc import CompanyOut
from api.schemas.requests import JobAccepted

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=Page[CompanyOut])
def list_companies(
    session: Session = Depends(get_session),
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Page[CompanyOut]:
    stmt = select(Company)
    if q:
        stmt = stmt.where(Company.name.ilike(f"%{q}%"))
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(Company.name).offset((page - 1) * page_size).limit(page_size)
    items = [CompanyOut.model_validate(c) for c in session.scalars(stmt).all()]
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(company_id: int, session: Session = Depends(get_session)) -> CompanyOut:
    company = session.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return CompanyOut.model_validate(company)


@router.post(
    "/{company_id}/research", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED
)
def research_company(
    company_id: int,
    session: Session = Depends(get_session),
    runner: JobRunner = Depends(get_runner),
) -> JobAccepted:
    company = session.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    if not company.website:
        raise HTTPException(status_code=422, detail="Company has no website on file to research")
    job_id = runner.submit(AsyncJobType.RESEARCH_COMPANY.value, {"company_id": company_id})
    return JobAccepted(job_id=job_id)
