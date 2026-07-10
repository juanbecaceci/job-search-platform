"""In-process async job runner (DECISIONS #4: ThreadPoolExecutor(2), no broker).

A job is a row in the `jobs` table plus a handler run on a worker thread. The
runner owns the state machine (queued → running → succeeded/failed/cancelled),
persists progress, and publishes SSE events through the `EventBus`. Handlers
stay ignorant of all that: they get a session, the job row, params, and a
`progress(fraction, message, stats=None)` callback, and return a result dict.

Handler contract:
    def handler(session: Session, job: Job, params: dict, progress: Progress) -> dict
- Use `session` for all DB work; it's committed on success.
- Call `progress(...)` to report advancement — it persists progress, emits an
  SSE `progress` event, AND raises `JobCancelled` if a cancel was requested
  (cooperative cancellation, best-effort per the spec).
- Raise to fail the job; the exception message becomes `job.error`.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any, Protocol

from api.db.engine import SessionLocal
from api.jobs.event_bus import EventBus
from api.models import Job
from api.models.enums import JobStatus


class JobCancelled(Exception):
    """Raised inside a handler (via the progress callback) to abort a job."""


class Progress(Protocol):
    def __call__(
        self, fraction: float, message: str, stats: dict[str, Any] | None = None
    ) -> None: ...


Handler = Callable[..., dict[str, Any]]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class JobRunner:
    def __init__(self, event_bus: EventBus, max_workers: int = 2) -> None:
        self.bus = event_bus
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="jobrunner"
        )
        self._handlers: dict[str, Handler] = {}
        self._cancel_requested: set[str] = set()
        self._lock = threading.Lock()

    # ── registration ────────────────────────────────────────
    def register(self, job_type: str, handler: Handler) -> None:
        self._handlers[job_type] = handler

    # ── submission ──────────────────────────────────────────
    def submit(self, job_type: str, params: dict[str, Any] | None = None) -> str:
        if job_type not in self._handlers:
            raise ValueError(f"No handler registered for job type {job_type!r}")
        job_id = uuid.uuid4().hex
        with SessionLocal() as session:
            session.add(
                Job(id=job_id, type=job_type, status=JobStatus.QUEUED.value, progress=0.0)
            )
            session.commit()
        self._executor.submit(self._run, job_id, job_type, params or {})
        return job_id

    # ── cancellation (cooperative, best-effort) ─────────────
    def request_cancel(self, job_id: str) -> None:
        with self._lock:
            self._cancel_requested.add(job_id)

    def _is_cancelled(self, job_id: str) -> bool:
        with self._lock:
            return job_id in self._cancel_requested

    def _clear_cancel(self, job_id: str) -> None:
        with self._lock:
            self._cancel_requested.discard(job_id)

    # ── execution ───────────────────────────────────────────
    def _run(self, job_id: str, job_type: str, params: dict[str, Any]) -> None:
        handler = self._handlers[job_type]
        session = SessionLocal()
        try:
            job = session.get(Job, job_id)
            job.status = JobStatus.RUNNING.value
            job.started_at = _utcnow()
            session.commit()

            def progress(
                fraction: float, message: str, stats: dict[str, Any] | None = None
            ) -> None:
                if self._is_cancelled(job_id):
                    raise JobCancelled()
                job.progress = max(0.0, min(1.0, fraction))
                job.progress_message = message
                session.commit()
                data: dict[str, Any] = {"progress": job.progress, "message": message}
                if stats is not None:
                    data["stats"] = stats
                self.bus.publish(job_id, "progress", data)

            result = handler(session, job, params, progress)

            job.status = JobStatus.SUCCEEDED.value
            job.progress = 1.0
            job.result = result
            job.finished_at = _utcnow()
            session.commit()
            self.bus.publish(job_id, "done", {"result": result})

        except JobCancelled:
            session.rollback()
            self._finalize(session, job_id, JobStatus.CANCELLED.value, error="cancelled")
            self.bus.publish(job_id, "failed", {"error": "cancelled"})
        except Exception as exc:  # noqa: BLE001 — any handler error fails the job
            session.rollback()
            self._finalize(session, job_id, JobStatus.FAILED.value, error=str(exc))
            self.bus.publish(job_id, "failed", {"error": str(exc)})
        finally:
            session.close()
            self._clear_cancel(job_id)

    def _finalize(self, session, job_id: str, status: str, error: str | None) -> None:
        """Persist a terminal state after a rollback (own tiny transaction)."""
        job = session.get(Job, job_id)
        if job is None:
            return
        job.status = status
        job.error = error
        job.finished_at = _utcnow()
        session.commit()

    # ── shutdown ────────────────────────────────────────────
    def shutdown(self, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=True)
