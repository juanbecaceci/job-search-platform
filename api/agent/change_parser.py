"""Extracts `proposed_changes` blocks from agent text → validated objects.

The agent ends a turn with a fenced ```json block containing a top-level
`proposed_changes` array (see prompt_builder). This scans the assistant's text
for such blocks, validates each item, and returns them. Parsing is a pure
function so it's unit-testable; the chat layer turns the results into
`pending_changes` rows (DECISIONS #6 — nothing is applied here).
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

# Fenced code blocks: ```json ... ``` or ``` ... ``` (json tag optional).
_FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)

_VALID_CHANGE_TYPES = {"update", "create", "delete", "action"}


class ProposedChange(BaseModel):
    module: str
    change_type: str
    target_table: str | None = None
    target_id: str | None = None
    summary: str | None = None
    diff: Any = Field(default_factory=list)

    def normalized_type(self) -> str:
        return self.change_type if self.change_type in _VALID_CHANGE_TYPES else "update"


def _iter_json_blocks(text: str):
    for match in _FENCE_RE.finditer(text or ""):
        body = match.group(1).strip()
        if not body:
            continue
        try:
            yield json.loads(body)
        except json.JSONDecodeError:
            continue


def parse_proposed_changes(text: str) -> list[ProposedChange]:
    """Return every valid proposed change found in the agent's text.

    Accepts blocks shaped as `{"proposed_changes": [...]}`. Invalid items are
    skipped rather than failing the whole turn — a malformed change shouldn't
    lose the assistant's message.
    """
    changes: list[ProposedChange] = []
    for obj in _iter_json_blocks(text):
        if not isinstance(obj, dict):
            continue
        items = obj.get("proposed_changes")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                changes.append(ProposedChange.model_validate(item))
            except ValidationError:
                continue
    return changes
