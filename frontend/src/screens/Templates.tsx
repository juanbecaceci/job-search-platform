import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, Loading, ErrorNote, Badge } from "@/components/ui";
import { fmtDateTime } from "@/lib/format";

export default function Templates() {
  const templates = useQuery({ queryKey: ["templates"], queryFn: () => api.templates() });
  if (templates.isLoading) return <Loading />;
  if (templates.error) return <ErrorNote error={templates.error} />;

  return (
    <div style={{ padding: "20px 24px 40px", display: "flex", flexWrap: "wrap", gap: 20, maxWidth: 1180, alignItems: "flex-start" }}>
      {templates.data!.map((t) => (
        <Card key={t.id} style={{ flex: "1 1 520px", minWidth: 400 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 10 }}>
            <span style={{ fontFamily: "var(--font-display)", fontSize: 16, fontWeight: 500, color: "var(--text-primary)", flex: 1 }}>
              {t.name}
            </span>
            {t.active_version && <Badge color="var(--text-accent)">v{t.active_version.version} active</Badge>}
          </div>
          <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 10, fontFamily: "var(--font-mono)" }}>
            {t.kind} · updated {fmtDateTime(t.active_version?.created_at)}
          </div>
          <pre
            style={{
              margin: 0,
              maxHeight: 320,
              overflow: "auto",
              background: "var(--surface-sunken)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: 14,
              fontSize: 12,
              lineHeight: 1.6,
              color: "var(--text-secondary)",
              fontFamily: "var(--font-mono)",
              whiteSpace: "pre-wrap",
            }}
          >
            {t.active_version?.content_md || "—"}
          </pre>
        </Card>
      ))}
    </div>
  );
}
