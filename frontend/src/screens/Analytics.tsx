import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { daysAgo, today, fmtScore } from "@/lib/format";
import { Card, Eyebrow, Loading, ErrorNote, Button } from "@/components/ui";

export default function Analytics() {
  const range = useMemo(() => ({ from: daysAgo(90), to: today() }), []);
  const sources = useQuery({ queryKey: ["analytics", "sources", range], queryFn: () => api.analyticsSources(range) });
  const funnel = useQuery({ queryKey: ["analytics", "funnel", range], queryFn: () => api.analyticsFunnel(range) });

  if (sources.isLoading || funnel.isLoading) return <Loading />;
  if (sources.error) return <ErrorNote error={sources.error} />;

  const f = funnel.data!;
  const funnelSteps = [
    { label: "Discovered", value: f.discovered },
    { label: "Applied", value: f.applied },
    { label: "Responded", value: f.responded },
    { label: "Interviews", value: f.interviews },
    { label: "Offers", value: f.offers },
    { label: "Accepted", value: f.accepted },
  ];
  const maxF = Math.max(1, f.discovered);

  return (
    <div style={{ padding: "20px 24px 40px", maxWidth: 1100 }}>
      {/* Funnel */}
      <Card style={{ marginBottom: 16 }}>
        <Eyebrow style={{ fontWeight: 600, marginBottom: 16 }}>Conversion funnel · last 90 days</Eyebrow>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {funnelSteps.map((s) => (
            <div key={s.label} style={{ display: "grid", gridTemplateColumns: "110px 1fr 48px", gap: 12, alignItems: "center" }}>
              <span style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>{s.label}</span>
              <div style={{ height: 22, borderRadius: 4, background: "rgba(138,148,166,0.1)", overflow: "hidden" }}>
                <div
                  style={{
                    width: `${(s.value / maxF) * 100}%`,
                    height: "100%",
                    background: "var(--gradient-accent-line)",
                    minWidth: s.value > 0 ? 2 : 0,
                    transition: "width var(--duration-base) var(--ease-standard)",
                  }}
                />
              </div>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--text-primary)", textAlign: "right" }}>
                {s.value}
              </span>
            </div>
          ))}
        </div>
      </Card>

      {/* Source effectiveness */}
      <Card style={{ marginBottom: 16 }}>
        <Eyebrow style={{ fontWeight: 600, marginBottom: 14 }}>Source effectiveness</Eyebrow>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 90px 80px 80px 90px 80px",
            gap: 12,
            padding: "0 0 8px",
            borderBottom: "1px solid var(--border-subtle)",
          }}
        >
          {["Source", "Discovered", "Avg score", "Applied", "Interviews", "Offers"].map((h) => (
            <span key={h} style={{ fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--text-tertiary)", fontWeight: 600 }}>
              {h}
            </span>
          ))}
        </div>
        {sources.data!.map((s) => (
          <div
            key={s.source}
            style={{ display: "grid", gridTemplateColumns: "1fr 90px 80px 80px 90px 80px", gap: 12, padding: "10px 0", borderTop: "1px solid var(--border-subtle)", alignItems: "center" }}
          >
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5, color: "var(--text-primary)" }}>{s.source}</span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5, color: "var(--text-secondary)" }}>{s.discovered}</span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5, color: "var(--text-secondary)" }}>{fmtScore(s.avg_score)}</span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5, color: "var(--text-secondary)" }}>{s.applied}</span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5, color: "var(--text-secondary)" }}>{s.interviews}</span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5, color: "var(--text-secondary)" }}>{s.offers}</span>
          </div>
        ))}
      </Card>

      <StaleList />
    </div>
  );
}

function StaleList() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const [days, setDays] = useState(14);
  const stale = useQuery({ queryKey: ["analytics", "stale", days], queryFn: () => api.analyticsStale(days) });
  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => api.changeStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["analytics", "stale"] }),
  });

  return (
    <Card>
      <div style={{ display: "flex", alignItems: "center", marginBottom: 12 }}>
        <Eyebrow style={{ fontWeight: 600, flex: 1 }}>Stale applications</Eyebrow>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--text-tertiary)" }}>
          <span>older than</span>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            style={{
              background: "var(--surface-sunken)",
              border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-md)",
              padding: "4px 8px",
              fontSize: 12,
              color: "var(--text-primary)",
            }}
          >
            {[7, 14, 30].map((d) => (
              <option key={d} value={d}>
                {d} days
              </option>
            ))}
          </select>
        </div>
      </div>
      {stale.data?.length === 0 && <div style={{ fontSize: 13, color: "var(--text-secondary)", padding: "8px 0" }}>Nothing stale — you're on top of it.</div>}
      {stale.data?.map((item) => (
        <div
          key={item.position.id}
          style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 0", borderTop: "1px solid var(--border-subtle)" }}
        >
          <div style={{ flex: 1, minWidth: 0, cursor: "pointer" }} onClick={() => nav(`/positions/${item.position.id}`)}>
            <div style={{ fontSize: 13.5, fontWeight: 500, color: "var(--text-primary)" }}>{item.position.role}</div>
            <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
              {item.position.company?.name ?? "—"} · {item.position.status} · {item.days_stale} days silent
            </div>
          </div>
          {item.suggested_action === "mark_ghosted" ? (
            <Button size="sm" variant="ghost" onClick={() => setStatus.mutate({ id: item.position.id, status: "Ghosted" })}>
              Mark ghosted
            </Button>
          ) : (
            <Button size="sm" variant="secondary" onClick={() => nav(`/positions/${item.position.id}`)}>
              Follow up
            </Button>
          )}
        </div>
      ))}
    </Card>
  );
}
