"""Extracts a single fenced code block from an agent's one-shot reply.

Used by job handlers that call the agent for a direct work-product write
(evaluation scores, a drafted document, a research brief) rather than a chat
turn — these never go through the `proposed_changes` HITL protocol
(`change_parser.py`), so they get their own tiny, separate extractor.
"""

from __future__ import annotations

import re


def extract_fenced_block(text: str, tag: str) -> str | None:
    """Return the content of the first ```<tag> fenced block in `text`.

    Falls back to the first fenced block of any tag, then to the full text
    stripped (the agent may forget the fence) — never fails outright, since a
    malformed fence shouldn't crash the job; callers validate the content
    itself (e.g. `json.loads`).
    """
    tagged = re.search(rf"```{re.escape(tag)}\s*\n(.*?)```", text or "", re.DOTALL | re.IGNORECASE)
    if tagged:
        body = tagged.group(1).strip()
        if body:
            return body

    any_fence = re.search(r"```(?:\w+)?\s*\n(.*?)```", text or "", re.DOTALL)
    if any_fence:
        body = any_fence.group(1).strip()
        if body:
            return body

    stripped = (text or "").strip()
    return stripped or None
