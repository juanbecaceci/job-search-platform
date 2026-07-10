import { createBrowserRouter, RouterProvider } from "react-router-dom";
import AppShell from "@/components/shell/AppShell";
import Dashboard from "@/screens/Dashboard";
import Positions from "@/screens/Positions";
import Board from "@/screens/Board";
import PositionDetail from "@/screens/PositionDetail";
import SearchesList from "@/screens/SearchesList";
import NewSearch from "@/screens/NewSearch";
import SearchDetail from "@/screens/SearchDetail";
import Analytics from "@/screens/Analytics";
import Profile from "@/screens/Profile";
import Templates from "@/screens/Templates";
import Scoring from "@/screens/Scoring";
import Memories from "@/screens/Memories";
import Settings from "@/screens/Settings";
import Onboarding from "@/screens/Onboarding";

const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: "/onboarding", element: <Onboarding /> },
      { path: "/", element: <Dashboard /> },
      { path: "/searches", element: <SearchesList /> },
      { path: "/searches/new", element: <NewSearch /> },
      { path: "/searches/:id", element: <SearchDetail /> },
      { path: "/positions", element: <Positions /> },
      { path: "/positions/board", element: <Board /> },
      { path: "/positions/:id", element: <PositionDetail /> },
      { path: "/analytics", element: <Analytics /> },
      { path: "/profile", element: <Profile /> },
      { path: "/templates", element: <Templates /> },
      { path: "/scoring", element: <Scoring /> },
      { path: "/memories", element: <Memories /> },
      { path: "/settings", element: <Settings /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
