"""Translate score/salary category values to English

The UI is English by rule (root CLAUDE.md), but four score bands, the
unpublished-salary gate and two outcome markers were Spanish and user-facing —
they rendered verbatim on the dashboard, the positions table and the position
detail. This rewrites the stored values so existing rows keep matching the
enums and the UI's color lookup.

Data only; no schema change. Four places hold these strings:

  positions.score_category      a band, or one of the two outcome markers
  positions.salary_gate         PASS | FAIL | the unpublished marker
  scoring_configs.categories    JSON array of {id, min_score, max_score, ...}
  scoring_configs.salary_gate   JSON object with `unpublished_status`

`scoring_configs` rows are versioned and immutable in normal operation, but
they are read back to score positions, so old versions get rewritten too —
otherwise re-running an old config reintroduces Spanish ids.

Reversible: `downgrade()` maps every value back.

Revision ID: a3f1c9d47b20
Revises: e722e2638ce1
Create Date: 2026-08-02 21:40:00.000000

"""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3f1c9d47b20"
down_revision: Union[str, Sequence[str], None] = "e722e2638ce1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Score bands plus the two markers the evaluator writes when the salary gate
# decides the outcome instead of the score.
CATEGORY_ES_TO_EN = {
    "EXCELENTE": "EXCELLENT",
    "BUENA": "GOOD",
    "ACEPTABLE": "ACCEPTABLE",
    "DESCARTAR": "DISCARD",
    "A VALIDAR": "NEEDS VALIDATION",
    "DESCARTADA POR SALARIO": "BELOW SALARY FLOOR",
}
# `positions.salary_gate` only ever carries PASS / FAIL / the unpublished marker.
SALARY_GATE_ES_TO_EN = {"A VALIDAR": "NEEDS VALIDATION"}

CRITERION_NAME_ES_TO_EN = {
    "Alineacion con el perfil": "Profile alignment",
    "Modalidad remota": "Remote modality",
    "Seniority y crecimiento": "Seniority and growth",
    "Empresa y estabilidad": "Company and stability",
}


def _rewrite(
    mapping: dict[str, str],
    salary_mapping: dict[str, str],
    criterion_names: dict[str, str],
) -> None:
    bind = op.get_bind()

    for old, new in mapping.items():
        bind.execute(
            sa.text("UPDATE positions SET score_category = :new WHERE score_category = :old"),
            {"old": old, "new": new},
        )

    for old, new in salary_mapping.items():
        bind.execute(
            sa.text("UPDATE positions SET salary_gate = :new WHERE salary_gate = :old"),
            {"old": old, "new": new},
        )

    # JSON columns: read, remap, write back. Small tables (one row per config
    # version), so a Python round-trip beats a SQLite JSON expression.
    rows = bind.execute(
        sa.text("SELECT id, categories, salary_gate FROM scoring_configs")
    ).fetchall()
    for row in rows:
        categories = json.loads(row.categories) if isinstance(row.categories, str) else row.categories
        gate = json.loads(row.salary_gate) if isinstance(row.salary_gate, str) else row.salary_gate

        for category in categories or []:
            if category.get("id") in mapping:
                category["id"] = mapping[category["id"]]
        if gate and gate.get("unpublished_status") in mapping:
            gate["unpublished_status"] = mapping[gate["unpublished_status"]]

        bind.execute(
            sa.text(
                "UPDATE scoring_configs SET categories = :categories, salary_gate = :gate "
                "WHERE id = :id"
            ),
            {
                "categories": json.dumps(categories, ensure_ascii=False),
                "gate": json.dumps(gate, ensure_ascii=False),
                "id": row.id,
            },
        )

    # Criterion display names live in the same table, in a third JSON column.
    rows = bind.execute(sa.text("SELECT id, criteria FROM scoring_configs")).fetchall()
    for row in rows:
        criteria = json.loads(row.criteria) if isinstance(row.criteria, str) else row.criteria
        for criterion in criteria or []:
            if criterion.get("name") in criterion_names:
                criterion["name"] = criterion_names[criterion["name"]]
        bind.execute(
            sa.text("UPDATE scoring_configs SET criteria = :criteria WHERE id = :id"),
            {"criteria": json.dumps(criteria, ensure_ascii=False), "id": row.id},
        )


def upgrade() -> None:
    _rewrite(CATEGORY_ES_TO_EN, SALARY_GATE_ES_TO_EN, CRITERION_NAME_ES_TO_EN)


def downgrade() -> None:
    _rewrite(
        {new: old for old, new in CATEGORY_ES_TO_EN.items()},
        {new: old for old, new in SALARY_GATE_ES_TO_EN.items()},
        {new: old for old, new in CRITERION_NAME_ES_TO_EN.items()},
    )
