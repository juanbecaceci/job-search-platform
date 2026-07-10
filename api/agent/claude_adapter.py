"""ClaudeAdapter — drives the user's Claude Code CLI headless (DECISIONS #5, #10).

Invocation (no API key — the user's own subscription):

    <prompt on stdin> | claude -p --output-format stream-json --verbose \
                               --include-partial-messages [--resume <session_id>] \
                               [--append-system-prompt <system>]

The prompt goes over **stdin**, not argv: Windows caps a command line at 32,767
characters and prompts are unbounded (a long CV can extract to ~63k chars). Over
that limit `CreateProcess` fails with winerror 206, which Python surfaces as
`FileNotFoundError` — indistinguishable from a missing binary unless you check
`winerror`, so `run()` checks it explicitly.

`--output-format stream-json` emits newline-delimited JSON; each line is one
event object keyed by `type`. `--include-partial-messages` adds `stream_event`
lines carrying token-level deltas so we can surface real streaming. The parser
below (`iter_events_from_lines`) is a **pure function** over the NDJSON lines so
it can be unit-tested without spawning the CLI.

Event mapping (Claude Code stream-json → AgentEvent):
  system/init            → capture session_id (returned in the DoneEvent)
  stream_event delta     → TokenEvent (content_block_delta / text_delta)
  stream_event tool_use  → ToolUseEvent (content_block_start, tool_use block)
  assistant (whole msg)  → fallback text/tool_use if partials are absent
  result                 → DoneEvent (final text + session_id)
  anything with is_error → ErrorEvent

The exact field set can shift across CLI versions, so the parser ignores unknown
types and is defensive about missing keys. Validate against the installed CLI
when first wiring this up on a real machine.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Iterable, Iterator
from pathlib import Path

from api.agent.adapter import (
    AgentAdapter,
    AgentEvent,
    AgentTask,
    DoneEvent,
    ErrorEvent,
    TokenEvent,
    ToolUseEvent,
)
from api.config import AGENT_CLI_PATH, ROOT_DIR


def _clean_env() -> dict[str, str]:
    """Environment for the headless subprocess.

    Strips the parent process's nested-session markers so the CLI starts a clean
    headless run even when the API server was itself launched from inside a
    Claude Code session (e.g. the VSCode extension sets CLAUDE_CODE_ENTRYPOINT,
    CLAUDECODE, CLAUDE_CODE_SESSION_ID, …). Leaving them in can make the child
    behave as a nested session.
    """
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("CLAUDECODE") or key.startswith("CLAUDE_CODE") or key in {
            "CLAUDE_PID",
            "CLAUDE_AGENT_SDK_VERSION",
        }:
            env.pop(key, None)
    return env


def _tool_summary(name: str, tool_input: dict) -> str:
    """A short human label for a tool call (no raw args dumped to the UI)."""
    if not isinstance(tool_input, dict):
        return ""
    for key in ("file_path", "path", "pattern", "command", "query", "url"):
        if key in tool_input:
            return f"{key}={tool_input[key]}"
    return ""


def iter_events_from_lines(lines: Iterable[str]) -> Iterator[AgentEvent]:
    """Pure NDJSON → AgentEvent stream. No I/O, no subprocess — unit-testable.

    Guarantees a single terminal event: a `DoneEvent` when a `result` line is
    seen, else an `ErrorEvent` if the stream ends without one.
    """
    session_id: str | None = None
    saw_terminal = False
    # Accumulate assistant text as a fallback when no partial deltas are emitted.
    fallback_text: list[str] = []
    streamed_any_token = False

    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(msg, dict):
            continue

        mtype = msg.get("type")

        if mtype == "system" and msg.get("subtype") == "init":
            session_id = msg.get("session_id") or session_id
            continue

        if mtype == "stream_event":
            event = msg.get("event", {})
            etype = event.get("type")
            if etype == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta" and delta.get("text"):
                    streamed_any_token = True
                    yield TokenEvent(text=delta["text"])
            elif etype == "content_block_start":
                block = event.get("content_block", {})
                if block.get("type") == "tool_use":
                    yield ToolUseEvent(
                        name=block.get("name", "tool"),
                        summary=_tool_summary(block.get("name", ""), block.get("input", {})),
                    )
            continue

        if mtype == "assistant":
            for block in msg.get("message", {}).get("content", []) or []:
                btype = block.get("type")
                if btype == "text":
                    fallback_text.append(block.get("text", ""))
                elif btype == "tool_use":
                    yield ToolUseEvent(
                        name=block.get("name", "tool"),
                        summary=_tool_summary(block.get("name", ""), block.get("input", {})),
                    )
            continue

        if mtype == "result":
            saw_terminal = True
            session_id = msg.get("session_id") or session_id
            if msg.get("is_error"):
                yield ErrorEvent(message=str(msg.get("result") or msg.get("error") or "agent error"))
                return
            text = msg.get("result")
            if not text and fallback_text:
                text = "".join(fallback_text)
            # If tokens were streamed we still send the consolidated text on done
            # (the chat layer uses it to persist the final message).
            yield DoneEvent(text=text or "", resume_id=session_id, raw=msg)
            return

    if not saw_terminal:
        if fallback_text and not streamed_any_token:
            # A stream that ended cleanly with assistant text but no result line.
            yield DoneEvent(text="".join(fallback_text), resume_id=session_id, raw=None)
        else:
            yield ErrorEvent(message="agent stream ended without a result")


class ClaudeAdapter(AgentAdapter):
    def __init__(self, binary: str | None = None) -> None:
        self._binary = binary or AGENT_CLI_PATH

    def _build_command(self, task: AgentTask) -> list[str]:
        """Argv for the CLI. The prompt is NOT here — it goes over stdin.

        Windows caps a command line at 32,767 chars, and prompts are unbounded
        (a long CV can extract to ~63k). Passing `-p` with no positional value
        makes the CLI read the prompt from stdin, which has no such limit.
        """
        cmd = [
            self._binary,
            "-p",
            "--output-format",
            "stream-json",
            "--verbose",
            "--include-partial-messages",
        ]
        if task.system:
            cmd += ["--append-system-prompt", task.system]
        if task.resume_id:
            cmd += ["--resume", task.resume_id]
        if task.allowed_tools:
            # Headless auto-denies un-allowlisted tools, so an MCP-backed source
            # gets nothing back unless its tool is named here.
            cmd += ["--allowedTools", ",".join(task.allowed_tools)]
        return cmd

    def run(self, task: AgentTask) -> Iterator[AgentEvent]:
        cmd = self._build_command(task)
        cwd = str(task.cwd or ROOT_DIR)
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                text=True,
                encoding="utf-8",  # CLI emits UTF-8; Windows text mode defaults to cp1252
                errors="replace",
                bufsize=1,  # line-buffered
                env=_clean_env(),
            )
        except FileNotFoundError as exc:
            # Windows raises FileNotFoundError for BOTH a missing binary
            # (winerror 2) and an over-long command line (winerror 206) — don't
            # report the second as the first, it sends debugging the wrong way.
            if getattr(exc, "winerror", None) == 206:
                yield ErrorEvent(
                    message=(
                        "Agent command line too long for Windows (32,767 char limit). "
                        "The prompt goes over stdin, so this means the system prompt "
                        f"itself is oversized ({len(task.system or '')} chars)."
                    )
                )
            else:
                yield ErrorEvent(
                    message=(
                        f"Agent CLI not found: {self._binary!r}. Set AGENT_CLI_PATH to your "
                        "Claude Code binary (see Settings)."
                    )
                )
            return

        # Hand the prompt over and close stdin so the CLI knows it's complete.
        try:
            if proc.stdin is not None:
                proc.stdin.write(task.prompt or "")
                proc.stdin.close()
        except OSError as exc:
            proc.kill()
            yield ErrorEvent(message=f"could not send prompt to agent: {exc}")
            return

        terminal_sent = False
        try:
            assert proc.stdout is not None
            for event in iter_events_from_lines(proc.stdout):
                if isinstance(event, (DoneEvent, ErrorEvent)):
                    terminal_sent = True
                yield event
            proc.wait(timeout=task.timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            if not terminal_sent:
                yield ErrorEvent(message="agent timed out")
                terminal_sent = True
        finally:
            if proc.poll() is None:
                proc.kill()

        # Only surface a process-level failure if the stream itself didn't
        # already deliver a terminal event (keeps the one-terminal contract).
        if not terminal_sent:
            stderr = proc.stderr.read() if proc.stderr else ""
            yield ErrorEvent(message=f"agent exited {proc.returncode}: {stderr[:500]}")
