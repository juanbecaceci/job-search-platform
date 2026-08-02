# Agent Instructions — Job Search Platform

Self-hosted, single-user job search platform. **Stages 0–5 and the Pre-publish
checklist are complete** (spec → SQLite + read API → write ops + async jobs →
agent adapter → frontend → publish-readiness); the only open action is adding a
remote and pushing — see the resume point in `PROGRESS.md`, which has a trap
about *which* refs may be pushed.

## Which file answers what — open only what you need

| You need | File | How to use it |
|---|---|---|
| Current stage, resume point, how to run, real-data state | [PROGRESS.md](PROGRESS.md) | **read first, every session**; update it the moment you finish a task |
| Settled architectural calls (#1–#34) | [DECISIONS.md](DECISIONS.md) | check before proposing anything different; cite the entry number to reopen one |
| Data model, API paths, SSE events, view map | [PLATFORM_SPEC.md](PLATFORM_SPEC.md) | **never read end to end** — jump to §3 enums, §4 entity shapes, §5 API reference, §6 SSE, §7 global shell, §8 view map, §9 UX rules |
| Backend layout + conventions | [api/CLAUDE.md](api/CLAUDE.md) | before writing anything in `api/` |
| Deterministic-tools rules | [core/CLAUDE.md](core/CLAUDE.md) | before writing anything in `core/` |
| Frontend layout + styling conventions | [frontend/CLAUDE.md](frontend/CLAUDE.md) | before writing anything in `frontend/` |
| "Why is it like this?" about a past change | [PROGRESS_LOG.md](PROGRESS_LOG.md) | append-only session history; **not** orientation reading |
| Design system / prototype brief | [DESIGN_BRIEF.md](DESIGN_BRIEF.md) | design-only work |
| The SOPs the agent itself follows per module | `workflows/*.md` | injected into chat prompts by `api/agent/prompt_builder.py` — read the one file for the module you're touching |

Don't reconstruct status from `git log`, and don't batch `PROGRESS.md` updates to
the end of a session.

## What this is

The public, genericized version of a private job-search automation system
(WAT framework: Workflows / Agent / Tools). Anyone who clones this repo runs it
locally with **their own agent CLI subscription** — no `ANTHROPIC_API_KEY`, no
hosted backend, no shared data. v1 ships only the Claude Code adapter; the
interface reserves room for others (DECISIONS #5).

```
React SPA (frontend/) ◄─HTTP+SSE─► FastAPI (api/) ◄─► SQLite (data/, gitignored)
                                       ├─ core/   deterministic tools (ported as-is)
                                       └─ agent/  AgentAdapter → claude -p (user's subscription)
```

## Hard rules (non-negotiable, not up for re-derivation)

1. **`data/` is the only place user data lives.** Never write personal info,
   credentials, or generated content anywhere else. `scripts/check_no_secrets.py`
   is installed as a pre-commit hook — if it blocks a commit, fix the content,
   don't bypass the hook.
2. **No Anthropic/OpenAI API key, ever** (DECISIONS #10). Reasoning happens
   through the user's own agent CLI in `api/agent/`, resolved via
   `AGENT_CLI_PATH` (DECISIONS #13). If a task seems to need an API key, the
   design is wrong — stop and reconsider, don't add one.
3. **`core/` is deterministic only** — see [core/CLAUDE.md](core/CLAUDE.md).
4. **Human-in-the-loop is strict** (DECISIONS #6): the agent proposes
   `pending_changes` diffs and never writes to the DB;
   `api/services/change_applier.py` is the only apply path, and its write surface
   is an explicit per-field catalog (DECISIONS #21/#22). Two deliberate
   carve-outs you must know before touching `api/agent/` or the job handlers:
   direct work-product writes bypass the gate (DECISIONS #14), and the user's own
   profile forms write directly (DECISIONS #19). Read those entries rather than
   inferring the boundary — and see [api/CLAUDE.md](api/CLAUDE.md) for the rest
   of the backend conventions.
5. **UI language is English.** `workflows/*.md` intentionally mix Spanish/English
   (they're SOPs for the agent's own operation, not user-facing) — don't
   "fix" that (DECISIONS #8).
6. **Genericization discipline**: if you ever port more files from the private
   `Copilot` repo, grep the incoming content for personal names, employers,
   metrics, or dates before committing (see git history of `cd2ee06` for the
   pattern used). Never reuse that repo's git history (DECISIONS #7).

## Session checklist

1. Read `PROGRESS.md` → confirm current stage and resume point.
2. Open only the directory `CLAUDE.md` and `PLATFORM_SPEC.md` section your task
   needs (see the table above).
3. Check `DECISIONS.md` before proposing a different architecture.
4. Do the work.
5. Update `PROGRESS.md` (tick items, move the resume point) before ending the
   session — this is what saves the next session from re-deriving state. Append
   one line to `PROGRESS_LOG.md`.
6. If you made a new irreversible/architectural call, append it to
   `DECISIONS.md` in one line + rationale.
