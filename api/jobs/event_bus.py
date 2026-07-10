"""In-process pub/sub for job progress, consumed by the SSE endpoint.

Single-user, single-process app (DECISIONS #3: SSE, not WebSocket; #4: no
Redis/broker), so a plain in-memory bus is enough. Each job gets:

- a **buffer** of every event emitted (so a client that connects *after* the job
  started — or reconnects with `Last-Event-ID` — still receives the backlog,
  including the terminal `done`/`failed`), and
- a set of live subscriber queues for events emitted while connected.

Events are `(seq, event, data)`; `seq` is the monotonic per-job id used as the
SSE event id for `Last-Event-ID` resumption. Terminal events (`done`, `failed`)
mark the job closed so subscribers know to stop.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from collections.abc import Iterator
from queue import Queue
from typing import Any

Event = tuple[int, str, dict[str, Any]]  # (seq, event_name, data)

_TERMINAL = {"done", "failed"}


class EventBus:
    def __init__(self, buffer_size: int = 2000) -> None:
        self._buffer_size = buffer_size
        self._lock = threading.Lock()
        self._subscribers: dict[str, set[Queue[Event]]] = defaultdict(set)
        self._buffers: dict[str, list[Event]] = defaultdict(list)
        self._seq: dict[str, int] = defaultdict(int)
        self._closed: set[str] = set()

    def publish(self, job_id: str, event: str, data: dict[str, Any]) -> None:
        """Append an event to a job's stream and fan it out to live subscribers."""
        with self._lock:
            seq = self._seq[job_id]
            self._seq[job_id] += 1
            item: Event = (seq, event, data)

            buf = self._buffers[job_id]
            buf.append(item)
            if len(buf) > self._buffer_size:
                del buf[: len(buf) - self._buffer_size]

            for q in self._subscribers[job_id]:
                q.put(item)
            if event in _TERMINAL:
                self._closed.add(job_id)

    def subscribe(
        self, job_id: str, last_event_id: int | None = None
    ) -> Iterator[Event]:
        """Yield a job's events: buffered backlog first, then live until terminal.

        Registering the queue and snapshotting the backlog happen under one lock,
        so no event is dropped or duplicated across the backlog/live boundary
        (`publish` holds the same lock).
        """
        q: Queue[Event] = Queue()
        with self._lock:
            backlog = [
                it
                for it in self._buffers[job_id]
                if last_event_id is None or it[0] > last_event_id
            ]
            already_closed = job_id in self._closed
            self._subscribers[job_id].add(q)

        try:
            for it in backlog:
                yield it
                if it[1] in _TERMINAL:
                    return
            if already_closed:
                return
            while True:
                it = q.get()
                yield it
                if it[1] in _TERMINAL:
                    return
        finally:
            with self._lock:
                self._subscribers[job_id].discard(q)

    def clear(self, job_id: str) -> None:
        """Drop a finished job's buffer once nobody needs it (optional cleanup)."""
        with self._lock:
            self._buffers.pop(job_id, None)
            self._seq.pop(job_id, None)
            self._closed.discard(job_id)
