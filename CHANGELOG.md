# Changelog

Shipped history of the `dividedby/gearbox` hard fork. Forward work lives in GitHub
issues/epics, not here — see the [open epics](https://github.com/dividedby/gearbox/issues?q=is%3Aopen+label%3Aepic).

Versions before full divergence (2026-06-18) were also mirrored upstream as PRs
(#10–#24); upstream never engaged, so mirroring stopped. See `docs/adr/0002-full-divergence.md`.

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
- **R9** `SessionEnd` hook (`hooks/scripts/session-summary.py`) writing a per-session
  rollup to `~/.claude/gearbox-sessions.jsonl`. `Stop` fires every turn; `SessionEnd` is
  the correct once-per-session hook (verified against the hooks reference). The payload
  carries no cost/tier data, so the hook reads the dispatch log filtered by `session_id`.
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
