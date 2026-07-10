import { useState, useMemo, type CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, Button, Loading } from "@/components/ui";

const POSTED = [7, 30, 180];

export default function NewSearch() {
  const nav = useNavigate();
  const defaults = useQuery({ queryKey: ["searchDefaults"], queryFn: () => api.searchDefaults() });

  const [step, setStep] = useState(1);
  const [name, setName] = useState("");
  const [sources, setSources] = useState<Set<string>>(new Set());
  const [keywords, setKeywords] = useState<string[]>([]);
  const [kwInput, setKwInput] = useState("");
  const [postedWithin, setPostedWithin] = useState(30);
  const [creating, setCreating] = useState(false);
  const [initialized, setInitialized] = useState(false);

  // Seed sources (enabled defaults) + keywords (first group) once defaults load.
  useMemo(() => {
    if (defaults.data && !initialized) {
      setSources(new Set(defaults.data.sources.filter((s) => s.enabled_default).map((s) => s.id)));
      const firstGroup = Object.values(defaults.data.keyword_groups)[0] ?? [];
      setKeywords(firstGroup.slice(0, 6));
      setInitialized(true);
    }
  }, [defaults.data, initialized]);

  if (defaults.isLoading) return <Loading />;

  const toggleSource = (id: string) =>
    setSources((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  const addKeyword = () => {
    const v = kwInput.trim();
    if (v && !keywords.includes(v)) setKeywords((k) => [...k, v]);
    setKwInput("");
  };

  async function createAndRun() {
    setCreating(true);
    try {
      const search = await api.createSearch({
        name: name || "Untitled search",
        sources: [...sources],
        keywords,
        posted_within_days: postedWithin,
        markets: [],
      });
      const run = await api.runSearch(search.id);
      nav(`/searches/${search.id}?job=${run.job_id}`);
    } catch (e) {
      setCreating(false);
      alert(`Could not create/run search: ${(e as Error).message}`);
    }
  }

  const canNext = step === 1 ? name.trim().length > 0 : step === 2 ? sources.size > 0 : true;
  const dots = ["Name", "Sources", "Keywords"];

  return (
    <div style={{ padding: "24px 24px 40px", maxWidth: 640 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 22 }}>
        {dots.map((label, i) => {
          const n = i + 1;
          const active = n === step;
          const done = n < step;
          return (
            <div key={label} style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: active || done ? "var(--accent-primary)" : "rgba(138,148,166,0.3)",
                }}
              />
              <span style={{ fontSize: 12, color: active ? "var(--text-primary)" : "var(--text-tertiary)", marginRight: i < 2 ? 6 : 0 }}>
                {label}
              </span>
            </div>
          );
        })}
      </div>

      <Card style={{ padding: 26 }}>
        {step === 1 && (
          <>
            <StepTitle title="Name your search" hint='A short label to recognize it later, e.g. "AI Ops July".' />
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Search name…"
              autoFocus
              style={inputStyle}
            />
          </>
        )}
        {step === 2 && (
          <>
            <StepTitle title="Choose sources" hint="All sources are on by default — turn off any you don't want." />
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
              {defaults.data!.sources.map((s) => {
                const on = sources.has(s.id);
                return (
                  <button
                    key={s.id}
                    onClick={() => toggleSource(s.id)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 6,
                      padding: "10px 12px",
                      fontSize: 12.5,
                      borderRadius: "var(--radius-md)",
                      cursor: "pointer",
                      background: on ? "color-mix(in srgb, var(--accent-primary) 12%, transparent)" : "var(--surface-sunken)",
                      border: `1px solid ${on ? "var(--border-accent)" : "var(--border-default)"}`,
                      color: on ? "var(--text-primary)" : "var(--text-secondary)",
                    }}
                  >
                    <span>{s.label}</span>
                    {on && (
                      <svg width="13" height="13" viewBox="0 0 14 14" style={{ color: "var(--accent-primary)" }}>
                        <path d="M2.5 7.5 5.5 10.5 11.5 3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    )}
                  </button>
                );
              })}
            </div>
          </>
        )}
        {step === 3 && (
          <>
            <StepTitle title="Keywords & recency" hint="Pre-filled from your defaults — add or remove as needed." />
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
              {keywords.map((kw) => (
                <span
                  key={kw}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    fontFamily: "var(--font-mono)",
                    fontSize: 11.5,
                    background: "rgba(138,148,166,0.1)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: 5,
                    padding: "4px 6px 4px 9px",
                    color: "var(--text-secondary)",
                  }}
                >
                  {kw}
                  <button
                    onClick={() => setKeywords((k) => k.filter((x) => x !== kw))}
                    style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-tertiary)", padding: 2, display: "flex" }}
                  >
                    <svg width="9" height="9" viewBox="0 0 10 10">
                      <path d="M2.5 2.5 7.5 7.5 M7.5 2.5 2.5 7.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                    </svg>
                  </button>
                </span>
              ))}
            </div>
            <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
              <input
                value={kwInput}
                onChange={(e) => setKwInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addKeyword();
                  }
                }}
                placeholder="Add a keyword…"
                style={{ ...inputStyle, flex: 1, marginBottom: 0 }}
              />
              <Button size="sm" variant="secondary" onClick={addKeyword}>
                Add
              </Button>
            </div>
            <div style={{ fontSize: 11, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--text-tertiary)", fontWeight: 600, marginBottom: 8 }}>
              Posted within
            </div>
            <div style={{ display: "flex", border: "1px solid var(--border-default)", borderRadius: "var(--radius-md)", overflow: "hidden", width: "fit-content" }}>
              {POSTED.map((d) => (
                <button
                  key={d}
                  onClick={() => setPostedWithin(d)}
                  style={{
                    padding: "7px 14px",
                    fontSize: 12,
                    border: "none",
                    cursor: "pointer",
                    background: postedWithin === d ? "var(--surface-card-alt)" : "transparent",
                    color: postedWithin === d ? "var(--text-primary)" : "var(--text-secondary)",
                  }}
                >
                  {d} days
                </button>
              ))}
            </div>
          </>
        )}
      </Card>

      <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
        {step > 1 && (
          <Button variant="ghost" onClick={() => setStep((s) => s - 1)}>
            Back
          </Button>
        )}
        <div style={{ flex: 1 }} />
        <Button variant="ghost" onClick={() => nav("/searches")}>
          Cancel
        </Button>
        {step < 3 ? (
          <Button onClick={() => setStep((s) => s + 1)} disabled={!canNext}>
            Next
          </Button>
        ) : (
          <Button onClick={createAndRun} disabled={creating || keywords.length === 0}>
            {creating ? "Creating…" : "Create & Run"}
          </Button>
        )}
      </div>
    </div>
  );
}

function StepTitle({ title, hint }: { title: string; hint: string }) {
  return (
    <>
      <div style={{ fontFamily: "var(--font-display)", fontWeight: 500, fontSize: 17, color: "var(--text-primary)", marginBottom: 4 }}>
        {title}
      </div>
      <div style={{ fontSize: 12.5, color: "var(--text-secondary)", marginBottom: 16 }}>{hint}</div>
    </>
  );
}

const inputStyle: CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  background: "var(--surface-sunken)",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-md)",
  padding: "10px 12px",
  fontSize: 14,
  color: "var(--text-primary)",
  fontFamily: "var(--font-body)",
  outline: "none",
  marginBottom: 16,
};
