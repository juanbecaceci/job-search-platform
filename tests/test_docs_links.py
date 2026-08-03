"""Every relative link in the repo's markdown actually points at something.

The docs cross-reference each other heavily — four `CLAUDE.md` files, the spec,
the decision log, the progress log — and they're the on-ramp for both a human
reader and the agent itself. A dead link in `CLAUDE.md` sends a session looking
for a file that moved; a dead link in `README.md` is the first thing a visitor
clicks. Neither shows up in any other check, and moving one file breaks a
handful at once.

Only relative links are followed. External URLs aren't fetched — that would make
the suite depend on the network and on other people's uptime.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parent.parent

# [text](target) and ![alt](target), ignoring reference-style and autolinks.
_LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)>\s]+)")

# Fenced code blocks hold example paths that needn't exist (`config/…` samples,
# shell snippets), so they're stripped before links are collected.
_FENCE = re.compile(r"```.*?```", re.S)


def tracked_markdown() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "*.md"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return [ROOT / line for line in out.stdout.splitlines() if line.strip()]


def links_in(path: Path) -> list[str]:
    text = _FENCE.sub("", path.read_text("utf-8"))
    return _LINK.findall(text)


def is_external(target: str) -> bool:
    return target.startswith(("http://", "https://", "mailto:", "#"))


def is_placeholder(target: str) -> bool:
    """`config/defaults/*.md` are CV/cover-letter templates, not documents.

    Their `[LinkedIn]({{LINKEDIN_URL}})` links are filled in at render time, so
    there's nothing on disk to point at.
    """
    return "{{" in target or "{%" in target


MARKDOWN = tracked_markdown()


def test_there_is_markdown_to_check():
    """Guard the discovery step: an empty list would make every test below vacuous."""
    assert len(MARKDOWN) >= 8, f"only found {len(MARKDOWN)} markdown files"


@pytest.mark.parametrize("doc", MARKDOWN, ids=lambda p: str(p.relative_to(ROOT)))
def test_relative_links_resolve(doc: Path):
    broken = []
    for target in links_in(doc):
        if is_external(target) or is_placeholder(target):
            continue
        # Strip any anchor; we check the file exists, not the heading.
        rel = unquote(target.split("#")[0])
        if not rel:
            continue
        if not (doc.parent / rel).resolve().exists():
            broken.append(target)
    assert not broken, f"{doc.relative_to(ROOT)} has broken links: {broken}"
