import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { statusColor, isTerminal, TERMINAL } from "@/lib/format";
import { ScoreBadge, Loading, ErrorNote } from "@/components/ui";
import { useSetTopbarRight } from "@/components/shell/AppShell";
import PositionsViewToggle from "@/components/ViewToggle";
import type { BoardColumn, PositionCard } from "@/lib/types";

export default function Board() {
  useSetTopbarRight(<PositionsViewToggle active="board" />, []);
  const nav = useNavigate();
  const qc = useQueryClient();
  const [dragId, setDragId] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set(TERMINAL));

  const query = useQuery({ queryKey: ["board"], queryFn: () => api.board() });
  const move = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => api.changeStatus(id, status),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["board"] });
      qc.invalidateQueries({ queryKey: ["positions"] });
    },
  });

  if (query.isLoading) return <Loading />;
  if (query.error) return <ErrorNote error={query.error} />;
  const columns = query.data!.columns;
  const total = columns.reduce((n, c) => n + c.count, 0);
  if (total === 0)
    return (
      <div
        style={{
          margin: 24,
          background: "var(--surface-card)",
          border: "1px solid var(--border-default)",
          borderRadius: "var(--radius-lg)",
          padding: "48px 40px",
          textAlign: "center",
        }}
      >
        <div style={{ fontFamily: "var(--font-display)", fontWeight: 500, fontSize: 18, color: "var(--text-primary)" }}>
          No positions yet.
        </div>
        <div style={{ fontSize: 13.5, color: "var(--text-secondary)", marginTop: 8 }}>
          Positions appear here once a search runs and discovers roles.
        </div>
      </div>
    );

  const toggleCollapse = (status: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(status)) next.delete(status);
      else next.add(status);
      return next;
    });

  return (
    <div
      style={{
        flex: 1,
        height: "100%",
        overflowX: "auto",
        overflowY: "hidden",
        padding: "18px 24px 20px",
        display: "flex",
        gap: 12,
        alignItems: "flex-start",
      }}
    >
      {columns.map((col) => (
        <Column
          key={col.status}
          col={col}
          collapsed={collapsed.has(col.status)}
          collapsible={isTerminal(col.status)}
          onToggle={() => toggleCollapse(col.status)}
          onOpen={(id) => nav(`/positions/${id}`)}
          onDropCard={(id) => {
            if (id) move.mutate({ id, status: col.status });
            setDragId(null);
          }}
          onDragStart={setDragId}
          draggingId={dragId}
        />
      ))}
    </div>
  );
}

function Column({
  col,
  collapsed,
  collapsible,
  onToggle,
  onOpen,
  onDropCard,
  onDragStart,
}: {
  col: BoardColumn;
  collapsed: boolean;
  collapsible: boolean;
  onToggle: () => void;
  onOpen: (id: string) => void;
  onDropCard: (id: string | null) => void;
  onDragStart: (id: string) => void;
  draggingId: string | null;
}) {
  const color = statusColor(col.status);
  const [over, setOver] = useState(false);

  if (collapsed) {
    return (
      <button
        onClick={onToggle}
        style={{
          width: 48,
          minHeight: 220,
          flex: "none",
          background: "var(--surface-card)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "var(--radius-lg)",
          cursor: "pointer",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          padding: "14px 0",
          gap: 10,
        }}
      >
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-tertiary)", fontWeight: 600 }}>
          {col.count}
        </span>
        <span
          style={{
            writingMode: "vertical-rl",
            textOrientation: "mixed",
            fontSize: 11,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: "var(--text-tertiary)",
            fontWeight: 600,
          }}
        >
          {col.status}
        </span>
      </button>
    );
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        onDropCard(e.dataTransfer.getData("text/plain") || null);
      }}
      style={{
        width: 244,
        flex: "none",
        background: over ? "rgba(92,138,147,0.06)" : "transparent",
        border: `1px solid ${over ? "var(--border-accent)" : "transparent"}`,
        borderRadius: "var(--radius-lg)",
        padding: 6,
        maxHeight: "100%",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "0 4px 10px" }}>
        <span
          style={{
            fontSize: 11.5,
            fontWeight: 600,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            color: isTerminal(col.status) ? "var(--text-tertiary)" : color,
            flex: 1,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {col.status}
        </span>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: "var(--text-tertiary)",
            background: "rgba(138,148,166,0.12)",
            borderRadius: "var(--radius-pill)",
            padding: "1px 7px",
          }}
        >
          {col.count}
        </span>
        {collapsible && (
          <button
            onClick={onToggle}
            title="Collapse"
            style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-tertiary)", padding: 2, display: "flex" }}
          >
            <svg width="11" height="11" viewBox="0 0 10 10">
              <path d="M6.5 2.5 3.5 5 6.5 7.5" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        )}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 9, overflowY: "auto", minHeight: 60 }}>
        {col.positions.map((card) => (
          <BoardCard key={card.id} card={card} onOpen={() => onOpen(card.id)} onDragStart={() => onDragStart(card.id)} />
        ))}
      </div>
    </div>
  );
}

function BoardCard({ card, onOpen, onDragStart }: { card: PositionCard; onOpen: () => void; onDragStart: () => void }) {
  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("text/plain", card.id);
        onDragStart();
      }}
      onClick={onOpen}
      style={{
        background: "var(--surface-card)",
        border: "1px solid var(--border-default)",
        borderRadius: "var(--radius-md)",
        padding: 11,
        cursor: "pointer",
      }}
    >
      <div style={{ fontSize: 12.5, fontWeight: 500, color: "var(--text-primary)", lineHeight: 1.35 }}>{card.role}</div>
      <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 3 }}>{card.company?.name ?? "—"}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 7, marginTop: 9 }}>
        <ScoreBadge score={card.score} category={card.score_category} />
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-tertiary)" }}>{card.source}</span>
      </div>
    </div>
  );
}
