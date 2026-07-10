import { useState, type CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useJobAction } from "@/lib/useJobAction";
import { ALL_STATUSES, scoreColor } from "@/lib/format";
import { ScoreBadge, Loading, ErrorNote, Button } from "@/components/ui";
import { useSetTopbarRight } from "@/components/shell/AppShell";
import PositionsViewToggle from "@/components/ViewToggle";
import type { PositionCard } from "@/lib/types";

const SOURCES = ["remotive", "remoteok", "himalayas", "arbeitnow", "jobicy", "linkedin", "indeed", "manual"];
const TRACKS = ["full-time", "gig-freelance"];
const SORTS = [
  { value: "score", label: "Score ↓" },
  { value: "rank", label: "Rank" },
  { value: "-date", label: "Newest" },
  { value: "date", label: "Oldest" },
];

const selectStyle: CSSProperties = {
  background: "var(--surface-sunken)",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-md)",
  padding: "8px 10px",
  fontSize: 12.5,
  color: "var(--text-primary)",
  fontFamily: "var(--font-body)",
  outline: "none",
};
const colHead: CSSProperties = {
  fontSize: 10,
  letterSpacing: "0.1em",
  textTransform: "uppercase",
  color: "var(--text-tertiary)",
  fontWeight: 600,
};

export default function Positions() {
  useSetTopbarRight(<PositionsViewToggle active="table" />, []);
  const nav = useNavigate();
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [source, setSource] = useState("");
  const [track, setTrack] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [sort, setSort] = useState("score");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const params = { q, status, source, track, min_score: minScore || undefined, sort, page_size: 100 };
  const query = useQuery({
    queryKey: ["positions", params],
    queryFn: () => api.positions(params),
    placeholderData: (p) => p,
  });

  const changeStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => api.changeStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["positions"] }),
  });

  const evalJob = useJobAction(() => {
    setSelected(new Set());
    qc.invalidateQueries({ queryKey: ["positions"] });
  });

  const items = query.data?.items ?? [];
  const allSelected = items.length > 0 && items.every((p) => selected.has(p.id));
  const toggleAll = () => setSelected(allSelected ? new Set() : new Set(items.map((p) => p.id)));
  const toggleOne = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  return (
    <div style={{ padding: "20px 24px 40px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 16 }}>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search role or company…"
          style={{ ...selectStyle, width: 220 }}
        />
        <select value={status} onChange={(e) => setStatus(e.target.value)} style={selectStyle}>
          <option value="">All statuses</option>
          {ALL_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select value={source} onChange={(e) => setSource(e.target.value)} style={selectStyle}>
          <option value="">All sources</option>
          {SOURCES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select value={track} onChange={(e) => setTrack(e.target.value)} style={selectStyle}>
          <option value="">All tracks</option>
          {TRACKS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--text-tertiary)" }}>
          <span>Min score</span>
          <input
            type="range"
            min={0}
            max={100}
            step={5}
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            style={{ width: 100, accentColor: "var(--accent-primary)" }}
          />
          <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-secondary)", width: 24 }}>{minScore}</span>
        </div>
        <div style={{ flex: 1 }} />
        <select value={sort} onChange={(e) => setSort(e.target.value)} style={selectStyle}>
          {SORTS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      {query.isLoading ? (
        <Loading />
      ) : query.error ? (
        <ErrorNote error={query.error} />
      ) : (
        <>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
            <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
              {query.data!.total} position{query.data!.total !== 1 ? "s" : ""}
              {selected.size > 0 && ` · ${selected.size} selected`}
            </div>
            {selected.size > 0 && (
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                {evalJob.error && <span style={{ fontSize: 12, color: "var(--status-negative)" }}>{evalJob.error}</span>}
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={evalJob.busy}
                  onClick={() => evalJob.run(() => api.evaluatePositions(Array.from(selected)))}
                >
                  {evalJob.busy ? evalJob.message ?? "Evaluating…" : `Evaluate selected (${selected.size})`}
                </Button>
              </div>
            )}
          </div>
          {query.data!.items.length === 0 ? (
            <div
              style={{
                background: "var(--surface-card)",
                border: "1px solid var(--border-default)",
                borderRadius: "var(--radius-lg)",
                padding: "48px 40px",
                textAlign: "center",
              }}
            >
              <div style={{ fontFamily: "var(--font-display)", fontWeight: 500, fontSize: 18, color: "var(--text-primary)" }}>
                No positions match these filters.
              </div>
              <div style={{ fontSize: 13.5, color: "var(--text-secondary)", marginTop: 8 }}>
                Try widening the filters, or run a search to discover more.
              </div>
            </div>
          ) : (
            <div
              style={{
                border: "1px solid var(--border-default)",
                borderRadius: "var(--radius-lg)",
                overflow: "hidden",
                background: "var(--surface-card)",
              }}
            >
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "24px 1.8fr 90px 100px 90px 130px 120px 170px",
                  gap: 12,
                  padding: "9px 16px",
                  background: "var(--surface-card-alt)",
                  borderBottom: "1px solid var(--border-default)",
                  alignItems: "center",
                }}
              >
                <input type="checkbox" checked={allSelected} onChange={toggleAll} style={{ accentColor: "var(--accent-primary)" }} />
                {["Position", "Source", "Track", "Score", "Salary", "Discovered", "Status"].map((h) => (
                  <span key={h} style={colHead}>
                    {h}
                  </span>
                ))}
              </div>
              {query.data!.items.map((p) => (
                <Row
                  key={p.id}
                  p={p}
                  checked={selected.has(p.id)}
                  onToggle={() => toggleOne(p.id)}
                  onOpen={() => nav(`/positions/${p.id}`)}
                  onStatus={(status) => changeStatus.mutate({ id: p.id, status })}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Row({
  p,
  checked,
  onToggle,
  onOpen,
  onStatus,
}: {
  p: PositionCard;
  checked: boolean;
  onToggle: () => void;
  onOpen: () => void;
  onStatus: (s: string) => void;
}) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "24px 1.8fr 90px 100px 90px 130px 120px 170px",
        gap: 12,
        padding: "11px 16px",
        borderTop: "1px solid var(--border-subtle)",
        alignItems: "center",
      }}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={onToggle}
        onClick={(e) => e.stopPropagation()}
        style={{ accentColor: "var(--accent-primary)" }}
      />
      <div style={{ minWidth: 0, cursor: "pointer" }} onClick={onOpen}>
        <div style={{ fontSize: 13.5, fontWeight: 500, color: "var(--text-primary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {p.role}
        </div>
        <div style={{ fontSize: 11.5, color: "var(--text-secondary)", marginTop: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {p.company?.name ?? "—"}
        </div>
      </div>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--text-tertiary)" }}>{p.source}</span>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--text-tertiary)" }}>{p.track ?? "—"}</span>
      <div>
        <ScoreBadge score={p.score} category={p.score_category} />
        {p.score_category && (
          <div style={{ fontSize: 9.5, letterSpacing: "0.06em", color: scoreColor(p.score_category), marginTop: 2 }}>
            {p.score_category}
          </div>
        )}
      </div>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--text-secondary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
        {p.salary_raw ?? "—"}
      </span>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--text-tertiary)" }}>—</span>
      <select
        value={p.status}
        onChange={(e) => onStatus(e.target.value)}
        onClick={(e) => e.stopPropagation()}
        style={{
          ...selectStyle,
          fontSize: 11.5,
          padding: "5px 8px",
          color: "var(--text-secondary)",
        }}
      >
        {ALL_STATUSES.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
    </div>
  );
}
