import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, Eyebrow, Loading, ErrorNote, Badge } from "@/components/ui";
import { scoreColor } from "@/lib/format";
import { fmtDateTime } from "@/lib/format";

export default function Scoring() {
  const cfg = useQuery({ queryKey: ["scoring", "config"], queryFn: () => api.scoringConfig() });
  const versions = useQuery({ queryKey: ["scoring", "versions"], queryFn: () => api.scoringVersions() });

  if (cfg.isLoading) return <Loading />;
  if (cfg.error) return <ErrorNote error={cfg.error} />;
  const c = cfg.data!;
  const weightSum = c.criteria.reduce((n, cr) => n + cr.weight, 0);
  const catColor = (id: string) => scoreColor(id);

  return (
    <div style={{ padding: "20px 24px 40px", maxWidth: 900 }}>
      <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 20, lineHeight: 1.6 }}>
        Active scoring config <strong style={{ color: "var(--text-primary)" }}>v{c.version}</strong>. To change weights,
        gate or categories, ask the agent in chat — it proposes the edit and you approve it in the changes tray.
      </div>

      {/* Salary gate */}
      <Card style={{ marginBottom: 16 }}>
        <Eyebrow style={{ fontWeight: 600, marginBottom: 12 }}>Salary gate (eliminatory)</Eyebrow>
        <div style={{ display: "flex", gap: 24, flexWrap: "wrap", fontSize: 13 }}>
          {Object.entries(c.salary_gate).map(([k, v]) => (
            <div key={k}>
              <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>{k}</div>
              <div style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)", marginTop: 2 }}>{String(v)}</div>
            </div>
          ))}
        </div>
      </Card>

      {/* Criteria weights */}
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "baseline", marginBottom: 16 }}>
          <Eyebrow style={{ fontWeight: 600, flex: 1 }}>Criteria weights</Eyebrow>
          <Badge color={Math.abs(weightSum - 1) < 1e-6 ? "var(--status-positive)" : "var(--status-negative)"}>
            Σ = {weightSum.toFixed(2)}
          </Badge>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {c.criteria.map((cr) => (
            <div key={cr.id}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 6 }}>
                <span style={{ fontSize: 13.5, fontWeight: 500, color: "var(--text-primary)", flex: 1 }}>{cr.name}</span>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--text-accent)" }}>
                  {(cr.weight * 100).toFixed(0)}%
                </span>
              </div>
              <div style={{ height: 6, borderRadius: 3, background: "rgba(138,148,166,0.14)", overflow: "hidden" }}>
                <div style={{ width: `${cr.weight * 100}%`, height: "100%", background: "var(--gradient-accent-line)" }} />
              </div>
              {cr.description && (
                <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 6, lineHeight: 1.5 }}>{cr.description}</div>
              )}
            </div>
          ))}
        </div>
      </Card>

      {/* Categories */}
      <Card style={{ marginBottom: 16 }}>
        <Eyebrow style={{ fontWeight: 600, marginBottom: 12 }}>Score categories</Eyebrow>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {c.categories.map((cat) => (
            <div key={cat.id} style={{ display: "grid", gridTemplateColumns: "120px 90px 1fr", gap: 12, alignItems: "center" }}>
              <span style={{ fontSize: 12.5, fontWeight: 600, color: catColor(cat.id) }}>{cat.id}</span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--text-secondary)" }}>
                {cat.min_score}–{cat.max_score}
              </span>
              <span style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>{cat.recommended_action}</span>
            </div>
          ))}
        </div>
      </Card>

      {/* Version history */}
      <Card>
        <Eyebrow style={{ fontWeight: 600, marginBottom: 12 }}>Version history</Eyebrow>
        {versions.data?.map((v) => (
          <div
            key={v.version}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "8px 0",
              borderTop: "1px solid var(--border-subtle)",
            }}
          >
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--text-primary)" }}>v{v.version}</span>
            {v.is_active && <Badge color="var(--status-positive)">active</Badge>}
            <span style={{ fontSize: 12, color: "var(--text-tertiary)", flex: 1 }}>by {v.created_by}</span>
            <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>{fmtDateTime(v.created_at)}</span>
          </div>
        ))}
      </Card>
    </div>
  );
}
