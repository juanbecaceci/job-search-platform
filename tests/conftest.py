"""Shared fixtures: a throwaway in-memory database and the rows tests build on.

Two things are set up before any `api.*` import: `DATABASE_URL`, so importing
`api.config` can never resolve to the developer's real `data/app.db`, and
`AGENT_CLI_PATH`, so nothing can accidentally shell out to a real agent CLI.
Nothing in this suite touches the network, the filesystem outside tmp, or the
agent.
"""

from __future__ import annotations

import os

# Must precede the `api.*` imports below — `api.config` reads these at import.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("AGENT_CLI_PATH", "/nonexistent/agent-cli")

import pytest  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from api.db.base import Base  # noqa: E402
from api.models import (  # noqa: E402
    Company,
    PendingChange,
    Position,
    ScoringConfig,
    Template,
    TemplateVersion,
)
from api.models.enums import PendingChangeStatus, PositionStatus, Source  # noqa: E402

# Importing the models package is what populates Base.metadata; this makes that
# dependency explicit so an import sorter can't quietly drop it.
assert Position is not None


@pytest.fixture
def session() -> Session:
    """A fresh in-memory database per test, with foreign keys enforced.

    `StaticPool` + a shared connection keeps every session in the same
    `sqlite://` instance; without it each connection gets its own empty DB.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, _record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    Base.metadata.drop_all(engine)
    engine.dispose()


# ── Row builders ─────────────────────────────────────────────────────────────


@pytest.fixture
def scoring_config(session: Session) -> ScoringConfig:
    """An active v1 config shaped like the seeded default (weights sum to 1.0)."""
    config = ScoringConfig(
        version=1,
        is_active=True,
        salary_gate={
            "floor_usd_month": 3500,
            "evaluation_basis": "lower_bound",
            "unpublished_status": "NEEDS VALIDATION",
        },
        score_threshold_auto_discard=45,
        scale_max=5,
        categories=[
            {"id": "EXCELLENT", "min_score": 80, "max_score": 100, "recommended_action": "Apply immediately."},
            {"id": "GOOD", "min_score": 60, "max_score": 79, "recommended_action": "Apply."},
            {"id": "ACCEPTABLE", "min_score": 45, "max_score": 59, "recommended_action": "Apply if nothing better."},
            {"id": "DISCARD", "min_score": 0, "max_score": 44, "recommended_action": "Do not invest time."},
        ],
        criteria=[
            {"id": "profile_alignment", "name": "Profile alignment", "weight": 0.40},
            {"id": "remote_modality", "name": "Remote modality", "weight": 0.25},
            {"id": "seniority_growth", "name": "Seniority and growth", "weight": 0.20},
            {"id": "company_stability", "name": "Company and stability", "weight": 0.15},
        ],
        created_by="system",
    )
    session.add(config)
    session.flush()
    return config


@pytest.fixture
def position(session: Session) -> Position:
    company = Company(name="Meridian Labs", industry="AI Infrastructure")
    session.add(company)
    session.flush()
    pos = Position(
        id="meridian-labs-platform-engineer-aaa111",
        company_id=company.id,
        source=Source.LINKEDIN.value,
        sources=[Source.LINKEDIN.value],
        role="Platform Engineer",
        status=PositionStatus.DISCOVERED.value,
        tags=[],
    )
    session.add(pos)
    session.flush()
    return pos


@pytest.fixture
def template(session: Session) -> Template:
    tpl = Template(kind="cv", name="CV default")
    tpl.versions.append(
        TemplateVersion(version=1, is_active=True, content_md="# v1", created_by="system")
    )
    session.add(tpl)
    session.flush()
    return tpl


@pytest.fixture
def make_change():
    """Build a PendingChange without persisting it.

    `apply()` only reads the row, so tests that don't care about the tray don't
    need it in the session.
    """

    def _make(
        target_table: str | None,
        diff,
        change_type: str = "update",
        target_id: str | None = None,
        module: str = "positions",
        edited_at=None,
    ) -> PendingChange:
        return PendingChange(
            module=module,
            change_type=change_type,
            target_table=target_table,
            target_id=target_id,
            summary="test change",
            diff=diff,
            status=PendingChangeStatus.PENDING.value,
            edited_at=edited_at,
        )

    return _make
