# Gearbox roadmap → v2.0.0

Shipped arc derived from the [2026-06-15 audit](./audit-2026-06-15.md) (backlog
`Gn`). Forward ladder (v0.5.0 → v2.0.0) added by the **2026-06-16 reassessment**,
which folded in three new inputs:

- **`[PA]`** — prior-art / competitive scan (RouteLLM, semantic-router, LiteLLM/
  Portkey, claude-code-router, Helicone/Langfuse, CrewAI/LangGraph).
- **`[CC]`** — current Claude Code extension surface (hooks, status line, MCP,
  subagent tool-scoping, headless mode).
- **`[KB]`** — the `agent-research` knowledge base (token economics, prompt
  caching, blind-scoring eval, smart-zone context, parallel fan-out).

New items carry `R#` IDs with a source tag; carried-over audit items keep their
`G#`. Detailed notes for shipped milestones live in `README.md` + git history.

**Strategic spine (from the prior-art verdict).** Gearbox's moat is narrow but
real: *verifier-gated tier routing native to Claude Code*, driven by its own
telemetry — nothing else pairs a verifier loop with tier routing. The routing
*intelligence*, though, is weak next to learned routers, and the cost claims are
unbenchmarked. So the ladder makes routing **credible** (eval harness, v0.5.0),
**controllable** (budget caps + knob, v0.6.0), **visible** (dashboard, v0.7.0),
**efficient** (prompt-cache-aware, v0.8.0), and **self-improving on a signal only
gearbox has** (graded-verifier reward, v0.9.0) — *before* it earns 1.0 and then
climbs toward a real learned router and safe online learning.

Sequencing rule (unchanged): each milestone leaves the plugin shippable; fixes
precede features; nothing learns from the reward signal until the signal is clean,
enforced, measurable, and graded.

> **Hook caveat.** Every `[CC]` item that names a hook event (`Notification`,
> `Stop`/`SessionEnd`, `PreCompact`, `SubagentStop`, `UserPromptSubmit`) must
> re-verify the event against the *then-current* Claude Code hooks reference before
> building — the feature scan over-enumerated events; only confirmed hooks are
> used here, but pin the schema at build time.

---

## Shipped (v0.1.8 → v0.7.1)

| Milestone | Theme | Headline | Backlog | Status |
|-----------|-------|----------|---------|--------|
| **v0.1.8** | Hardening & cleanup | Fix data path, close spec contradictions, delete dead code | G1–G14, G17, G18 (G15/G16/G12 → no-code) | ✅ landed 2026-06-15 |
| **v0.2.0** | Integrity & CI | Auto-BASELINE capture + CI + spec-vs-code drift guard | G19, G20, G21, G22, G15 | ✅ landed 2026-06-15 |
| **v0.3.0** | Observability & data quality | Global-log consolidation + dashboard + offline eval scorecard | G23, G24, G25, G26 | ✅ landed 2026-06-15 |
| **v0.4.0** | Learned router (**static-prior subset only**) | Min-sample-guarded `{task-class × tier}` win-rate prior, surfaced as an advisory via `/gearbox:recommend` + SessionStart | partial G27 | ✅ landed 2026-06-16 |
| **v0.5.0** | Credibility (**modeled subset**) | Exact per-component token cost from the `usage` split + a modeled scorecard vs always-Sonnet / always-Opus / escalate-on-fail | R2, R1 (modeled), R3 (no-op) | ✅ landed 2026-06-16 |
| **v0.6.0** | Control (**knob + caps + measured benchmark**) | Cost/quality aggressiveness knob + opt-in weighted-token budget caps (ask-on-overrun) + 80/100% threshold warnings + measured counterfactual benchmark | R6, R4, R5, R1-live, R3 | ✅ landed 2026-06-16 |
| **v0.7.0** | Visibility | Status-line segment + richer dashboard + SessionEnd session summaries + escalation logging | R7, R8, R9 | ✅ landed 2026-06-17 |
| **v0.7.1** | Visibility (point) | Status-line segment reframed to show estimated savings vs an all-Opus baseline (money/weighted-token toggle) + doctor CHECK 6 Step-C fix | R8 (extends) | ✅ landed 2026-06-17 |

**v0.4.0 scope correction.** v0.4.0 shipped only the *static win-rate prior* — a
keyword-bucketed `{task-class × tier}` table (verifier approve-rate + cost),
advisory-only, never overriding the hard floors / max-dimension routing / circuit
breaker. The **full learned router (G27)** and **transcript mining (G32)** did
**not** ship; both are carried into the forward ladder (G27 → v1.2.0, G32 →
v0.9.0). The prior is also **reward-sparse** today (first run: 47 dispatches, 3
with a verifier verdict) — the v0.9.0 graded-reward work is what densifies it.

**v0.5.0 scope correction.** v0.5.0 shipped the **exact-cost fix (R2)** — the
logger now bills each delegation per-component from the real `usage` split
(input / output / cache_read / cache_creation, with a 5m/1h cache-write
sub-breakdown), closing the "`cost_usd` is always estimated" limitation — and the
**modeled baseline scorecard (R1)**: `bench/eval.py` now scores the live router
against always-Sonnet, always-Opus, and escalate-on-fail, re-pinning the stale
`$45/M` opus rate. **R3 is an explicit no-op** (no headless `claude -p` shipped).
The **measured** counterfactual benchmark — the `--live` half of R1 that would run
the fixed task set under each policy via `claude -p` — was **deferred to v0.6.0**:
it depends on a forced-tier mechanism (the v0.6.0 aggressiveness knob **R6**) that
does not exist yet, so a headless run cannot be pinned to "always-Sonnet" today.
The modeled scorecard is the credibility gate until R6 unlocks measured runs.

**v0.6.0 scope correction.** v0.6.0 shipped the **control** features: the cost/quality
aggressiveness knob (**R6** — `cost-conscious` / `balanced` / `quality-first` +
benchmark-only `always-T0/T1/T2`) and **opt-in budget caps + threshold warnings
(R4/R5)**. A PreToolUse hook asks before an over-cap dispatch (default unit = weighted
Haiku-equivalent tokens, derived from exact cost, so an Opus token counts ~5× a Haiku
token — matching subscription usage-limit burn); a PostToolUse hook warns at 80%/100%
and post-hoc per-task. **R5 was reframed** — the `Notification` hook event is
observational-only, so the warning is emitted by the budget hook itself, not a
`Notification` hook. The **measured benchmark (R1-live)** + its cost-ledger summary
line (**R3**) — initially paused — **shipped 2026-06-17**: `bench/run-live.py` runs the
fixed task set under each policy via headless `claude -p` (forcing baselines with R6's
forced-tier profiles; always-Opus via an edit-capable `always-opus-build` builder@opus
profile, since `always-t2` routes to the read-only architect) against a committed toy
fixture, capturing exact per-policy cost (R2) + a deterministic acceptability grade into
`bench/training-data.jsonl`, and emits the canonical cost-ledger summary line. **A local
benchmark run needs no ledger entry** — the `agent-research` ledger only meters headless
`claude -p` that runs in a **GitHub Actions workflow**, and R1-live deliberately runs
locally (spends money, `bypassPermissions`), never in CI. The summary line just keeps a
run metering-ready *if* R1-live is ever wrapped in a CI workflow (then it would be
onboarded as a ledger consumer). Fork stayed at **0.6.0** through R1-live/R3 (the
`bench/` tooling runs from the repo, not the installed plugin cache, so no reinstall).

**Post-milestone patches.** Two plugin-cache changes (which *do* need a reinstall)
bumped the fork past 0.6.0: **0.6.1** — the R32 orchestrator context-hygiene routing
rule (rule 11; the runtime-free half, see v1.6.0); **0.6.2** — a doctor CHECK 8 fix:
version freshness read `CLAUDE_PLUGIN_ROOT` from `os.environ` inside its python
subprocess, but the command shell doesn't carry that env var, so it silently compared
the installed version against the *upstream* repo instead of the fork's manifest. Now
the substituted `${CLAUDE_PLUGIN_ROOT}` token is passed as `argv[1]` (matching CHECK 0).

**v0.7.0 scope correction.** Two shipped items diverge from the original R7/R8/R9 spec.
**(1) R8** — Claude Code plugins cannot register the main `statusLine` (only
`subagentStatusLine`), so a plugin `statusLine` command is not possible. Shipped instead
as a composable segment `bench/statusline.py`: reads the status-line JSON on stdin,
prints `[builder×5 scout×3 …] $2.43` for the current session, and is wired into the
user's own `~/.claude/settings.json` (standalone or composed into an existing status
line). Doctor **CHECK 10** was added (PASS-on-present, reports wiring status
informationally, never fails on the optional wiring). **(2) R9** — `Stop` fires every
assistant turn; `SessionEnd` is the correct once-per-session hook. The `SessionEnd`
payload carries no cost or tier data (only `session_id`/`cwd`/`transcript_path`/`reason`)
and its output is ignored, so `hooks/scripts/session-summary.py` reads the dispatch log
filtered by `session_id` and writes a rollup to a **separate file**
`~/.claude/gearbox-sessions.jsonl` — kept separate so existing dispatch-log readers
need no filtering. The Hook caveat ("re-verify hook events at build time") was honored:
`SessionEnd` was confirmed against the current Claude Code hooks reference before
building. The **escalation-logging change** (routing.md rule 3 now requires escalation
dispatches to prefix the Task prompt with `[gearbox-escalation from=T<n> to=T<m>]`;
`hooks/scripts/log-routing.py` parses it into new record fields `escalation` /
`escalated_from` / `escalated_to`) is the explicit data source for R7's escalation-rate
column and R9's per-session escalation count. This plugin-cache change (hooks + bench +
commands) does require a reinstall + restart; pending as of 2026-06-17.

---

## Forward ladder (v0.8.0 → v2.0.0)

*(v0.7.0 is complete — the Visibility milestone: composable status-line segment,
richer dashboard (escalation rate, cost-over-time, prior-vs-actual tier mix),
`SessionEnd` per-session summaries, and explicit escalation logging. See the Shipped
table and the "v0.7.0 scope correction" note above. The ladder below starts
at v0.8.0.)*

### v0.6.0 — Control ✅ (shipped 2026-06-16; R1-live/R3 2026-06-17, fork 0.6.0)

Shipped: the cost/quality **aggressiveness knob (R6)** and **opt-in budget caps +
threshold warnings (R4/R5)** — detail in the Shipped table and the "v0.6.0 scope
correction" above. Gearbox can now enforce a ceiling (ask-before-overrun) and dial
the cost/quality frontier per project and in CI; the everyday usage-saver is
`GEARBOX_PROFILE=cost-conscious`, the hard backstop is a `.claude/gearbox-budget.json`
cap.

**Measured benchmark + ledger line (R1-live/R3 — shipped 2026-06-17):**
- **R1-live `[PA]`/`[KB]`:** the **measured** half of R1 — `bench/run-live.py`, a
  `--live` harness that runs the fixed task set under each policy (live / always-Sonnet
  / always-Opus) via `claude -p`, forcing each baseline with R6's forced-tier profiles,
  each run on a fresh temp copy of the committed `bench/fixtures/toy-cli/` fixture, with
  the repo-under-test loaded via `--plugin-dir` (hermetic, no reinstall). Captures exact
  per-policy cost from the run's JSON envelope (`total_cost_usd`, R2), confirms the
  policy's effective tier actually bound via `modelUsage`, grades acceptability with a
  deterministic per-task check, and writes `eval.py`-compatible rows to the (gitignored)
  `bench/training-data.jsonl` — replacing the v0.5.0 *modeled* baselines with a measured
  cost-at-equal-acceptability comparison (`--live` runs `eval.py`'s modeled scorecard on
  the live-policy rows as a credibility cross-check). A hard `--max-cost` ceiling (pre-run
  estimate gate + mid-pass halt) is the spend guardrail; runs use `bypassPermissions` and
  are local-maintainer-only — CI runs only the offline `--selfcheck`, never real `claude -p`.
  always-Opus uses a benchmark-only `always-opus-build` profile (`gearbox:builder` on
  opus) — `always-t2` routes to the read-only `gearbox:architect`, which can't complete
  editing tasks under a forced profile (real routing is unaffected). (Note: the measured
  set drops a distinct *escalate-on-fail* policy — the live router already escalates on
  reject, so it would just be the live run; `eval.py` keeps it as a modeled baseline.)
  *The `toy-cli` fixture is deliberately minimal; making the benchmark produce
  decision-grade results is tracked as **R29–R31** (v1.4.0, may pull forward).*
- **R3:** the runner emits the canonical `total_cost_usd=… num_turns=…` cost-ledger
  summary line, so a run is metering-ready. But a **local benchmark run needs no ledger
  entry** — the `agent-research` ledger only meters headless `claude -p` that runs in a
  **GitHub Actions workflow**, and R1-live deliberately runs locally, never in CI. The
  line matters only if R1-live is ever wrapped in a CI workflow — then it would be
  onboarded as a ledger consumer (`cost_surface.py` + `cost-ledger.yml`).

*Exit (met):* the benchmark's baselines are **measured** (real per-policy cost +
deterministic acceptability), not just modeled, and R3 makes each headless run
ledger-ready.

### v0.7.0 — Visibility ✅ (shipped 2026-06-17, fork 0.7.0)

Raw JSONL isn't legible. A 41★ competitor (`0xrdan/claude-router`) already ships
HTML analytics — match the bar.

- **R7 `[PA]` (extends `bench/dashboard.py`):** ✅ a richer cost/analytics dashboard
  over the global log — spend by tier, always-on **escalation rate** column, verifier
  reject rate, **cost over time** (`--over-time` per-day cost), **prior-vs-actual tier
  mix** (`--prior`, reusing `recommend.py`'s classifier via a new `recommended_tiers()`
  helper). Powered by the explicit `[gearbox-escalation]` marker → `escalation` log
  field as the data source for escalation metrics.
- **R8 `[CC]`:** ✅ a composable status-line segment (`bench/statusline.py`) — reads
  the status-line JSON on stdin. **As of v0.7.1** it prints estimated savings —
  `gearbox saved $0.43` — for the current session (counterfactual: re-price each session
  dispatch's token split at the top-tier Opus rates pinned in `log-routing.py`, minus
  actual `cost_usd`; `GEARBOX_STATUSLINE_UNIT=usd|tokens` toggles money vs Haiku-equivalent
  weighted tokens), replacing the original raw spend + role/count output
  (`[builder×5 scout×3 …] $2.43`). **Note:** Claude Code plugins cannot register the main `statusLine` (only
  `subagentStatusLine`), so this is wired into the user's own `~/.claude/settings.json`
  rather than being a plugin-registered command. Doctor **CHECK 10** reports wiring
  status (PASS-on-present, informational only, never fails on the optional wiring).
- **R9 `[CC]`:** ✅ a `SessionEnd` hook (`hooks/scripts/session-summary.py`) writing a
  per-session rollup to `~/.claude/gearbox-sessions.jsonl`. **Note:** `Stop` fires
  every assistant turn; `SessionEnd` is the correct once-per-session hook. The payload
  carries no cost/tier data, so the hook reads the dispatch log filtered by `session_id`
  and writes to a separate sessions file (keeping existing dispatch-log readers filter-free).
  The Hook caveat was honored — `SessionEnd` verified against the current Claude Code
  hooks reference before building.

*Exit:* routing quality and spend are visible live (status line) and per-session
(summary), not just buried in JSONL.

### v0.8.0 — Prompt-caching-aware routing

The static routing policy (~2.5 KB) is injected every SessionStart and re-billed
as input each turn. Anthropic prompt caching changes the cheapest-tier math — and
*no competitor owns this*.

- **R10 `[KB]`:** pin the static routing policy as a **cached prefix**
  (`cache_control: ephemeral`); measure `cache_read` vs `cache_creation` tokens to
  quantify the saving. (KB: `manual-prompt-cache-points.md`,
  `token-economics-as-a-cost-lever.md`.)
- **R11 `[PA]` (whitespace):** prompt-cache-aware tier math — factor a warm cache
  into the cheapest-capable-tier decision (a cached-context task may be cheaper on a
  larger tier than a cold one on a smaller tier). Genuine whitespace; no rival owns
  it; fits gearbox's Anthropic-only scope.
- **R12 `[CC]`:** a `PreCompact` hook — snapshot routing/cost/session state before
  compaction so the session ledger and prior survive it.

*Exit:* the static policy is cached, not re-billed; routing accounts for cache
state; session state survives compaction.

### v0.9.0 — Graded reward: the moat

The verifier is binary today. Turning it into a *graded* signal is the one feature
no competitor has — and it directly attacks the reward-sparsity limitation.

- **R13 `[PA]`/`[KB]` (the moat):** a **graded verifier signal** — the verifier
  emits a score (quality / coverage / cost-efficiency on a fixed scale) rather than
  just APPROVE/REJECT, and the score feeds the prior as reward. (KB:
  `synthesis-blind-scoring.md` graded scales.)
- **R14 `[G32]`:** mine session transcripts
  (`~/.claude/projects/<proj>/<session>.jsonl`) for the **negative-reward** signal
  the structured log can't see —
  orchestrator corrections ("scout was wrong"), re-dispatches, judgment escalations
  — joined by `session_id`/`uid`. Inherits `_scrub_secrets` + `prompt_head` caps;
  never persists raw transcript text. (= existing G32.)
- **R15 `[CC]`:** a `SubagentStop` hook — capture each subagent's outcome at
  completion as a structured signal, hardening today's verdict-regex-in-PostToolUse
  capture.
- **R16 `[CC]`:** a `UserPromptSubmit` pre-classifier — score the incoming task's
  tier *before* the turn runs and surface an advisory ("looks like a T2 task") to
  the orchestrator.

*Exit:* every editing delegation yields a graded reward; corrections become
negative signal; the prior is no longer reward-sparse.

### v1.0.0 — Production / adoption bar

What turns a working fork into a 1.0 others depend on. Built on a router that is
now credible (0.5), controllable (0.6), visible (0.7), efficient (0.8), learning
(0.9).

- **G28 `[PA]`:** release hygiene — semver git tags, a CHANGELOG, and doctor
  CHECK 8 comparing against a tagged release rather than `main` HEAD.
- **G30:** cross-surface SessionStart injection robustness (close the known
  limitation that injection may vary across Claude Code surfaces).
- **R17 `[CC]`:** per-tier `allowedTools` restrictions in agent frontmatter —
  grunt can't spawn `Bash`; scout/verifier stay read-only — *enforced*, not just
  documented. Flag/demote tasks that request forbidden ops.
- **R18 `[KB]`/`[G20]`:** a **declarative routing spec** — express the rubric as a
  machine-readable table (`task-class → max-scope → tier → model/effort`) instead
  of prose, and extend the spec-vs-code consistency test (G20) to validate it.
  (KB: `prompts-are-code.md`.)
- **G31 `[PA]`:** moat positioning doc — lock in verifier + graded reward as the
  differentiation vs Anthropic native routing
  ([#27665](https://github.com/anthropics/claude-code/issues/27665)); 1.0 messaging
  and investment center them.

*Exit:* tagged, changelogged, tool-scoped, spec-driven, robust across surfaces,
with a clear moat story.

### v1.2.0 — Smarter classification: the learned router

Now that inputs are clean, enforced, measurable, graded, and benchmarkable, replace
the brittle keyword classifier. (= G27, upgraded with prior-art methodology.)

- **G27 `[PA]`:** a real learned router — **embedding/similarity** classification
  (semantic-router posture) + an **LLM-fallback** classifier when rules can't
  categorize; min-sample-guarded; keeps the static rubric as graceful fallback.
  Adoption **gated on R1** showing it beats the static prior on
  cost-at-equal-acceptability.
- **R19 `[KB]`:** capability-spectrum sub-scores — measure per-task-type win rates
  (file-edit / reasoning / test-write / architecture) per model, so the classifier
  routes on grounded capability deltas, not assumed tier jumps. (KB:
  `coding-agent-fundamentals.md`, `cost-benchmark.md`.)

*Exit:* routing decisions come from a measured classifier that degrades to the
rubric, not from keyword buckets.

### v1.4.0 — Calibration & experiments

- **R20 `[PA]`:** threshold-calibration tooling — "route X% to the strong tier →
  threshold," calibrated against the eval set (RouteLLM-style), turning the v0.6.0
  knob into a principled cost/quality frontier control.
- **R21 `[PA]`/`[KB]`:** A/B routing experiments — run two policies over the fixed
  task set, **blind-scored** (KB blind-scoring: sandbox isolation, contamination
  detection), to compare before adopting.
- **R22 (deferred from v0.4.0):** per-project routing tables keyed by `cwd`, once
  per-project dispatch volume supports them (the v0.4.0 prior is global-only).

**Benchmark task-set hardening (R1 follow-up — the v0.6.0 `toy-cli` fixture is
deliberately minimal; the first live passes showed it can't yet produce
decision-grade results). May pull forward: R29 gates R1's ability to gate G27
(v1.2.0).**

- **R29 `[R1-followup]`:** tier-discriminating benchmark tasks. Every policy hit
  100% acceptability on the first live passes, so "cost at equal acceptability"
  can't expose the *quality* gap routing exists for — the modeled "router saves
  X%" assumes a spread the fixture never demonstrates. Add tasks where cheaper
  tiers measurably fail / underperform (tier-sensitive: a subtle concurrency,
  algorithmic, or multi-file refactor where sonnet regresses but opus holds),
  each with an isolated deterministic grader. **Prerequisite** for R1 to
  meaningfully gate G27 adoption — without an acceptability spread, "router beats
  the static prior at equal acceptability" is untestable.
- **R30 `[R1-followup]`:** statistical power — more tasks, repetitions, CIs. The
  3-task set shows high run-to-run variance (live/T2 cost swung $0.19↔$0.43;
  per-policy means moved 30–60% across two passes). Grow the task set and add a
  `--repeat N` to average LLM nondeterminism; report per-policy cost +
  acceptability **confidence intervals** so a comparison is sound before it gates
  a routing change.
- **R31 `[R1-followup]`:** delegation-forcing + per-task fixture isolation. The
  headless orchestrator handled some trivial tasks inline (`bound=False` noise),
  and the T2 grader is grep-only because the shared fixture carries an orthogonal
  unfixed bug. Shape tasks to reliably force delegation (so the forced policy
  actually binds) and give each task an isolated fixture state so a full
  test-suite grader works instead of a presence-grep.

*Exit:* the cost/quality knob is calibrated against a **discriminating,
statistically sound** eval set; new policies are A/B-proven before they ship;
routing can specialize per project.

### v1.6.0 — Parallel orchestration

- **R23 `[PA]`/`[KB]`:** map-reduce / parallel agent fan-out — decompose a task
  into **non-overlapping** sub-tasks dispatched in parallel with deterministic
  carving + collision-safe naming (the log already carries a per-dispatch `uid`);
  reduce, then verify. (KB: `parallel-agent-fleet-on-main.md`; PA: CrewAI/LangGraph
  bar.)
- **R24 `[KB]`:** smart-zone context budgeting — time/token-bound each agent
  (~<40% window utilization) and escalate to a larger tier only when input demands
  exceed budget. (KB: `keep-the-agent-in-the-smart-zone.md`.)
- **R25 `[KB]`:** durable, path-free briefs — express delegation briefs
  behaviorally (input shape, success criteria, no hardcoded paths) so they survive
  refactors. (KB: `durable-briefs-for-afk-agents.md`.)
- **R32 `[KB]`:** orchestrator intentional-compaction checkpoint — apply the
  smart-zone discipline to the *orchestrator's own* context (R24 budgets each
  sub-agent, not the orchestrator that accumulates every dispatch's report).
  Between dispatch batches, at a clean boundary, when headroom is low: the flush
  is already free (every dispatch is logged to `gearbox-log.jsonl` by the
  PostToolUse hook), so the orchestrator drops the verbose agent reports and
  continues lean — proactive compaction before the harness's forced lossy
  auto-compact (flush first, drop second). The **runtime-free policy rule**
  (`routing.md` rule 11) **shipped ahead at 2026-06-17 (fork 0.6.1)**; the
  proactive boundary trigger (pairing with R12's `PreCompact` hook) and a doctor
  check remain here at v1.6.0. (KB: `keep-the-agent-in-the-smart-zone.md`; source:
  the `context-firewall` skill.)

*Exit:* independent work fans out in parallel safely; per-agent context stays in
the smart zone; the orchestrator compacts proactively at boundaries instead of
decaying past its own smart zone; briefs outlive refactors.

### v1.8.0 — Ecosystem & integration

- **R26 `[CC]`:** a gearbox MCP server — expose the routing prior as queryable
  tools (`get_tier_for_task` / `get_win_rate` / `log_outcome`) so other tools and
  subagents query routing without spawning a gearbox session.
- **R27 `[PA]`:** OpenTelemetry export — emit telemetry as OTel spans so it
  interops with Helicone / Langfuse / standard observability, not just bespoke
  JSONL.
- **R28 (deferred from v0.4.0):** auto-regenerate the prior via a scheduled hook
  (drop the manual `/gearbox:recommend` run).
- **G29 `[PA]` (scope-guarded):** multi-provider escape hatch — config to redirect
  a tier to a non-Anthropic model (gateway), hedging price changes and partially
  surviving native routing. Prior-art flags this as arguably *outside* gearbox's
  Anthropic-native scope — build only if pricing/availability forces it.

*Exit:* gearbox is queryable (MCP), observable in standard tooling (OTel),
self-refreshing (scheduled prior), and provider-flexible if needed.

### v2.0.0 — Safe closed-loop self-improvement (moonshot)

Only after the router is learned (v1.2.0), calibrated (v1.4.0), and the reward is
graded (v0.9.0). (= G33, now with concrete reward inputs.)

- **G33:** online learning — a contextual bandit over `{task-class × model}` with
  bounded exploration (ε-greedy), fed by the **graded-verifier reward (R13)** and
  **transcript-mined negative signal (R14)**, behind hard rails: never overrides
  the hard floors / max-dimension routing / circuit breaker; **eval-harness (R1)
  gate** before any weight ships; **human-in-the-loop approval** for policy
  changes; privacy scrubbing at ingest; **one-command rollback**. The risk is a
  loop that overfits to one user's repos or silently degrades — the gate and
  rollback are the whole point.

*Exit:* gearbox improves its own routing from real, privacy-scrubbed usage without
hand-tuning — and can prove (R1) and undo (rollback) every change.

---

## At a glance

| Milestone | Theme | Headline | Items |
|-----------|-------|----------|-------|
| v0.1.8 ✅ | Hardening | Fix data path + delete dead code | G1–G14, G17, G18 |
| v0.2.0 ✅ | Integrity & CI | Auto-BASELINE + CI + drift guard | G19–G22, G15 |
| v0.3.0 ✅ | Observability | Log consolidation + dashboard + eval scorecard | G23–G26 |
| v0.4.0 ✅ | Static prior | Win-rate `{task-class × tier}` advisory | partial G27 |
| v0.5.0 ✅ | Credibility (modeled) | Exact per-component cost + modeled scorecard vs 3 baselines | R2, R1 (modeled), R3 (no-op) |
| **v0.6.0** ✅ | **Control** | Budget caps + aggressiveness knob + measured benchmark | **R4 ✅**, **R5 ✅**, **R6 ✅**, **R1-live ✅**, **R3 ✅** |
| **v0.7.0** ✅ | **Visibility** | Dashboard + status line + session accounting | **R7 ✅**, **R8 ✅**, **R9 ✅** |
| **v0.8.0** | **Efficiency** | Prompt-cache-aware routing | R10, R11, R12 |
| **v0.9.0** | **Graded reward** | Verifier score + transcript negative signal | R13, R14, R15, R16 |
| **v1.0.0** | **Adoption bar** | Tags, tool-scoping, declarative spec, moat | G28, G30, R17, R18, G31 |
| **v1.2.0** | **Learned router** | Embedding/LLM classifier over telemetry | G27, R19 |
| **v1.4.0** | **Calibration** | Threshold tuning + A/B + per-project tables + benchmark task-set hardening | R20, R21, R22, R29, R30, R31 |
| **v1.6.0** | **Parallelism** | Fan-out + smart-zone budgeting + durable briefs | R23, R24, R25, R32 (rule shipped 0.6.1) |
| **v1.8.0** | **Ecosystem** | MCP server + OTel + scheduled prior + providers | R26, R27, R28, G29 |
| **v2.0.0** | **Moonshot** | Safe online self-improvement | G33 |

**Known-limitation → milestone map** (from `README.md`):

| Limitation | Addressed by |
|------------|--------------|
| `cost_usd` always estimated | ✅ **closed v0.5.0** R2 (exact per-component cost from the `usage` split) |
| Routing prior is reward-sparse | **v0.9.0** R13 (graded reward) + R14; **v1.2.0** G27 |
| SessionStart injection varies across surfaces | **v1.0.0** G30 |
| Static policy re-billed as input every turn | **v0.8.0** R10 (cached prefix) |
| Prior must be regenerated manually | **v1.8.0** R28 (scheduled hook) |
| Agents load only at session start | inherent Claude Code constraint — documented, not on the ladder |

**Risk note.** The plugin tier is exposed to Anthropic shipping native routing
(#27665). The ladder front-loads durable value that survives a native release —
the **verifier loop** and the **graded-reward corpus** are the parts no native
router replicates (G31), and the credibility/control/visibility work (0.5–0.7) is
useful regardless. Provider hedging (G29) and the moonshot (G33) are deliberately
last, where the most sunk cost would be at risk.
