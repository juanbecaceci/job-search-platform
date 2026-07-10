"""One-shot agent calls for job handlers (DECISIONS #14, #16).

Every handler that calls the agent outside a chat thread needs the same thing:
run the task to completion, return the final text, and **fail loudly if the
agent failed**. That last part is the reason this is shared code — each handler
used to keep a private `_run_agent` that collected `DoneEvent.text` and ignored
`ErrorEvent` entirely, so an agent that never ran at all returned `""`, and the
handler then reported whatever its own parse step complained about ("agent
returned no structured profile block") instead of the real cause. That sent
debugging in the wrong direction; a failure here should say what actually broke.
"""

from __future__ import annotations

from api.agent.adapter import AgentTask, DoneEvent, ErrorEvent
from api.agent.claude_adapter import ClaudeAdapter
from api.config import ROOT_DIR


class AgentRunError(RuntimeError):
    """The agent CLI reported an error, or produced no output at all."""


def run_agent_text(
    system: str,
    user_prompt: str,
    timeout: float | None = None,
    allowed_tools: list[str] | None = None,
) -> str:
    """Run one agent task and return its final text.

    Raises `AgentRunError` if the agent emitted an error or finished empty,
    rather than handing back `""` for the caller to misdiagnose downstream.

    `allowed_tools` names the tools the headless run may use without a
    permission prompt (see `AgentTask.allowed_tools`). Omit it for pure
    text-in/text-out tasks; pass it for tasks that must reach a tool, such as
    an MCP job-board connector.
    """
    adapter = ClaudeAdapter()
    task = AgentTask(
        prompt=user_prompt,
        system=system,
        cwd=ROOT_DIR,
        allowed_tools=list(allowed_tools or []),
        **({"timeout": timeout} if timeout is not None else {}),
    )

    final_text = ""
    error: str | None = None
    for event in adapter.run(task):
        if isinstance(event, DoneEvent):
            final_text = event.text or ""
        elif isinstance(event, ErrorEvent):
            error = event.message

    if error:
        raise AgentRunError(error)
    if not final_text.strip():
        raise AgentRunError("agent produced no output")
    return final_text
