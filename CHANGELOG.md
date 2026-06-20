# Changelog

Shipped history of the `dividedby/gearbox` hard fork. Forward work lives in GitHub
issues/epics, not here — see the [open epics](https://github.com/dividedby/gearbox/issues?q=is%3Aopen+label%3Aepic).

Versions before full divergence (2026-06-18) were also mirrored upstream as PRs
(#10–#24); upstream never engaged, so mirroring stopped. See `docs/adr/0002-full-divergence.md`.

## [Unreleased]

Work landing toward the v0.9.0 epic (#9, "Graded reward — the moat"). Rolls into a
`[0.9.0]` section when the epic completes.

### SubagentStop outcome capture (#30, R15)
- **#30** New `hooks/scripts/subagent-outcome.py` — `SubagentStop` hook that fires
  when any subagent finishes and writes a structured outcome record
  (`ts`, `session_id`, `agent_id`, `agent_type`, `verdict`, `quality_score`,
  `message_head`) to `~/.claude/gearbox-subagent-outcomes.jsonl`. Verdict/score
  extraction uses the same regexes and clamp as `log-routing.py`.
- **Schema fix (R15 review):** primary message source is `last_assistant_message`
  (undocumented field — cheap fast-path when present); reliable documented fallback
  reads the final assistant text block from the subagent's transcript jsonl at
  `<session-dir>/subagents/agent-<agent_id>.jsonl`, with `agent_transcript_path`
  preferred when the payload carries it. If neither yields a message, verdict/score
  are recorded as null (graceful, exit 0).
- **Shared clamp helper:** extracted `clamp_quality_score(verdict, raw_score)` from
  `log-routing.resolve_routing()` into a standalone function in `log-routing.py`;
  both `resolve_routing()` and `subagent-outcome._extract_verdict_score()` call it —
  eliminates drift between the two clamp implementations.
- **Loader consolidation:** replaced hand-rolled importlib bootstrap in
  `subagent-outcome.py` with `routing_loader.load_log_routing()`.
- Both `--selfcheck` suites extended (transcript-read fallback, `agent_transcript_path`
  preference, all-empty graceful path) and green.

### Graded reward (#28, R13)
- **#28** Graded verifier signal — the verifier now emits a `SCORE: N` line (integer
  0–3 quality ordinal: 0=reject, 1=weak, 2=solid, 3=excellent) alongside the existing
  `VERDICT:` line, which stays authoritative for the orchestrator gate (`agents/verifier.md`).
- `hooks/scripts/log-routing.py` captures it as a new `quality_score` log field
  (verifier records only), clamped for consistency against the verdict (REJECT→0;
  APPROVE with absent/contradictory score→null; never fabricated), and stamps each
  record with a new `schema_version: 2` field (the one-liner #24 deferred to point of need).
- `bench/label.py` turns the score into reward: `reward = (quality_score / 3) / cost_usd`
  (linear). A new session-adjacency join attributes each verifier's score to the nearest
  preceding implementer dispatch, which doubles as the editing-dispatch filter. Reward is
  now **auto-derived from the log by default** (closing the loop — graded reward on every
  editing delegation, not the ~6% a human reached); the interactive human loop is retained
  behind `--manual` and now takes a 0–3 grade. Ceiling: the adjacency join is
  sequential-only; explicit correlation IDs follow when parallel verification lands (#13).
  Both `--selfcheck` suites extended and green.

## [0.8.0] — 2026-06-19 · Cache measurement & compaction snapshot (#25, #27)

The v0.8.0 epic (#8, "prompt-cache-aware routing") was **retired** after a
capability review: prompt caching is harness-controlled, so a plugin cannot pin
the routing policy via `cache_control: ephemeral` — and the injected policy
already sits inside the auto-cached prefix, so that saving happens for free. What
survived is buildable and shipped: measure the saving that already happens (#25),
and snapshot the session ledger before compaction (#27, now under epic #13). The
speculative cache-aware tier math (#26) was closed.

### Cache measurement (#25)
- **#25** `bench/cache-savings.py` — read-only report that quantifies the realized
  prompt-caching saving from `gearbox-log.jsonl`: per-model `cache_read` vs.
  `cache_creation` split and the net USD it saved against the full input rate
  (gross read saving − cache-creation premium). Closes the buildable half of R10:
  caching is automatic and harness-controlled — there is no plugin `cache_control`
  lever to add (the injected policy already sits inside the auto-cached prefix), so
  the only real deliverable is measuring the saving that already happens.
  `--selfcheck`-pinned.

### Parallel orchestration (epic #13)
- **#27** `hooks/scripts/snapshot-precompact.py` — new `PreCompact` hook (registered
  in `hooks.json`, no matcher → fires on manual and auto compaction). Snapshots the
  session's routing/cost ledger (dispatches, cost, weighted/total/cache tokens, tier
  breakdown), aggregated from `gearbox-log.jsonl`, plus the raw payload verbatim, to
  `~/.claude/gearbox-precompact-<session_id>.json` so the post-compaction session can
  recover its spend. Side-effecting and fail-open: never blocks compaction. Consuming
  the snapshot at the post-compact SessionStart is R32, tracked in #13. `--selfcheck`-pinned.

## [0.7.2] — 2026-06-19 · Single source of truth & internal cleanup (epics #6, #7)

Internal hardening only — refactors, a concurrency fix, and docs. No user-facing
behavior change; all numeric values identical before and after.

### Single source of truth (epic #7)
- **#22** `hooks/scripts/rates.py` — single source of truth for the model rate
  card: `TOKEN_RATES` (per-component USD/M), `BLENDED_RATES` (fallback blended
  USD/M), and `HAIKU_REF` (weighted-token denominator, kept as an independent
  tunable rather than derived from the input rate). Dated, `--selfcheck`-pinned,
  CI-gated. `log-routing.py`, `budget_common.py`, `bench/statusline.py`, and
  `bench/eval.py` now import it instead of declaring rates locally; cross-reference
  sync comments removed.
- **#23** Canonical `TIER_MODEL` (`{"T0": "haiku", "T1": "sonnet", "T2": "opus"}`)
  derived from `_AGENT_ROUTING` in `log-routing.py` at module load — asserts
  intra-tier consistency and excludes the TV (verifier) meta-tier. `bench/run-live.py`
  `_TIER_FAMILY` and `bench/eval.py` `_TIER_RATES` now derive from it; a shared
  `hooks/scripts/routing_loader.py` replaces three duplicate importlib helpers;
  `check_consistency.py` gained a `compare_tier_model()` gate (non-vacuous
  selfcheck covering wrong/missing/extra tier and TV exclusion).
- **#41** `bench/tasks.md` blended-rate prose now points at the `BLENDED_RATES`
  card in `rates.py` instead of restating the numbers.

### Seam cleanup & fixes (epic #6)
- **#16** Concurrency fix — opt-in baseline keying via an orchestrator-minted
  `[gearbox-baseline-id=<id>]` token. `capture-baseline.py` still writes the legacy
  `.claude/gearbox-baseline.txt` (sequential behavior unchanged) and additionally
  writes `.claude/gearbox-baseline-<id>.txt` on the parallel path; stale keyed files
  (>1h) cleaned on write, legacy file untouched. `routing.md` rule 9 and
  `agents/verifier.md` document the sequential/parallel paths and that `tool_use_id`
  is unavailable at dispatch time. `--selfcheck` rewritten.
- **#18** `run-live.py` skips `(task_id, policy)` pairs already present in
  `bench/training-data.jsonl` (and within-run duplicates), mirroring `label.py`'s
  `load_labeled_keys()`; skips logged to stdout. `--selfcheck` extended.
- **#20** `inject-routing.py` emits a one-line stderr diagnostic when neither
  `routing.md` copy is found (names the likely `CLAUDE_PLUGIN_ROOT` cause, lists the
  two paths checked); fail-open preserved (exit 0, empty stdout). `_selfcheck` extended.
- **#19** Documented `task_cap` as **warn-only by design** (never blocks dispatches):
  docstrings in `budget-warn.py`, `enforce-budget.py`, and `budget_common.py`, plus
  the `README.md` Budget caps section, now state `session_cap` blocks and `task_cap`
  warns. No enforcement behavior changed; no code logic touched.
- **#21** Removed the unconsumed `session-summary.py` seam and its `SessionEnd` hook
  registration — `~/.claude/gearbox-sessions.jsonl` had zero consumers and was ~95%
  re-derivable from `gearbox-log.jsonl`. Any existing file is no longer written; users
  may delete it at their discretion.

## [0.7.1] — 2026-06-17 · Visibility (point)
- Status-line segment reframed to show **estimated savings vs an all-Opus baseline**
  (`gearbox saved $0.43`) instead of raw spend; `GEARBOX_STATUSLINE_UNIT=usd|tokens`
  toggles money vs Haiku-equivalent weighted tokens.
- Doctor CHECK 6 Step-C fix: the log-recount snippet iterated the `Path` object
  instead of `p.open()`, raising `TypeError`.

## [0.7.0] — 2026-06-17 · Visibility (R7–R9)
- **R7** richer `bench/dashboard.py`: spend by tier, escalation rate, verifier reject
  rate, cost-over-time (`--over-time`), prior-vs-actual tier mix (`--prior`).
- **R8** composable status-line segment (`bench/statusline.py`). Plugins cannot register
  the main `statusLine` (only `subagentStatusLine`), so it is wired into the user's own
  `settings.json`; doctor CHECK 10 reports wiring status (informational, never fails).
- Explicit escalation logging: the `[gearbox-escalation from=T<n> to=T<m>]` marker →
  `escalation`/`escalated_from`/`escalated_to` log fields.

## [0.6.2] — 2026-06-17
- Doctor CHECK 8 fix: version freshness now resolves the plugin root from the substituted
  `${CLAUDE_PLUGIN_ROOT}` token (argv, like CHECK 0) instead of `os.environ`, which the
  command shell doesn't carry — it had been silently comparing against the *upstream*
  repo's version, not the fork's manifest.

## [0.6.1] — 2026-06-17
- **R32 (partial)** orchestrator context-hygiene routing rule (`routing.md` rule 11): a
  proactive intentional-compaction checkpoint between dispatch batches, dropping verbose
  agent reports already persisted to the routing log before the harness's forced
  auto-compact. The runtime-free half; the boundary trigger + doctor check remain (now
  tracked in the v1.6.0 epic).

## [0.6.0] — 2026-06-16 (R1-live/R3 2026-06-17) · Control (R4–R6, R1-live, R3)
- **R6** cost/quality aggressiveness knob: `GEARBOX_PROFILE=cost-conscious|balanced|quality-first`
  + benchmark-only forced-tier profiles.
- **R4/R5** opt-in weighted-token budget caps + 80%/100% threshold warnings. A PreToolUse
  hook asks before an over-cap dispatch (default unit = Haiku-equivalent weighted tokens);
  a PostToolUse hook warns. R5 reframed — the warning is emitted by the budget hook itself,
  not a `Notification` hook (that event is observational-only).
- **R1-live** `bench/run-live.py`: the measured counterfactual benchmark — runs the fixed
  task set under each policy via headless `claude -p` (forcing baselines with R6 profiles;
  always-Opus via an edit-capable `always-opus-build` profile, since `always-t2` routes to
  the read-only architect), each on a fresh temp copy of `bench/fixtures/toy-cli/`, capturing
  exact per-policy cost (R2) + a deterministic acceptability grade. Local-maintainer-only
  (`bypassPermissions`); CI runs only the offline `--selfcheck`.
- **R3** the runner emits the canonical `total_cost_usd=… num_turns=…` cost-ledger line, so
  a run is metering-ready if ever wrapped in a CI workflow.

## [0.5.0] — 2026-06-16 · Credibility (R2, R1 modeled)
- **R2** exact per-component token cost: the logger bills each delegation from the real
  `usage` split (input / output / cache_read / cache_creation, with a 5m/1h cache-write
  sub-breakdown), closing the "`cost_usd` is always estimated" limitation.
- **R1 (modeled)** `bench/eval.py` scores the live router against always-Sonnet, always-Opus,
  and escalate-on-fail, re-pinning the stale `$45/M` Opus rate. R3 was a no-op at this
  milestone (no headless `claude -p` yet).

## [0.4.0] — 2026-06-16 · Static win-rate prior (partial G27)
- A min-sample-guarded `{task-class × tier}` win-rate prior (verifier approve-rate + cost),
  surfaced as an advisory via `/gearbox:recommend` + SessionStart. Advisory only — never
  overrides hard floors / max-dimension routing / circuit breaker.
- **Scope:** the *static prior* only. The full learned router (G27) and transcript mining
  (G32) did not ship — both carried into the forward ladder (now v1.2.0 / v0.9.0 epics).

## [0.3.1] — 2026-06-15
- CodeRabbit review-fix patch (Observability milestone follow-up).

## [0.3.0] — 2026-06-15 · Observability & data quality (G23–G26)
- Global-log consolidation + dashboard + offline eval scorecard.

## [0.2.0] — 2026-06-15 · Integrity & CI (G15, G19–G22)
- **G21** PreToolUse `capture-baseline.py` auto-captures `git status --short` to
  `.claude/gearbox-baseline.txt` before T1/T2 dispatches; the verifier reads it (removing
  the manual BASELINE step).
- **G19/G20** first standing automation: GitHub Actions runs the selfchecks + JSON manifest
  validation + a spec-vs-code consistency test (`bench/check_consistency.py`) that fails on
  drift between the `routing.md` tier table, `_AGENT_ROUTING`, and agent `model:` frontmatter.
- **G22/G15** documented the architect→builder execution handoff (read-only architect →
  orchestrator routes execution to builder); gated the ultrathink advice after verifying
  thinking doesn't cross the Task boundary.

## [0.1.8] — 2026-06-15 · Hardening & cleanup (G1–G18)
- **G1** security: `prompt_head` secret-scrubbed before write; `bench/training-data.jsonl`
  gitignored — a credential in a delegation prompt can no longer reach a committable file.
- **G2–G18** log hardening: per-dispatch `uid`; log dir from `CLAUDE_PROJECT_DIR`; split-usage
  tokens summed when only one side present; `bool` rejected as a token count; verifier logged
  as tier `TV`; metric extraction trimmed to confirmed keys; dead string-`tool_response`
  parse path deleted.
- **G6/G7** `/gearbox:init` guards an unset `CLAUDE_PLUGIN_ROOT`; doctor CHECK 7 uses `grep -F`.
- **G9/G10/G13/G14** routing-spec clarifications (verdict-line wording, T1/T2 trigger,
  max-across-dimensions scoring, "design problem" definition).

## [0.1.4] – [0.1.7] — 2026-06-14/15 · Fork bring-up
- Forked to `dividedby/gearbox`; implemented all 11 filed upstream issues; ran our install
  off the fork. Pinned the real Task `tool_response` usage keys (`totalTokens` /
  `totalToolUseCount` / `totalDurationMs`, captured from session transcripts); doctor CHECK 8
  derives the source repo from manifest `repository`; recorded resolved `model` / `tier` /
  verifier `verdict` (the reward signal); `_record_id` includes delegation discriminators
  so distinct parallel delegations don't collide. Set `plugin.json` `repository` →
  `dividedby/gearbox`. Detail in `maintenance/README.md` ("Fork").
