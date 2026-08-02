# Decisions

Settled architectural calls. If a session is tempted to re-debate one of these,
it needs a genuinely new fact to justify reopening it — cite the entry number.
This file exists so tokens don't get spent re-deriving conclusions already reached.

1. **SQLite (not Postgres/MySQL) is the source of verity.** Single-user,
   self-hosted, zero-ops. WAL mode + `busy_timeout=5000` + short transactions
   is sufficient concurrency for `max_workers=2`. Do not introduce a server DB.

2. **Google Sheets is an optional one-way export mirror, never fed back in.**
   The migration (`migrate_from_sheets.py`) runs once, going forward SQLite is
   authoritative. `POST /export/sheets` truncates and rewrites tabs; it never
   reads from Sheets after migration.

3. **SSE, not WebSocket**, for job progress and chat streaming. Single-user,
   unidirectional traffic, trivial reconnection via `Last-Event-ID`. No need
   for the complexity of bidirectional sockets.

4. **`ThreadPoolExecutor(max_workers=2)` + a `jobs` table, not Celery/Redis.**
   This is a self-hosted single-user app — no message broker, no worker
   orchestration infra. If throughput ever becomes a real problem, revisit;
   it hasn't been, so don't add the infra preemptively.

5. **Agent adapter is an explicit interface; v1 ships only `ClaudeAdapter`.**
   `AgentTask -> Iterator[AgentEvent]` is the contract. A `CodexAdapter` is
   reserved for v2 — don't build it speculatively, don't skip the interface
   either (the interface is what makes v2 cheap later).

6. **Human-in-the-loop is strict and structural, not a UI suggestion.** The
   agent never writes to the DB. It always ends a turn with a
   ` ```json proposed_changes` ` block; `change_parser.py` validates it into
   `pending_changes` rows; only `ChangeApplier` (triggered by
   `POST /changes/{id}/approve`) writes to domain tables. Do not add a code
   path where the agent's output is applied without that approval step, even
   for "safe" changes like notes.

7. **The public repo has a fresh git history, disconnected from the private
   `Copilot` repo.** The private repo's history contains real personal data
   (professional profile, employer names, metrics) that must never enter a
   public remote — not even via a squashed clone. Every file ported here was
   copied as a file, then grepped clean, then committed fresh.

8. **UI language is English; `workflows/*.md` may mix Spanish/English.**
   The workflows are SOPs the agent reads to operate (originally written by/for
   a Spanish-speaking user) — they're an internal operating manual, not a
   user-facing surface, so translating them fully has no product value and
   was skipped deliberately.

9. **`core/` is a deterministic layer, ported as-is — no new LLM calls belong
   there.** All reasoning (scoring sub-scores, document drafting, chat) goes
   through `api/agent/`, which shells out to the user's own agent CLI. This
   preserves the "no API key" guarantee end to end. See `core/CLAUDE.md`.

10. **No `ANTHROPIC_API_KEY` / no Anthropic API billing, anywhere in this
    repo.** The reasoning cost is the user's own Claude Code (or future Codex)
    subscription, invoked headless. This is the core value proposition
    ("BYO-agent") — any design that requires an API key is a wrong turn.

11. **"Active version" is a boolean flag on the version row, not a back-pointer
    FK on the parent.** `template_versions.is_active` / `scoring_configs.is_active`
    instead of `templates.active_version_id`. A parent→active-version FK plus the
    existing version→parent FK is a circular foreign key, which SQLite can't add
    via `ALTER` (no batch-friendly path in Alembic). The API composes the nested
    `active_version` shape (§4.9) from the flagged row. Enforce "exactly one
    active per parent" at the service layer, not with a DB constraint.

12. **The frontend styles with inline styles + CSS custom properties, NOT
    Tailwind** (despite DESIGN_BRIEF.md saying "React + Tailwind"). The design
    delivered by the Claude Design session was built entirely with inline styles
    referencing brand CSS variables, so the React app ports that 1:1. Matching
    the delivered design exactly beat re-deriving it in a Tailwind theme. Don't
    add Tailwind later "to clean it up" — it would fork the styling system from
    the design source.
    **`frontend/src/styles/tokens.css` is the design source of record**, with
    `DESIGN_BRIEF.md` for the intent behind it. The original prototype export
    (`frontend/design-reference/design.html`) is **not shipped** and this repo
    does not depend on it (decided 2026-08-02, gitignored): it renders the
    author's name in 55 places — mostly the `<Name>DesignSystem_302711.*` global
    namespace its components resolve through — and it loads its tokens and
    component bundle from a personal `_ds/…` directory that was never part of
    this repo, so it renders as an unstyled skeleton for anyone else. Retheming
    means editing `tokens.css`; the running app is the reference.

13. **The agent CLI binary is resolved via `AGENT_CLI_PATH` (default `claude`
    on PATH), invoked as a plain subprocess.** No API key (see #10). Because
    Claude Code can run from the VSCode extension (which puts no `claude` on
    PATH) OR a standalone install, the path is a config knob in the user's
    `.env`, and `claude_adapter.py` strips inherited `CLAUDE_CODE*` nested-session
    env vars + reads stdout as UTF-8 before parsing the stream-json. Don't
    hardcode a binary location.

14. **Job handlers may call the agent directly (one-shot, no chat thread, no
    `proposed_changes`/HITL gate) for direct work-product writes.** `evaluate_
    batch`, `generate_document`, and `research_company` (`api/jobs/handlers/`)
    construct a task-specific prompt (`api/agent/task_prompts.py`), call
    `ClaudeAdapter().run(task)` synchronously inside the job, and write the
    result straight onto the entity (`Position.evaluation`, a new `Document`,
    `Company.research_md`) — no approval step. This does **not** contradict
    decision #6: HITL gates chat-driven *decisions* about config/profile/
    position state (things a user debates and approves); these three are
    *draft work products* the spec already models as plain `202` jobs (§5),
    the same trust tier as a search run. If a future job handler wants to
    change scoring/profile/position status from agent output, that goes
    through `proposed_changes` like chat does — don't let this precedent
    justify skipping HITL for state-changing writes.

15. **Onboarding completion is derived from the profile, never stored.**
    `GET /onboarding/status` computes `completed` as "`profile_basics.full_name`
    is set AND at least one `profile_sections` row has content" — the same bar
    `generate_document` needs before it will draft a CV. No settings row, no
    `POST /onboarding/complete`. A stored flag can disagree with the data (user
    clears their profile, migration lands a partial one, two clients race);
    a derived one can't, and it makes approving the imported changes *be* the
    completion event rather than something the UI has to remember to signal.
    The cost is that "skip for now" has no server-side home, so it's a
    localStorage flag in `frontend/src/lib/onboarding.ts` that only suppresses
    the redirect guard on that browser. If a future need makes skip-state
    genuinely shared (multi-device, say), add the flag then — but keep
    `completed` derived and let the flag only *suppress the guard*, never
    fake completion.

16. **`import_cv` is the reference for "job handler that proposes".** It calls
    the agent one-shot like the DECISIONS #14 handlers, but writes
    `pending_changes` instead of the entity, because the profile is
    user-approved state. It also refuses to re-propose a section whose slug
    already exists, so re-importing a CV can't duplicate the profile — any
    future proposing handler should carry the same idempotence, since a
    pending change may sit unapproved while the world moves on.

17. **The agent prompt goes over stdin, never argv.** Windows caps a command
    line at 32,767 chars; prompts are unbounded (a long CV can extract to ~63k,
    and job descriptions can be long too). Over the limit `CreateProcess` fails
    with winerror 206, which Python raises as `FileNotFoundError` — identical
    to a missing binary unless you inspect `winerror`, so it masqueraded as
    "Agent CLI not found" while the binary was sitting right there. `claude -p`
    with no positional value reads the prompt from stdin, verified against the
    real CLI (same stream-json output). Don't move the prompt back into argv
    "for simplicity". `--append-system-prompt` is still argv — it's bounded by
    our own templates, and `run()` now reports winerror 206 truthfully if one
    ever grows past the limit.

18. **One-shot agent calls go through `api/agent/one_shot.py:run_agent_text`,
    which raises on failure.** All four job handlers previously kept a private
    `_run_agent` that collected `DoneEvent.text` and silently dropped
    `ErrorEvent`, so an agent that never started returned `""` and the handler
    blamed its own parse step ("agent returned no structured profile block").
    Errors must surface as errors — a handler that reports the wrong cause
    costs far more than the duplication it saved. Don't reintroduce a local
    runner that ignores `ErrorEvent`.

19. **The user edits their own profile directly; the HITL tray gates only the
    agent.** `PUT /profile/basics`, `POST/PUT/DELETE /profile/sections`, and
    `POST /profile/sections/reorder` write straight to the DB from the UI. This
    reverses the earlier "chat-only editing for profile/templates/scoring" note
    in `PLATFORM_SPEC.md` §5 — which explicitly invited exactly this ("don't add
    them without a matching UI decision"), and Juan made that decision on
    2026-07-29. It does **not** weaken DECISIONS #6: that rule is about the
    *agent* never writing unreviewed, and agent-proposed profile changes still
    go through `pending_changes`. Routing a user's own form submission through
    an approval queue would be ceremony, not safety. Templates and scoring stay
    chat-only until the same call is made for them.

20. **A pending proposal can be corrected before approval (`PATCH
    /changes/{id}`), not just accepted or rejected.** When the agent extracts a
    CV section slightly wrong, reject-and-re-prompt is a bad loop; editing the
    text and approving is the natural move. Safety is unchanged because
    `ChangeApplier` validates the *edited* diff against the same field
    whitelists — an edit can't reach a field the original proposal couldn't
    (regression-tested). Editing is refused once a change leaves `pending`, and
    refused entirely for `action` changes (rewriting a job payload is a much
    sharper tool than fixing prose). `edited_at` records the rewrite, and
    profile writes from an edited proposal are attributed `updated_by="user"`,
    so provenance stays honest.

21. **The agent's write surface is an explicit catalog, and the chat layer
    checks it when a proposal is parsed.** `change_applier.SUPPORTED_TARGETS`
    lists every writable `(target_table, change_type)` pair; `is_supported()`
    is called in `chat.py` so a proposal aimed at something unwritable is
    marked `failed` with an explaining message immediately, instead of looking
    approvable and blowing up on approve (which is what happened to a real
    `job_sites_config` proposal in Juan's DB). The same catalog is rendered
    into the agent's output protocol, so it knows the shape it must produce.
    Adding a table means: a whitelisted `_apply_*`, an entry in
    `SUPPORTED_TARGETS`, and a row in the protocol table — keep the three in
    sync (a test asserts no advertised target is unreachable).

22. **Widening the agent's reach is per-field, never per-table.** As of
    2026-07-29 it can also write `templates`, `searches`, `companies`,
    `applications`, and `documents` — but only specific columns, chosen so a
    wrong proposal can't rewrite history or fabricate results:
    - `templates` writes a NEW active version, never edits one in place (same
      reason scoring is versioned: you must be able to see what a document was
      generated from, and roll back).
    - `searches` exposes config only. Metrics (`total_found`, `avg_score`, …)
      and `status` are derived from runs — letting the agent set them would let
      it invent history. Editing a *running* search is refused.
    - `companies.name` stays read-only: it's the dedupe key the Sheets
      migration and fetchers match on, so renaming splits a company's history.
    - `documents` may change `content_md`/`status`, never the binary paths or
      availability flags; changing the source marks existing PDF/DOCX exports
      unavailable so nobody sends a file whose text was edited out from under it.
    - Repo config files (`config/job_sites.json`) are NOT writable through this
      path at all, and `settings` remains read-only. The applier writes DB rows
      under `data/`; giving the agent a route to tracked repo files is a
      different blast radius than editing user data (hard rule #1).

23. **Google auth is shared, headless-safe, and one-token.** `core/google_auth.py`
    owns credential loading for both Sheets and Drive, with a single token at
    `data/credentials/token.json` carrying both scopes. Two problems it fixes:
    the per-tool auth called `flow.run_local_server()` on any invalid token,
    which from inside a job handler means a server thread blocking on a browser
    prompt nobody will ever see; and `upload_to_drive.py` kept its own
    `token_drive.json` **at the repo root**, violating hard rule #1 and forcing
    a second authorization. Servers call `get_credentials(interactive=False)`,
    which raises `GoogleAuthError` with a "run `scripts/authorize_google.py`"
    hint instead of prompting. Only that script ever authorizes interactively.
    Don't reintroduce a browser flow reachable from an API request.

24. **`PUT /settings` is whitelisted, not a generic key-value write.**
    `WRITABLE_KEYS` in `api/routers/settings.py` names each settable key and its
    type. The bag also holds runtime facts (paths, adapter identity) that aren't
    user preferences, so a blanket write would turn a preferences form into a
    way to reconfigure the backend from the browser. Add a key when a real
    control needs it.

25. **Sheets export is gated on an explicit opt-in.** `POST /export/sheets`
    returns `409` unless `sheets_export_enabled` is true. The export truncates
    and rewrites every tab (decision #2), so it can destroy a spreadsheet a user
    still hand-edits; requiring them to turn it on first makes that a decision
    rather than an accident. The Settings copy states the one-way overwrite
    plainly for the same reason.

26. **Drive uploads mirror the user's own foldering and replace rather than
    duplicate.** Documents go into a `Company - Role` subfolder of the
    configured folder (found-or-created by name), because that's the convention
    people already keep by hand — dumping files flat into the parent mixes them
    with the tracker spreadsheet and existing folders. Re-uploading updates the
    same Drive file instead of creating a second copy: re-exporting a tweaked CV
    is routine, duplicates make it ambiguous which one was sent, and updating
    keeps the file id so links already shared with a recruiter stay valid. The
    exported filename is preserved end-to-end for the same reason — it's what a
    recruiter sees on download.

27. **MCP-backed job sources live in `api/agent/`, never `core/`, and report
    "unavailable" as *skipped* rather than *failed*.** Resolving an MCP
    connector means invoking the agent CLI, so an MCP fetcher is an LLM call
    and is barred from `core/` by hard rule #3 — even though it is conceptually
    "just another fetcher" alongside the five HTTP ones. `api/agent/
    mcp_sources.py` holds them, matching the `_FETCHERS` contract
    (`keywords -> list[normalized position]`) so `search_run` needs no special
    case. Two consequences worth stating: (a) one call costs an agent turn
    (~40s measured) versus milliseconds for an HTTP fetcher, which is why these
    sources are opt-in per search, not on by default; (b) an unregistered or
    unauthorized connector raises `McpSourceUnavailable` and is recorded as a
    skipped source, because "you never connected Indeed" is a setup state, not
    a failed run — conflating the two would make every run of a fresh clone
    look broken. The agent's role in these prompts is transcription only, with
    the `tipo` mapping and date normalization done deterministically in Python
    so they aren't re-decided on each run.

28. **The Indeed MCP is the primary Indeed path; `core/fetch_jobs_indeed.py`
    (Scrappa) stays as the portable fallback.** Verified 2026-07-30 that the
    connector is not Claude-Connector-only as previously believed: the endpoint
    advertises RFC 7591 dynamic client registration (anonymous `POST` to
    `secure.indeed.com/oauth/v2/register` returns `201`) and challenges
    unauthenticated calls with a standard `401` + `WWW-Authenticate`. So any MCP
    client can self-register and a cloner can authorize their own. It is still
    not a hard requirement: the backend runs `claude -p` headless and cannot
    complete OAuth, so first-time authorization is a one-off interactive step,
    and without it the source is simply skipped. `config/job_sites.json` already
    modelled exactly this (`type: mcp` + `fallback: api_provider`).

29. **The Indeed connector is registered by the user, never shipped as a
    committed `.mcp.json`.** Measured 2026-07-30: adding a project-scoped
    `indeed` server made `fetch_indeed` fail with `McpSourceUnavailable`
    (`10 positions in 27s` without the file, unavailable with it), because a
    project server sits in "pending approval" until accepted interactively and
    while pending it **suppresses an already-working account connector** for
    the same tool. Shipping the file would therefore break every cloner who
    already had Indeed connected in their own agent CLI account — the opposite
    of the intent. The README documents a one-line `claude mcp add` instead, so
    users with an account connector change nothing and users without one opt in
    explicitly. Corollary: this is also why `--strict-mcp-config` is not free —
    it would force the `.mcp.json` path and reintroduce exactly this collision.
    That corollary was measured on 2026-07-31 and settled the question: the
    flag is **not** adopted (see #34).

30. **Indeed descriptions are fetched in the same agent turn as the search, and
    Indeed URLs are never treated as identity.** Two properties of Indeed's MCP
    forced both calls (measured 2026-07-30): its `job_id` is re-issued per
    session (one posting was `JOBSEARCH_67`, then `JOBSEARCH_117`), so an id
    cannot be persisted and resolved in a later job — enrichment has to happen
    inline or not at all; and its `View Job URL` is a per-request redirect token
    rather than a permalink (the same posting returned three different URLs
    across three calls), so URL-based dedupe silently fails to collapse
    duplicates. Dedupe is therefore on company+role, matching
    `make_position_id`, and a stored Indeed URL is understood to be perishable.
    Descriptions default ON (`INDEED_FETCH_DESCRIPTIONS`) capped at
    `INDEED_MAX_DETAILS=25` because the description is what the evaluator
    actually reads, but it is the dominant cost: ~25s for 10 postings without,
    ~135s with (~11s per posting).

31. **LinkedIn is a first-class source; its description cache lives under
    `data/`.** Wiring it closed the biggest functional gap in discovery — it was
    the second-largest source in the real dataset (219 of 539 positions) yet
    unreachable from the new runner. It goes straight into `_FETCHERS` as plain
    in-process HTTP (no agent turn, unlike `indeed`), with `scrape_linkedin`
    called once per keyword, deduped before enrichment so no detail request is
    spent on a duplicate. Two latent path bugs were fixed in
    `core/scrape_jobs.py` on the way: `CONFIG_PATH` and `LI_DESC_CACHE_PATH`
    were **CWD-relative**, so imported in-process by a job handler they resolved
    against wherever uvicorn was started — and the description cache (scraped
    job content, i.e. user data) landed in a `.tmp/` outside `data/`, breaking
    hard rule #1. Both now resolve against the repo root, with the cache under
    `data/cache/` where it is already gitignored. Descriptions default ON: the
    cache makes re-runs nearly free (27s cold vs 1s warm for 10 postings), and
    the existing anti-429 machinery degrades to card metadata rather than
    failing the run.

32. **Search geography is configuration with neutral defaults; the region
    filter is region-driven, not LATAM-hardcoded.** Closing the first
    pre-publish item meant more than deleting the `Argentina` / `AR` literals
    from `config/job_sites.json` and `.env.example`. The real personalization
    was `core/location_filters.py`: it only knew how to filter for LATAM, and
    the four standalone CLIs called it **by default** (`--market
    latam-argentina`), so a cloner running them silently dropped every job that
    wasn't LATAM-eligible. It is now a `REGIONS` table (`latam`,
    `north-america`, `europe`, `apac`) selected by `TARGET_REGION`, defaulting
    to `worldwide`, which filters nothing — a new user sees everything until
    they say where they are. `filter_latam_remote` survives as a thin alias so
    the old behaviour stays available by name, and `--market` is kept as an
    alias of the new `--region`. An unrecognized key falls back to no filtering
    (a typo in `.env` must not silently empty a search) but warns once on
    stderr. Legacy values — including the `Argentina-LATAM` string the old
    `.env.example` shipped, which is in live `.env` files — are mapped rather
    than ignored. The `search_run` job handler is unaffected: it never geo-filters
    (see its docstring), so this changes the CLIs, not the app.
    Prerequisite fixed alongside it: `core/env_config.py` now loads
    `data/credentials/.env` before a root `.env`, resolved from the repo root.
    Without it the fetchers' bare `load_dotenv()` read only a root `.env`, so a
    user who followed the README would set `TARGET_REGION` where nothing read it
    — the config would have been genericized but inert. `api/config.py` reads
    the same variable names, so `core/` and `api/` agree on one configuration.

33. **The public history starts at one clean commit; the pre-scrub history is
    kept only as a local backup ref.** The pre-publish secrets sweep cleaned the
    working tree, but the author's name and — more importantly — real job-search
    particulars (a named employer with position slug and application date, the
    Drive folder, CV size) were in earlier commits, and `git` keeps those
    reachable forever. Since no remote existed yet, the cheapest correct fix was
    to squash the branch into a single commit over the already-genericized tree,
    rather than publish a history whose diffs still disclose what the files no
    longer say. Development history is preserved locally at
    `backup/pre-squash-<date>` — **never push that ref**; it exists so the squash
    is reversible, not to be shared. The author's name stays in `LICENSE` and in
    commit authorship metadata, which is normal for a repo owner and was an
    explicit choice, not an oversight.

34. **`--strict-mcp-config` is NOT used on the agent subprocess.** The platform
    spawns the CLI with no MCP scoping flags, and inherits whatever servers the
    cloner has registered. That was an open pre-publish item on the theory that
    a cloner's connectors — Gmail, Drive — leak into the tool space of an agent
    this platform spawns. Two measurements on 2026-07-31 closed it the other
    way. **The cost is real:** the same `fetch_indeed` call returned 10
    positions in 37.8s normally and `McpSourceUnavailable` in 11.9s with the
    flag added — it ignores claude.ai *account* connectors, so adopting it
    forces the `.mcp.json` path that #29 already rejected. **The benefit is
    not:** Gmail (`list_labels`) and Drive (`search_files`), driven through
    `run_agent_text` both with and without an allowlist, came back
    permission-denied every time ("permission … not granted in this
    non-interactive session"). The headless default-deny of #27 already
    contains them — the allowlist is what lets Indeed through, and nothing else
    gets through without being on it. So the flag buys no privacy that already
    exists and breaks a working source. What survives as an argument is only
    determinism and the token weight of loaded tool definitions, which does not
    justify the breakage. Reopen only with a new fact — e.g. if headless stops
    defaulting to deny, or if a handler starts passing a broad allowlist.

    **Corollary on method, which cost two wrong answers before the right one:**
    do not measure agent tool availability by asking the agent. "Do you have
    tool X?" returned a confident ABSENT *for Indeed*, in the exact
    configuration where `fetch_indeed` works. MCP tools resolve on demand, so a
    valid probe must be **task-shaped and carry a system prompt** (what
    `build_indeed_search_prompt` supplies and `--append-system-prompt`
    delivers) — and must be validated against Indeed as a known-reachable
    control before its answer is believed. A probe that cannot see a connector
    proven to be there is measuring nothing.
