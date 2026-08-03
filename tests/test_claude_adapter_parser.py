"""The NDJSON → AgentEvent parser in `api/agent/claude_adapter.py`.

This is the seam between the platform and an external CLI whose output format
isn't ours to control, so it's written as a pure function over lines and
documented as such. Everything below runs without spawning anything.

The invariant that matters most: **the stream always terminates.** Chat and
every job handler wait on a terminal event, so a truncated or malformed stream
that yielded nothing terminal would hang a request rather than fail it. The CLI
crashing mid-answer is exactly when that happens.
"""

from __future__ import annotations

import json

from api.agent.adapter import DoneEvent, ErrorEvent, TokenEvent, ToolUseEvent
from api.agent.claude_adapter import iter_events_from_lines


def lines(*objs) -> list[str]:
    return [json.dumps(o) for o in objs]


INIT = {"type": "system", "subtype": "init", "session_id": "sess-abc"}


def delta(text: str) -> dict:
    return {
        "type": "stream_event",
        "event": {
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": text},
        },
    }


def result(text: str, **extra) -> dict:
    return {"type": "result", "result": text, "session_id": "sess-abc", **extra}


# ── The happy path ──────────────────────────────────────────────────────────


def test_streams_tokens_then_terminates_with_done():
    events = list(iter_events_from_lines(lines(INIT, delta("Hel"), delta("lo"), result("Hello"))))

    assert [type(e) for e in events] == [TokenEvent, TokenEvent, DoneEvent]
    assert [e.text for e in events[:2]] == ["Hel", "lo"]
    assert events[-1].text == "Hello"


def test_session_id_from_init_is_carried_to_done():
    """`--resume` continuity depends on this id surviving the whole stream."""
    events = list(iter_events_from_lines(lines(INIT, result("hi"))))
    assert events[-1].resume_id == "sess-abc"


def test_session_id_survives_a_result_without_one():
    payload = {"type": "result", "result": "hi"}
    events = list(iter_events_from_lines(lines(INIT, payload)))
    assert events[-1].resume_id == "sess-abc"


def test_tool_use_is_reported():
    block = {
        "type": "stream_event",
        "event": {
            "type": "content_block_start",
            "content_block": {"type": "tool_use", "name": "Read", "input": {"file_path": "a.py"}},
        },
    }
    events = list(iter_events_from_lines(lines(INIT, block, result("done"))))
    tools = [e for e in events if isinstance(e, ToolUseEvent)]
    assert len(tools) == 1
    assert tools[0].name == "Read"


# ── Fallback when the CLI emits no partial deltas ───────────────────────────


def test_assistant_text_is_used_when_no_deltas_streamed():
    """`--include-partial-messages` may be absent or unsupported by a CLI build."""
    assistant = {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "whole answer"}]},
    }
    events = list(iter_events_from_lines(lines(INIT, assistant, {"type": "result", "result": ""})))
    assert isinstance(events[-1], DoneEvent)
    assert events[-1].text == "whole answer"


def test_result_text_wins_over_accumulated_fallback():
    assistant = {"type": "assistant", "message": {"content": [{"type": "text", "text": "partial"}]}}
    events = list(iter_events_from_lines(lines(INIT, assistant, result("final"))))
    assert events[-1].text == "final"


# ── Errors and malformed input ──────────────────────────────────────────────


def test_is_error_result_becomes_an_error_event():
    events = list(iter_events_from_lines(lines(INIT, result("nope", is_error=True))))
    assert isinstance(events[-1], ErrorEvent)
    assert "nope" in events[-1].message


def test_a_stream_that_never_terminates_still_yields_a_terminal_event():
    """The hang-vs-fail case: no `result` line at all."""
    events = list(iter_events_from_lines(lines(INIT, delta("half an ans"))))
    assert events, "parser yielded nothing — a caller would wait forever"
    assert isinstance(events[-1], (DoneEvent, ErrorEvent))


def test_empty_stream_yields_a_terminal_event():
    events = list(iter_events_from_lines([]))
    assert events
    assert isinstance(events[-1], (DoneEvent, ErrorEvent))


def test_malformed_lines_are_skipped_not_fatal():
    raw = ["{not json", "", "   ", json.dumps(INIT), "null", "[1,2,3]", json.dumps(result("ok"))]
    events = list(iter_events_from_lines(raw))
    assert isinstance(events[-1], DoneEvent)
    assert events[-1].text == "ok"


def test_unknown_event_types_are_ignored():
    """The CLI's field set shifts between versions; unknown lines must not throw."""
    raw = lines(
        INIT,
        {"type": "some_future_type", "payload": {"nested": True}},
        {"type": "stream_event", "event": {"type": "content_block_stop"}},
        result("ok"),
    )
    events = list(iter_events_from_lines(raw))
    assert isinstance(events[-1], DoneEvent)


def test_exactly_one_terminal_event_is_yielded():
    """A second `result` line must not produce a second DoneEvent."""
    raw = lines(INIT, result("first"), result("second"))
    events = list(iter_events_from_lines(raw))
    terminal = [e for e in events if isinstance(e, (DoneEvent, ErrorEvent))]
    assert len(terminal) == 1
    assert terminal[0].text == "first"
