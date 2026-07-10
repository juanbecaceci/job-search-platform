import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useJobAction } from "@/lib/useJobAction";
import { ALL_STATUSES, fmtDate, fmtDateTime, scoreColor, statusColor } from "@/lib/format";
import { Card, Loading, ErrorNote, Button, Spinner } from "@/components/ui";
import type { DocumentOut, EvaluationCriterion, PositionDetail as PD } from "@/lib/types";

const TABS = ["Info", "Evaluation", "History", "Documents", "Company", "Application"] as const;
type Tab = (typeof TABS)[number];

const fieldLabel: React.CSSProperties = { fontSize: 10.5, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--text-tertiary)", fontWeight: 600 };
const fieldValue: React.CSSProperties = { fontSize: 13.5, color: "var(--text-primary)", marginTop: 4 };
const inputStyle: React.CSSProperties = {
  width: "100%", boxSizing: "border-box", background: "var(--surface-sunken)",
  border: "1px solid var(--border-default)", borderRadius: "var(--radius-md)",
  padding: "8px 10px", fontSize: 13, color: "var(--text-primary)", fontFamily: "var(--font-body)", outline: "none",
};

export default function PositionDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("Info");
  const detail = useQuery({ queryKey: ["position", id], queryFn: () => api.position(id!), enabled: !!id });

  const changeStatus = useMutation({
    mutationFn: (status: string) => api.changeStatus(id!, status),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["position", id] });
      qc.invalidateQueries({ queryKey: ["positions"] });
    },
  });

  if (detail.isLoading) return <Loading />;
  if (detail.error) return <ErrorNote error={detail.error} />;
  const d = detail.data!;
  const p = d.position;

  return (
    <div style={{ padding: "20px 24px 40px", maxWidth: 1040 }}>
      <button
        onClick={() => nav(-1)}
        style={{ display: "flex", alignItems: "center", gap: 6, background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)", fontSize: 12.5, padding: 0, marginBottom: 14 }}
      >
        <svg width="12" height="12" viewBox="0 0 10 10">
          <path d="M6.5 2.5 3.5 5 6.5 7.5" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Back
      </button>

      <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 6 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontFamily: "var(--font-display)", fontWeight: 500, fontSize: 24, letterSpacing: "-0.01em", color: "var(--text-primary)" }}>
            {p.role}
          </div>
          <div style={{ fontSize: 14, color: "var(--text-secondary)", marginTop: 4 }}>
            {p.company?.name ?? "—"} · {p.location ?? "—"}
            {p.url && (
              <>
                {" · "}
                <a href={p.url} target="_blank" rel="noreferrer">
                  {p.source} listing ↗
                </a>
              </>
            )}
          </div>
        </div>
        <div style={{ textAlign: "right", flex: "none" }}>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 26, fontWeight: 600, color: scoreColor(p.score_category) }}>
            {p.score !== null && p.score !== undefined ? Math.round(p.score) : "—"}
          </span>
          <div style={{ fontSize: 11, letterSpacing: "0.06em", color: scoreColor(p.score_category) }}>{p.score_category ?? ""}</div>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "14px 0 20px" }}>
        <select
          value={p.status}
          onChange={(e) => changeStatus.mutate(e.target.value)}
          style={{
            background: `color-mix(in srgb, ${statusColor(p.status)} 12%, transparent)`,
            border: `1px solid color-mix(in srgb, ${statusColor(p.status)} 30%, transparent)`,
            borderRadius: "var(--radius-md)",
            padding: "7px 10px",
            fontSize: 12.5,
            color: "var(--text-primary)",
            fontFamily: "var(--font-body)",
            outline: "none",
          }}
        >
          {ALL_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <span style={{ fontSize: 11.5, color: "var(--text-tertiary)" }}>Discovered {fmtDate(p.date_discovered)}</span>
        {p.salary_gate === "A VALIDAR" && (
          <span style={{ fontSize: 9.5, letterSpacing: "0.1em", fontWeight: 600, color: "var(--status-warning)" }}>SALARY A VALIDAR</span>
        )}
      </div>

      <div style={{ display: "flex", gap: 4, borderBottom: "1px solid var(--border-subtle)", marginBottom: 20 }}>
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              background: "none",
              border: "none",
              borderBottom: `2px solid ${tab === t ? "var(--accent-primary)" : "transparent"}`,
              padding: "8px 12px",
              cursor: "pointer",
              fontSize: 13,
              color: tab === t ? "var(--text-primary)" : "var(--text-secondary)",
              marginBottom: -1,
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Info" && <InfoTab d={d} onNotes={(notes) => api.patchPosition(id!, { notes }).then(() => qc.invalidateQueries({ queryKey: ["position", id] }))} />}
      {tab === "Evaluation" && <EvaluationTab d={d} positionId={id!} qc={qc} />}
      {tab === "History" && <HistoryTab d={d} />}
      {tab === "Documents" && <DocumentsTab d={d} positionId={id!} qc={qc} />}
      {tab === "Company" && <CompanyTab d={d} qc={qc} />}
      {tab === "Application" && <ApplicationTab d={d} positionId={id!} qc={qc} />}
    </div>
  );
}

function InfoTab({ d, onNotes }: { d: PD; onNotes: (notes: string) => void }) {
  const p = d.position;
  const [notes, setNotes] = useState(p.notes ?? "");
  useEffect(() => setNotes(p.notes ?? ""), [p.notes]);
  const fields: [string, string][] = [
    ["Type", p.tipo ?? "—"],
    ["Track", p.track ?? "—"],
    ["Remote", p.remote ?? "—"],
    ["Salary", p.salary_raw ?? "—"],
    ["Salary gate", p.salary_gate ?? "—"],
    ["Source", p.sources.join(", ")],
    ["Date posted", fmtDate(p.date_posted)],
    ["Rank", p.rank ? `#${p.rank}` : "—"],
  ];
  return (
    <Card style={{ padding: "22px 24px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px 32px" }}>
      {fields.map(([label, value]) => (
        <div key={label}>
          <div style={fieldLabel}>{label}</div>
          <div style={fieldValue}>{value}</div>
        </div>
      ))}
      <div style={{ gridColumn: "1 / -1" }}>
        <div style={{ ...fieldLabel, marginBottom: 6 }}>Tags</div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {p.tags.length ? (
            p.tags.map((t) => (
              <span key={t} style={{ fontFamily: "var(--font-mono)", fontSize: 11, background: "rgba(138,148,166,0.1)", border: "1px solid var(--border-subtle)", borderRadius: 5, padding: "3px 8px", color: "var(--text-secondary)" }}>
                {t}
              </span>
            ))
          ) : (
            <span style={{ color: "var(--text-tertiary)", fontSize: 12.5 }}>—</span>
          )}
        </div>
      </div>
      <div style={{ gridColumn: "1 / -1" }}>
        <div style={{ ...fieldLabel, marginBottom: 6 }}>Description</div>
        <div style={{ fontSize: 13, lineHeight: 1.65, color: "var(--text-secondary)", whiteSpace: "pre-wrap" }}>{p.description ?? "—"}</div>
      </div>
      <div style={{ gridColumn: "1 / -1" }}>
        <div style={{ ...fieldLabel, marginBottom: 6 }}>Notes</div>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          onBlur={() => notes !== (p.notes ?? "") && onNotes(notes)}
          placeholder="Add a note…"
          rows={3}
          style={{ width: "100%", boxSizing: "border-box", background: "var(--surface-sunken)", border: "1px solid var(--border-default)", borderRadius: "var(--radius-md)", padding: "10px 12px", fontSize: 13, color: "var(--text-primary)", fontFamily: "var(--font-body)", outline: "none", resize: "vertical" }}
        />
      </div>
    </Card>
  );
}

function EvaluationTab({ d, positionId, qc }: { d: PD; positionId: string; qc: QueryClient }) {
  const p = d.position;
  const job = useJobAction(() => qc.invalidateQueries({ queryKey: ["position", positionId] }));

  const reEvaluateButton = (
    <Button variant="secondary" size="sm" disabled={job.busy} onClick={() => job.run(() => api.evaluatePosition(positionId))}>
      {job.busy ? <Spinner size={13} /> : null}
      {job.busy ? job.message ?? "Evaluating…" : "Re-evaluate"}
    </Button>
  );

  if (!p.evaluation || Object.keys(p.evaluation).length === 0) {
    return (
      <Card style={{ padding: 40, textAlign: "center" }}>
        <div style={{ fontSize: 14, color: "var(--text-secondary)" }}>Not evaluated yet.</div>
        <div style={{ fontSize: 12.5, color: "var(--text-tertiary)", marginTop: 8, marginBottom: 16 }}>
          Ask the agent to evaluate it, or it'll be scored on the next search run.
        </div>
        {reEvaluateButton}
        {job.error && <div style={{ fontSize: 12, color: "var(--status-negative)", marginTop: 10 }}>{job.error}</div>}
      </Card>
    );
  }
  const color = scoreColor(p.score_category);
  const circ = 2 * Math.PI * 48;
  const dash = `${(circ * (p.score ?? 0)) / 100} ${circ}`;
  const criteria = Object.entries(p.evaluation) as [string, EvaluationCriterion][];
  return (
    <Card style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
        {reEvaluateButton}
      </div>
      {job.error && <div style={{ fontSize: 12, color: "var(--status-negative)", marginBottom: 12 }}>{job.error}</div>}
      <div style={{ display: "flex", gap: 32, alignItems: "center", paddingBottom: 22, borderBottom: "1px solid var(--border-subtle)", marginBottom: 20 }}>
        <svg width="112" height="112" viewBox="0 0 112 112" style={{ flex: "none" }}>
          <circle cx="56" cy="56" r="48" fill="none" stroke="var(--border-subtle)" strokeWidth="9" />
          <circle cx="56" cy="56" r="48" fill="none" stroke={color} strokeWidth="9" strokeLinecap="round" strokeDasharray={dash} transform="rotate(-90 56 56)" />
          <text x="56" y="52" textAnchor="middle" style={{ fontFamily: "var(--font-display)", fontSize: 26, fontWeight: 600, fill: "var(--text-primary)" }}>
            {Math.round(p.score ?? 0)}
          </text>
          <text x="56" y="70" textAnchor="middle" style={{ fontFamily: "var(--font-mono)", fontSize: 9, fill: "var(--text-tertiary)" }}>
            / 100
          </text>
        </svg>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 15, fontWeight: 600, color }}>{p.score_category}</div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 8, lineHeight: 1.6 }}>{p.recommended_action ?? p.summary ?? ""}</div>
          <div style={{ display: "flex", gap: 16, marginTop: 14, fontSize: 11.5, color: "var(--text-tertiary)" }}>
            <span>
              Salary gate: <strong style={{ color: "var(--text-secondary)" }}>{p.salary_gate ?? "—"}</strong>
            </span>
            <span>Config v{p.scoring_config_version ?? "—"}</span>
          </div>
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {criteria.map(([key, c]) => (
          <div key={key}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 6 }}>
              <span style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)", flex: 1, textTransform: "capitalize" }}>
                {key.replace(/_/g, " ")}
              </span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--text-tertiary)" }}>weight {(c.weight * 100).toFixed(0)}%</span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 600, color }}>{c.score}/5</span>
            </div>
            <div style={{ height: 6, borderRadius: 3, background: "rgba(138,148,166,0.14)", overflow: "hidden" }}>
              <div style={{ width: `${(c.score / 5) * 100}%`, height: "100%", background: color }} />
            </div>
            {c.rationale && <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 6, lineHeight: 1.55 }}>{c.rationale}</div>}
          </div>
        ))}
      </div>
    </Card>
  );
}

function HistoryTab({ d }: { d: PD }) {
  const events = [...d.events].reverse();
  return (
    <Card style={{ padding: "22px 26px" }}>
      {events.length === 0 && <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>No history yet.</div>}
      {events.map((ev, i) => (
        <div key={ev.id} style={{ display: "flex", gap: 14, paddingBottom: i < events.length - 1 ? 18 : 0, marginBottom: i < events.length - 1 ? 18 : 0, borderBottom: i < events.length - 1 ? "1px solid var(--border-subtle)" : "none" }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--accent-primary)", marginTop: 5, flex: "none" }} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, color: "var(--text-primary)" }}>{describeEvent(ev)}</div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-tertiary)", marginTop: 4 }}>
              {fmtDateTime(ev.created_at)} · {ev.actor}
            </div>
          </div>
        </div>
      ))}
    </Card>
  );
}
function describeEvent(ev: PD["events"][number]): string {
  switch (ev.event_type) {
    case "created":
      return "Position discovered";
    case "status_change":
      return `Status: ${ev.from_value ?? "—"} → ${ev.to_value}`;
    case "score_change":
      return `Score updated${ev.to_value ? ` to ${ev.to_value}` : ""}`;
    case "field_update":
      return "Fields edited";
    case "note":
      return "Note added";
    case "document_generated":
      return "Document generated";
    case "application_update":
      return "Application updated";
    default:
      return ev.event_type;
  }
}

function DocumentsTab({ d, positionId, qc }: { d: PD; positionId: string; qc: QueryClient }) {
  const invalidate = () => qc.invalidateQueries({ queryKey: ["position", positionId] });
  const cvJob = useJobAction(invalidate);
  const clJob = useJobAction(invalidate);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <Card style={{ padding: "14px 18px", display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span style={{ fontSize: 12.5, color: "var(--text-secondary)", flex: 1 }}>
          Generate a tailored document for this position:
        </span>
        <Button
          variant="secondary"
          size="sm"
          disabled={cvJob.busy}
          onClick={() => cvJob.run(() => api.generateDocument(positionId, "cv"))}
        >
          {cvJob.busy ? <Spinner size={13} /> : null}
          {cvJob.busy ? cvJob.message ?? "Drafting…" : "Generate CV"}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={clJob.busy}
          onClick={() => clJob.run(() => api.generateDocument(positionId, "cover_letter"))}
        >
          {clJob.busy ? <Spinner size={13} /> : null}
          {clJob.busy ? clJob.message ?? "Drafting…" : "Generate cover letter"}
        </Button>
      </Card>
      {(cvJob.error || clJob.error) && (
        <div style={{ fontSize: 12, color: "var(--status-negative)" }}>{cvJob.error || clJob.error}</div>
      )}

      {d.documents.length === 0 ? (
        <Card style={{ padding: 40, textAlign: "center" }}>
          <div style={{ fontSize: 13.5, color: "var(--text-secondary)" }}>
            No documents yet. Generate a tailored CV once this position reaches CV Draft.
          </div>
        </Card>
      ) : (
        d.documents.map((doc) => <DocumentCard key={doc.id} doc={doc} onChanged={invalidate} />)
      )}
    </div>
  );
}

function DocumentCard({ doc, onChanged }: { doc: DocumentOut; onChanged: () => void }) {
  const [md, setMd] = useState(doc.content_md ?? "");
  useEffect(() => setMd(doc.content_md ?? ""), [doc.content_md]);
  const [saving, setSaving] = useState(false);
  const exportJob = useJobAction(onChanged);
  const driveJob = useJobAction(onChanged);

  const save = () => {
    setSaving(true);
    api
      .updateDocument(doc.id, md)
      .then(onChanged)
      .finally(() => setSaving(false));
  };

  return (
    <Card style={{ padding: "18px 20px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <span style={{ fontSize: 13.5, fontWeight: 500, color: "var(--text-primary)", textTransform: "capitalize" }}>
          {doc.kind.replace(/_/g, " ")}
        </span>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-tertiary)" }}>
          v{doc.version} · {doc.status}
        </span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 10, alignItems: "center" }}>
          {doc.drive_url && (
            <a href={doc.drive_url} target="_blank" rel="noreferrer" style={{ fontSize: 12 }}>
              Open in Drive ↗
            </a>
          )}
          {doc.pdf_available && (
            <a href={api.documentFileUrl(doc.id, "pdf")} target="_blank" rel="noreferrer" style={{ fontSize: 12 }}>
              PDF ↓
            </a>
          )}
          {doc.docx_available && (
            <a href={api.documentFileUrl(doc.id, "docx")} target="_blank" rel="noreferrer" style={{ fontSize: 12 }}>
              DOCX ↓
            </a>
          )}
          <Button variant="secondary" size="sm" disabled={exportJob.busy} onClick={() => exportJob.run(() => api.exportDocument(doc.id))}>
            {exportJob.busy ? <Spinner size={13} /> : null}
            {exportJob.busy ? exportJob.message ?? "Exporting…" : "Export PDF/DOCX"}
          </Button>
          {/* Only offer the upload once there's a rendered file to send. */}
          {(doc.pdf_available || doc.docx_available) && (
            <Button
              variant="secondary"
              size="sm"
              disabled={driveJob.busy}
              onClick={() => driveJob.run(() => api.uploadDocumentToDrive(doc.id))}
              title="Upload the exported PDF/DOCX to your Google Drive folder"
            >
              {driveJob.busy ? <Spinner size={13} /> : null}
              {driveJob.busy ? driveJob.message ?? "Uploading…" : "Upload to Drive"}
            </Button>
          )}
        </div>
      </div>
      {exportJob.error && <div style={{ fontSize: 12, color: "var(--status-negative)", marginTop: 8 }}>{exportJob.error}</div>}
      {driveJob.error && <div style={{ fontSize: 12, color: "var(--status-negative)", marginTop: 8 }}>{driveJob.error}</div>}
      <textarea
        value={md}
        onChange={(e) => setMd(e.target.value)}
        rows={8}
        style={{ ...inputStyle, marginTop: 10, fontFamily: "var(--font-mono)", fontSize: 12, resize: "vertical" }}
      />
      {md !== (doc.content_md ?? "") && (
        <div style={{ marginTop: 8 }}>
          <Button size="sm" disabled={saving} onClick={save}>
            {saving ? <Spinner size={13} /> : null}
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      )}
    </Card>
  );
}

function CompanyTab({ d, qc }: { d: PD; qc: QueryClient }) {
  const c = d.position.company;
  const full = useQuery({
    queryKey: ["company", c?.id],
    queryFn: () => api.company(c!.id),
    enabled: !!c,
  });
  const job = useJobAction(() => qc.invalidateQueries({ queryKey: ["company", c?.id] }));

  if (!c) return <Card style={{ padding: 40, textAlign: "center" }}><span style={{ color: "var(--text-secondary)" }}>No company linked.</span></Card>;

  return (
    <Card style={{ padding: "22px 24px" }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px 32px" }}>
        <div><div style={fieldLabel}>Name</div><div style={fieldValue}>{c.name}</div></div>
        <div><div style={fieldLabel}>Industry</div><div style={fieldValue}>{c.industry ?? "—"}</div></div>
        <div><div style={fieldLabel}>Size</div><div style={fieldValue}>{c.size ?? "—"}</div></div>
        <div>
          <div style={fieldLabel}>Website</div>
          <div style={fieldValue}>{c.website ? <a href={c.website} target="_blank" rel="noreferrer">{c.website}</a> : "—"}</div>
        </div>
      </div>
      <div style={{ marginTop: 20, paddingTop: 18, borderTop: "1px solid var(--border-subtle)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
          <div style={fieldLabel}>Research</div>
          <Button
            variant="secondary"
            size="sm"
            disabled={job.busy || !c.website}
            title={c.website ? undefined : "No website on file"}
            onClick={() => job.run(() => api.researchCompany(c.id))}
            style={{ marginLeft: "auto" }}
          >
            {job.busy ? <Spinner size={13} /> : null}
            {job.busy ? job.message ?? "Researching…" : "Research company"}
          </Button>
        </div>
        {job.error && <div style={{ fontSize: 12, color: "var(--status-negative)", marginBottom: 10 }}>{job.error}</div>}
        {full.data?.research_md ? (
          <div style={{ fontSize: 13, lineHeight: 1.65, color: "var(--text-secondary)", whiteSpace: "pre-wrap" }}>
            {full.data.research_md}
          </div>
        ) : (
          <div style={{ fontSize: 12.5, color: "var(--text-tertiary)" }}>No research yet.</div>
        )}
      </div>
    </Card>
  );
}

function ApplicationTab({ d, positionId, qc }: { d: PD; positionId: string; qc: QueryClient }) {
  const a = d.application;
  const invalidate = () => qc.invalidateQueries({ queryKey: ["position", positionId] });

  if (!a) return <NewApplicationForm positionId={positionId} onCreated={invalidate} />;

  const patch = (body: Record<string, unknown>) => api.patchApplication(a.id, body).then(invalidate);

  return (
    <Card style={{ padding: "22px 24px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px 32px" }}>
      <EditableField label="Date applied" type="date" value={a.date_applied} onSave={(v) => patch({ date_applied: v || null })} />
      <EditableField label="Applied via" value={a.applied_via} onSave={(v) => patch({ applied_via: v || null })} />
      <EditableField label="Contact" value={a.contact} onSave={(v) => patch({ contact: v || null })} />
      <EditableField label="Response date" type="date" value={a.response_date} onSave={(v) => patch({ response_date: v || null })} />
      <EditableField label="Interview date" type="date" value={a.interview_date} onSave={(v) => patch({ interview_date: v || null })} />
      <EditableField label="Follow-up due" type="date" value={a.follow_up_due} onSave={(v) => patch({ follow_up_due: v || null })} />
      <EditableField label="Outcome" value={a.outcome} onSave={(v) => patch({ outcome: v || null })} />
      <div style={{ gridColumn: "1 / -1" }}>
        <EditableField label="Notes" textarea value={a.notes} onSave={(v) => patch({ notes: v || null })} />
      </div>
    </Card>
  );
}

function EditableField({
  label,
  value,
  onSave,
  type = "text",
  textarea,
}: {
  label: string;
  value?: string | null;
  onSave: (v: string) => void;
  type?: string;
  textarea?: boolean;
}) {
  const [v, setV] = useState(value ?? "");
  useEffect(() => setV(value ?? ""), [value]);
  return (
    <div>
      <div style={{ ...fieldLabel, marginBottom: 6 }}>{label}</div>
      {textarea ? (
        <textarea
          value={v}
          onChange={(e) => setV(e.target.value)}
          onBlur={() => v !== (value ?? "") && onSave(v)}
          rows={3}
          style={{ ...inputStyle, resize: "vertical" }}
        />
      ) : (
        <input
          type={type}
          value={v}
          onChange={(e) => setV(e.target.value)}
          onBlur={() => v !== (value ?? "") && onSave(v)}
          style={inputStyle}
        />
      )}
    </div>
  );
}

function NewApplicationForm({ positionId, onCreated }: { positionId: string; onCreated: () => void }) {
  const [form, setForm] = useState({ date_applied: "", applied_via: "", contact: "" });
  const [saving, setSaving] = useState(false);
  const submit = () => {
    setSaving(true);
    api
      .createApplication(positionId, {
        date_applied: form.date_applied || null,
        applied_via: form.applied_via || null,
        contact: form.contact || null,
      })
      .then(onCreated)
      .finally(() => setSaving(false));
  };
  return (
    <Card style={{ padding: "22px 24px" }}>
      <div style={{ fontSize: 13.5, color: "var(--text-secondary)", marginBottom: 16 }}>
        No application record yet — log one once you apply.
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginBottom: 16 }}>
        <div>
          <div style={{ ...fieldLabel, marginBottom: 6 }}>Date applied</div>
          <input
            type="date"
            value={form.date_applied}
            onChange={(e) => setForm({ ...form, date_applied: e.target.value })}
            style={inputStyle}
          />
        </div>
        <div>
          <div style={{ ...fieldLabel, marginBottom: 6 }}>Applied via</div>
          <input
            value={form.applied_via}
            onChange={(e) => setForm({ ...form, applied_via: e.target.value })}
            style={inputStyle}
          />
        </div>
        <div>
          <div style={{ ...fieldLabel, marginBottom: 6 }}>Contact</div>
          <input value={form.contact} onChange={(e) => setForm({ ...form, contact: e.target.value })} style={inputStyle} />
        </div>
      </div>
      <Button size="sm" disabled={saving} onClick={submit}>
        {saving ? <Spinner size={13} /> : null}
        {saving ? "Saving…" : "Log application"}
      </Button>
    </Card>
  );
}
