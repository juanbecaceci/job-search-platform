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

/** Score category → CSS var color.
 *
 * `score_category` holds one of the four score bands, or one of two markers the
 * evaluator writes when the salary gate decides the outcome instead of the
 * score. The token names are the design system's and stay as delivered
 * (DECISIONS #12), so they don't track this rename.
 */
export function scoreColor(category?: string | null): string {
  switch (category) {
    case "EXCELLENT":
      return "var(--score-exc)";
    case "GOOD":
      return "var(--score-buena)";
    case "ACCEPTABLE":
    case "NEEDS VALIDATION":
      return "var(--score-acep)";
    case "DISCARD":
    case "BELOW SALARY FLOOR":
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

// Dates are formatted in a fixed English locale, not the browser's. Passing
// `undefined` renders month names in whatever the OS is set to, so on a Spanish
// machine an otherwise-English UI showed "1 ago, 20:31" for 1 August. The UI is
// English by rule (see the root CLAUDE.md), and that has to include its dates.
const LOCALE = "en-GB";

export function fmtDate(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(LOCALE, { year: "numeric", month: "short", day: "numeric" });
}

export function fmtDateTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleString(LOCALE, {
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
