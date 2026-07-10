// Profile: read + direct editing of basics and sections.
//
// Edits here save straight through the profile API — they don't pass through
// the changes tray, because that gate is for the agent's writes, not yours
// (DECISIONS #19). Asking the agent in chat still works and still proposes.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ProfileBasics, ProfileSection } from "@/lib/types";
import { Button, Card, Eyebrow, Loading, ErrorNote } from "@/components/ui";
import { inputStyle, textareaStyle } from "@/components/ui";

const BASIC_FIELDS: [keyof ProfileBasics, string][] = [
  ["full_name", "Full name"],
  ["headline", "Headline"],
  ["email", "Email"],
  ["phone", "Phone"],
  ["location", "Location"],
  ["linkedin_url", "LinkedIn"],
  ["portfolio_url", "Portfolio"],
];

export default function Profile() {
  const qc = useQueryClient();
  const basics = useQuery({ queryKey: ["profile", "basics"], queryFn: () => api.profileBasics() });
  const sections = useQuery({ queryKey: ["profile", "sections"], queryFn: () => api.profileSections() });

  const [editingBasics, setEditingBasics] = useState(false);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string>("");

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["profile"] });
    qc.invalidateQueries({ queryKey: ["onboarding"] });
  };
  const fail = (e: unknown) => setError(e instanceof Error ? e.message : String(e));

  if (basics.isLoading) return <Loading />;
  if (basics.error) return <ErrorNote error={basics.error} />;

  const list = sections.data ?? [];

  return (
    <div style={{ padding: "20px 24px 40px", maxWidth: 840 }}>
      <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 16, lineHeight: 1.6 }}>
        Your profile feeds CV and cover-letter drafting. Edit it directly here, or ask the agent in chat to
        refine it — its suggestions land in the changes tray for approval.
      </div>

      {error && (
        <Card style={{ marginBottom: 14, borderColor: "var(--status-negative)", padding: 14 }}>
          <div style={{ fontSize: 12.5, color: "var(--status-negative)" }}>{error}</div>
        </Card>
      )}

      <BasicsCard
        basics={basics.data!}
        editing={editingBasics}
        onEdit={() => setEditingBasics(true)}
        onCancel={() => setEditingBasics(false)}
        onSaved={() => {
          setEditingBasics(false);
          invalidate();
        }}
        onError={fail}
      />

      <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "22px 0 12px" }}>
        <Eyebrow style={{ fontWeight: 600 }}>Sections</Eyebrow>
        <div style={{ flex: 1 }} />
        <Button size="sm" variant="secondary" onClick={() => setAdding(true)} disabled={adding}>
          + Add section
        </Button>
      </div>

      {adding && (
        <SectionEditor
          initial={{ title: "", content_md: "" }}
          onCancel={() => setAdding(false)}
          onSave={async ({ title, content_md }) => {
            await api.createProfileSection({
              slug: title.trim().toLowerCase().replace(/\s+/g, "_"),
              title: title.trim(),
              content_md,
            });
            setAdding(false);
            invalidate();
          }}
          onError={fail}
        />
      )}

      {list.length === 0 && !adding && (
        <Card>
          <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            No sections yet. Add one above, or{" "}
            <Link to="/onboarding" style={{ color: "var(--accent-primary)" }}>
              import your CV
            </Link>{" "}
            and let the agent draft them.
          </div>
        </Card>
      )}

      {list.map((section, index) => (
        <SectionCard
          key={section.id}
          section={section}
          isFirst={index === 0}
          isLast={index === list.length - 1}
          onMove={async (direction) => {
            const ids = list.map((s) => s.id);
            const target = index + direction;
            [ids[index], ids[target]] = [ids[target], ids[index]];
            await api.reorderProfileSections(ids);
            invalidate();
          }}
          onSaved={invalidate}
          onError={fail}
        />
      ))}
    </div>
  );
}

// ── basics ───────────────────────────────────────────────────

function BasicsCard({
  basics,
  editing,
  onEdit,
  onCancel,
  onSaved,
  onError,
}: {
  basics: ProfileBasics;
  editing: boolean;
  onEdit: () => void;
  onCancel: () => void;
  onSaved: () => void;
  onError: (e: unknown) => void;
}) {
  const [draft, setDraft] = useState<ProfileBasics>(basics);
  useEffect(() => setDraft(basics), [basics, editing]);

  const save = useMutation({
    mutationFn: () => api.updateProfileBasics(draft),
    onSuccess: onSaved,
    onError,
  });

  const empty = BASIC_FIELDS.every(([key]) => !basics[key]);

  return (
    <Card>
      <div style={{ display: "flex", alignItems: "center", marginBottom: 14 }}>
        <Eyebrow style={{ fontWeight: 600 }}>Basics</Eyebrow>
        <div style={{ flex: 1 }} />
        {editing ? (
          <div style={{ display: "flex", gap: 8 }}>
            <Button size="sm" variant="ghost" onClick={onCancel} disabled={save.isPending}>
              Cancel
            </Button>
            <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending}>
              {save.isPending ? "Saving…" : "Save"}
            </Button>
          </div>
        ) : (
          <Button size="sm" variant="secondary" onClick={onEdit}>
            Edit
          </Button>
        )}
      </div>

      {editing ? (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
          {BASIC_FIELDS.map(([key, label]) => (
            <label key={key} style={{ display: "block" }}>
              <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 4 }}>{label}</div>
              <input
                value={(draft[key] as string) ?? ""}
                onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))}
                style={{ ...inputStyle, marginBottom: 0 }}
              />
            </label>
          ))}
        </div>
      ) : empty ? (
        <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
          Nothing here yet — hit Edit, or{" "}
          <Link to="/onboarding" style={{ color: "var(--accent-primary)" }}>
            import your CV
          </Link>
          .
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {BASIC_FIELDS.map(([key, label]) => (
            <div key={key}>
              <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>{label}</div>
              <div style={{ fontSize: 13.5, color: "var(--text-primary)", marginTop: 3 }}>
                {(basics[key] as string) || "—"}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ── sections ─────────────────────────────────────────────────

function SectionCard({
  section,
  isFirst,
  isLast,
  onMove,
  onSaved,
  onError,
}: {
  section: ProfileSection;
  isFirst: boolean;
  isLast: boolean;
  onMove: (direction: 1 | -1) => Promise<void>;
  onSaved: () => void;
  onError: (e: unknown) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (editing) {
    return (
      <SectionEditor
        initial={{ title: section.title, content_md: section.content_md ?? "" }}
        onCancel={() => setEditing(false)}
        onSave={async ({ title, content_md }) => {
          await api.updateProfileSection(section.id, { title, content_md });
          setEditing(false);
          onSaved();
        }}
        onError={onError}
      />
    );
  }

  return (
    <Card style={{ marginBottom: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <Eyebrow style={{ fontWeight: 600 }}>{section.title}</Eyebrow>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--text-tertiary)" }}>
          {section.slug}
        </span>
        <div style={{ flex: 1 }} />
        <MoveButton label="Move up" disabled={isFirst} onClick={() => onMove(-1).catch(onError)}>
          ↑
        </MoveButton>
        <MoveButton label="Move down" disabled={isLast} onClick={() => onMove(1).catch(onError)}>
          ↓
        </MoveButton>
        <Button size="sm" variant="secondary" onClick={() => setEditing(true)}>
          Edit
        </Button>
        {confirmDelete ? (
          <>
            <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              variant="danger"
              onClick={() =>
                api
                  .deleteProfileSection(section.id)
                  .then(onSaved)
                  .catch(onError)
              }
            >
              Delete
            </Button>
          </>
        ) : (
          <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(true)}>
            Delete
          </Button>
        )}
      </div>
      <div
        style={{
          fontSize: 13.5,
          color: "var(--text-secondary)",
          whiteSpace: "pre-wrap",
          lineHeight: 1.6,
        }}
      >
        {section.content_md || "—"}
      </div>
    </Card>
  );
}

function MoveButton({
  children,
  label,
  disabled,
  onClick,
}: {
  children: React.ReactNode;
  label: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      title={label}
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
      style={{
        width: 28,
        height: 28,
        borderRadius: "var(--radius-md)",
        border: "1px solid var(--border-default)",
        background: "transparent",
        color: "var(--text-secondary)",
        cursor: disabled ? "default" : "pointer",
        opacity: disabled ? 0.3 : 1,
        fontSize: 13,
      }}
    >
      {children}
    </button>
  );
}

/** Shared add/edit form so a new section and an existing one look identical. */
function SectionEditor({
  initial,
  onCancel,
  onSave,
  onError,
}: {
  initial: { title: string; content_md: string };
  onCancel: () => void;
  onSave: (values: { title: string; content_md: string }) => Promise<void>;
  onError: (e: unknown) => void;
}) {
  const [title, setTitle] = useState(initial.title);
  const [content, setContent] = useState(initial.content_md);
  const [saving, setSaving] = useState(false);

  async function submit() {
    setSaving(true);
    try {
      await onSave({ title, content_md: content });
    } catch (e) {
      onError(e);
      setSaving(false);
    }
  }

  return (
    <Card style={{ marginBottom: 12 }} accent>
      <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 4 }}>Title</div>
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Experience"
        autoFocus
        style={inputStyle}
      />
      <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 4 }}>Content (Markdown)</div>
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={10}
        style={textareaStyle}
      />
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <div style={{ flex: 1 }} />
        <Button size="sm" variant="ghost" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
        <Button size="sm" onClick={submit} disabled={saving || !title.trim()}>
          {saving ? "Saving…" : "Save"}
        </Button>
      </div>
    </Card>
  );
}
