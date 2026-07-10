import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { daysAgo, today, fmtScore, scoreColor } from "@/lib/format";
import { Card, Eyebrow, StatTile, ScoreBadge, StatusChip, Loading, ErrorNote, Button } from "@/components/ui";
import { useSetTopbarRight } from "@/components/shell/AppShell";
import type { PositionCard, Search } from "@/lib/types";

const RANGES = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
];

function RangePicker({ value, onChange }: { value: number; onChange: (d: number) => void }) {
  return (
    <div style={{ display: "flex", border: "1px solid var(--border-default)", borderRadius: "var(--radius-md)", overflow: "hidden" }}>
      {RANGES.map((r) => (
        <button
          key={r.days}
          onClick={() => onChange(r.days)}
          style={{
            padding: "6px 12px",
            fontSize: 12,
            border: "none",
            cursor: "pointer",
            background: value === r.days ? "var(--surface-card)" : "transparent",
            color: value === r.days ? "var(--text-primary)" : "var(--text-secondary)",
          }}
        >
          {r.label}
        </button>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const [days, setDays] = useState(30);
  const nav = useNavigate();
  useSetTopbarRight(<RangePicker value={days} onChange={setDays} />, [days]);

  const range = useMemo(() => ({ from: daysAgo(days), to: today() }), [days]);
  const summary = useQuery({
    queryKey: ["dashboard", range.from, range.to],
    queryFn: () => api.dashboardSummary(range),
  });
  const searches = useQuery({ queryKey: ["searches", "recent"], queryFn: () => api.searches({ page_size: 4 }) });

  if (summary.isLoading) return <Loading label="Loading dashboard…" />;
  if (summary.error) return <ErrorNote error={summary.error} />;
  const d = summary.data!;
  const maxFound = Math.max(1, ...d.by_source.map((s) => s.found));

  const empty = d.positions_found === 0 && (searches.data?.total ?? 0) === 0;

  return (
    <div style={{ padding: "24px 24px 40px", maxWidth: 1200 }}>
      {empty ? (
        <FreshInstall onStart={() => nav("/searches/new")} />
      ) : (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
            <StatTile label="Positions found" value={d.positions_found} />
            <StatTile label="Evaluated" value={d.positions_evaluated} />
            <StatTile label="Avg score" value={fmtScore(d.avg_score)} />
            <StatTile label="Searches run" value={d.searches_run} />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "3fr 2fr", gap: 16, marginTop: 16 }}>
            <Card style={{ padding: "20px 24px" }}>
              <Eyebrow style={{ marginBottom: 16, fontWeight: 600 }}>By source</Eyebrow>
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {d.by_source.map((s) => (
                  <div
                    key={s.source}
                    style={{ display: "grid", gridTemplateColumns: "88px 1fr 52px 64px", gap: 12, alignItems: "center" }}
                  >
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--text-secondary)" }}>
                      {s.source}
                    </span>
                    <div style={{ height: 6, borderRadius: 3, background: "rgba(138,148,166,0.14)", overflow: "hidden" }}>
                      <div
                        style={{
                          width: `${(s.found / maxFound) * 100}%`,
                          height: "100%",
                          background: "var(--gradient-accent-line)",
                        }}
                      />
                    </div>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--text-primary)", textAlign: "right" }}>
                      {s.found}
                    </span>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, textAlign: "right", color: "var(--text-secondary)" }}>
                      {fmtScore(s.avg_score)}
                    </span>
                  </div>
                ))}
                {d.by_source.length === 0 && (
                  <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>No positions in this range.</div>
                )}
              </div>
              <div
                style={{
                  display: "flex",
                  gap: 12,
                  marginTop: 16,
                  paddingTop: 12,
                  borderTop: "1px solid var(--border-subtle)",
                  fontSize: 11,
                  color: "var(--text-tertiary)",
                }}
              >
                <span>bar = positions found</span>
                <span>·</span>
                <span>right column = avg score</span>
              </div>
            </Card>

            <Card style={{ padding: "20px 24px" }}>
              <div style={{ display: "flex", alignItems: "baseline", marginBottom: 12 }}>
                <Eyebrow style={{ flex: 1, fontWeight: 600 }}>Recent searches</Eyebrow>
                <Link to="/searches" style={{ fontSize: 12 }}>
                  View all
                </Link>
              </div>
              <div style={{ display: "flex", flexDirection: "column" }}>
                {(searches.data?.items ?? []).map((s) => (
                  <RecentSearch key={s.id} s={s} onOpen={() => nav(`/searches/${s.id}`)} />
                ))}
                {(searches.data?.items ?? []).length === 0 && (
                  <div style={{ fontSize: 13, color: "var(--text-secondary)", padding: "8px 0" }}>No searches yet.</div>
                )}
              </div>
            </Card>
          </div>

          <Card style={{ padding: "20px 24px", marginTop: 16 }}>
            <div style={{ display: "flex", alignItems: "baseline", marginBottom: 6 }}>
              <Eyebrow style={{ flex: 1, fontWeight: 600 }}>Top 5 positions</Eyebrow>
              <Link to="/positions" style={{ fontSize: 12 }}>
                All positions
              </Link>
            </div>
            {d.top_positions.length === 0 ? (
              <div style={{ fontSize: 13, color: "var(--text-secondary)", padding: "12px 0" }}>
                No evaluated positions yet.
              </div>
            ) : (
              d.top_positions.map((p, i) => <TopRow key={p.id} p={p} rank={i + 1} onOpen={() => nav(`/positions/${p.id}`)} />)
            )}
          </Card>
        </>
      )}
    </div>
  );
}

function RecentSearch({ s, onOpen }: { s: Search; onOpen: () => void }) {
  return (
    <div onClick={onOpen} style={{ padding: "11px 0", borderTop: "1px solid var(--border-subtle)", cursor: "pointer" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 13.5, fontWeight: 500, color: "var(--text-primary)", flex: 1 }}>{s.name}</span>
        <StatusChip status={statusChipLabel(s.status)} />
      </div>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-tertiary)", marginTop: 4 }}>
        {s.total_found} found · {s.total_new} new · avg {fmtScore(s.avg_score)}
      </div>
    </div>
  );
}
// search statuses aren't pipeline states — reuse the chip with a neutral label.
function statusChipLabel(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function TopRow({ p, rank, onOpen }: { p: PositionCard; rank: number; onOpen: () => void }) {
  return (
    <div
      onClick={onOpen}
      style={{
        display: "grid",
        gridTemplateColumns: "28px 1fr 150px 84px 96px 150px",
        gap: 14,
        alignItems: "center",
        padding: "13px 0",
        borderTop: "1px solid var(--border-subtle)",
        cursor: "pointer",
      }}
    >
      <span style={{ fontFamily: "var(--font-display)", fontSize: 15, color: "var(--text-tertiary)" }}>{rank}</span>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text-primary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {p.role}
        </div>
        <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {p.company?.name ?? "—"}
        </div>
      </div>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--text-secondary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
        {p.salary_raw ?? "—"}
      </div>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--text-tertiary)" }}>{p.source}</span>
      <div>
        <ScoreBadge score={p.score} category={p.score_category} />
        <div style={{ fontSize: 10, letterSpacing: "0.06em", color: scoreColor(p.score_category), marginTop: 2 }}>
          {p.score_category ?? ""}
        </div>
      </div>
      <div>
        <StatusChip status={p.status} />
      </div>
    </div>
  );
}

function FreshInstall({ onStart }: { onStart: () => void }) {
  return (
    <>
      <Card style={{ padding: "48px 40px", display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center" }}>
        <div
          style={{
            position: "relative",
            width: 44,
            height: 44,
            border: "1.5px solid var(--border-strong)",
            borderRadius: 5,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: "var(--font-display)",
            fontWeight: 600,
            fontSize: 16,
            color: "var(--text-primary)",
            marginBottom: 20,
          }}
        >
          JS
          <span style={{ position: "absolute", top: -4, right: -4, width: 7, height: 7, borderRadius: "50%", background: "var(--accent-primary)" }} />
        </div>
        <div style={{ fontFamily: "var(--font-display)", fontWeight: 500, fontSize: 26, letterSpacing: "-0.02em", color: "var(--text-primary)" }}>
          Mission control is ready.
        </div>
        <div style={{ fontSize: 14, color: "var(--text-secondary)", maxWidth: 440, lineHeight: 1.6, margin: "10px 0 24px" }}>
          No data yet. Create your first search to start discovering positions, or import your CV so the agent can draft your profile.
        </div>
        <Button onClick={onStart}>Create first search</Button>
      </Card>
    </>
  );
}
