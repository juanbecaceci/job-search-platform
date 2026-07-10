import { useNavigate } from "react-router-dom";

/** Table / Board segmented toggle for the positions views (lives in the topbar). */
export default function PositionsViewToggle({ active }: { active: "table" | "board" }) {
  const nav = useNavigate();
  const opt = (key: "table" | "board", label: string, to: string) => (
    <button
      onClick={() => nav(to)}
      style={{
        padding: "6px 12px",
        fontSize: 12,
        border: "none",
        cursor: "pointer",
        background: active === key ? "var(--surface-card)" : "transparent",
        color: active === key ? "var(--text-primary)" : "var(--text-secondary)",
      }}
    >
      {label}
    </button>
  );
  return (
    <div style={{ display: "flex", border: "1px solid var(--border-default)", borderRadius: "var(--radius-md)", overflow: "hidden" }}>
      {opt("table", "Table", "/positions")}
      {opt("board", "Board", "/positions/board")}
    </div>
  );
}
