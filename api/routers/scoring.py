"""Read endpoints for scoring config (GET only in Stage 2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db.engine import get_session
from api.models import ScoringConfig
from api.schemas.content import ScoringConfigOut

router = APIRouter(prefix="/scoring", tags=["scoring"])


@router.get("/config", response_model=ScoringConfigOut)
def get_active_config(session: Session = Depends(get_session)) -> ScoringConfigOut:
    config = session.scalar(
        select(ScoringConfig).where(ScoringConfig.is_active.is_(True))
    )
    if config is None:
        raise HTTPException(status_code=404, detail="No active scoring config")
    return ScoringConfigOut.model_validate(config)


@router.get("/config/versions", response_model=list[ScoringConfigOut])
def list_config_versions(session: Session = Depends(get_session)) -> list[ScoringConfigOut]:
    stmt = select(ScoringConfig).order_by(ScoringConfig.version.desc())
    return [ScoringConfigOut.model_validate(c) for c in session.scalars(stmt).all()]
