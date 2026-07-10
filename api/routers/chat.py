"""Chat threads/messages + the streaming agent turn (§5, §6).

`POST /chat/threads/{id}/messages` runs one agent turn through the adapter and
streams SSE events (`message_created`, `token`, `tool_use`, `pending_change`,
`done`, `error`). Proposed changes in the agent's reply become `pending_changes`
rows (never applied here — DECISIONS #6).
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from api.agent import (
    AgentAdapter,
    AgentTask,
    Attachment,
    DoneEvent,
    ErrorEvent,
    TokenEvent,
    ToolUseEvent,
)
from api.agent.change_parser import parse_proposed_changes
from api.agent.prompt_builder import build_system_prompt
from api.config import DATA_DIR, ROOT_DIR
from api.db.engine import SessionLocal, get_session
from api.deps import get_adapter
from api.models import (
    ChatMessage,
    ChatThread,
    PendingChange,
    Position,
    ProfileBasics,
    ProfileSection,
    ScoringConfig,
)
from api.schemas.chat import ChatMessageOut, ChatThreadOut, ThreadCreate
from api.services import change_applier

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/threads", response_model=list[ChatThreadOut])
def list_threads(
    session: Session = Depends(get_session),
    module: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> list[ChatThreadOut]:
    stmt = select(ChatThread).where(ChatThread.archived.is_(False))
    if module:
        stmt = stmt.where(ChatThread.module == module)
    if entity_type:
        stmt = stmt.where(ChatThread.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(ChatThread.entity_id == entity_id)
    stmt = stmt.order_by(ChatThread.updated_at.desc())
    return [ChatThreadOut.model_validate(t) for t in session.scalars(stmt).all()]


@router.post("/threads", response_model=ChatThreadOut, status_code=201)
def create_thread(body: ThreadCreate, session: Session = Depends(get_session)) -> ChatThreadOut:
    thread = ChatThread(
        title=body.title,
        module=body.module,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
    )
    session.add(thread)
    session.commit()
    return ChatThreadOut.model_validate(thread)


@router.get("/threads/{thread_id}/messages", response_model=list[ChatMessageOut])
def list_messages(thread_id: int, session: Session = Depends(get_session)) -> list[ChatMessageOut]:
    if session.get(ChatThread, thread_id) is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at, ChatMessage.id)
    )
    return [ChatMessageOut.model_validate(m) for m in session.scalars(stmt).all()]


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _entity_snapshot(session: Session, thread: ChatThread) -> dict | None:
    """A JSON slice of what the chat is scoped to, injected into the prompt."""
    if thread.module == "scoring":
        cfg = session.scalar(select(ScoringConfig).where(ScoringConfig.is_active.is_(True)))
        if cfg:
            return {
                "table": "scoring_configs",
                "version": cfg.version,
                "salary_gate": cfg.salary_gate,
                "score_threshold_auto_discard": cfg.score_threshold_auto_discard,
                "scale_max": cfg.scale_max,
                "categories": cfg.categories,
                "criteria": cfg.criteria,
            }
    if thread.module in ("profile", "onboarding"):
        # Without this the agent is asked to edit a profile it has never seen —
        # it can only guess at what's already there, or ask the user to paste it.
        basics = session.get(ProfileBasics, 1)
        sections = session.scalars(
            select(ProfileSection).order_by(ProfileSection.sort_order, ProfileSection.id)
        ).all()
        return {
            "table": "profile_basics",
            "basics": {
                f: getattr(basics, f, None) if basics else None
                for f in (
                    "full_name", "headline", "email", "phone",
                    "location", "linkedin_url", "portfolio_url",
                )
            },
            "sections": [
                {
                    "id": s.id,
                    "slug": s.slug,
                    "title": s.title,
                    "sort_order": s.sort_order,
                    "content_md": s.content_md,
                }
                for s in sections
            ],
        }
    if thread.entity_type == "position" and thread.entity_id:
        p = session.get(Position, thread.entity_id, options=[selectinload(Position.company)])
        if p:
            return {
                "table": "positions",
                "id": p.id,
                "role": p.role,
                "company": p.company.name if p.company else None,
                "status": p.status,
                "score": p.score,
                "score_category": p.score_category,
                "evaluation": p.evaluation,
                "salary_raw": p.salary_raw,
            }
    return None


@router.post("/threads/{thread_id}/messages")
async def post_message(
    thread_id: int,
    content: str = Form(...),
    files: list[UploadFile] = File(default=[]),
    adapter: AgentAdapter = Depends(get_adapter),
) -> StreamingResponse:
    with SessionLocal() as session:
        if session.get(ChatThread, thread_id) is None:
            raise HTTPException(status_code=404, detail="Thread not found")

    # Persist any attachments under data/ (never committed) before streaming.
    attachments: list[Attachment] = []
    attachment_meta: list[dict] = []
    if files:
        dest = DATA_DIR / "attachments" / str(thread_id)
        dest.mkdir(parents=True, exist_ok=True)
        for f in files:
            if not f.filename:
                continue
            path = dest / f.filename
            path.write_bytes(await f.read())
            attachments.append(Attachment(filename=f.filename, path=path, mime=f.content_type))
            attachment_meta.append({"filename": f.filename, "mime": f.content_type})

    def stream():
        yield from _run_turn(thread_id, content, attachments, attachment_meta, adapter)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _run_turn(thread_id, content, attachments, attachment_meta, adapter: AgentAdapter):
    session = SessionLocal()
    try:
        thread = session.get(ChatThread, thread_id)
        user_msg = ChatMessage(
            thread_id=thread_id, role="user", content=content,
            attachments=attachment_meta or None, status="complete",
        )
        session.add(user_msg)
        session.flush()
        assistant_msg = ChatMessage(thread_id=thread_id, role="assistant", content="", status="streaming")
        session.add(assistant_msg)
        session.flush()
        session.commit()
        yield _sse("message_created", {
            "user_message_id": user_msg.id, "assistant_message_id": assistant_msg.id,
        })

        entity = _entity_snapshot(session, thread)
        system = build_system_prompt(session, thread.module, entity)
        prompt = content
        if attachments:
            paths = ", ".join(str(a.path) for a in attachments)
            prompt += f"\n\n[Attached files available to read: {paths}]"
        task = AgentTask(
            prompt=prompt, system=system,
            resume_id=thread.adapter_thread_id, attachments=attachments, cwd=ROOT_DIR,
        )

        collected: list[str] = []
        final_text: str | None = None
        resume_id: str | None = None

        for ev in adapter.run(task):
            if isinstance(ev, TokenEvent):
                collected.append(ev.text)
                yield _sse("token", {"text": ev.text})
            elif isinstance(ev, ToolUseEvent):
                yield _sse("tool_use", {"name": ev.name, "summary": ev.summary})
            elif isinstance(ev, DoneEvent):
                final_text = ev.text or "".join(collected)
                resume_id = ev.resume_id
            elif isinstance(ev, ErrorEvent):
                assistant_msg.content = "".join(collected)
                assistant_msg.status = "error"
                session.commit()
                yield _sse("error", {"message": ev.message})
                return

        assistant_msg.content = final_text if final_text is not None else "".join(collected)
        assistant_msg.status = "complete"
        if resume_id:
            thread.adapter_thread_id = resume_id

        proposed = parse_proposed_changes(assistant_msg.content or "")
        emitted: list[tuple[int, object]] = []
        for pc in proposed:
            change_type = pc.normalized_type()
            # Catch a target the applier can't write *now*, rather than letting
            # a plausible-looking card sit in the tray until approve fails.
            supported = change_applier.is_supported(pc.target_table, change_type)
            row = PendingChange(
                thread_id=thread.id, module=pc.module, change_type=change_type,
                target_table=pc.target_table, target_id=pc.target_id,
                summary=pc.summary, diff=pc.diff,
                status="pending" if supported else "failed",
                apply_error=None if supported else (
                    f"Not an editable target: {pc.target_table!r}. "
                    f"The agent can change: {', '.join(sorted(change_applier.SUPPORTED_TARGETS))}."
                ),
            )
            session.add(row)
            session.flush()
            emitted.append((row.id, pc))
        assistant_msg.pending_change_ids = [cid for cid, _ in emitted] or None
        session.commit()

        for cid, pc in emitted:
            yield _sse("pending_change", {
                "change_id": cid, "module": pc.module, "summary": pc.summary, "diff": pc.diff,
            })
        yield _sse("done", {"message_id": assistant_msg.id})
    except Exception as exc:  # noqa: BLE001 — report any turn failure to the client
        session.rollback()
        yield _sse("error", {"message": str(exc)})
    finally:
        session.close()
