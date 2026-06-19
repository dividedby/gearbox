# Changelog

Shipped history of the `dividedby/gearbox` hard fork. Forward work lives in GitHub
issues/epics, not here — see the [open epics](https://github.com/dividedby/gearbox/issues?q=is%3Aopen+label%3Aepic).

Versions before full divergence (2026-06-18) were also mirrored upstream as PRs
(#10–#24); upstream never engaged, so mirroring stopped. See `docs/adr/0002-full-divergence.md`.

## [Unreleased] — 2026-06-19 · Canonical tier→model map (#23, epic #7)

### Changed
- **#23** `hooks/scripts/log-routing.py`: derives and exports `TIER_MODEL`
  (`{"T0": "haiku", "T1": "sonnet", "T2": "opus"}`) from `_AGENT_ROUTING` at
  module load. Asserts intra-tier consistency (two agents on the same tier must
  agree on model). TV (verifier meta-tier) is excluded.
- **#23** `bench/run-live.py`: `_TIER_FAMILY` now loaded from `TIER_MODEL` via
  importlib; independent literal removed.
- **#23** `bench/eval.py`: `_TIER_RATES` now derived as
  `BLENDED_RATES[TIER_MODEL[tier]]` for each routing tier; independent literal removed.
- **#23** `bench/check_consistency.py`: `compare_tier_model()` + `load_tier_model()`
  added; `run_real_check()` and `--selfcheck` now assert `TIER_MODEL` matches
  `_AGENT_ROUTING`. Zero behavior change; all numeric values identical.

## [Unreleased] — 2026-06-19 · Single rates module (#22, epic #7)

### Added
- **#22** `hooks/scripts/rates.py` — single source of truth for the model rate
  card. Exposes `TOKEN_RATES` (per-component USD/M), `BLENDED_RATES` (fallback
  blended USD/M), and `HAIKU_REF` (weighted-token denominator). Rate card
  confirmed 2026-06-19. `--selfcheck` pins all expected current values.

### Changed
- **#22** `hooks/scripts/log-routing.py`, `hooks/scripts/budget_common.py`,
  `bench/statusline.py`, and `bench/eval.py` now import rate constants from
  `rates.py` instead of declaring them locally. Cross-reference sync comments
  (ponytail: re-pin together) removed. Zero behavior change; all numeric values
  are identical.
- CI: added `python3 hooks/scripts/rates.py --selfcheck` step.

## [Unreleased] — 2026-06-19 · Remove session-summary seam (#21, epic #6)

### Removed
- **#21** `hooks/scripts/session-summary.py` and its `SessionEnd` hook registration
  removed. The script wrote per-session rollup records to `~/.claude/gearbox-sessions.jsonl`,
  but that file had zero consumers — ~95% of its data is re-derivable from
  `gearbox-log.jsonl`, and the only unique datum (`reason`) was judged not worth the
  maintenance cost. The `SessionEnd` block in `hooks/hooks.json` is removed entirely
  (session-summary was its sole entry). Any existing `~/.claude/gearbox-sessions.jsonl`
  file is no longer written; users may delete it at their discretion.

## [Unreleased] — 2026-06-19 · task_cap documented as warn-only by design (#19, epic #6)
- **#19** Clarified in-place that `task_cap` is **warn-only by design** and never
  blocks dispatches. `budget-warn.py` docstring now leads with an explicit
  "WARN-ONLY BY DESIGN" callout explaining why pre-dispatch enforcement is not
  possible (cost unknowable before a dispatch runs). `enforce-budget.py` docstring
  updated to explicitly name `task_cap` and redirect to `budget-warn.py`.
  `budget_common.py` `resolve_budget_config` docstring now documents both cap
  semantics side-by-side; `is_active` clarified that `task_cap` does not enable
  blocking. `README.md` Budget caps section now labels `session_cap` as
  **blocking** and `task_cap` as **warn-only, never blocks**, with guidance to use
  `session_cap` for hard enforcement. Version history blurb for 0.6.0 corrected
  ("per-task warn-only threshold" replaces "per-task ceilings").
  No enforcement behavior changed; no code logic touched.

## [Unreleased] — 2026-06-19 · Inject-routing not-found diagnostic (#20, epic #6)
- **#20** `inject-routing.py` now emits a one-line stderr diagnostic when neither
  the project-local nor the plugin copy of `routing.md` is found, naming the likely
  cause (`CLAUDE_PLUGIN_ROOT` unset or missing) and listing the two paths checked.
  Fail-open is preserved: the hook exits cleanly (code 0) and writes nothing to
  stdout, so no session is ever blocked. `_selfcheck` extended with a subprocess
  round-trip that asserts the diagnostic fires, stderr content, zero exit code, and
  empty stdout on the not-found path.

## [Unreleased] — 2026-06-19 · Benchmark dedup (#18, epic #6)
- **#18** `run-live.py` now skips `(task_id, policy)` pairs already present in
  `bench/training-data.jsonl` before running — mirrors `label.py`'s
  `load_labeled_keys()`. New `load_existing_keys()` loads the set from the output
  file; within a single run the in-memory set is updated after each write so
  within-run duplicates are also prevented. The skip is logged to stdout.
  `--selfcheck` extended with a round-trip test (existing pair skipped, new pair
  runs, malformed/incomplete rows silently ignored, missing file → empty set).
  `eval.py` not touched: the warning would be noise once the source is fixed.

## [Unreleased] — 2026-06-19 · Concurrency fix (#16, epic #6)
- **#16** Opt-in baseline keying via orchestrator-minted token: `capture-baseline.py`
  always writes `.claude/gearbox-baseline.txt` (legacy, preserving today's behavior
  for sequential dispatches). When the orchestrator embeds `[gearbox-baseline-id=<id>]`
  in an implementer's Task prompt (parallel path only), the hook also writes
  `.claude/gearbox-baseline-<id>.txt`. The orchestrator mints the token itself —
  `tool_use_id` is not available at dispatch time and must not be used.
- Stale keyed baseline files (>1 hour) are cleaned up on each write; legacy file
  is never touched by cleanup.
- `routing.md` rule 9 updated: sequential path documented (no orchestrator action
  needed); parallel path documented (orchestrator mints baseline_id, embeds in
  implementer prompt, passes same id to verifier). Explicit note that `tool_use_id`
  is NOT available to the orchestrator.
- `agents/verifier.md` updated: baseline selection priority (keyed by baseline_id →
  legacy → prompt BASELINE → missing-note); note that missing token under concurrency
  means the legacy baseline may be stale.
- `capture-baseline.py --selfcheck` rewritten: extract_baseline_id (present / absent /
  malformed / empty marker), build_body header (id present/absent), integration
  (with token → both files exist; without token → only legacy, keyed glob empty),
  and cleanup behavior.

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
