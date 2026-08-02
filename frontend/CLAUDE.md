# frontend/ — React SPA

Built through Stage 5 (all 14 screens wired to the live API); see root
`PROGRESS.md` for the resume point. Read this before writing code here — several
conventions are deliberate and look like mistakes if you don't know why.

## Before writing code

From `PLATFORM_SPEC.md`, load only what the screen needs:
- §4 "Entities" — the JSON shapes the API returns (mirrored in `src/lib/types.ts`)
- §5 "API reference" — which endpoints exist (mirrored in `src/lib/api.ts`)
- §6 "SSE event streams" — job + chat event names
- §7 "Global UI shell" — sidebar / ChatDrawer / JobsIndicator / ChangesTray /
  onboarding guard, all implemented in `src/components/shell/`
- §8 "View map" — the per-route feature list; §9 "UX rules" — score colors,
  terminal-state muting, empty states, confirmation rules

## Actual layout (as built)

```
frontend/
├── vite.config.ts        # `@` → ./src alias; dev proxy /api → :8000 (strips
│                          # /api). Override API_PROXY_TARGET / VITE_DEV_PORT to
│                          # point a second dev server at a throwaway-DB backend.
├── index.html
└── src/
    ├── App.tsx            # createBrowserRouter; every route nests under AppShell
    ├── main.tsx           # ThemeProvider + React Query client + tokens.css
    ├── styles/tokens.css  # brand tokens, ported 1:1 from the design output;
    │                       # light/dark via [data-theme] on <html>
    ├── lib/
    │   ├── api.ts          # typed fetch client — the ONLY place a URL is written
    │   ├── types.ts        # TS mirrors of PLATFORM_SPEC.md §4 / api/schemas
    │   ├── sse.ts          # subscribeJob (EventSource, GET) + chat stream
    │   │                   # (fetch + ReadableStream, since EventSource can't POST)
    │   ├── useJobAction.ts # shared hook: submit a 202 job → subscribe to its
    │   │                   # SSE progress → busy/message/error state
    │   ├── theme.tsx       # dark default, persisted to localStorage
    │   ├── onboarding.ts   # the client-side "skip for now" flag (DECISIONS #15)
    │   └── format.ts       # PIPELINE/TERMINAL status lists, score + status colors
    ├── components/
    │   ├── ui.tsx          # shared primitives: Button, Card, Eyebrow, Badge,
    │   │                   # ScoreBadge, StatusChip, StatTile, Spinner,
    │   │                   # EmptyState, Loading, ErrorNote + inputStyle /
    │   │                   # textareaStyle — extend this, don't re-style per screen
    │   ├── ViewToggle.tsx  # table ⇄ board switch, rendered into the topbar slot
    │   └── shell/          # AppShell (layout + onboarding guard + topbar-slot
    │                       # context), Sidebar, Topbar (JobsIndicator,
    │                       # ChangesTray, theme toggle), ChatDrawer
    └── screens/            # one file per route in App.tsx
```

Every file in `screens/` is routed from `App.tsx`; there is no scaffold screen to
wire a new route through (the leftover `Placeholder.tsx` was deleted 2026-08-02).
A new screen gets its own file plus a route.

## Non-negotiable conventions

- **Inline styles + CSS custom properties, NOT Tailwind** (DECISIONS #12). The
  delivered Claude Design output is built that way and the app ports it 1:1.
  Don't add Tailwind "to clean it up" — it forks the styling system from the
  design source. Use `style={{ … }}` with `var(--token)`; add new tokens to
  `styles/tokens.css`, don't hardcode hex values.
- **Use the `border`/`borderColor` longhands, never the `border` shorthand**, on
  anything whose color varies by variant or state. Mixing the shorthand with
  `borderColor` across a rerender makes React warn and can mis-render (this was a
  real bug in `ui.tsx`).
- **Every request goes through `lib/api.ts`.** No `fetch()` in a screen, no URL
  strings outside that file. When you add an endpoint, add it to `api.ts` and its
  response shape to `types.ts` — and make sure it exists in `PLATFORM_SPEC.md` §5
  first (the spec stays authoritative).
- **Async actions are jobs, not awaited requests.** Anything that returns `202
  {job_id}` (evaluate, generate/export document, research company, search run,
  CV import, Sheets export, Drive upload) must go through `useJobAction` so the
  user sees live SSE progress. Don't block a button on a long request.
- **Server state is React Query; local UI state is `useState`.** Invalidate the
  relevant query on mutation success rather than hand-patching cached data.
- **Both themes must work.** The visual pass covers 14 screens × light/dark;
  anything new gets checked in both (`data-theme` on `<html>`).
- **Agent-proposed changes and user edits are visually distinct interaction
  families** (§9). Proposals get the PendingChangeCard approve/reject flow;
  the user's own forms (profile, notes, status) write directly and optimistically
  — that asymmetry is DECISIONS #19, not an inconsistency to smooth over.

## Verify before calling it done

```bash
npm run typecheck      # tsc -b --noEmit
npm run build          # tsc -b && vite build
```

Then run it against the backend: `npm run dev` and open
**http://localhost:5173** — Vite binds `localhost`/IPv6, so `127.0.0.1:5173`
won't load. Check the browser console is clean and the page has no horizontal
overflow, in both themes.

## When you finish a milestone

Update `PROGRESS.md` at the repo root (tick the item, move the resume point) and
append one line to `PROGRESS_LOG.md`.
