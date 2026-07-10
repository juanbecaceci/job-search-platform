#!/usr/bin/env python3
"""Seed the DB with default config: scoring, templates, empty module memories.

Loads from ``config/defaults/``:
  - ``scoring_criteria.default.json`` -> ``scoring_configs`` (version 1, active)
  - ``cv_template.md``               -> ``templates`` (kind=cv) + version 1, active
  - ``cover_letter_template.md``     -> ``templates`` (kind=cover_letter) + v1, active
And creates one empty ``module_memories`` row per module.

Idempotent: re-running skips anything already present, so it's safe to run after
a fresh ``alembic upgrade head`` or to backfill a newly added module memory.

Run (from repo root, after migrations):
    python scripts/seed_defaults.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Repo root on the path so `import api...` resolves when run as a script.
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from api.db.engine import session_scope  # noqa: E402
from api.models import (  # noqa: E402
    ModuleMemory,
    ScoringConfig,
    Template,
    TemplateVersion,
)
from api.models.enums import Module  # noqa: E402

DEFAULTS_DIR = ROOT_DIR / "config" / "defaults"

# (kind, human name, source file) for the two seeded template families.
_TEMPLATE_SEEDS = (
    ("cv", "CV default", "cv_template.md"),
    ("cover_letter", "Cover letter default", "cover_letter_template.md"),
)


def seed_scoring(session: Session) -> str:
    """Insert scoring config v1 (active) if no scoring config exists yet."""
    if session.scalar(select(ScoringConfig.id).limit(1)) is not None:
        return "scoring: already present, skipped"

    data = json.loads((DEFAULTS_DIR / "scoring_criteria.default.json").read_text("utf-8"))
    session.add(
        ScoringConfig(
            version=1,
            is_active=True,
            salary_gate=data["salary_gate"],
            score_threshold_auto_discard=data["score_threshold_auto_discard"],
            scale_max=data["scale_max"],
            categories=data["categories"],
            criteria=data["criteria"],
            created_by="system",
        )
    )
    return "scoring: seeded v1 (active)"


def seed_templates(session: Session) -> list[str]:
    """Create each template family + its version-1 active content, if missing."""
    results: list[str] = []
    for kind, name, filename in _TEMPLATE_SEEDS:
        if session.scalar(select(Template.id).where(Template.kind == kind).limit(1)):
            results.append(f"template[{kind}]: already present, skipped")
            continue

        content = (DEFAULTS_DIR / filename).read_text("utf-8")
        template = Template(kind=kind, name=name)
        template.versions.append(
            TemplateVersion(
                version=1,
                is_active=True,
                content_md=content,
                change_note="Seeded default template",
                created_by="system",
            )
        )
        session.add(template)
        results.append(f"template[{kind}]: seeded v1 (active)")
    return results


def seed_module_memories(session: Session) -> str:
    """Ensure one empty memory row exists per module (backfills new modules)."""
    existing = set(session.scalars(select(ModuleMemory.module)).all())
    added = 0
    for module in Module:
        if module.value in existing:
            continue
        session.add(
            ModuleMemory(module=module.value, content_md="", updated_by="system")
        )
        added += 1
    return f"module_memories: {added} added, {len(existing)} already present"


def main() -> None:
    with session_scope() as session:
        outcomes = [seed_scoring(session)]
        outcomes.extend(seed_templates(session))
        outcomes.append(seed_module_memories(session))

    print("Seed complete:")
    for line in outcomes:
        print(f"  - {line}")


if __name__ == "__main__":
    main()
