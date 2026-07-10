"""Agent layer: the BYO-agent bridge (DECISIONS #5, #9, #10).

All LLM reasoning runs through the user's own agent CLI (Claude Code in v1),
invoked headless as a subprocess — never an Anthropic API key. The adapter is an
explicit interface so a future CodexAdapter is a drop-in; v1 ships only
`ClaudeAdapter`.
"""

from api.agent.adapter import (
    AgentAdapter,
    AgentEvent,
    AgentTask,
    Attachment,
    DoneEvent,
    ErrorEvent,
    TokenEvent,
    ToolUseEvent,
)

__all__ = [
    "AgentAdapter",
    "AgentTask",
    "Attachment",
    "AgentEvent",
    "TokenEvent",
    "ToolUseEvent",
    "DoneEvent",
    "ErrorEvent",
]
