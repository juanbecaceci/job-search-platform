import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { isOnboardingSkipped } from "@/lib/onboarding";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import ChatDrawer from "./ChatDrawer";

const TITLES: Record<string, string> = {
  "/": "Dashboard",
  "/onboarding": "Setup",
  "/searches": "Searches",
  "/positions": "Positions",
  "/analytics": "Analytics",
  "/profile": "Profile",
  "/templates": "Templates",
  "/scoring": "Scoring",
  "/memories": "Memories",
  "/settings": "Settings",
};

function titleFor(pathname: string): string {
  if (pathname === "/positions/board") return "Board";
  if (pathname.startsWith("/positions/")) return "Position";
  if (pathname.startsWith("/searches/new")) return "New search";
  if (pathname.startsWith("/searches/")) return "Search";
  return TITLES[pathname] ?? "Job Search";
}

// Lets a screen inject controls into the topbar (range picker, view toggle).
const TopbarSlot = createContext<(node: ReactNode) => void>(() => {});
export function useSetTopbarRight(node: ReactNode, deps: unknown[]) {
  const setRight = useContext(TopbarSlot);
  useEffect(() => {
    setRight(node);
    return () => setRight(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

export default function AppShell() {
  const location = useLocation();
  const [chatOpen, setChatOpen] = useState(false);
  const [right, setRight] = useState<ReactNode>(null);

  // Onboarding guard (§7.5): without a usable profile the agent can't draft
  // anything, so first run lands on the wizard. Held until the status query
  // resolves — redirecting on `undefined` would bounce every cold load.
  const onboarding = useQuery({ queryKey: ["onboarding"], queryFn: () => api.onboardingStatus() });
  const needsOnboarding =
    onboarding.data?.completed === false &&
    !isOnboardingSkipped() &&
    location.pathname !== "/onboarding";
  if (needsOnboarding) return <Navigate to="/onboarding" replace />;

  return (
    <div
      style={{
        display: "flex",
        width: "100%",
        height: "100vh",
        overflow: "hidden",
        background: "var(--surface-page)",
        color: "var(--text-primary)",
        fontFamily: "var(--font-body)",
        fontSize: 14,
      }}
    >
      <Sidebar />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <Topbar title={titleFor(location.pathname)} right={right} onToggleChat={() => setChatOpen((o) => !o)} />
        <main style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
          <TopbarSlot.Provider value={setRight}>
            <Outlet />
          </TopbarSlot.Provider>
        </main>
      </div>
      <ChatDrawer open={chatOpen} onClose={() => setChatOpen(false)} />
    </div>
  );
}
