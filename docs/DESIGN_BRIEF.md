# Design Brief — Job Search Platform UI

> Prompt for the UI design session (Claude Design). Attach `PLATFORM_SPEC.md` with it.

You are designing the complete web UI for "Job Search Platform" — a self-hosted,
single-user job search automation platform. The attached PLATFORM_SPEC.md is the
binding contract: follow its entities, enums, API shapes, view map (§8) and UX
rules (§9) exactly. Do not invent data fields or screens that aren't in the spec.

## Product personality
"Mission control for your job hunt." Calm, confident, data-dense but breathable.
The user is running a serious pipeline, not browsing a job board. English UI.

## The signature element (make THIS the eye-catcher)
The platform's differentiator is the visible AI agent working alongside the user.
Invest the design energy here:
1. ChatDrawer — a global right-side panel. Agent responses stream in token by
   token; tool-use steps appear as subtle inline chips ("Reading scoring config…").
   It should feel alive, like watching someone work.
2. PendingChangeCard — the agent proposes changes as diffs (old → new, field by
   field) with Approve / Reject. This card is the soul of the product: make the
   proposed-vs-applied distinction unmistakable (e.g. a distinct accent border/
   glow reserved ONLY for pending agent proposals, nothing else in the app uses it).
3. Live search progress — when a search runs, per-source progress bars fill in
   real time with counts (fetched / new / duplicates). Satisfying to watch.
Everything else stays visually quiet so these three moments stand out.

## Motion rules (fluid, never busy)
- Animate state changes only: drawer open/close, kanban card drop, progress bars,
  token streaming, count-ups on dashboard stat tiles, approve/reject resolution.
- 150–250 ms, ease-out; subtle scale/fade, no bounces, no parallax, no looping
  decorative animations, nothing animates while idle.
- Streaming text and progress bars are the only continuous motion, and only
  while real work is happening.
- Respect prefers-reduced-motion.

## Visual system
- Neutral, slightly warm base; generous whitespace; strong typographic hierarchy.
  Light and dark themes.
- ONE brand accent color, used sparingly (primary actions + the agent-proposal
  treatment).
- Semantic score scale, used consistently everywhere a score appears:
  EXCELLENT (80–100) / GOOD (60–79) / ACCEPTABLE (45–59) / DISCARD (0–44),
  plus a neutral for unevaluated. Score is always shown 0–100.
- Pipeline status chips: one consistent chip system for the 15 states; terminal
  states (Rejected / Withdrawn / Ghosted) are always muted/desaturated.
- Tabular data (positions table) is compact and scannable; cards (kanban,
  top-5) are richer.

## Screens to design (in this order, iterating with me)
1. Global shell: sidebar + ChatDrawer + JobsIndicator + ChangesTray
2. Dashboard (/) — stat tiles, by-source breakdown, top 5, recent searches
3. Positions table + Kanban board (/positions, /positions/board)
4. Position detail with tabs (/positions/:id) — incl. Evaluation tab with score
   dial + per-criterion bars with rationale, and History timeline
5. Searches list + 3-step new-search wizard + search detail with live run progress
6. Analytics — source effectiveness, funnel, stale applications
7. Profile, Templates (with version history), Scoring editor (live Σ weights =
   1.0 validation), Memories, Settings
8. Onboarding wizard (first run: drop CV PDF → agent builds profile via chat)

## States you must design, not skip
- Empty states for a fresh install (no data anywhere) — each one points to the
  next action.
- Loading, streaming, job-running, error, and "agent proposal pending" states.
- Approve/reject resolution feedback.

Desktop-first (min 1280px), degrade gracefully to tablet. Build with React +
Tailwind. Start with screen 1 and 2 only; wait for my feedback before continuing.
