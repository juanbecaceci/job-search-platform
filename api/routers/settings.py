"""The settings key/value bag (§5 `/settings`).

Read is open; **writes are whitelisted**. `WRITABLE_KEYS` lists the settings the
UI may change and the type each must be. The bag is JSON-valued and also holds
runtime facts that are *not* user preferences (paths, adapter identity), so
letting the SPA PUT arbitrary keys would turn a preferences form into a way to
reconfigure the backend. Add a key here only when a real control needs it.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db.engine import get_session
from api.models import Setting

router = APIRouter(prefix="/settings", tags=["settings"])

# key -> accepted python type
WRITABLE_KEYS: dict[str, type] = {
    "sheets_export_enabled": bool,
}


class SettingsUpdate(BaseModel):
    values: dict[str, Any]


@router.get("", response_model=dict[str, Any])
def get_settings(session: Session = Depends(get_session)) -> dict[str, Any]:
    """Return all settings as a flat {key: value} bag."""
    stored = {s.key: s.value for s in session.scalars(select(Setting)).all()}
    # Surface writable keys even before they've ever been set, so the UI can
    # render a control without a special "unset" case.
    for key, kind in WRITABLE_KEYS.items():
        stored.setdefault(key, False if kind is bool else None)
    return stored


@router.put("", response_model=dict[str, Any])
def update_settings(
    body: SettingsUpdate,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Update whitelisted settings. Unknown or mistyped keys are rejected."""
    for key, value in body.values.items():
        expected = WRITABLE_KEYS.get(key)
        if expected is None:
            raise HTTPException(
                status_code=422,
                detail=f"Setting is not writable: {key!r} (writable: {sorted(WRITABLE_KEYS)})",
            )
        # bool is a subclass of int — check it first so True doesn't pass as int.
        if not isinstance(value, expected) or (expected is not bool and isinstance(value, bool)):
            raise HTTPException(
                status_code=422,
                detail=f"Setting {key!r} must be {expected.__name__}, got {type(value).__name__}",
            )
        row = session.get(Setting, key)
        if row is None:
            session.add(Setting(key=key, value=value))
        else:
            row.value = value
    session.commit()
    return get_settings(session)
