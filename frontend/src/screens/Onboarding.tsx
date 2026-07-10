// First-run wizard (§8 /onboarding): welcome → drop CV PDF → review the
// agent's proposed profile changes → done. The review step is the HITL gate:
// the import job never writes the profile, it only proposes (DECISIONS #6/#14),
// so nothing lands until the user approves here.

import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { subscribeJob } from "@/lib/sse";
import type { PendingChange } from "@/lib/types";
import { Button, Card, Spinner, inputStyle, textareaStyle } from "@/components/ui";
import { markOnboardingSkipped } from "@/lib/onboarding";

type Phase = "welcome" | "upload" | "importing" | "review" | "done";

interface DiffEntry {
  field: string;
  old: unknown;
  new: unknown;
}

const asDiff = (diff: unknown): DiffEntry[] => (Array.isArray(diff) ? (diff as DiffEntry[]) : []);

export default function Onboarding() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["onboarding"], queryFn: () => api.onboardingStatus() });

  const [phase, setPhase] = useState<Phase>("welcome");
  const [progress, setProgress] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [changeIds, setChangeIds] = useState<number[]>([]);
  const [changes, setChanges] = useState<PendingChange[]>([]);
  const [resolved, setResolved] = useState<Record<number, "applied" | "rejected">>({});
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // Someone who already has a profile shouldn't be walked through setup again.
  useEffect(() => {
    if (status.data?.completed && phase === "welcome") setPhase("done");
  }, [status.data?.completed, phase]);

  async function upload(file: File) {
    setError("");
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Please choose a PDF file.");
      return;
    }
    setPhase("importing");
    setProgress("uploading…");
    try {
      const { job_id } = await api.importCv(file);
      subscribeJob(job_id, {
        onProgress: (d) => setProgress(d.message || "working…"),
        onDone: async (d) => {
          const ids = ((d.result as { pending_change_ids?: number[] })?.pending_change_ids) ?? [];
          setChangeIds(ids);
          const pending = await api.changes("pending");
          setChanges(pending.filter((c) => ids.includes(c.id)));
          setPhase("review");
        },
        onFailed: (d) => {
          setError(d.error || "The import job failed.");
          setPhase("upload");
        },
      });
    } catch (e) {
      setError((e as Error).message);
      setPhase("upload");
    }
  }

  async function resolve(id: number, action: "applied" | "rejected") {
    try {
      if (action === "applied") await api.approveChange(id);
      else await api.rejectChange(id);
      setResolved((r) => ({ ...r, [id]: action }));
      qc.invalidateQueries({ queryKey: ["onboarding"] });
      qc.invalidateQueries({ queryKey: ["profile"] });
      qc.invalidateQueries({ queryKey: ["changes"] });
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function approveAll() {
    for (const c of changes) {
      if (!resolved[c.id]) await resolve(c.id, "applied");
    }
  }

  const allResolved = changes.length > 0 && changes.every((c) => resolved[c.id]);
  const appliedCount = useMemo(
    () => Object.values(resolved).filter((v) => v === "applied").length,
    [resolved],
  );

  function finish() {
    qc.invalidateQueries({ queryKey: ["onboarding"] });
    nav("/");
  }

  function skip() {
    // Backend `completed` is derived purely from profile data, so "skip" is a
    // local escape hatch only — it suppresses the guard on this browser and
    // stops mattering the moment a real profile exists.
    markOnboardingSkipped();
    nav("/");
  }

  const steps: { key: Phase; label: string }[] = [
    { key: "welcome", label: "Welcome" },
    { key: "upload", label: "Import CV" },
    { key: "review", label: "Review" },
    { key: "done", label: "Done" },
  ];
  const stepIndex = phase === "importing" ? 1 : steps.findIndex((s) => s.key === phase);

  return (
    <div style={{ padding: "24px 24px 40px", maxWidth: 720 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 22 }}>
        {steps.map((s, i) => (
          <div key={s.key} style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: i <= stepIndex ? "var(--accent-primary)" : "rgba(138,148,166,0.3)",
              }}
            />
            <span
              style={{
                fontSize: 12,
                color: i === stepIndex ? "var(--text-primary)" : "var(--text-tertiary)",
                marginRight: i < steps.length - 1 ? 6 : 0,
              }}
            >
              {s.label}
            </span>
          </div>
        ))}
      </div>

      {error && (
        <Card style={{ marginBottom: 14, borderColor: "var(--status-negative)", padding: 14 }}>
          <div style={{ fontSize: 12.5, color: "var(--status-negative)" }}>{error}</div>
        </Card>
      )}

      <Card style={{ padding: 26 }}>
        {phase === "welcome" && (
          <>
            <StepTitle
              title="Set up your profile"
              hint="Your profile is what the agent uses to draft CVs and cover letters. Import a CV once and it fills itself in."
            />
            <ol style={{ margin: "0 0 22px", paddingLeft: 18, fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.9 }}>
              <li>Drop in a CV PDF.</li>
              <li>The agent reads it and proposes profile basics + sections.</li>
              <li>You approve what's right — nothing is saved until you do.</li>
            </ol>
            <div style={{ display: "flex", gap: 10 }}>
              <Button onClick={() => setPhase("upload")}>Get started</Button>
              <Button variant="ghost" onClick={skip}>
                Skip for now
              </Button>
            </div>
          </>
        )}

        {phase === "upload" && (
          <>
            <StepTitle title="Import your CV" hint="A text-based PDF (not a scan). It's stored locally under data/ and never leaves your machine." />
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                const f = e.dataTransfer.files?.[0];
                if (f) upload(f);
              }}
              onClick={() => fileRef.current?.click()}
              style={{
                border: `1.5px dashed ${dragging ? "var(--border-accent)" : "var(--border-default)"}`,
                borderRadius: "var(--radius-lg)",
                background: dragging
                  ? "color-mix(in srgb, var(--accent-primary) 8%, transparent)"
                  : "var(--surface-sunken)",
                padding: "38px 20px",
                textAlign: "center",
                cursor: "pointer",
                marginBottom: 18,
              }}
            >
              <div style={{ fontSize: 13.5, color: "var(--text-primary)", marginBottom: 4 }}>
                Drop your CV here, or click to browse
              </div>
              <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>PDF only</div>
              <input
                ref={fileRef}
                type="file"
                accept="application/pdf,.pdf"
                style={{ display: "none" }}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) upload(f);
                }}
              />
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              <Button variant="ghost" onClick={() => setPhase("welcome")}>
                Back
              </Button>
              <div style={{ flex: 1 }} />
              <Button variant="ghost" onClick={skip}>
                Skip for now
              </Button>
            </div>
          </>
        )}

        {phase === "importing" && (
          <>
            <StepTitle title="Reading your CV" hint="The agent is extracting your profile. This usually takes under a minute." />
            <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--text-secondary)", fontSize: 13 }}>
              <Spinner />
              <span>{progress}</span>
            </div>
          </>
        )}

        {phase === "review" && (
          <>
            <StepTitle
              title="Review what the agent found"
              hint="Approve each piece to save it to your profile. Hit Edit to correct the text first, or Reject to drop it — nothing is saved until you approve."
            />
            {changes.length === 0 && (
              <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                Nothing new to propose — your profile already covers what this CV contains.
              </div>
            )}
            {changes.map((c) => (
              <ProposalCard
                key={c.id}
                change={c}
                state={resolved[c.id]}
                onResolve={(action) => resolve(c.id, action)}
                onEdited={(updated) =>
                  setChanges((list) => list.map((x) => (x.id === updated.id ? updated : x)))
                }
                onError={(e) => setError(e instanceof Error ? e.message : String(e))}
              />
            ))}
            <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
              {!allResolved && changes.length > 0 && (
                <Button onClick={approveAll}>Approve all</Button>
              )}
              <div style={{ flex: 1 }} />
              <Button variant={allResolved || changes.length === 0 ? "primary" : "ghost"} onClick={() => setPhase("done")}>
                Continue
              </Button>
            </div>
          </>
        )}

        {phase === "done" && (
          <>
            <StepTitle
              title={status.data?.completed ? "Your profile is ready" : "Profile still incomplete"}
              hint={
                status.data?.completed
                  ? "The agent can now draft CVs and cover letters tailored to each position."
                  : "You can finish anytime — import a CV here, or build sections by chatting with the agent on the Profile screen."
              }
            />
            <div style={{ display: "grid", gap: 8, marginBottom: 20 }}>
              {(status.data?.steps ?? []).map((s) => (
                <div key={s.id} style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 13 }}>
                  <span style={{ color: s.done ? "var(--status-positive)" : "var(--text-tertiary)" }}>
                    {s.done ? "✓" : "○"}
                  </span>
                  <span style={{ color: s.done ? "var(--text-primary)" : "var(--text-secondary)" }}>{s.label}</span>
                </div>
              ))}
            </div>
            {appliedCount > 0 && (
              <div style={{ fontSize: 12.5, color: "var(--text-tertiary)", marginBottom: 18 }}>
                Saved {appliedCount} {appliedCount === 1 ? "change" : "changes"} from{" "}
                {changeIds.length} proposed.
              </div>
            )}
            <div style={{ display: "flex", gap: 10 }}>
              <Button onClick={finish}>Go to dashboard</Button>
              {!status.data?.completed && (
                <Button variant="secondary" onClick={() => setPhase("upload")}>
                  Import another CV
                </Button>
              )}
              {!status.data?.completed && (
                <Button variant="ghost" onClick={skip}>
                  Skip for now
                </Button>
              )}
            </div>
          </>
        )}
      </Card>
    </div>
  );
}

/** One proposed change: view its diff, correct it in place, then approve.
 *
 * Editing PATCHes the pending change and approves the corrected version, so
 * what lands in the profile is what's on screen — no reject-and-re-prompt loop
 * when the agent mangles a section. The applier's whitelists still police the
 * edited diff, so this can't reach fields the proposal couldn't. */
function ProposalCard({
  change,
  state,
  onResolve,
  onEdited,
  onError,
}: {
  change: PendingChange;
  state?: "applied" | "rejected";
  onResolve: (action: "applied" | "rejected") => void;
  onEdited: (updated: PendingChange) => void;
  onError: (e: unknown) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const diff = asDiff(change.diff);

  function startEditing() {
    setDraft(Object.fromEntries(diff.map((d) => [d.field, String(d.new ?? "")])));
    setEditing(true);
  }

  async function saveEdit() {
    setSaving(true);
    try {
      const next = diff.map((d) => ({
        ...d,
        // sort_order is numeric; the rest are text as typed.
        new: d.field === "sort_order" ? Number(draft[d.field]) : draft[d.field],
      }));
      onEdited(await api.editChange(change.id, { diff: next }));
      setEditing(false);
    } catch (e) {
      onError(e);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      style={{
        border: `1px solid ${editing ? "var(--border-accent)" : "var(--border-default)"}`,
        borderRadius: "var(--radius-md)",
        padding: 14,
        marginBottom: 10,
        opacity: state ? 0.55 : 1,
        background: "var(--surface-sunken)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: state ? 0 : 10 }}>
        <div style={{ flex: 1, fontSize: 13, color: "var(--text-primary)" }}>
          {change.summary}
          {change.edited_at && !state && (
            <span style={{ fontSize: 11, color: "var(--text-tertiary)", marginLeft: 8 }}>· edited</span>
          )}
        </div>
        {state ? (
          <span
            style={{
              fontSize: 11.5,
              color: state === "applied" ? "var(--status-positive)" : "var(--text-tertiary)",
            }}
          >
            {state === "applied" ? "Saved" : "Rejected"}
          </span>
        ) : editing ? (
          <>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)} disabled={saving}>
              Cancel
            </Button>
            <Button size="sm" onClick={saveEdit} disabled={saving}>
              {saving ? "Saving…" : "Save edit"}
            </Button>
          </>
        ) : (
          <>
            <Button size="sm" variant="ghost" onClick={() => onResolve("rejected")}>
              Reject
            </Button>
            <Button size="sm" variant="secondary" onClick={startEditing}>
              Edit
            </Button>
            <Button size="sm" onClick={() => onResolve("applied")}>
              Approve
            </Button>
          </>
        )}
      </div>

      {!state && (
        <div style={{ display: "grid", gap: editing ? 10 : 6 }}>
          {diff.map((d) =>
            editing ? (
              <label key={d.field} style={{ display: "block" }}>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-tertiary)", marginBottom: 4 }}>
                  {d.field}
                </div>
                {(draft[d.field] ?? "").length > 60 ? (
                  <textarea
                    value={draft[d.field] ?? ""}
                    onChange={(e) => setDraft((s) => ({ ...s, [d.field]: e.target.value }))}
                    rows={8}
                    style={textareaStyle}
                  />
                ) : (
                  <input
                    value={draft[d.field] ?? ""}
                    onChange={(e) => setDraft((s) => ({ ...s, [d.field]: e.target.value }))}
                    style={{ ...inputStyle, marginBottom: 0 }}
                  />
                )}
              </label>
            ) : (
              <div key={d.field} style={{ display: "flex", gap: 8, fontSize: 12 }}>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-tertiary)", minWidth: 90 }}>
                  {d.field}
                </span>
                <span
                  style={{
                    color: "var(--text-secondary)",
                    whiteSpace: "pre-wrap",
                    lineHeight: 1.5,
                    maxHeight: 120,
                    overflow: "auto",
                  }}
                >
                  {String(d.new ?? "—")}
                </span>
              </div>
            ),
          )}
        </div>
      )}
    </div>
  );
}

function StepTitle({ title, hint }: { title: string; hint: string }) {
  return (
    <>
      <div style={{ fontFamily: "var(--font-display)", fontWeight: 500, fontSize: 17, color: "var(--text-primary)", marginBottom: 4 }}>
        {title}
      </div>
      <div style={{ fontSize: 12.5, color: "var(--text-secondary)", marginBottom: 16, lineHeight: 1.6 }}>{hint}</div>
    </>
  );
}
