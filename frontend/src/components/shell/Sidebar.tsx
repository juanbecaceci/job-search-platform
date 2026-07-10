import { NavLink } from "react-router-dom";
import type { CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface NavItem {
  to: string;
  label: string;
}
interface NavGroup {
  heading?: string;
  items: NavItem[];
}

const GROUPS: NavGroup[] = [
  {
    items: [
      { to: "/", label: "Dashboard" },
      { to: "/searches", label: "Searches" },
      { to: "/positions", label: "Positions" },
      { to: "/analytics", label: "Analytics" },
    ],
  },
  {
    heading: "Configure",
    items: [
      { to: "/profile", label: "Profile" },
      { to: "/templates", label: "Templates" },
      { to: "/scoring", label: "Scoring" },
      { to: "/memories", label: "Memories" },
      { to: "/settings", label: "Settings" },
    ],
  },
];

const Arrow = () => (
  <svg width="10" height="10" viewBox="0 0 10 10" style={{ flex: "none" }}>
    <path d="M2 1v4.5h5" fill="none" stroke="currentColor" strokeWidth="1.5" />
    <path d="M4.8 3.2 7.2 5.5 4.8 7.8" fill="none" stroke="currentColor" strokeWidth="1.5" />
  </svg>
);

export default function Sidebar() {
  // Whose install this is comes from the user's own profile, never from a
  // literal — this repo is cloned and run by other people. Same query key as
  // the Profile screen, so editing your name there updates this immediately
  // (that screen invalidates the whole `["profile"]` prefix).
  const basics = useQuery({
    queryKey: ["profile", "basics"],
    queryFn: () => api.profileBasics(),
  });
  const fullName = basics.data?.full_name?.trim();

  const itemStyle = (active: boolean): CSSProperties => ({
    display: "flex",
    alignItems: "center",
    gap: 9,
    padding: "8px 10px",
    borderRadius: "var(--radius-md)",
    fontSize: 13,
    fontWeight: active ? 600 : 500,
    color: active ? "var(--text-primary)" : "var(--text-secondary)",
    background: active ? "rgba(138,148,166,0.10)" : "transparent",
    textDecoration: "none",
    transition: "background var(--duration-fast), color var(--duration-fast)",
  });

  return (
    <aside
      style={{
        width: 216,
        flex: "none",
        display: "flex",
        flexDirection: "column",
        borderRight: "1px solid var(--border-subtle)",
        background: "var(--surface-sunken)",
        padding: "20px 12px 16px",
      }}
    >
      {/* Logo */}
      <div style={{ display: "flex", alignItems: "center", gap: 11, padding: "0 8px 22px" }}>
        <div
          style={{
            position: "relative",
            width: 34,
            height: 34,
            flex: "none",
            border: "1.5px solid var(--border-strong)",
            borderRadius: 4,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: "var(--font-display)",
            fontWeight: 600,
            fontSize: 13,
            letterSpacing: "-0.02em",
            color: "var(--text-primary)",
          }}
        >
          JS
          <span
            style={{
              position: "absolute",
              top: -3,
              right: -3,
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: "var(--accent-primary)",
            }}
          />
        </div>
        <div>
          <div
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 600,
              fontSize: 13,
              letterSpacing: "0.06em",
              color: "var(--text-primary)",
            }}
          >
            JOB SEARCH
          </div>
          {fullName && (
            <div
              style={{
                fontSize: 9,
                letterSpacing: "0.18em",
                color: "var(--text-tertiary)",
                textTransform: "uppercase",
                marginTop: 1,
                maxWidth: 140,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
              title={fullName}
            >
              {fullName}
            </div>
          )}
        </div>
      </div>

      {/* Nav */}
      <nav style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {GROUPS.map((group, gi) => (
          <div key={gi} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {group.heading && (
              <div
                style={{
                  fontSize: 10,
                  letterSpacing: "0.16em",
                  textTransform: "uppercase",
                  color: "var(--text-tertiary)",
                  padding: "16px 10px 6px",
                }}
              >
                {group.heading}
              </div>
            )}
            {group.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                style={({ isActive }) => itemStyle(isActive)}
              >
                {({ isActive }) => (
                  <>
                    <span style={{ color: isActive ? "var(--accent-primary)" : "var(--text-tertiary)" }}>
                      <Arrow />
                    </span>
                    <span>{item.label}</span>
                  </>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div
        style={{
          marginTop: "auto",
          padding: "10px 10px 0",
          fontSize: 9,
          letterSpacing: "0.14em",
          color: "var(--text-tertiary)",
          textTransform: "uppercase",
        }}
      >
        Self-hosted · v1
      </div>
    </aside>
  );
}
