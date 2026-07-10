import { useEffect, useState } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { subscribeJob } from "@/lib/sse";
import { useJobAction } from "@/lib/useJobAction";
import { fmtScore, fmtDateTime } from "@/lib/format";
import { Card, Eyebrow, StatTile, Loading, ErrorNote, ScoreBadge, StatusChip, Badge, Button } from "@/components/ui";
import type { PositionCard } from "@/lib/types";

type SourceStat = { fetched?: number; new?: number; duplicates?: number; errors?: number; skipped?: number };

export default function SearchDetail() {
  const { id } = useParams();
  const searchId = Number(id);
  const [params] = useSearchParams();
  const nav = useNavigate();
  const qc = useQueryClient();

  const jobId = params.get("job");
  const [live, setLive] = useState<{ progress: number; message: string; stats: Record<string, SourceStat> } | null>(
    jobId ? { progress: 0, message: "starting…", stats: {} } : null,
  );

  const detail = useQuery({ queryKey: ["search", searchId], queryFn: () => api.search(searchId) });
  const evalJob = useJobAction(() => {
    qc.invalidateQueries({ queryKey: ["search", searchId] });
    qc.invalidateQueries({ queryKey: ["positions"] });
  });

  // Subscribe to the live run stream when arriving from the wizard.
  useEffect(() => {
    if (!jobId) return;
    const unsub = subscribeJob(jobId, {
      onProgress: (d) => setLive({ progress: d.progress, message: d.message, stats: (d.stats as Record<string, SourceStat>) || {} }),
      onDone: () => {
        setLive(null);
        qc.invalidateQueries({ queryKey: ["search", searchId] });
        qc.invalidateQueries({ queryKey: ["positions"] });
      },
      onFailed: (d) => setLive((l) => (l ? { ...l, message: `failed: ${d.error}` } : l)),
    });
    return unsub;
  }, [jobId, searchId, qc]);

  if (detail.isLoading) return <Loading />;
  if (detail.error) return <ErrorNote error={detail.error} />;
  const s = detail.data!;
  const latestRun = s.runs[s.runs.length - 1];
  const sourceStats: Record<string, SourceStat> = live?.stats ?? (latestRun?.stats as Record<string, SourceStat>) ?? {};
  const allPositions = s.positions_by_source.flatMap((b) => b.positions);

  return (
    <div style={{ padding: "20px 24px 40px", maxWidth: 980 }}>
      <button
        onClick={() => nav("/searches")}
        style={{ display: "flex", alignItems: "center", gap: 6, background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)", fontSize: 12.5, padding: 0, marginBottom: 14 }}
      >
        <svg width="12" height="12" viewBox="0 0 10 10">
          <path d="M6.5 2.5 3.5 5 6.5 7.5" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Back to searches
      </button>

      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6 }}>
        <div style={{ fontFamily: "var(--font-display)", fontWeight: 500, fontSize: 22, letterSpacing: "-0.01em", color: "var(--text-primary)" }}>
          {s.name}
        </div>
        <Badge color={live ? "var(--status-positive)" : "var(--text-accent)"}>{live ? "running" : s.status}</Badge>
      </div>
      <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginBottom: 20 }}>
        Last run {fmtDateTime(s.last_run_at)} · posted within {s.posted_within_days ?? "—"} days
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 20 }}>
        <StatTile label="Found" value={s.total_found} />
        <StatTile label="New" value={s.total_new} />
        <StatTile label="Evaluated" value={s.total_evaluated} />
        <StatTile label="Avg score" value={fmtScore(s.avg_score)} />
      </div>

      {live && (
        <Card accent style={{ marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--status-positive)", animation: "jsPulse 1.4s ease-in-out infinite" }} />
            <Eyebrow style={{ fontWeight: 600 }}>Live run in progress · {live.message}</Eyebrow>
          </div>
          <SourceBars stats={sourceStats} live />
        </Card>
      )}

      <Card style={{ marginBottom: 20 }}>
        <Eyebrow style={{ fontWeight: 600, marginBottom: 12 }}>Per-source results</Eyebrow>
        <div style={{ display: "grid", gridTemplateColumns: "100px 1fr 1fr 1fr 1fr", gap: 10, padding: "6px 0", borderBottom: "1px solid var(--border-subtle)" }}>
          {["Source", "Fetched", "New", "Duplicates", "Errors"].map((h) => (
            <span key={h} style={{ fontSize: 10.5, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-tertiary)", fontWeight: 600 }}>
              {h}
            </span>
          ))}
        </div>
        {Object.keys(sourceStats).length === 0 && (
          <div style={{ fontSize: 13, color: "var(--text-tertiary)", padding: "10px 0" }}>No run stats yet.</div>
        )}
        {Object.entries(sourceStats).map(([name, st]) => (
          <div
            key={name}
            style={{ display: "grid", gridTemplateColumns: "100px 1fr 1fr 1fr 1fr", gap: 10, padding: "9px 0", borderBottom: "1px solid var(--border-subtle)", fontFamily: "var(--font-mono)", fontSize: 12.5, color: "var(--text-primary)" }}
          >
            <span style={{ color: "var(--text-secondary)" }}>{name}</span>
            <span>{st.skipped ? "—" : (st.fetched ?? 0)}</span>
            <span>{st.new ?? 0}</span>
            <span>{st.duplicates ?? 0}</span>
            <span style={{ color: st.errors ? "var(--status-negative)" : "var(--text-primary)" }}>{st.skipped ? "skip" : (st.errors ?? 0)}</span>
          </div>
        ))}
      </Card>

      <div style={{ marginBottom: 20 }}>
        <Eyebrow style={{ fontWeight: 600, marginBottom: 8 }}>Keywords used</Eyebrow>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {s.keywords.map((kw) => (
            <span key={kw} style={{ fontFamily: "var(--font-mono)", fontSize: 11, background: "rgba(138,148,166,0.1)", border: "1px solid var(--border-subtle)", borderRadius: 5, padding: "3px 8px", color: "var(--text-secondary)" }}>
              {kw}
            </span>
          ))}
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
        <Eyebrow style={{ fontWeight: 600, marginBottom: 0 }}>Found positions ({allPositions.length})</Eyebrow>
        {allPositions.length > 0 && (
          <Button
            variant="secondary"
            size="sm"
            disabled={evalJob.busy}
            onClick={() => evalJob.run(() => api.evaluatePositions(allPositions.map((p) => p.id)))}
          >
            {evalJob.busy ? evalJob.message ?? "Evaluating…" : "Evaluate all found"}
          </Button>
        )}
      </div>
      {evalJob.error && (
        <div style={{ fontSize: 12, color: "var(--status-negative)", marginBottom: 10 }}>{evalJob.error}</div>
      )}
      {allPositions.length === 0 ? (
        <div style={{ fontSize: 13, color: "var(--text-tertiary)" }}>No positions attributed to this search yet.</div>
      ) : (
        <div style={{ border: "1px solid var(--border-default)", borderRadius: "var(--radius-lg)", overflow: "hidden", background: "var(--surface-card)" }}>
          {allPositions.map((p: PositionCard) => (
            <div
              key={p.id}
              onClick={() => nav(`/positions/${p.id}`)}
              style={{ display: "grid", gridTemplateColumns: "1.6fr 90px 100px 170px", gap: 12, alignItems: "center", padding: "11px 16px", borderTop: "1px solid var(--border-subtle)", cursor: "pointer" }}
            >
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{p.role}</div>
                <div style={{ fontSize: 11.5, color: "var(--text-secondary)", marginTop: 2 }}>{p.company?.name ?? "—"}</div>
              </div>
              <ScoreBadge score={p.score} category={p.score_category} />
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--text-tertiary)" }}>{p.source}</span>
              <StatusChip status={p.status} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SourceBars({ stats, live }: { stats: Record<string, SourceStat>; live?: boolean }) {
  const entries = Object.entries(stats);
  const max = Math.max(1, ...entries.map(([, s]) => s.fetched ?? 0));
  if (entries.length === 0)
    return <div style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>Waiting for the first source…</div>;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {entries.map(([name, s]) => (
        <div key={name}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 6 }}>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5, color: "var(--text-primary)", fontWeight: 600, width: 80 }}>{name}</span>
            <span style={{ fontSize: 11.5, color: "var(--text-secondary)", flex: 1 }}>
              {s.skipped ? "skipped" : `${s.fetched ?? 0} fetched · ${s.new ?? 0} new · ${s.duplicates ?? 0} dup`}
            </span>
          </div>
          <div style={{ height: 6, borderRadius: 3, background: "rgba(138,148,166,0.14)", overflow: "hidden" }}>
            <div
              style={{
                width: `${((s.fetched ?? 0) / max) * 100}%`,
                height: "100%",
                background: "var(--gradient-accent-line)",
                transition: live ? "width var(--duration-base) var(--ease-standard)" : undefined,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
