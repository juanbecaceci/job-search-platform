"""SQLite engine + session factory.

Connection PRAGMAs (DECISIONS #1, api/CLAUDE.md):
- ``journal_mode=WAL``   — readers don't block the single writer; needed because
  the JobRunner (``ThreadPoolExecutor(2)``) writes while HTTP requests read.
- ``foreign_keys=ON``    — SQLite disables FK enforcement per-connection by default.
- ``busy_timeout=5000``  — wait up to 5s for a lock instead of erroring immediately.

``check_same_thread=False`` because sessions are used across the runner's worker
threads; safety comes from short transactions + one session per unit of work,
not from thread affinity.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from api.config import DATABASE_URL

_is_sqlite = DATABASE_URL.startswith("sqlite")

engine: Engine = create_engine(
    DATABASE_URL,
    future=True,
    # Only meaningful for SQLite; harmless key otherwise but we guard anyway.
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    """Apply the required PRAGMAs on every new SQLite connection."""
    if not _is_sqlite:
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
    finally:
        cursor.close()


SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True
)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session context: commit on success, rollback on error.

    Use for background/job code and scripts. FastAPI routes use ``get_session``.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yields a session, always closed after the request.

    Routes commit explicitly (or via the service layer); this only guarantees
    cleanup so a route that raises doesn't leak a connection.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
