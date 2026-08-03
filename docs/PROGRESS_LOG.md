# Progress log

> Append-only session history, newest first. **Not** required reading — a
> resuming session needs [PROGRESS.md](PROGRESS.md) (status + resume point) and
> [DECISIONS.md](../DECISIONS.md) (settled calls). Come here only to answer
> "why is it like this?" about a specific past change.

---

- 2026-08-02 — **Root cleanup, pinned deps, two more test modules, social card.**
  `PROGRESS.md` / `PROGRESS_LOG.md` / `DESIGN_BRIEF.md` → `docs/` via `git mv`;
  root is now `README.md`, `DECISIONS.md`, `PLATFORM_SPEC.md`, `LICENSE`,
  `CLAUDE.md` (the harness requires that one in root) plus config. Order of
  operations was deliberate: wrote **`tests/test_docs_links.py`** first, moved
  the files, then let the failing test enumerate every broken reference — 5
  files, plus 8 prose mentions the link checker *can't* see, found with grep.
  Two link-checker false positives were real signal about the test, not the
  docs: `config/defaults/*.md` are CV templates whose `[LinkedIn]({{LINKEDIN_URL}})`
  is filled at render time, so `{{…}}` targets are now skipped.
  Also fixed two stale claims in root `CLAUDE.md` while there: it still said the
  only open action was "adding a remote and pushing" (published since), and
  cited DECISIONS `#1–#35` (now #37).
  **`requirements.txt` pinned and translated.** Checked `Requires-Python` on all
  17 packages before pinning rather than assuming — none demand >3.11, so the
  3.11 CI leg is safe. Dry-run install of both requirement files resolves.
  **`tests/test_claude_adapter_parser.py`** (12 tests) covers the NDJSON→
  AgentEvent parser, which had been documented as "unit-testable" since Stage 4
  with no test. Beyond the happy path it pins the termination guarantee — an
  empty stream, a truncated stream and a doubled `result` line each yield
  exactly one terminal event — because a non-terminating parse hangs the caller
  rather than erroring.
  **`docs/social-preview.png`** rendered with Playwright from an HTML card
  (1280×640 @2x, palette from `tokens.css`). First render put the URL on top of
  the tech chips — absolute footer over flowed content; fixed by making the
  footer a flex row of the body. Source HTML lives in the session scratchpad,
  not the repo; recreate it if the card needs a change. Suite: **138 tests**.
- 2026-08-02 — **README restructured to lead with design, not installation.**
  It read as a user manual: what it is → how to install → 90 lines of
  LinkedIn/Indeed configuration → roadmap, with nothing about *why the code is
  shaped this way* until never. Rewritten as: pitch → hero screenshot → **How
  it's built** (five numbered ideas — the HITL write gate, the agent-as-subprocess
  with no API key, the determinism/judgment split, jobs+SSE, publishable-by-
  construction — each linking the file that implements it) → **For reviewers —
  the 5-minute tour** (a table naming `change_applier.py`, `prompt_builder.py` +
  its catalog test, `DECISIONS.md`, `PROGRESS_LOG.md`) → screenshots → features
  → tests → setup → layout. Setup moved from 30% to 45% down; LinkedIn and
  Indeed setup collapsed into `<details>`. **No content was cut** — the market
  settings, timing measurements and the `.mcp.json` rationale all survive.
  Every factual claim added was re-verified against the code (`AgentAdapter` is
  an ABC yielding `Iterator[AgentEvent]`; `claude_adapter` spawns a subprocess
  and parses `--output-format stream-json` NDJSON with the prompt on stdin;
  DECISIONS.md really has 37 entries; source count is 7, so "the other six" is
  right in the Indeed section — the old text said "five", which had silently
  excluded LinkedIn). All 20 local links checked to resolve.
- 2026-08-02 — **First tests and CI.** 105 pytest tests in `tests/`, hermetic
  (in-memory SQLite per test, `DATABASE_URL`/`AGENT_CLI_PATH` pinned in
  `conftest` before any `api.*` import, no network). Four modules:
  `test_change_applier.py` (whitelists tested for what they *refuse*, scoring
  and template versioning, position history events, `edited_at` authorship,
  stale-export invalidation), `test_agent_protocol_catalog.py` (parses the
  writable-targets table out of `prompt_builder._OUTPUT_PROTOCOL` and
  cross-checks it against `SUPPORTED_TARGETS` + the `_*_EDITABLE` sets both
  ways — the test `api/CLAUDE.md` has described since Stage 4), `test_scoring.py`
  and `test_location_filters.py`. **Mutation-checked, 5/5 caught:** widening
  `_POSITION_EDITABLE` to include `score`; deleting `documents` from
  `SUPPORTED_TARGETS`; `>=` → `>` on the band boundary; disabling the
  weight-sum invariant; making `_authorship` always return `agent`.
  `pytest.ini` puts both the repo root and `core/` on `pythonpath` — `core/`
  modules import each other as siblings, so `from env_config import …` fails
  otherwise (same fixup `search_run.py` does at runtime).
  **`check_no_secrets.py` gained `--all`** (scan `git ls-files` instead of the
  staged set): CI stages nothing, so the job was going to pass having read 0
  files. Verified: staged mode reports 0 scanned, `--all` reports 155.
  `.github/workflows/ci.yml` = pytest on 3.11/3.13 · frontend typecheck+build ·
  a from-zero migration rebuild incl. `downgrade base` · the secrets sweep; the
  migration and demo-seed jobs were simulated locally before committing the
  workflow. ⚠️ One self-inflicted scare worth remembering: the mutation script
  restored files with `Path.write_text`, which on Windows rewrites LF as CRLF —
  `core/evaluate_position.py` came back byte-different (487 lines = 487 bytes)
  and would have landed as a whole-file rewrite. Restored from a `cp` backup.
  Use binary copies, not `write_text`, to restore.
- 2026-08-02 — **Closed the three defects the screenshot review surfaced.**
  (a) `PositionCard` gained `date_discovered` (`api/schemas/position.py`,
  `frontend/src/lib/types.ts`, the table cell in `Positions.tsx`), so the
  `Discovered` column stopped rendering an em dash on every row; spec §5 now
  lists the compact-card fields. (b) Date formatting is pinned to `en-GB` in
  `lib/format.ts`. **Correcting the previous entry: "1 ago, 20:31" was not a
  formatting bug** — `toLocaleString(undefined, …)` inherits the OS locale, and
  this machine is `es-ES`, so an English UI rendered Spanish month names;
  measured in-browser before fixing. (c) All user-facing Spanish is gone
  (DECISIONS #37): `ScoreCategory` → `EXCELLENT/GOOD/ACCEPTABLE/DISCARD`,
  `SalaryGate.A_VALIDAR` → `NEEDS VALIDATION`, the two unnamed markers are now
  constants (`BELOW SALARY FLOOR`, `NEEDS VALIDATION`), seeded criterion names
  and the evaluator's `recommended_action` strings translated. Migration
  `a3f1c9d47b20` rewrites stored values across `positions` and every
  `scoring_configs` version; verified on a **copy** of the real `app.db` (539
  positions — counts identical before/after, `downgrade` round-trips exactly),
  never against the original. `normalize_salary_gate` keeps the Spanish
  spellings as input aliases. `npm run typecheck` and `vite build` clean (104
  modules); demo re-seeded and all 32 screenshots re-captured.
- 2026-08-02 — **Screenshots for the README, from a synthetic dataset**
  (DECISIONS #36). The repo had no images at all, so nothing showed that the 14
  screens exist. Capturing from `data/app.db` was not an option — it holds a
  real search (211 positions, live applications, the author's CV), and the most
  compelling screens are the ones that leak the most. Added
  `scripts/seed_demo.py`: invented companies/positions/profile/pending changes,
  double-guarded against running anywhere but a throwaway DB. Captured all 14
  screens (plus the changes tray and the agent drawer) in light and dark via
  Playwright at 1.5x into `docs/screenshots/` (32 images, 4.9 MB), and rebuilt
  the top of the README around them. Two pre-existing UI bugs surfaced while
  reviewing the captures and were **left unfixed**, deliberately, since they
  change the API contract: (a) the positions table renders a `Discovered`
  column that can never populate — `PositionCard` carries no `date_discovered`
  in either `api/schemas/position.py` or `frontend/src/lib/types.ts`; (b) the
  searches list renders "1 ago, 20:31" for a last-run timestamp. Also worth a
  decision someday: the seeded scoring criteria are Spanish (`Alineacion con el
  perfil`, missing accent included) and `ScoreCategory` is Spanish end to end,
  both user-facing, against the English-UI rule in `CLAUDE.md`.
- 2026-08-02 — **Wired geo filtering into `search_run` and made
  `searches.markets` mean something** (DECISIONS #35). The column had been
  write-only: `POST /searches` accepted it, `change_applier` let the agent edit
  it, `prompt_builder` advertised it as editable config, `sheets_export` wrote
  it out — and nothing read it, while the wizard hardcoded `markets: []`. So
  "limit this search to Europe" was a request the system accepted, persisted
  and ignored. Meanwhile the runner never geo-filtered while the four CLIs did,
  so the same search returned different results from the UI and the terminal.
  Juan's calls: **union** semantics (a position survives if any listed market
  could take it, empty falls back to `TARGET_REGION`) and **filter by default**
  rather than opt-in.
  · New `filter_by_regions` / `effective_regions` in `core/location_filters.py`.
  · `search_run` filters per source before dedupe; `fetched` stays the raw
    count and `filtered_out` sits next to it, so the funnel reads "the source
    returned N, geography removed M". Also `total_filtered_out` + the resolved
    `regions` on the job result, a `Filtered` column in the per-source table,
    and the count in the live progress message. **Surfacing the drop is the
    load-bearing part** — #32 records that the CLIs shipped with
    `--market latam-argentina` as a default and silently emptied cloners'
    searches; wiring the filter without the counter reproduces that bug inside
    the app.
  · `GET /searches/defaults` now serves `regions` + `default_region` from the
    `REGIONS` table so the wizard keeps no second copy; wizard step 3 gained
    market chips and states what an empty selection falls back to.
  · **The asymmetry worth remembering**: `filter_by_regions` returns the list
    untouched when it resolves to "no filtering", so non-remote roles survive —
    whereas `is_region_eligible` rejects non-remote roles *before* looking at
    the region (line 152, ahead of the worldwide check). Copying the CLI
    behaviour would have made the `worldwide` default silently drop every
    on-site role, contradicting "filters nothing" as promised in
    `.env.example`, `core/CLAUDE.md` and #32.
  · Verified: 13 pure-logic checks (union, fallback, worldwide-wins,
    legacy alias, unknown key stays permissive, non-remote both ways, input not
    mutated) and 11 handler checks against a **throwaway DB** with a fake
    fetcher — the script aborts if the engine resolves to `app.db`. `tsc -b
    --noEmit` and `vite build` clean. No live search was run, so real data is
    untouched.
  · ⚠️ Behaviour change for Juan specifically: his `TARGET_REGION` is
    `Argentina-LATAM` (→ `latam`), inherited from the old `.env.example` rather
    than chosen, so unmarked searches now filter to LATAM. Noted in
    `PROGRESS.md` with the one-line way out.
- 2026-08-02 — **Repo is public; audited the published result, then renamed the
  local branch to `main`.** The audit ran against a **fresh clone of the public
  repo** and scanned **all 9 commits** — every version of every file, 157 paths
  ever added — which is the check every earlier sweep had missed: they all read
  the tip, and a file committed then deleted still lives in history. Clean on
  every axis (0 paths ever under `data/`, 0 credential/key/DB files, 0 API keys
  or private keys, 0 absolute local paths, `.env.example` neutral in every
  historical version, largest blob is `package-lock.json`). The opaque-looking
  ids were all traced to npm integrity hashes rather than waved off. Two things
  are public by design and were reported as such rather than as "zero findings":
  the author's name (`LICENSE`, commit metadata, the repo URL cited in the docs)
  and the GitHub `users.noreply` alias — the personal `@gmail.com` appears
  nowhere. Then `git branch -m stage5-complete main`: tracking survived the
  rename, so local and remote share a name at last. `PROGRESS.md`'s git-state
  and publication blocks were rewritten rather than patched — they had grown
  into layered warnings about traps that no longer exist ("No remote is
  configured", "push `stage5-complete` alone"), and renaming branches inside
  stale advice would have preserved the staleness. The closed Pre-publish entry
  keeps its original text with a RESOLVED pointer, since that section is a
  record. Also deduped the surname-baseline note, which had ended up in two
  places — the usual way two notes start disagreeing.
- 2026-08-02 — **Deleted local `main`** (was `922e5e1`), closing the `--all`
  trap for good: no local ref carries `3948e07` / `ce4c31a` any more, and the
  only branch left is `stage5-complete`, tracking `origin/main`. Checked first:
  the only tracked files `main` had that the published tree lacks were
  `core/parse_profile.py` and `frontend/src/screens/Placeholder.tsx` — the two
  dead files deliberately deleted earlier the same day — so nothing of value
  went with it. Reflog-recoverable for now via `git branch <name> 922e5e1`.
  ↳ Found while verifying: the surname check now matches **3** tracked files,
  not 1. All three are self-inflicted and benign — `LICENSE`, plus the repo's
  own public URL cited in `PROGRESS.md` and `PROGRESS_LOG.md`. The baseline is
  recorded in `PROGRESS.md` so the next session doesn't read 3 as a regression.
  One was worth fixing though: this log had spelled out the literal
  `users.noreply` address, which check #4 (emails) does **not** exclude, so it
  would have reported an email finding on every future sweep. Reworded.
- 2026-08-02 — **Deleted `backup/pre-squash-20260731`** (was `097c68f`), on
  Juan's call, to shrink the `--all` blast radius now that a remote exists.
  Checked before deleting rather than after: its tree differs from the published
  root `3dc75c5` by **one line of `PROGRESS.md`**, so the branch held no content
  the public repo lacks — only the granular 10-commit history, 4 commits of
  which were exclusive to it (`097c68f`, `a29d6ac`, `b77f4bd`, `ce4c31a`). Those
  are dangling but reflog-recoverable for ~30–90 days via
  `git branch <name> 097c68f`. **The trap is only half closed**, which is worth
  being explicit about: `ce4c31a` (author's name in 4 files) is now on no
  branch, but local `main` (`922e5e1`) still carries `3948e07` (3 files). `main`
  serves no purpose now that `stage5-complete` tracks `origin/main` — deleting
  it is the step that actually ends this.
- 2026-08-02 — **PUBLISHED.** `stage5-complete` pushed to
  https://github.com/juanbecaceci/job-search-platform as `origin/main`, tip
  `f5dc1d2`. Sequence: re-ran the six mechanical checks against that exact
  commit (155 files, 0 under `data/`, author only in `LICENSE`, 0 emails /
  absolute paths / credential strings, `check_no_secrets.py` exit 0), confirmed
  the remote had **0 refs** (an empty repo — a GitHub-generated README would
  have collided with the squashed root), then `git push -u origin
  stage5-complete:main`, an explicit refspec and never `--all`. Verified after:
  the remote holds only `main`, `origin/main` == local HEAD, the published root
  is `3dc75c5` with no parents (no pre-squash history), and `data/` contributes
  0 paths. One thing the six checks never covered, checked separately and clean:
  **commit author metadata** — the commits carry the GitHub `users.noreply`
  address, not a personal one, so the file-content sweep wasn't hiding a leak in
  the header. (Written without the literal address on purpose: spelling it out
  makes check #4 of the sweep report an email finding forever after.) `stage5-complete` now tracks
  `origin/main`, which means the `--all` trap finally has a remote to fire at —
  local `main` and `backup/pre-squash-20260731` are still name-bearing.
- 2026-08-02 — **README status refreshed before creating the GitHub repo.** Its
  status blockquote still said "Remaining before a public release: first-run
  onboarding docs and a final secrets sweep" and the roadmap still had
  `- [ ] final secrets sweep, design-source decision` — both closed days ago.
  Left as they were, the first thing a visitor read would have been "this may
  still contain secrets", the opposite of what six checks verified. Now: status
  says feature-complete and ready to clone (naming `00_first_run.md` and the
  closed checklist), and the roadmap line is ticked with *why* the design
  prototype isn't shipped. Swept the rest of the README for the same failure
  mode — no other stale claim, no unchecked boxes left.
- 2026-08-02 — **Harness audit before adding the remote** (asked for as a
  pre-push check, and it earned its keep). Structure was sound: the 4
  `CLAUDE.md` files exist and are cross-referenced, 0 broken markdown links
  across the 9 docs, `PLATFORM_SPEC.md` §3–§9 match what the routing table
  promises, `api/`+`core/`+`frontend/` layouts match the real trees file by
  file, and nothing stale ships (0 tracked `__pycache__`/`.pyc`, 157 files).
  Four staleness bugs fixed: root `CLAUDE.md` advertised DECISIONS **#1–#26**
  when there are **34** (the missing 8 are the MCP/Indeed/LinkedIn/geography
  calls — exactly the ones a new session would re-debate) and still said the
  Pre-publish checklist was pending; `core/CLAUDE.md` said `google_auth.py` was
  the only module written rather than ported (`env_config.py` is the second, 14
  modules now). **The real find: `workflows/07_interview_prep.md` was orphaned**
  — no module mapped it in `_MODULE_WORKFLOWS`, no `interview` value in the
  `Module` enum, zero references anywhere, so an SOP that was written *and*
  migrated in the 2026-07-31 pass never reached the agent, while `CLAUDE.md` and
  the README both claimed every workflow is injected. Juan's call: map it to
  **`positions`**, since `Interview Scheduled` is a position status and prep is
  asked for from a position's chat. Verified: all 8 workflows now reachable, no
  ghost filenames, `_MODULE_WORKFLOWS` keys ↔ `Module` enum agree both ways, and
  all 8 module prompts assemble against an in-memory DB with the output protocol
  intact. Cost noted: the `positions` prompt goes 11.4k → 16.4k chars per turn.
  **Two dead files deleted** in the same pass, once Juan confirmed: 
  `core/parse_profile.py` (extracted CV text so a human could paste it into a
  chat that wrote `context/professional_profile.md` — a pre-platform flow;
  `api/jobs/handlers/import_cv.py` replaced it with the same `pypdf` extraction
  plus a `pending_changes` proposal, and its docstring still taught `context/raw/`
  + `.tmp/` paths that don't exist here) and
  `frontend/src/screens/Placeholder.tsx` ("This screen is being wired up next",
  with all 14 wired). Both verified unreferenced first, including `core/`'s
  sibling-import style. `requirements.txt` is unchanged — `pypdf` is still used
  by `import_cv.py` and `python-docx` by `generate_cv.py` /
  `generate_cover_letter.py`. Verified after: all 13 `core/` modules import,
  `api.main` imports, `tsc -b --noEmit` clean, `vite build` clean at **104
  modules — the same count as before**, which is itself the proof `Placeholder`
  was never in the graph. `core/CLAUDE.md` now says 13 modules (11 ported + 2
  written here) and records why `parse_profile.py` must not come back;
  `frontend/CLAUDE.md`'s "delete it rather than wiring through it" note is gone.
- 2026-08-02 — Committed everything (`4e78215`: the 2026-07-31 workflow
  migration + both of today's items) and ran the **final secrets sweep on the
  committed tree**, which closes the Pre-publish checklist. Six checks clean: no
  tracked path under `data/`, `data/` ignored, `check_no_secrets.py` exit 0
  (also as the pre-commit hook), the author's name in `LICENSE` and nowhere else,
  no tracked env/credential/DB files, and no emails, absolute local paths,
  credential-shaped strings or opaque Sheets/Drive ids anywhere tracked. Noted
  but deliberately left: the seeded USD 3,500/month salary floor is an
  opinionated default a cloner inherits (configurable, documented, not personal
  data). Nothing now blocks publication except Juan's go-ahead — and the push
  must be `stage5-complete` alone, never `--all`.
- 2026-08-02 — Closed `frontend/design-reference/`: **not shipped**. Juan chose
  dropping it over genericizing, once the inspection showed the cost: 55 name
  occurrences of which only 1 is the cosmetic sidebar label — 47 are the
  `<Name>DesignSystem_302711.*` JS global namespace every component resolves
  through, 7 are `_ds/` asset paths — and the bundle that defines that namespace
  isn't in the repo, so the file renders as an unstyled skeleton anyway.
  Gitignored (Juan keeps the local copy), DECISIONS #12 rewritten to name
  `frontend/src/styles/tokens.css` as the design source of record. Corrected the
  old note's "references `_ds/…` 55 times" — that count was the name, not the
  asset refs. Found while updating the git-state note: **the squash already
  happened on 2026-07-31** — `stage5-complete` is a single root commit whose only
  name-bearing file is `LICENSE`, while `main` (6 commits) and
  `backup/pre-squash-20260731` (10) still carry it in history. So the last item's
  history question is settled and the live risk is which refs get pushed. Next:
  commit the working tree, then the final secrets sweep.
- 2026-08-02 — Closed the "reconcile core dotenv loading" pre-publish item.
  `sheets_manager.py` + `google_auth.py` now call `env_config.load_env()`
  instead of a CWD-relative `load_dotenv("data/credentials/.env")`. Measured the
  bug first against HEAD, from a CWD outside the repo: `SPREADSHEET_ID` was
  `None` and the token path pointed at a file that wasn't there. Two things the
  item didn't anticipate: `google_auth.py`'s `CREDENTIALS_FILE`/`TOKEN_FILE`
  defaults had the same CWD bug (new `env_config.repo_path()` fixes them, and
  `sheets_manager.py`'s dead duplicates of both are gone), and the Sheets/Drive
  CLIs were **already broken standalone** — they import `core.google_auth`,
  which needs the repo root on `sys.path`, but `python core/sheets_manager.py`
  puts `core/` there, so both raised `ModuleNotFoundError: No module named
  'core'`. The three Google modules now self-bootstrap the root rather than
  trusting the caller, because `api/routers/positions.py` imports one of them
  with no path fixup. Verified 11/11 from a foreign CWD across both entry-point
  shapes; read-only, no Google call. Next: `frontend/design-reference/` (needs
  Juan's decision), then the final secrets sweep.
- 2026-07-31 — Measured the `--strict-mcp-config` pre-publish item instead of
  reasoning about it, and it flipped. (1) The flag **breaks the Indeed account
  connector**: same `fetch_indeed` call, baseline 10 positions in 37.8s, with
  the flag `McpSourceUnavailable` in 11.9s — DECISIONS #29's corollary is now
  measured. (2) The privacy premise it was based on is **false**: Gmail and
  Drive are permission-denied from every agent call, with and without an
  allowlist ("permission … not granted in this non-interactive session"), so
  the headless default-deny of DECISIONS #27 already contains them. Recommend
  closing the item as "not adopting". Method note worth keeping: two earlier
  probes asked the agent "do you have tool X?" and returned a confident ABSENT
  **for Indeed itself** — self-report is invalid here; a probe must be
  task-shaped, carry a system prompt, and be validated against Indeed as a
  known-reachable control before its answer means anything.
  Closed the item as "not adopting" and wrote the harness up to match:
  DECISIONS #34 (the call + both measurements + the method corollary),
  `api/CLAUDE.md` (the default-deny is load-bearing; never probe tool
  availability by asking the agent), the checklist item, the resume pointer,
  and the README roadmap. Three of six pre-publish items now closed.

- 2026-07-31 — Onboarding assets for cloners. New `workflows/00_first_run.md`
  (the first-run SOP: market vars, agent CLI, CV import + its approval step,
  optional Google, a small first search, evaluation as a separate step, plus a
  troubleshooting table of the traps a first run actually hits), wired into the
  `onboarding` module ahead of the profile SOP. Rewrote
  `01_build_profile.md`, which still described the pre-platform flow
  (`context/professional_profile.md`, `core/parse_profile.py`, "use the Edit
  tool") and was being injected into the `profile` and `onboarding` chats —
  the agent was being told to write files this repo doesn't have. Also closed
  a gap in the earlier region work: `workflows/` was excluded from that sweep
  and still documented `markets = Argentina-LATAM remote` plus the pre-rename
  flags. Found along the way: CV upload is **PDF only** (422 otherwise) and
  nothing told the user. 45 checks over prompt assembly, workflow existence,
  dead paths and region defaults.

- 2026-07-31 — Migrated the rest of the workflow corpus (`03`–`07`) off the
  pre-platform flow: `.tmp/` scratch files, a `context/` directory that doesn't
  exist here, `output/cvs/…` paths that would have violated hard rule #1,
  Sheets as the system of record, Upwork as a source. Kept the operational
  knowledge that was actually valuable (per-source filtering mechanics, the
  anti-429 levers, the keyword-axis strategy) and rewrote the mechanics around
  the real jobs and endpoints. Two things the old text stated backwards and the
  agent was being told to believe: that evaluation sets `Rejected`/`Evaluating`
  (it deliberately never changes status) and that dedupe keys on
  `company+role+url` (URL is precisely what it must not use — Indeed rotates
  it). `04` now reads weights from the active scoring config instead of
  hardcoding the seeded defaults, which matters since this install runs v2.
  131 checks over the whole corpus.

- 2026-07-31 — Secrets sweep, code/UI half. Fixed the two tracked files that
  named the author: `Sidebar.tsx` now reads `full_name` from `profile_basics`
  (React Query, same key as the Profile screen, so it updates when you edit it —
  and it's the correct behaviour for any cloner, not just a redaction), and the
  `tokens.css` header describes the file as the design source of record instead
  of crediting a person. All mechanical checks pass. The sweep also turned up
  something the checklist didn't anticipate: `PROGRESS_LOG.md` / `PROGRESS.md` /
  `DECISIONS.md` carry real job-search detail — a named employer he applied to
  with slug and date, CV size, Drive folder — which is a bigger disclosure than
  the name in `LICENSE`. Juan chose to scrub the particulars and keep the docs,
  so that's done too: every engineering lesson survives, the identifying details
  don't. He also chose to squash the branch into one clean commit rather than
  carry the pre-scrub tree in history (DECISIONS #33).

- 2026-07-31 — Closed the first pre-publish item: search geography is now
  configuration, not code. Bigger than the `Argentina`/`AR` literals it started
  as — `core/location_filters.py` could only filter for LATAM and the four
  standalone CLIs called it *by default*, so a cloner silently lost every
  non-LATAM job. Now a `REGIONS` table driven by `TARGET_REGION`, default
  `worldwide` (filters nothing). New `core/env_config.py` fixes the prerequisite:
  the fetchers' bare `load_dotenv()` never read `data/credentials/.env`, where
  the README tells users to put their config, so the setting would have been
  inert. Legacy `--market` values and the old `Argentina-LATAM` env string are
  aliased, not ignored. 49 pure-logic checks + CLI/API import checks; the
  `search_run` handler is untouched and still never geo-filters. See
  DECISIONS #32.

- 2026-07-31 — Wired `linkedin` into `search_run`, closing the biggest discovery
  gap: it was 219 of 539 positions in the real DB but unreachable from the new
  runner. Plain in-process HTTP, no agent turn. Found and fixed two latent path
  bugs in `core/scrape_jobs.py` while doing it — `CONFIG_PATH` and
  `LI_DESC_CACHE_PATH` were CWD-relative, so imported by a job handler they
  resolved against uvicorn's start directory, and the description cache (scraped
  job text = user data) wrote to `.tmp/` outside `data/`, breaking hard rule #1.
  Both now resolve from the repo root, cache under `data/cache/` (DECISIONS #31).
  Default location is `Worldwide`, not `Argentina` — verified both return
  results. 10/10 descriptions in 27s cold, 1s warm from cache.

- 2026-07-30 — Wired the `indeed` source through its MCP connector. Probed all
  the newly-connected job MCPs first (Dice/ZipRecruiter/Snagajob/Aquent/Upwork):
  only Indeed returns LATAM-relevant results, Upwork is client-side (hiring
  freelancers, not finding work), Snagajob/Aquent are the wrong segment
  entirely. Proved the backend can reach connectors at all — the standalone
  binary at `AGENT_CLI_PATH` sees them, and `claude -p --allowedTools ...`
  calls them — which is why `AgentTask.allowed_tools` had to exist. Also
  disproved the long-standing "Indeed MCP is Claude-Connector-only" note:
  anonymous RFC 7591 dynamic client registration returns 201, so a cloner can
  self-authorize (DECISIONS #28). New `api/agent/mcp_sources.py` (NOT `core/` —
  it's an LLM call, DECISIONS #27). Live E2E: 20 real positions in 40s.
  Deferred deliberately: `--strict-mcp-config` (now a pre-publish item) and
  `get_job_details` description enrichment.
  Follow-up same day: documented cloner onboarding for the source in the README.
  Tried shipping a committed `.mcp.json` and REVERTED it — measured that a
  pending-approval project server suppresses a working account connector, so the
  file broke `fetch_indeed` (27s/10 results without it, unavailable with it) and
  would break any cloner who already had Indeed connected (DECISIONS #29). The
  README documents a one-line `claude mcp add` instead. Also learned not to probe
  tool availability by asking the model to list its own tools — it reported "no
  MCP servers" moments after a live MCP call had returned 20 real positions.
  Then added description enrichment via `get_job_details`, which surfaced two
  Indeed quirks: `job_id` is session-scoped (so enrichment must happen in the
  same turn, not a later job) and `View Job URL` is a per-request redirect token
  (so the URL-keyed dedupe I had written was silently wrong — now company+role).
  Both recorded as DECISIONS #30. Live: 10/10 postings with real descriptions.
  Closing verification pass: frontend `tsc --noEmit` clean, backend booted on a
  throwaway DB and all 17 read endpoints returned 200 (the one 404 was an
  unseeded scoring config, not a regression — 200 after `seed_defaults.py`).
  Inspected `frontend/design-reference/design.html` before committing and left
  it OUT: it renders the author's real name and references design-system assets
  that don't exist in the repo. `check_no_secrets.py` does not catch names.

- 2026-07-29 — **Harness audit + reference cleanup** (docs only, no code
  touched). Split this log out of `PROGRESS.md`, which had grown to 608 lines and
  is mandatory every-session reading — ~45% of it was append-only history a
  resuming session never needs, so the required read is now 360 lines. Staleness
  fixed: `PROGRESS.md` still had "Stage 5 🔨 in progress" as a section heading
  while its own header said COMPLETE, and a Stage 5 item still claimed Sheets/
  Drive were unverified against live Google (contradicted 300 lines above by the
  live-verification notes); `api/CLAUDE.md` was missing `one_shot.py` and
  `requests_profile.py` from its layout (both added 2026-07-29); `core/CLAUDE.md`
  said "these 12 files were ported" when `google_auth.py` (13th) was written here,
  not ported, and its rules were still future-tense about Stages 2/3; `README.md`
  said "under construction" with Stages 2–5 unchecked and advertised LinkedIn/
  Indeed discovery that isn't wired into `search_run`; `DECISIONS.md` had #26
  before #25, which breaks the cite-the-number lookup the file's own header asks
  for. Reference hygiene: root `CLAUDE.md` gained a "which file answers what"
  table (the run commands and real-data state were buried in a 600-line file), its
  hard rules now cite decision numbers instead of "see DECISIONS.md entry on
  this", and rule 4 names the two carve-outs (#14 direct work-product writes, #19
  user profile forms) that a session inferring the HITL boundary would otherwise
  get wrong. **New `frontend/CLAUDE.md`** — `frontend/` is 38 tracked files and 14
  screens with no on-ramp, while `core/` and `api/` both had one; it documents the
  non-obvious calls (inline styles not Tailwind per #12, the border-longhand
  rule, all-requests-through-`api.ts`, 202-jobs-through-`useJobAction`, the
  localhost-not-127.0.0.1 gotcha) and flags `screens/Placeholder.tsx` as dead
  scaffold. Verified: all markdown links and backticked file paths in the harness
  docs resolve, DECISIONS is 1–26 with no gaps in order, and no file was
  mojibaked (PowerShell 5.1's `Get-Content` reads these UTF-8 files as cp1252 —
  the split had to go through `[System.IO.File]` with an explicit encoding).
- 2026-07-29 — **Sheets export run live — after recovering an application that
  would have been destroyed by it.** Before exporting I diffed the sheet against
  SQLite: the Applications tab had 4 rows, the DB 3. The extra row was NOT junk —
  it was a real application (CV + cover-letter Drive links, ATS contact), living
  only in the Sheet under a *stale position id* from the old manual workflow.
  The same job exists in SQLite under its current
  `<company>-<role>-<hash>` slug, which had been moved to **Applied** — but
  with **no `applications` row and no `documents`**. So the platform said
  "Applied" while the evidence of what was sent lived only in a spreadsheet the
  export was about to truncate. Backfilled it (1 application + 2 documents with
  their Drive URLs + an `application_update` event, actor=system, shaped exactly
  like `migrate_from_sheets.py`'s output), dry-run then applied on a copy, then
  on the real DB after a backup (`data/app.db.bak-backfill-20260729-012149`).
  The one-off recovery script read from Sheets; that does **not** loosen
  DECISIONS #2 — the *export* still never reads back, this was a repair in the
  same spirit as the original migration. Then ran the export through the real
  endpoint: 539/4/4/306 rows, headers intact, the recovered row present with its
  links. Lesson worth keeping: **diff before any truncate-and-rewrite** — the
  row counts alone (4 vs 3) were the only signal that real data was at risk.
- 2026-07-29 — **Google authorized + Drive upload verified live.** Ran
  `scripts/authorize_google.py` (both scopes, one token). Read-only connectivity
  confirmed for Sheets (4 tabs present) and Drive (the folder named by
  `GOOGLE_DRIVE_FOLDER_ID`, writable). Two real bugs found and fixed by the live E2E, neither visible in
  the API-level tests: (1) uploads went **flat** into the parent folder, ignoring
  the per-position subfolder convention the user's own Drive already used —
  added `ensure_folder()` (find-or-create, idempotent by name) and
  `_folder_name()` (`Company - Role`); (2) re-uploading **duplicated files** and
  stripped the recruiter-facing filename (`<Full-Name>-CV-<Role>-v1.pdf` was
  being renamed to `cv-v1.pdf`) — `upload_file(..., replace_existing=True)` now
  updates the existing file in place, so ids and shared links survive, and the
  exported filename is kept. Verified 11/11 against live Drive on a DB copy with
  a synthetic `ZZ Test Co` position; all test files/folders deleted afterwards
  and the folder confirmed back to its original 5 items.
- 2026-07-29 — **Stage 5 finished: Sheets export, Drive upload, visual pass.**
  · **Sheets export**: `replace_sheet()` in `core/sheets_manager.py` (truncate +
  rewrite, the missing SQLite→Sheets direction), `api/jobs/handlers/sheets_export.py`
  building all 4 tabs from the DB in the original tracker's column layout,
  `POST /export/sheets` (`409` unless opted in), and a Settings toggle backed by
  a **whitelisted** `PUT /settings` (DECISIONS #24/#25).
  · **Drive upload**: the stated blocker was `upload_to_drive.py`'s credential
  handling, and it ran deeper than expected — every Google entry point called
  `flow.run_local_server()` on an invalid token, i.e. a job handler would block
  a server thread on a browser prompt. Added `core/google_auth.py`: one token
  under `data/credentials/` carrying **both** Sheets+Drive scopes,
  `interactive=False` for servers (raises `GoogleAuthError` with a re-auth hint,
  never prompts), plus `scripts/authorize_google.py` for the one-time browser
  flow. Then `api/jobs/handlers/upload_drive.py` + `POST /documents/{id}/upload-drive`
  (`409` unless already exported) and an "Upload to Drive" button on the
  document cards. → DECISIONS #23.
  · **Visual pass DONE** (the long-standing OWED item): all 14 screens × light
  and dark = **28/28 clean** — no console errors, no page-level horizontal
  overflow, every screen rendering real content. Screenshots reviewed; light
  theme was never checked before and holds up.
  Verified: 15/15 API checks (settings whitelist rejects unknown keys, wrong
  types and int-as-bool; export `409`→`202` gating; the export job failing
  *before writing anything* with an actionable re-auth message; Drive upload
  `404`/`409` gating), and the row builders checked against the real DB
  read-only (539/3/4/306 rows, all header-aligned).
  ⚠️ **NOT verified against live Google**: the stored OAuth token is expired or
  revoked, so neither the real export nor a real Drive upload has run. Juan must
  run `python scripts/authorize_google.py` once; after that both are one click.
  ⚠️ I submitted one real export job during gating tests — it died at the auth
  step (progress 0.05) and wrote nothing, but it *would* have truncated the real
  spreadsheet had the token been live. Don't POST /export/sheets in tests
  against a config pointing at a real sheet.
- 2026-07-29 — **Widened the agent's write surface to the missing tables.**
  Juan asked for this after I flagged the gap: the agent could *converse* in 8
  modules but `ChangeApplier` only accepted 5 tables, so plausible proposals
  failed at approve time (his real DB had exactly that — a `job_sites_config`
  change, status `failed`, "Unsupported target_table"). Added whitelisted
  handlers for **`templates`** (writes a NEW active version, never in-place —
  same rollback logic as scoring), **`searches`** (config only; metrics/status
  excluded, running searches refused, sources validated against the `Source`
  enum), **`companies`** (not `name` — it's the dedupe key), **`applications`**
  (ISO dates parsed), and **`documents`** (`content_md`/`status`; a content
  change marks PDF/DOCX exports unavailable). Deliberately still NOT writable:
  `config/job_sites.json` (a tracked repo file, different blast radius than
  user data under `data/` — per-search settings live in the `searches` row) and
  `settings`. Added `SUPPORTED_TARGETS` + `is_supported()`, wired into
  `chat.py` so an unwritable proposal is marked `failed` with an explanation
  **when parsed**, not on approve; and rendered the whole catalog as a table in
  `prompt_builder`'s output protocol so the agent knows its own limits.
  → DECISIONS #21/#22. Verified: 29/29 unit checks on the new surface (incl.
  every guardrail above and "no advertised target is unreachable", which keeps
  the catalog and the dispatcher honest), 5/5 on the chat fail-fast via the
  `ScriptedAdapter`, plus regression checks that profile create/update/delete
  and the scoring weight-sum invariant still behave.
- 2026-07-29 — **Profile is now directly editable, and chat-editing actually
  works.** Juan asked for manual section editing in both the wizard and the
  Profile screen, plus editing via chat. Three pieces:
  (1) **Direct edits** — `PUT /profile/basics`, `POST/PUT/DELETE
  /profile/sections`, `POST /profile/sections/reorder` (new
  `api/schemas/requests_profile.py`), and a rebuilt `Profile.tsx` with inline
  basics editing, section add/edit/delete, and move up/down. These bypass the
  HITL tray on purpose → DECISIONS #19; this reverses the old §5 "chat-only"
  note, which explicitly invited the reversal. Templates/scoring stay chat-only.
  (2) **Editable proposals** — `PATCH /changes/{id}` rewrites a still-pending
  diff before approval (new `pending_changes.edited_at` column, migration
  `e722e2638ce1`, applied to the real DB after a backup + copy test). The wizard's
  review cards gained an Edit mode. The applier re-validates the edited diff, so
  an edit can't widen what the change may touch (regression-tested) →
  DECISIONS #20. Edited proposals apply as `updated_by="user"`.
  (3) **Chat editing FIXED** — `chat.py:_entity_snapshot` only ever injected
  `scoring` and `position` context, so the profile agent had never seen the
  user's profile; it now gets basics + every section with ids, and
  `prompt_builder`'s protocol spells out the create/update/delete shapes for
  `profile_sections`. Also added `delete` support to `change_applier`.
  VERIFIED (all on DB copies): 33/33 API checks (CRUD, slug normalization,
  409/404/422 paths, reorder invariants, PATCH+approve, whitelist still
  enforced after an edit, agent-proposed delete); 17/17 browser checks incl.
  editing a proposal in the wizard and confirming the USER's text landed instead
  of the agent's; and a real-CLI chat turn where the agent quoted the existing
  Skills text verbatim in `old` (only possible with the snapshot fix) and its
  approved change applied correctly. Fixed a latent React warning in `ui.tsx`
  (`border` shorthand mixed with `borderColor` across rerenders) surfaced by the
  new cards; added shared `inputStyle`/`textareaStyle` to `ui.tsx`.
- 2026-07-29 — **Fixed two real bugs hit importing a long CV**
  ("agent returned no structured profile block"). Root cause was NOT the
  onboarding code: (1) the prompt was passed as `-p <prompt>` in **argv**, and
  the CV extracted to ~63k chars vs Windows' 32,767 command-line cap, so
  `CreateProcess` failed with winerror 206 — which Python raises as
  `FileNotFoundError`, so `claude_adapter.py` reported **"Agent CLI not found"**
  for a binary that was present. Prompt now goes over **stdin** (`claude -p`
  with no positional value; verified against the real CLI, same stream-json),
  and winerror 206 is reported truthfully. (2) All FOUR job handlers kept a
  private `_run_agent` that captured `DoneEvent` and **silently dropped
  `ErrorEvent`**, so an agent that never ran returned `""` and each handler
  blamed its own parse step — this is what made a launch failure look like a
  parsing failure. Replaced with shared `api/agent/one_shot.py:run_agent_text`,
  which raises `AgentRunError`; `evaluate_batch`/`generate_document`/
  `research_company`/`import_cv` all migrated. → DECISIONS #17/#18. Verified:
  the real 63k-char CV now imports in ~65s (7 sections, 3/7 basics filled —
  the other 4 correctly left null, the PDF doesn't state them), and a chat turn
  still streams tokens→done through the same adapter (smoke thread deleted
  afterwards, scoped by id). Also dropped a dead `core/` sys.path insert from
  `import_cv.py` and a now-unused `ROOT_DIR` import from `generate_document.py`.
- 2026-07-28 — **Onboarding wizard built + verified end-to-end** (the last
  genuinely-unstarted Stage 5 item). Backend: `api/routers/onboarding.py`,
  `api/jobs/handlers/import_cv.py` (pypdf text extraction → agent →
  `pending_changes`), `build_cv_import_prompt`, and `create` support for
  `profile_sections` in `change_applier.py`. Frontend: `Onboarding.tsx` wizard,
  `lib/onboarding.ts`, the §7.5 guard in `AppShell.tsx`, `/onboarding` route,
  chat scoped to `profile` there, a Profile-screen link. Juan chose the literal
  spec guard (hard redirect) + purely-derived `completed` → DECISIONS #15; the
  propose-don't-write shape of `import_cv` → DECISIONS #16.
  VERIFIED, all against **copies** of `data/app.db` (real DB never written —
  confirmed after: profile still empty, positions 539, pending_changes
  unchanged): 7/7 unit checks on the new applier path (create, duplicate-slug
  refusal, missing slug, non-whitelisted field, basics upsert, update-by-id
  regression); live API smoke (status shape, 422 on non-PDF/empty); a real
  agent-CLI import of a synthetic CV (~16s) producing 6 accurate grounded
  proposals → approve → profile built → status flips to `completed`;
  re-import proposed basics only, zero duplicate sections; and a headless
  Playwright run of the whole wizard, **14/14 checks, zero console errors**
  (guard bounces `/` and `/positions`, upload → live progress → review →
  approve-all → done → dashboard reachable → Profile shows the import →
  revisiting short-circuits to done). Screenshots reviewed — on-brand.
  Cleaned the synthetic test PDFs out of `data/uploads/` afterwards. NOTE:
  `tsc`/`vite build` clean (104 modules); `TestClient` is unusable in this
  venv (starlette now wants `httpx2`, not installed) — used live uvicorn on a
  DB copy instead, which is what the previous sessions' pattern already was.
- 2026-07-28 — Follow-up harness pass on root `CLAUDE.md` itself (checked
  separately from the audit below): found two small staleness spots and fixed
  them. Rule 2 said "see `api/agent/` once built" — leftover Stage-1 phrasing;
  `api/agent/` has existed since Stage 4. Rule 4 pointed to `core/CLAUDE.md`
  for `core/` conventions but had no equivalent pointer to `api/CLAUDE.md` for
  `api/` — added one. Everything else in root `CLAUDE.md` checked out: all
  linked files exist, and `scripts/check_no_secrets.py` is confirmed actually
  installed at `.git/hooks/pre-commit` (not just documented as such).
- 2026-07-28 — Harness audit: checked `CLAUDE.md`/`PROGRESS.md`/`DECISIONS.md`/
  `PLATFORM_SPEC.md`/`core/CLAUDE.md`/`api/CLAUDE.md` against the actual
  routers/models/frontend. Found two stale spots and fixed them: (1)
  `api/CLAUDE.md` still said "Empty as of Stage 1 (only `.gitkeep`)" with an
  aspirational layout (a `repos/` dir that was never built, no `schemas/`)
  even though `api/` has been fully built through Stage 5 — rewrote it to
  describe the actual layout + the deliberately-unbuilt routes. (2)
  `PLATFORM_SPEC.md` §5 claimed `GET/PUT /memories/{module}` and `GET/PUT
  /settings`; both are GET-only in the real routers (their own module
  docstrings say so) — no PUT exists for either. Updated the table + added a
  note, mirroring how the profile/scoring/templates PUT removal was already
  documented. Everything else checked out accurate (`PROGRESS.md`'s resume
  point, `DECISIONS.md`, `core/CLAUDE.md`, workflow file references, the
  pre-publish checklist items). Also flagged but NOT acted on: the entire
  Stage 2–5 `api/`+`frontend/` build is still untracked in git (only
  `.gitkeep`-era `api/` was ever committed) — worth a checkpoint commit,
  pending Juan's go-ahead.
- 2026-07-23 — Bulk (re-)evaluate: Juan hit a real gap running a new search
  from the front end — no way to evaluate the newly-found positions except
  one at a time from Position Detail. Added `POST /positions/evaluate`
  (`api/routers/positions.py` + `EvaluateBatchRequest`), a thin wrapper over
  the already-batch-capable `evaluate_batch` job handler (no handler changes
  needed). Frontend: shared `useJobAction` hook (extracted from
  `PositionDetail.tsx`), "Evaluate all found" button on `SearchDetail.tsx`,
  row-select + bulk "Evaluate selected" bar on `Positions.tsx`.
  `PLATFORM_SPEC.md` §5/§8 updated. `tsc` clean; OpenAPI schema confirms no
  route collision; schema validation checked directly. Not run against real
  `data/app.db` (would trigger the live agent CLI on real positions) — logic
  mirrors the already-verified single-position path.
- 2026-07-21 — Position Detail action cluster built + real-CLI-verified:
  evaluate, generate/export CV+cover-letter docs, research company, log/edit
  application. 4 new job handlers (`api/jobs/handlers/{evaluate_batch,
  generate_document,export_document,research_company}.py`), 2 new agent
  modules (`task_prompts.py`, `output_parser.py`) for one-shot (non-chat)
  agent calls from job handlers, `api/routers/documents.py` (new) +
  additions to `positions.py`/`companies.py`, matching frontend wiring in
  `PositionDetail.tsx` + `api.ts`/`types.ts`. Dropped direct-edit PUTs for
  profile/scoring/templates from scope (matches the shipped chat-only UI
  design — see `PLATFORM_SPEC.md` §5 note). Verified against a COPY of the
  real DB (never the real `data/app.db`): all 5 flows run live through the
  real `claude` CLI (10–40s each) — evaluate produced grounded per-criterion
  rationale, generate correctly REFUSED to fabricate a CV when
  profile_basics/profile_sections were empty (real finding: Juan never ran
  onboarding), export rendered real PDF/DOCX under `data/documents/`, research
  produced a real company brief from live-scraped pages. Browser-verified via
  a headless-Chromium Playwright script (screenshots, zero console errors):
  re-evaluate live SSE flow, Documents/Company tab buttons, Application
  create→edit flow. `tsc`/`vite build` clean. Not built: Drive upload
  (needs `core/upload_to_drive.py` credential-path fix first, like
  `sheets_manager.py` got), onboarding wizard, Sheets export. Next: pick one
  of those three, or the remaining screens' visual pass.
- 2026-07-18 — Standalone CLI: official installer stalls on the 244MB CDN
  download here, so copied the extension's self-contained `claude.exe` to a
  stable path (`%LOCALAPPDATA%\claude-cli`) + PATH; `AGENT_CLI_PATH` repointed
  there; chat re-verified. Discovered scoring in the REAL DB is now v2 (Juan's
  own approved reweight via chat) — preserved. ⚠️ I had bulk-cleared the
  chat/pending tables as "test artifacts" and lost Juan's real chat history for
  that change (config survived). Recorded the lesson: don't clear those tables.
- 2026-07-18 — Frontend chat fixed + real-CLI agent verified. Root cause: no
  `claude` on PATH (VSCode-extension entrypoint). Pointed AGENT_CLI_PATH at the
  bundled binary, added env-cleaning + UTF-8 stdout in `claude_adapter.py`.
  End-to-end HITL with the real CLI works (reweight → proposed_changes →
  pending_change → SSE done). Cleaned test artifacts from the real DB.
- 2026-07-18 — Stage 5 (frontend) major progress: imported Juan's Claude Design
  project via DesignSync MCP; scaffolded Vite+React+TS app in `frontend/`, ported
  brand tokens, built typed API client + SSE helpers + app shell (sidebar, topbar
  with JobsIndicator/ChangesTray/theme, ChatDrawer) + ALL 13 screens wired to the
  live API. Verified: tsc + vite build clean; dev server proxies to backend, 20
  data endpoints + a position detail all 200 on real data. Remaining: onboarding
  wizard, Sheets toggle, and backend endpoints for a few write actions the UI
  references (evaluate/generate/research/PUT edits) + real-CLI chat test.
- 2026-07-18 — Stage 4 DONE: agent adapter layer (`api/agent/`: AgentAdapter ABC,
  ClaudeAdapter w/ pure NDJSON parser, ScriptedAdapter fake, prompt_builder,
  change_parser), ChangeApplier service (the HITL apply gate), chat router (SSE
  turns) + changes router (approve/reject), adapter wired into lifespan. Verified
  the full HITL loop with a fake adapter (20 checks): reweight → pending_change →
  approve → new active scoring v2; parser 14 checks; HTTP wiring smoke over
  uvicorn. Real `claude` CLI smoke still owed (binary not findable here). Next: 5.
- 2026-07-18 — Stage 3 DONE: EventBus + JobRunner (ThreadPoolExecutor(2), SSE,
  cancel), `search_run` handler wrapping the 5 free-API fetchers (per-source
  progress + stats, dedupe via make_position_id, writes search_runs +
  search_run_positions), write endpoints (POST/PATCH positions, status change,
  create/run/delete search), jobs router + SSE stream. E2E-verified live
  (remotive+jobicy: 101 new, 11 dedupe hits, live SSE) on a DB copy; real data
  untouched. Found+fixed a duplicate-link UNIQUE bug via the E2E. Next: Stage 4.
- 2026-07-18 — Real-data migration DONE: set up `.venv`, `alembic upgrade head`,
  seeded, and ran `migrate_from_sheets.py` against Juan's real Job Tracker (OAuth
  authorized). 327 positions / 211 companies / 3 apps / 12 docs / 654 events into
  `data/app.db`. Verified live via uvicorn. Stage 2 fully done. 3 findings logged
  (unlinked positions, dashboard date window, companies-count). Next: Stage 3.
- 2026-07-18 — Aligned `core/sheets_manager.py` credential handling with
  `.env.example` + hard-rule-#1 (creds/token now under `data/credentials/`,
  accepts `SPREADSHEET_ID`/`GOOGLE_CREDENTIALS_PATH`, loads `data/credentials/.env`).
  Added a Pre-publish checklist (regional-defaults genericization, onboarding
  assets, core dotenv reconcile, secrets sweep). Next per Juan: he runs the
  real-Sheets migration verification with his Google creds.
- 2026-07-18 — Stage 2 code-complete: `api/main.py` (app factory, CORS, health) +
  full read-API surface in `api/routers/` (dashboard, analytics, searches,
  positions, profile, templates, scoring, companies, memories, settings) with
  Pydantic schemas in `api/schemas/`. Added fastapi/uvicorn/python-multipart.
  Verified with a TestClient smoke test: 28 endpoints + 15 payload checks pass
  on seed→migrate synthetic data. Only real-Sheets migration verification owed.
  Next: Stage 3 — `api/jobs/runner.py`.
- 2026-07-18 — Stage 2: 19 SQLAlchemy models (`api/models/` + `enums.py`,
  `api/db/base.py`); `api/config.py` + `api/db/engine.py` (WAL/FK/busy_timeout,
  sessions); Alembic scaffolded (`api/db/alembic/`, root `alembic.ini`) with
  initial revision `c416b77fadf6`. `scripts/seed_defaults.py` +
  `scripts/migrate_from_sheets.py` (both idempotent). Verified: migrate → seed →
  re-seed on a clean DB; migration logic against synthetic sheets (26 assertions).
  Added `sqlalchemy`/`alembic` to requirements. Next: `api/main.py` + read routers.
  ⚠️ Real-Sheets migration verification still owed (needs Juan's Google creds).
- 2026-07-10 — Stages 0–1 completed. Harness files added (this file,
  `CLAUDE.md`, `DECISIONS.md`, `core/CLAUDE.md`, `api/CLAUDE.md`).
