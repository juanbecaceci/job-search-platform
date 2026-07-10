"""Read endpoints for per-module memories (GET only in Stage 2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db.engine import get_session
from api.models import ModuleMemory
from api.schemas.misc import ModuleMemoryOut

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("", response_model=list[ModuleMemoryOut])
def list_memories(session: Session = Depends(get_session)) -> list[ModuleMemoryOut]:
    stmt = select(ModuleMemory).order_by(ModuleMemory.module)
    return [ModuleMemoryOut.model_validate(m) for m in session.scalars(stmt).all()]


@router.get("/{module}", response_model=ModuleMemoryOut)
def get_memory(module: str, session: Session = Depends(get_session)) -> ModuleMemoryOut:
    memory = session.get(ModuleMemory, module)
    if memory is None:
        raise HTTPException(status_code=404, detail="Module memory not found")
    return ModuleMemoryOut.model_validate(memory)
