"""ScriptedAdapter — a deterministic agent for tests and offline development.

Yields a predefined event sequence (or one derived from a callable), so the chat
pipeline, change parsing, and the HITL approve flow can be exercised without the
real CLI. Not used in production.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

from api.agent.adapter import AgentAdapter, AgentEvent, AgentTask, DoneEvent, TokenEvent


class ScriptedAdapter(AgentAdapter):
    def __init__(
        self,
        events: list[AgentEvent] | None = None,
        script: Callable[[AgentTask], list[AgentEvent]] | None = None,
    ) -> None:
        self._events = events
        self._script = script

    def run(self, task: AgentTask) -> Iterator[AgentEvent]:
        events = self._script(task) if self._script else self._events
        if events is None:
            # Minimal echo so the default fake always terminates correctly.
            events = [TokenEvent(text="ok"), DoneEvent(text="ok", resume_id="fake-session")]
        yield from events
