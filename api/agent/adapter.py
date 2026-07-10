"""The agent adapter contract: `AgentTask -> Iterator[AgentEvent]` (DECISIONS #5).

An adapter turns one agent turn (a user prompt + context) into a stream of
events the chat layer maps onto SSE (§6): text tokens, tool-use indicators, a
terminal `done` (carrying the full text + a resume id for conversation
continuity), or an `error`. The interface is intentionally minimal and
transport-agnostic so `ClaudeAdapter` (v1) and a future `CodexAdapter` are
interchangeable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Attachment:
    filename: str
    path: Path
    mime: str | None = None


@dataclass
class AgentTask:
    """One agent turn."""

    prompt: str
    system: str | None = None
    # Adapter-side conversation id to continue a thread (Claude session_id →
    # `--resume`). None starts a fresh conversation.
    resume_id: str | None = None
    attachments: list[Attachment] = field(default_factory=list)
    # Working directory the agent runs in (defaults to the repo root). Kept
    # explicit so callers can scope file access.
    cwd: Path | None = None
    # Hard ceiling on a turn's wall-clock time (seconds).
    timeout: float = 600.0
    # Tools the CLI may use without an interactive permission prompt. Headless
    # runs auto-DENY anything not listed, so a task that needs a tool (e.g. an
    # MCP job-board connector) must name it here or the call silently fails.
    # Empty = the CLI's own defaults, which is what chat turns want.
    allowed_tools: list[str] = field(default_factory=list)


# ── event types ──────────────────────────────────────────────


@dataclass
class TokenEvent:
    """A chunk of assistant text (streamed)."""

    text: str


@dataclass
class ToolUseEvent:
    """The agent invoked a tool (surface as an indicator, not the raw args)."""

    name: str
    summary: str = ""


@dataclass
class DoneEvent:
    """Terminal success: the full assistant text + resume id for continuity."""

    text: str
    resume_id: str | None = None
    raw: dict | None = None


@dataclass
class ErrorEvent:
    """Terminal failure."""

    message: str


AgentEvent = TokenEvent | ToolUseEvent | DoneEvent | ErrorEvent


class AgentAdapter(ABC):
    """Runs an `AgentTask`, yielding `AgentEvent`s until a terminal one."""

    @abstractmethod
    def run(self, task: AgentTask) -> Iterator[AgentEvent]:
        """Yield events; the last is exactly one `DoneEvent` or `ErrorEvent`."""
        raise NotImplementedError
