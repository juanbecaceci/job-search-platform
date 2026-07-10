import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { streamChat } from "@/lib/sse";
import type { ChatMessage, ChatThread } from "@/lib/types";
import { Spinner } from "@/components/ui";

interface ChatContext {
  module: string;
  entity_type?: string;
  entity_id?: string;
  label: string;
}

/** Derive the agent module + bound entity from the active route. */
function deriveContext(pathname: string): ChatContext {
  const posDetail = pathname.match(/^\/positions\/([^/]+)$/);
  if (posDetail && posDetail[1] !== "board") {
    return { module: "positions", entity_type: "position", entity_id: posDetail[1], label: "this position" };
  }
  if (pathname.startsWith("/positions")) return { module: "positions", label: "positions" };
  if (pathname.startsWith("/searches")) return { module: "searches", label: "searches" };
  if (pathname.startsWith("/scoring")) return { module: "scoring", label: "scoring" };
  if (pathname.startsWith("/profile")) return { module: "profile", label: "your profile" };
  // The wizard's follow-up step is a profile conversation (§8 /onboarding).
  if (pathname.startsWith("/onboarding")) return { module: "profile", label: "your profile" };
  if (pathname.startsWith("/templates")) return { module: "templates", label: "templates" };
  if (pathname.startsWith("/documents")) return { module: "documents", label: "documents" };
  return { module: "analytics", label: "your pipeline" };
}

interface LiveMsg extends Partial<ChatMessage> {
  role: string;
  content: string;
  streaming?: boolean;
  tools?: { name: string; summary: string }[];
  changeIds?: number[];
}

export default function ChatDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const location = useLocation();
  const ctx = deriveContext(location.pathname);
  const qc = useQueryClient();
  const [thread, setThread] = useState<ChatThread | null>(null);
  const [messages, setMessages] = useState<LiveMsg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Reset thread binding when the route context changes.
  useEffect(() => {
    setThread(null);
    setMessages([]);
  }, [ctx.module, ctx.entity_id]);

  // Lazily resolve / create the thread when opened.
  useEffect(() => {
    if (!open || thread) return;
    let cancelled = false;
    (async () => {
      const existing = await api.chatThreads({
        module: ctx.module,
        entity_type: ctx.entity_type,
        entity_id: ctx.entity_id,
      });
      let t = existing[0];
      if (!t) {
        t = await api.createThread({
          module: ctx.module,
          entity_type: ctx.entity_type,
          entity_id: ctx.entity_id,
        });
      }
      if (cancelled) return;
      setThread(t);
      const hist = await api.chatMessages(t.id);
      if (!cancelled)
        setMessages(hist.map((m) => ({ ...m, role: m.role, content: m.content || "" })));
    })();
    return () => {
      cancelled = true;
    };
  }, [open, thread, ctx.module, ctx.entity_type, ctx.entity_id]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

  async function send() {
    if (!thread || !input.trim() || busy) return;
    const text = input.trim();
    setInput("");
    setBusy(true);
    setMessages((m) => [
      ...m,
      { role: "user", content: text },
      { role: "assistant", content: "", streaming: true, tools: [], changeIds: [] },
    ]);
    const updateLast = (fn: (m: LiveMsg) => LiveMsg) =>
      setMessages((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = fn(copy[copy.length - 1]);
        return copy;
      });
    try {
      for await (const ev of streamChat(thread.id, text)) {
        if (ev.event === "token") updateLast((m) => ({ ...m, content: m.content + ev.data.text }));
        else if (ev.event === "tool_use")
          updateLast((m) => ({ ...m, tools: [...(m.tools || []), ev.data] }));
        else if (ev.event === "pending_change") {
          updateLast((m) => ({ ...m, changeIds: [...(m.changeIds || []), ev.data.change_id] }));
          qc.invalidateQueries({ queryKey: ["changes"] });
        } else if (ev.event === "done") updateLast((m) => ({ ...m, streaming: false }));
        else if (ev.event === "error")
          updateLast((m) => ({ ...m, streaming: false, content: m.content + `\n[error: ${ev.data.message}]` }));
      }
    } catch (e) {
      updateLast((m) => ({ ...m, streaming: false, content: m.content + `\n[error: ${(e as Error).message}]` }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside
      style={{
        width: open ? 400 : 0,
        flex: "none",
        borderLeft: open ? "1px solid var(--border-subtle)" : "none",
        background: "var(--surface-sunken)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        transition: "width var(--duration-slow) var(--ease-standard)",
      }}
    >
      {open && (
        <>
          <div
            style={{
              height: 56,
              flex: "none",
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "0 16px",
              borderBottom: "1px solid var(--border-subtle)",
            }}
          >
            <span
              style={{
                fontFamily: "var(--font-display)",
                fontSize: 14,
                fontWeight: 500,
                color: "var(--text-primary)",
              }}
            >
              Agent
            </span>
            <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>· {ctx.label}</span>
            <div style={{ flex: 1 }} />
            <button
              onClick={onClose}
              style={{ background: "none", border: "none", color: "var(--text-secondary)", cursor: "pointer", fontSize: 18 }}
            >
              ×
            </button>
          </div>

          <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
            {messages.length === 0 && (
              <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6 }}>
                Ask the agent about {ctx.label}. It can propose changes (scoring, notes, searches) that
                you approve from the changes tray.
              </div>
            )}
            {messages.map((m, i) => (
              <MessageBubble key={i} msg={m} />
            ))}
          </div>

          <div style={{ flex: "none", padding: 12, borderTop: "1px solid var(--border-subtle)" }}>
            <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void send();
                  }
                }}
                placeholder={thread ? "Message the agent…" : "Connecting…"}
                disabled={!thread || busy}
                rows={2}
                style={{
                  flex: 1,
                  resize: "none",
                  background: "var(--surface-card-alt)",
                  border: "1px solid var(--border-default)",
                  borderRadius: "var(--radius-md)",
                  padding: "9px 11px",
                  fontSize: 13,
                  color: "var(--text-primary)",
                  fontFamily: "var(--font-body)",
                  outline: "none",
                }}
              />
              <button
                onClick={() => void send()}
                disabled={!thread || busy || !input.trim()}
                style={{
                  width: 38,
                  height: 38,
                  flex: "none",
                  borderRadius: "var(--radius-md)",
                  border: "none",
                  background: "var(--interactive-default)",
                  color: "var(--text-on-accent)",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  opacity: !thread || busy || !input.trim() ? 0.5 : 1,
                }}
              >
                {busy ? <Spinner size={14} /> : "→"}
              </button>
            </div>
          </div>
        </>
      )}
    </aside>
  );
}

function MessageBubble({ msg }: { msg: LiveMsg }) {
  const isUser = msg.role === "user";
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: isUser ? "flex-end" : "flex-start" }}>
      {(msg.tools?.length ?? 0) > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
          {msg.tools!.map((t, i) => (
            <span
              key={i}
              style={{
                fontSize: 11,
                fontFamily: "var(--font-mono)",
                color: "var(--text-tertiary)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-sm)",
                padding: "2px 7px",
              }}
            >
              {t.name}
              {t.summary ? ` · ${t.summary}` : ""}
            </span>
          ))}
        </div>
      )}
      <div
        style={{
          maxWidth: "88%",
          background: isUser ? "var(--surface-card)" : "transparent",
          border: isUser ? "1px solid var(--border-default)" : "none",
          borderRadius: "var(--radius-md)",
          padding: isUser ? "9px 12px" : 0,
          fontSize: 13.5,
          lineHeight: 1.6,
          color: "var(--text-primary)",
          whiteSpace: "pre-wrap",
        }}
      >
        {stripChangeBlock(msg.content)}
        {msg.streaming && (
          <span
            style={{ display: "inline-block", width: 7, marginLeft: 2, animation: "jsCaret 1s step-end infinite" }}
          >
            ▌
          </span>
        )}
      </div>
      {(msg.changeIds?.length ?? 0) > 0 && (
        <div style={{ fontSize: 12, color: "var(--accent-primary)" }}>
          ⤷ proposed {msg.changeIds!.length} change{msg.changeIds!.length > 1 ? "s" : ""} — review in the changes tray
        </div>
      )}
    </div>
  );
}

/** Hide the machine-readable proposed_changes json block from the chat bubble. */
function stripChangeBlock(text: string): string {
  return text.replace(/```json\s*[\s\S]*?"proposed_changes"[\s\S]*?```/g, "").trim();
}
