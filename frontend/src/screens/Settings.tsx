import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useJobAction } from "@/lib/useJobAction";
import { Button, Card, Eyebrow, Loading, ErrorNote, Spinner } from "@/components/ui";

export default function Settings() {
  const qc = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: () => api.settings() });
  const exportJob = useJobAction(() => qc.invalidateQueries({ queryKey: ["settings"] }));

  if (settings.isLoading) return <Loading />;
  if (settings.error) return <ErrorNote error={settings.error} />;

  const values = settings.data ?? {};
  const sheetsOn = values.sheets_export_enabled === true;
  // Everything except the settings that have their own control below.
  const rest = Object.entries(values).filter(([k]) => k !== "sheets_export_enabled");

  const toggleSheets = async () => {
    await api.updateSettings({ sheets_export_enabled: !sheetsOn });
    qc.invalidateQueries({ queryKey: ["settings"] });
  };

  return (
    <div style={{ padding: "20px 24px 40px", maxWidth: 640 }}>
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
          <Eyebrow style={{ fontWeight: 600 }}>Google Sheets export</Eyebrow>
          <div style={{ flex: 1 }} />
          <Switch on={sheetsOn} onChange={toggleSheets} label="Enable Sheets export" />
        </div>
        <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6, marginBottom: sheetsOn ? 14 : 0 }}>
          Mirrors your tracker into the configured spreadsheet. It's one-way: each tab is rewritten
          from this database, so anything you edit in Sheets is overwritten on the next export.
        </div>

        {sheetsOn && (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <Button onClick={() => exportJob.run(() => api.exportToSheets())} disabled={exportJob.busy}>
                {exportJob.busy ? "Exporting…" : "Export now"}
              </Button>
              {exportJob.busy && (
                <span style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, color: "var(--text-secondary)" }}>
                  <Spinner />
                  {exportJob.message}
                </span>
              )}
            </div>
            {exportJob.error && (
              <div style={{ fontSize: 12.5, color: "var(--status-negative)", marginTop: 10 }}>
                {exportJob.error}
              </div>
            )}
            <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 10 }}>
              Needs Google credentials in <code style={{ fontFamily: "var(--font-mono)" }}>data/credentials/</code> and
              a <code style={{ fontFamily: "var(--font-mono)" }}>SPREADSHEET_ID</code> in that folder's{" "}
              <code style={{ fontFamily: "var(--font-mono)" }}>.env</code>.
            </div>
          </>
        )}
      </Card>

      <Card style={{ marginBottom: 16 }}>
        <Eyebrow style={{ fontWeight: 600, marginBottom: 12 }}>Stored settings</Eyebrow>
        {rest.length === 0 ? (
          <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            Nothing else stored yet — defaults apply (agent adapter = Claude).
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {rest.map(([k, v]) => (
              <div key={k} style={{ display: "flex", gap: 12, padding: "8px 0", borderTop: "1px solid var(--border-subtle)" }}>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5, color: "var(--text-secondary)", flex: 1 }}>{k}</span>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5, color: "var(--text-primary)" }}>{JSON.stringify(v)}</span>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <Eyebrow style={{ fontWeight: 600, marginBottom: 12 }}>Agent CLI</Eyebrow>
        <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6 }}>
          Reasoning runs through your own Claude Code CLI (no API key). Set{" "}
          <code style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>AGENT_CLI_PATH</code> if{" "}
          <code style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>claude</code> isn't on PATH when
          the server runs.
        </div>
      </Card>
    </div>
  );
}

function Switch({ on, onChange, label }: { on: boolean; onChange: () => void; label: string }) {
  return (
    <button
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={onChange}
      style={{
        width: 42,
        height: 24,
        borderRadius: 999,
        borderWidth: 1,
        borderStyle: "solid",
        borderColor: on ? "var(--border-accent)" : "var(--border-default)",
        background: on ? "var(--interactive-default)" : "var(--surface-sunken)",
        cursor: "pointer",
        padding: 2,
        display: "flex",
        justifyContent: on ? "flex-end" : "flex-start",
        alignItems: "center",
        transition: "background var(--duration-fast) var(--ease-standard)",
      }}
    >
      <span
        style={{
          width: 18,
          height: 18,
          borderRadius: "50%",
          background: on ? "var(--text-on-accent)" : "var(--text-tertiary)",
          display: "block",
        }}
      />
    </button>
  );
}
