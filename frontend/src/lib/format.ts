// Small presentation helpers shared across screens.

export const PIPELINE: string[] = [
  "Discovered",
  "Evaluating",
  "Shortlisted",
  "CV Draft",
  "Ready to Apply",
  "Applied",
  "Acknowledged",
  "Interview Scheduled",
  "Interviewing",
  "Offer Received",
  "Negotiating",
  "Accepted",
];
export const TERMINAL: string[] = ["Rejected", "Withdrawn", "Ghosted"];
export const ALL_STATUSES = [...PIPELINE, ...TERMINAL];

/** Score category → CSS var color. */
export function scoreColor(category?: string | null): string {
  switch (category) {
    case "EXCELENTE":
      return "var(--score-exc)";
    case "BUENA":
      return "var(--score-buena)";
    case "ACEPTABLE":
      return "var(--score-acep)";
    case "DESCARTAR":
      return "var(--score-desc)";
    default:
      return "var(--score-none)";
  }
}

/** Pipeline status → a color group (early / prep / active / offer / terminal). */
export function statusColor(status: string): string {
  if (TERMINAL.includes(status)) return "var(--st-terminal)";
  const idx = PIPELINE.indexOf(status);
  if (idx < 0) return "var(--st-early)";
  if (idx <= 1) return "var(--st-early)"; // Discovered, Evaluating
  if (idx <= 4) return "var(--st-prep)"; // Shortlisted..Ready to Apply
  if (idx <= 8) return "var(--st-active)"; // Applied..Interviewing
  return "var(--st-offer)"; // Offer Received..Accepted
}

export const isTerminal = (status: string) => TERMINAL.includes(status);

export function fmtDate(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function fmtDateTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function fmtScore(score?: number | null): string {
  return score === null || score === undefined ? "—" : String(Math.round(score));
}

/** ISO date N days ago (for default dashboard/analytics ranges). */
export function daysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}
export const today = () => new Date().toISOString().slice(0, 10);
