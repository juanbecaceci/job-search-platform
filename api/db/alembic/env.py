"""Alembic environment.

Wired to the app's own metadata and engine so migrations always match the ORM
and honor the SQLite PRAGMAs. The DB URL comes from ``api.config`` (env-driven),
not from ``alembic.ini`` — keep ``sqlalchemy.url`` blank in the ini.

``render_as_batch=True`` makes Alembic emit SQLite-safe ALTERs via the
copy-and-move table pattern (SQLite can't ALTER most things in place).
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context

# Ensure the repo root is importable (alembic may run with a bare sys.path).
ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.db.engine import engine  # noqa: E402
from api.models import Base  # noqa: E402  (registers every table on the metadata)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection."""
    context.configure(
        url=str(engine.url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the app's configured engine."""
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
