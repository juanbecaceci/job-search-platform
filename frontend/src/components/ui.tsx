// Shared UI primitives, styled to the brand tokens (inline styles + CSS vars,
// matching the Claude Design output).

import type { CSSProperties, ReactNode } from "react";
import { scoreColor, statusColor, isTerminal, fmtScore } from "@/lib/format";

// ── Button ───────────────────────────────────────────────────
type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md";

const btnBase: CSSProperties = {
  fontFamily: "var(--font-body)",
  fontWeight: 500,
  // Longhand, not the `border` shorthand: variants override `borderColor`, and
  // React warns (and can mis-render) when the two are mixed across a rerender.
  borderWidth: 1,
  borderStyle: "solid",
  borderColor: "transparent",
  borderRadius: "var(--radius-md)",
  cursor: "pointer",
  transition: "background var(--duration-fast) var(--ease-standard), color var(--duration-fast), border-color var(--duration-fast)",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: 7,
  whiteSpace: "nowrap",
};

export function Button({
  children,
  variant = "primary",
  size = "md",
  onClick,
  disabled,
  type = "button",
  style,
  title,
}: {
  children: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit";
  style?: CSSProperties;
  title?: string;
}) {
  const sizes: Record<ButtonSize, CSSProperties> = {
    sm: { fontSize: 12.5, padding: "7px 12px", height: 32 },
    md: { fontSize: 13.5, padding: "9px 16px", height: 38 },
  };
  const variants: Record<ButtonVariant, CSSProperties> = {
    primary: { background: "var(--interactive-default)", color: "var(--text-on-accent)" },
    secondary: {
      background: "transparent",
      color: "var(--text-primary)",
      borderColor: "var(--border-strong)",
    },
    ghost: { background: "transparent", color: "var(--text-secondary)" },
    danger: { background: "var(--status-negative)", color: "#fff" },
  };
  return (
    <button
      type={type}
      title={title}
      onClick={onClick}
      disabled={disabled}
      style={{
        ...btnBase,
        ...sizes[size],
        ...variants[variant],
        opacity: disabled ? 0.5 : 1,
        pointerEvents: disabled ? "none" : undefined,
        ...style,
      }}
    >
      {children}
    </button>
  );
}

// ── Card ─────────────────────────────────────────────────────
export function Card({
  children,
  style,
  accent,
  onClick,
}: {
  children: ReactNode;
  style?: CSSProperties;
  accent?: boolean;
  onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      style={{
        background: "var(--surface-card)",
        border: `1px solid ${accent ? "var(--border-accent)" : "var(--border-default)"}`,
        borderRadius: "var(--radius-lg)",
        padding: 20,
        cursor: onClick ? "pointer" : undefined,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

// ── Eyebrow / section label ──────────────────────────────────
export function Eyebrow({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <div
      style={{
        fontSize: 10,
        letterSpacing: "0.16em",
        textTransform: "uppercase",
        color: "var(--text-tertiary)",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

// ── Badge (status pill) ──────────────────────────────────────
export function Badge({
  children,
  color = "var(--text-secondary)",
  style,
}: {
  children: ReactNode;
  color?: string;
  style?: CSSProperties;
}) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        fontSize: 11,
        fontWeight: 500,
        padding: "3px 9px",
        borderRadius: "var(--radius-pill)",
        color,
        background: "color-mix(in srgb, currentColor 12%, transparent)",
        border: "1px solid color-mix(in srgb, currentColor 26%, transparent)",
        ...style,
      }}
    >
      {children}
    </span>
  );
}

// ── ScoreBadge ───────────────────────────────────────────────
export function ScoreBadge({
  score,
  category,
}: {
  score?: number | null;
  category?: string | null;
}) {
  const color = scoreColor(category);
  const has = score !== null && score !== undefined;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        fontFamily: "var(--font-mono)",
        fontSize: 13,
        fontWeight: 600,
        color: has ? color : "var(--text-tertiary)",
      }}
    >
      <span
        style={{ width: 7, height: 7, borderRadius: "50%", background: has ? color : "var(--score-none)" }}
      />
      {fmtScore(score)}
    </span>
  );
}

// ── StatusChip ───────────────────────────────────────────────
export function StatusChip({ status }: { status: string }) {
  const color = statusColor(status);
  const muted = isTerminal(status);
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        fontSize: 11.5,
        fontWeight: 500,
        padding: "3px 10px",
        borderRadius: "var(--radius-pill)",
        color: muted ? "var(--text-tertiary)" : color,
        background: `color-mix(in srgb, ${color} ${muted ? 8 : 14}%, transparent)`,
        border: `1px solid color-mix(in srgb, ${color} ${muted ? 18 : 30}%, transparent)`,
        opacity: muted ? 0.85 : 1,
      }}
    >
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: color }} />
      {status}
    </span>
  );
}

// ── StatTile (KPI) ───────────────────────────────────────────
export function StatTile({
  label,
  value,
  sub,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
}) {
  return (
    <Card style={{ padding: 20 }}>
      <Eyebrow>{label}</Eyebrow>
      <div
        style={{
          fontFamily: "var(--font-display)",
          fontWeight: 500,
          fontSize: 36,
          letterSpacing: "-0.02em",
          color: "var(--text-primary)",
          marginTop: 8,
          lineHeight: 1.1,
        }}
      >
        {value}
      </div>
      {sub && <div style={{ fontSize: 12.5, color: "var(--text-secondary)", marginTop: 6 }}>{sub}</div>}
    </Card>
  );
}

// ── Spinner ──────────────────────────────────────────────────
export function Spinner({ size = 16 }: { size?: number }) {
  return (
    <span
      style={{
        display: "inline-block",
        width: size,
        height: size,
        border: "2px solid var(--border-strong)",
        borderTopColor: "var(--accent-primary)",
        borderRadius: "50%",
        animation: "jsSpin 0.7s linear infinite",
      }}
    />
  );
}

// ── EmptyState ───────────────────────────────────────────────
export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 12,
        padding: "64px 24px",
        textAlign: "center",
      }}
    >
      <div style={{ fontFamily: "var(--font-display)", fontSize: 18, color: "var(--text-primary)" }}>
        {title}
      </div>
      {hint && <div style={{ fontSize: 13.5, color: "var(--text-secondary)", maxWidth: 420 }}>{hint}</div>}
      {action}
    </div>
  );
}

// ── PageState (loading / error wrappers) ─────────────────────
export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: 32, color: "var(--text-secondary)" }}>
      <Spinner /> {label}
    </div>
  );
}
export function ErrorNote({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div
      style={{
        margin: 24,
        padding: 16,
        border: "1px solid color-mix(in srgb, var(--status-negative) 30%, transparent)",
        background: "color-mix(in srgb, var(--status-negative) 8%, transparent)",
        borderRadius: "var(--radius-md)",
        color: "var(--status-negative)",
        fontSize: 13.5,
      }}
    >
      {msg}
    </div>
  );
}

// ── form field styles ────────────────────────────────────────
// Shared so every editable surface (profile, wizard) looks identical.
export const inputStyle: CSSProperties = {
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

export const textareaStyle: CSSProperties = {
  ...inputStyle,
  marginBottom: 0,
  fontSize: 13,
  lineHeight: 1.6,
  resize: "vertical",
};
