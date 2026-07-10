import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, Eyebrow, Loading, ErrorNote } from "@/components/ui";

export default function Memories() {
  const memories = useQuery({ queryKey: ["memories"], queryFn: () => api.memories() });
  if (memories.isLoading) return <Loading />;
  if (memories.error) return <ErrorNote error={memories.error} />;

  return (
    <div style={{ padding: "20px 24px 40px", maxWidth: 1000 }}>
      <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 16, lineHeight: 1.6 }}>
        Lessons the agent carries per module. It updates these as it learns from your approvals and rejections.
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 16 }}>
        {memories.data!.map((m) => (
          <Card key={m.module} style={{ flex: "1 1 440px", minWidth: 320 }}>
            <Eyebrow style={{ fontWeight: 600, marginBottom: 10 }}>{m.module}</Eyebrow>
            <div style={{ fontSize: 13, color: "var(--text-secondary)", whiteSpace: "pre-wrap", lineHeight: 1.6, minHeight: 40 }}>
              {m.content_md?.trim() || <span style={{ color: "var(--text-tertiary)" }}>No lessons recorded yet.</span>}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
