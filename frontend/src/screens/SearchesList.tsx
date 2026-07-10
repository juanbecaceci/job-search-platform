import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { fmtScore, fmtDateTime } from "@/lib/format";
import { Card, Loading, ErrorNote, Button, Badge } from "@/components/ui";
import type { Search } from "@/lib/types";

const statusBadgeColor = (status: string) =>
  ({
    running: "var(--status-positive)",
    finished: "var(--text-accent)",
    analyzed: "var(--text-accent)",
    failed: "var(--status-negative)",
    draft: "var(--text-tertiary)",
  })[status] ?? "var(--text-secondary)";

export default function SearchesList() {
  const nav = useNavigate();
  const searches = useQuery({ queryKey: ["searches", "list"], queryFn: () => api.searches({ page_size: 100 }) });

  if (searches.isLoading) return <Loading />;
  if (searches.error) return <ErrorNote error={searches.error} />;
  const rows = searches.data!.items;

  return (
    <div style={{ padding: "20px 24px 40px", maxWidth: 1100 }}>
      <div style={{ display: "flex", alignItems: "center", marginBottom: 16 }}>
        <div style={{ flex: 1 }} />
        <Button onClick={() => nav("/searches/new")}>New search</Button>
      </div>

      {rows.length === 0 ? (
        <Card style={{ padding: "48px 40px", textAlign: "center" }}>
          <div style={{ fontFamily: "var(--font-display)", fontWeight: 500, fontSize: 18, color: "var(--text-primary)" }}>
            No searches yet.
          </div>
          <div style={{ fontSize: 13.5, color: "var(--text-secondary)", marginTop: 8 }}>
            Create your first search to start discovering positions.
          </div>
        </Card>
      ) : (
        <div style={{ border: "1px solid var(--border-default)", borderRadius: "var(--radius-lg)", overflow: "hidden", background: "var(--surface-card)" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "2fr 110px 1.4fr 90px 130px",
              gap: 12,
              padding: "9px 16px",
              background: "var(--surface-card-alt)",
              borderBottom: "1px solid var(--border-default)",
            }}
          >
            {["Name", "Status", "Sources", "Avg score", "Last run"].map((h) => (
              <span key={h} style={{ fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--text-tertiary)", fontWeight: 600 }}>
                {h}
              </span>
            ))}
          </div>
          {rows.map((s: Search) => (
            <div
              key={s.id}
              onClick={() => nav(`/searches/${s.id}`)}
              style={{
                display: "grid",
                gridTemplateColumns: "2fr 110px 1.4fr 90px 130px",
                gap: 12,
                alignItems: "center",
                padding: "13px 16px",
                borderTop: "1px solid var(--border-subtle)",
                cursor: "pointer",
              }}
            >
              <span style={{ fontSize: 13.5, fontWeight: 500, color: "var(--text-primary)" }}>{s.name}</span>
              <span>
                <Badge color={statusBadgeColor(s.status)}>{s.status}</Badge>
              </span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--text-tertiary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {s.sources.join(", ") || "—"}
              </span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--text-primary)" }}>{fmtScore(s.avg_score)}</span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--text-tertiary)" }}>{fmtDateTime(s.last_run_at)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
