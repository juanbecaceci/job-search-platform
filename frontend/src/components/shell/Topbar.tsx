import { useState, type CSSProperties, type ReactNode } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import type { Job, PendingChange } from "@/lib/types";
import { Button } from "@/components/ui";

const iconBtn: CSSProperties = {
  width: 34,
  height: 34,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  background: "transparent",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-md)",
  color: "var(--text-secondary)",
  cursor: "pointer",
  position: "relative",
};

function Popover({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        position: "absolute",
        right: 0,
        top: "calc(100% + 8px)",
        width: 380,
        maxHeight: "70vh",
        overflowY: "auto",
        background: "var(--surface-raised)",
        border: "1px solid var(--border-default)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-lg)",
        zIndex: 60,
        padding: 6,
        animation: "jsFadeIn 0.16s ease-out",
      }}
    >
      {children}
    </div>
  );
}

const popHeading: CSSProperties = {
  fontSize: 10,
  letterSpacing: "0.14em",
  textTransform: "uppercase",
  color: "var(--text-tertiary)",
  padding: "8px 10px 6px",
};

function JobsIndicator() {
  const [open, setOpen] = useState(false);
  const { data } = useQuery({
    queryKey: ["jobs", "recent"],
    queryFn: () => api.jobs({ page_size: 8 }),
    refetchInterval: 2500,
  });
  const jobs = data?.items ?? [];
  const running = jobs.filter((j) => j.status === "running" || j.status === "queued");

  return (
    <div style={{ position: "relative" }}>
      <button style={iconBtn} title="Background jobs" onClick={() => setOpen((o) => !o)}>
        <svg width="16" height="16" viewBox="0 0 16 16">
          <path
            d="M1.5 8h3l2-5 3 10 2-5h3"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        </svg>
        {running.length > 0 && (
          <span
            style={{
              position: "absolute",
              top: 5,
              right: 5,
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: "var(--status-positive)",
              animation: "jsPulse 1.6s ease-in-out infinite",
            }}
          />
        )}
      </button>
      {open && (
        <>
          <div onClick={() => setOpen(false)} style={{ position: "fixed", inset: 0, zIndex: 50 }} />
          <Popover>
            <div style={popHeading}>Background jobs</div>
            {jobs.length === 0 && (
              <div style={{ padding: "8px 10px 12px", fontSize: 13, color: "var(--text-secondary)" }}>
                No jobs yet. Searches, evaluations and exports show up here.
              </div>
            )}
            {jobs.map((job) => (
              <JobRow key={job.id} job={job} />
            ))}
          </Popover>
        </>
      )}
    </div>
  );
}

function JobRow({ job }: { job: Job }) {
  const pct = Math.round((job.progress || 0) * 100);
  const statusColor =
    job.status === "succeeded"
      ? "var(--status-positive)"
      : job.status === "failed"
        ? "var(--status-negative)"
        : "var(--text-secondary)";
  return (
    <div style={{ padding: "8px 10px 12px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)", flex: 1 }}>
          {job.type}
        </span>
        <span style={{ fontSize: 11, color: statusColor }}>{job.status}</span>
      </div>
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color: "var(--text-tertiary)",
          margin: "4px 0 6px",
        }}
      >
        {job.progress_message || "—"}
      </div>
      <div style={{ height: 4, borderRadius: 2, background: "rgba(138,148,166,0.18)", overflow: "hidden" }}>
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background: "var(--accent-primary)",
            transition: "width var(--duration-base) var(--ease-standard)",
          }}
        />
      </div>
    </div>
  );
}

function diffRows(diff: unknown): { field: string; oldStr: string; newStr: string }[] {
  if (Array.isArray(diff)) {
    return diff
      .filter((d) => d && typeof d === "object" && "field" in d)
      .map((d) => {
        const o = d as { field: string; old?: unknown; new?: unknown };
        return { field: o.field, oldStr: String(o.old ?? "—"), newStr: String(o.new ?? "—") };
      });
  }
  return [];
}

function ChangeCard({ change }: { change: PendingChange }) {
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["changes"] });
    qc.invalidateQueries({ queryKey: ["scoring"] });
    qc.invalidateQueries({ queryKey: ["positions"] });
  };
  const approve = useMutation({ mutationFn: () => api.approveChange(change.id), onSuccess: invalidate });
  const reject = useMutation({
    mutationFn: () => api.rejectChange(change.id, reason || undefined),
    onSuccess: invalidate,
  });
  const rows = diffRows(change.diff);
  const pending = change.status === "pending";

  return (
    <div
      style={{
        padding: 12,
        margin: "4px 2px",
        borderRadius: "var(--radius-md)",
        border: pending ? "1px solid var(--border-accent)" : "1px solid var(--border-subtle)",
        boxShadow: pending ? "0 0 0 1px rgba(92,138,147,0.18)" : undefined,
        background: "var(--surface-card)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span
          style={{
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            color: pending ? "var(--accent-primary)" : "var(--text-tertiary)",
          }}
        >
          {pending ? "Proposed" : change.status}
        </span>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-tertiary)" }}>
          {change.module} · #{change.id}
        </span>
      </div>
      <div style={{ fontSize: 13, color: "var(--text-primary)", margin: "8px 0 2px", lineHeight: 1.45 }}>
        {change.summary || `${change.change_type} ${change.target_table ?? ""}`}
      </div>

      {rows.length > 0 && (
        <button
          onClick={() => setExpanded((e) => !e)}
          style={{
            background: "none",
            border: "none",
            padding: "4px 0",
            cursor: "pointer",
            fontSize: 12,
            color: "var(--text-secondary)",
          }}
        >
          {expanded ? "Hide" : "Show"} {rows.length} field change{rows.length > 1 ? "s" : ""}
        </button>
      )}
      {expanded && (
        <div
          style={{
            borderTop: "1px solid var(--border-subtle)",
            marginTop: 4,
            paddingTop: 8,
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          {rows.map((d, i) => (
            <div key={i} style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, lineHeight: 1.5 }}>
              <div style={{ color: "var(--text-tertiary)" }}>{d.field}</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
                <span style={{ color: "var(--status-negative)", textDecoration: "line-through", opacity: 0.85 }}>
                  {d.oldStr}
                </span>
                <span style={{ color: "var(--text-tertiary)" }}>→</span>
                <span style={{ color: "var(--status-positive)", fontWeight: 600 }}>{d.newStr}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {pending && !rejecting && (
        <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
          <Button size="sm" onClick={() => approve.mutate()} disabled={approve.isPending}>
            {approve.isPending ? "Applying…" : "Approve"}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setRejecting(true)}>
            Reject
          </Button>
        </div>
      )}
      {pending && rejecting && (
        <div style={{ marginTop: 10, borderTop: "1px solid var(--border-subtle)", paddingTop: 10 }}>
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Reason (optional)"
            style={{
              width: "100%",
              boxSizing: "border-box",
              background: "var(--surface-card-alt)",
              border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-md)",
              padding: "7px 10px",
              fontSize: 12.5,
              color: "var(--text-primary)",
              fontFamily: "var(--font-body)",
              outline: "none",
              marginBottom: 10,
            }}
          />
          <div style={{ display: "flex", gap: 8 }}>
            <Button size="sm" variant="danger" onClick={() => reject.mutate()} disabled={reject.isPending}>
              Confirm reject
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setRejecting(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}
      {approve.isError && (
        <div style={{ marginTop: 8, fontSize: 12, color: "var(--status-negative)" }}>
          {(approve.error as Error).message}
        </div>
      )}
    </div>
  );
}

function ChangesTray() {
  const [open, setOpen] = useState(false);
  const { data } = useQuery({
    queryKey: ["changes", "pending"],
    queryFn: () => api.changes("pending"),
    refetchInterval: 4000,
  });
  const changes = data ?? [];
  return (
    <div style={{ position: "relative" }}>
      <button style={iconBtn} title="Pending changes" onClick={() => setOpen((o) => !o)}>
        <svg width="16" height="16" viewBox="0 0 16 16">
          <path
            d="M3.5 3.5h9L14 9.5v3.5a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V9.5Z"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
          <path d="M2 9.5H5L6.5 12h3L11 9.5H14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
        </svg>
        {changes.length > 0 && (
          <span
            style={{
              position: "absolute",
              top: -5,
              right: -5,
              minWidth: 16,
              height: 16,
              padding: "0 4px",
              borderRadius: 8,
              background: "var(--accent-primary)",
              color: "var(--text-on-accent)",
              fontSize: 10,
              fontWeight: 600,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {changes.length}
          </span>
        )}
      </button>
      {open && (
        <>
          <div onClick={() => setOpen(false)} style={{ position: "fixed", inset: 0, zIndex: 50 }} />
          <Popover>
            <div style={popHeading}>Pending changes</div>
            {changes.length === 0 && (
              <div style={{ padding: "8px 10px 12px", fontSize: 13, color: "var(--text-secondary)" }}>
                Nothing waiting for review. When the agent proposes a change, it lands here for your approval.
              </div>
            )}
            {changes.map((c) => (
              <ChangeCard key={c.id} change={c} />
            ))}
          </Popover>
        </>
      )}
    </div>
  );
}

export default function Topbar({
  title,
  right,
  onToggleChat,
}: {
  title: string;
  right?: ReactNode;
  onToggleChat: () => void;
}) {
  const { theme, toggle } = useTheme();
  return (
    <header
      style={{
        height: 56,
        flex: "none",
        display: "flex",
        alignItems: "center",
        gap: 14,
        padding: "0 20px",
        borderBottom: "1px solid var(--border-subtle)",
      }}
    >
      <h1
        style={{
          fontFamily: "var(--font-display)",
          fontWeight: 500,
          fontSize: 18,
          letterSpacing: "-0.01em",
          margin: 0,
          color: "var(--text-primary)",
        }}
      >
        {title}
      </h1>
      {right}
      <div style={{ flex: 1 }} />

      <button style={iconBtn} title="Toggle theme" onClick={toggle}>
        {theme === "light" ? (
          <svg width="16" height="16" viewBox="0 0 16 16">
            <circle cx="8" cy="8" r="3.4" fill="none" stroke="currentColor" strokeWidth="1.4" />
            <path
              d="M8 1.3v1.7M8 13v1.7M2.6 8H1M15 8h-1.6M3.8 3.8l1.2 1.2M11 11l1.2 1.2M12.2 3.8 11 5M5 11l-1.2 1.2"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
            />
          </svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 16 16">
            <path
              d="M13.8 9.5A6 6 0 0 1 6.5 2.2a6 6 0 1 0 7.3 7.3Z"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </button>

      <JobsIndicator />
      <ChangesTray />

      <button style={iconBtn} title="Agent chat" onClick={onToggleChat}>
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <rect x="3" y="3.4" width="10" height="7.6" rx="2.4" stroke="currentColor" strokeWidth="1.2" />
          <circle cx="6.1" cy="7.1" r="1" fill="currentColor" />
          <circle cx="9.9" cy="7.1" r="1" fill="currentColor" />
          <path
            d="M4.2 14.5v-1.3a2.8 2.8 0 0 1 2.8-2.8h2a2.8 2.8 0 0 1 2.8 2.8v1.3"
            stroke="currentColor"
            strokeWidth="1.2"
            strokeLinecap="round"
          />
        </svg>
      </button>
    </header>
  );
}
