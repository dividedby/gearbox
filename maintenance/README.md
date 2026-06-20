# Gearbox: tracking notes

**Upstream:** https://github.com/Adityaraj0421/gearbox  
**Our fork:** https://github.com/dividedby/gearbox (fork `main` at v1.0.0 — all filed issues + post-install fixes + 2026-06-15 audit hardening + v0.2.0 Integrity & CI and v0.3.0 Observability & data-quality milestones + v0.3.1 CodeRabbit review-fix patch + v0.4.0 routing-prior milestone (a static win-rate routing prior) + v0.5.0 Credibility milestone (exact per-component token cost + modeled baseline scorecard) + v0.6.0 Control milestone: cost/quality aggressiveness knob + opt-in weighted-token budget caps + measured counterfactual benchmark (R1-live) & cost-ledger summary line (R3) + v0.6.1 orchestrator context-hygiene routing rule (R32, partial) + v0.6.2 doctor CHECK 8 plugin-root fix + v0.7.0 Visibility milestone: status-line segment + richer dashboard + explicit escalation logging + v0.7.1 status-line savings reframe (segment shows estimated savings vs an all-Opus baseline, money/weighted-token toggle) + doctor CHECK 6 Step-C fix + v0.7.2 Single source of truth & internal cleanup (epics #6, #7): #16 concurrency fix (opt-in baseline keying via orchestrator-minted baseline_id token), #18 benchmark dedup, #19 task_cap warn-only docs, #20 inject-routing not-found diagnostic, #21 session-summary seam removal, #22 single rates module, #23 canonical tier→model map + shared routing_loader, #41 tasks.md rate-prose pin — internal hardening, no behavior change + v0.8.0 Cache measurement & compaction snapshot: epic #8 ("prompt-cache-aware routing") retired — caching is harness-controlled, no plugin `cache_control` lever, injected policy already inside the auto-cached prefix; #25 `bench/cache-savings.py` measures the realized cache_read-vs-creation saving the log already captures, #27 `snapshot-precompact.py` PreCompact hook snapshots the session ledger before compaction (now under epic #13), #26 cache-aware tier math closed as speculative) + v0.9.0 Graded reward — the moat (epic #9): #28 graded verifier `SCORE: 0–3` → `reward=(score/3)/cost` (R13), #29 `bench/mine-corrections.py` transcript miner for the negative-reward signal — corrections/re-dispatches/escalations attributed to the failing dispatch (R14), #30 `subagent-outcome.py` SubagentStop hook capturing structured outcomes (R15), #31 `classify-prompt.py` UserPromptSubmit tier pre-classifier advisory (R16) + v1.0.0 Production / adoption bar (epic #10): #55 release-tag convention (G28, retro v0.9.0 tag), #56 tool-scoping consistency assertion (R17), #57 canonical task-class registry `bench/task-classes.json` (R18), #58 differentiation ADR-0003 (G31), #59 SessionStart injection-variance investigation — ruled out (G30))  
**Installed:** 2026-06-19, user scope, **v1.0.0** (fork) — reinstalled this session (`/plugin` update + `/reload-plugins`); CHECK 8 confirms installed == latest (1.0.0). Tags: lightweight semver `v0.9.0` at `ee54fc8`, `v1.0.0` at `09c853b`.  
**Doctor status:** fork **v1.0.0** ran 2026-06-19 — **all 11 checks PASS (healthy)**. CHECK 6 live dispatch logged (`Agent`/`gearbox:scout`/`haiku`, log 383→384); CHECK 8 installed == latest (1.0.0); CHECK 9 routing-prior artifact present (generated 2026-06-16, age 3d); CHECK 10 status-line segment self-checks OK, reports `NOT_WIRED` (optional — not wired in this session's settings.json). The `SubagentStop`/`UserPromptSubmit` hooks are live but not covered by a dedicated doctor check — a future addition could assert their registration.  
**Shipped history:** [CHANGELOG.md](../CHANGELOG.md). **Forward work:** GitHub [epics](https://github.com/dividedby/gearbox/issues?q=is%3Aopen+label%3Aepic) + issues (the in-repo `docs/roadmap.md` + `audit-2026-06-15.md` were retired into GitHub on 2026-06-18; full text in git history).

## Fork

Upstream went quiet with our 9 issues unanswered (single maintainer, repo days old).
Decision (2026-06-14): fork to `dividedby/gearbox`, implement all 9, run our install
off the fork, and mirror each change upstream as a PR in case the maintainer returns.

- Fork `main` carries all 9 fixes (merge-commit only, per our branching policy) + a
  version bump to **0.1.4**. Each fix landed on a `feature/*` branch and was reviewed
  (5 of 7 via `gearbox:verifier`; the two mechanical edits — #1, #2 — lead self-checked)
  before merge.
- 7 upstream PRs opened (one per theme): #10–#16. See the table below.
- Post-install fixes (v0.1.5), found while validating the fork via `/gearbox:doctor`:
  - **#17** (upstream PR) — pinned the real Task `tool_response` usage keys
    (`totalTokens` / `totalToolUseCount` / `totalDurationMs`; captured from the session
    transcript), so `num_turns`/`duration_ms` stop logging null; also fixed a
    falsy-coalescing bug that dropped a legitimate `0`. Confirmed: no cost field exists
    in `tool_response`, so cost stays estimated.
  - **#18** (upstream PR) — doctor CHECK 8 freshness now derives the source repo from
    the manifest `repository` field instead of a hardcoded upstream URL.
  - Fork-only: set `plugin.json` `repository` → `dividedby/gearbox` (so #18's freshness
    check tracks the fork) + version bump to 0.1.5. Not mirrored upstream.
- Post-install fixes (v0.1.6), from the 2026-06-15 maintenance/insights pass:
  - **#20** (upstream PR [#21](https://github.com/Adityaraj0421/gearbox/pull/21)) — scout
    reliability: counts must be command-derived and quoted, the ref read is pinned and
    reported, findings tagged CONFIRMED/INFERRED/NOT-FOUND; `routing.md` adds a "scout
    results are recon, not ground truth" rule (a count/answer gating a mutation is
    re-verified by the orchestrator; a surprising or empty result gets a second look).
  - **#22** (upstream PR [#23](https://github.com/Adityaraj0421/gearbox/pull/23)) —
    `log-routing.py` now records resolved `model` (passed > derived-from-tier > absent,
    with a `model_source` provenance field), `tier`, and the verifier `verdict`
    (approve/reject) — the reward signal the v0.3.0 routing prior needs. Fixes the large
    share of entries that logged `model = "(not passed)"` because the Task call omitted
    the param.
  - Fork-only: version bump to 0.1.6. Not mirrored upstream.
- Post-install fixes (v0.1.7), from reviewing CodeRabbit comments on our upstream
  PRs (2026-06-15). Most PR comments were CodeRabbit rate-limit notices — the org's
  prepaid credits are exhausted, so 10 of 12 open PRs got no bot review; only #10
  (clean) and #21 (cumulative diff) were reviewed. Two legitimate findings, fixed by
  amending the originating feature branches (which updates their PRs):
  - PR [#16](https://github.com/Adityaraj0421/gearbox/pull/16) (`bench/label.py`) —
    `_record_id` hashed only `ts|session_id|prompt_head`; added the delegation
    discriminators (`tool_name`/`subagent_type`/`model`) so two distinct delegations
    sharing those values can't collide and silently drop one during resumable dedup.
  - PR [#17](https://github.com/Adityaraj0421/gearbox/pull/17) (`log-routing.py`) —
    derive `total_tokens` by summing split `usage.input_tokens`/`output_tokens` when
    no aggregate token field is present, so `cost_usd` can still be estimated.
  - Fork-only: version bump to 0.1.7. Not mirrored upstream.
- Post-install fixes (v0.1.8), from the 2026-06-15 full-surface audit
  (2026-06-15 full-surface audit; see `CHANGELOG.md` and git history). Four atomic `feature/*`
  branches + version bump on fork `main`; all selfchecks green; installed and
  doctor-green (all 9 checks PASS, 2026-06-15):
  - **G1** (security, `feature/log-privacy`): `prompt_head` is secret-scrubbed
    before write and `bench/training-data.jsonl` is gitignored — a credential in a
    delegation prompt can no longer reach a committable file.
  - **G2–G18** (`feature/log-hardening`): per-dispatch `uid` so parallel identical
    delegations don't collide and get deduped; log dir from `CLAUDE_PROJECT_DIR`;
    split-usage tokens summed when only one side present; `bool` rejected as a
    token count; verifier logged as tier `TV` not `T0`; metric extraction trimmed
    to confirmed keys; dead string-`tool_response` parse path deleted.
  - **G6/G7** (`feature/cmd-guards`): `/gearbox:init` guards an unset
    `CLAUDE_PLUGIN_ROOT`; doctor CHECK 7 uses `grep -F`.
  - **G9/G10/G13/G14** (`feature/routing-spec-clarify`): verifier verdict-line
    wording aligned with the scan-anywhere reader; verifier trigger uses the T1/T2
    abstraction; routing rule 2 routes on max-across-dimensions; rule 3 defines
    "design problem".
  - Resolved without code change: **G16** (`Explore` is a valid fallback subagent
    type), **G12** (manifest `author` stays upstream's per minimal-divergence).
  - Fork-only: version bump to 0.1.8. Audit items G15/G19–G31 are deferred to the
    v0.2.0+ work (now tracked as GitHub epics).
- v0.2.0 (Integrity & CI milestone, 2026-06-15) — five items across atomic
  `feature/*` branches + version bump on fork `main`; CI green, all four selfchecks
  pass, doctor all-9-PASS on the v0.2.0 install:
  - **G21** (`feature/baseline-capture`): a PreToolUse hook (`capture-baseline.py`)
    auto-captures `git status --short` to `.claude/gearbox-baseline.txt` before T1/T2
    implementer dispatches; the verifier reads it (file-based — a PreToolUse hook
    can't inject into the spawned subagent), removing the manual capture step. (See #16
    for the subsequent keying-by-dispatch_id fix that prevents parallel-dispatch collision.)
  - **G19/G20** (`feature/ci`): first standing automation — GitHub Actions runs the
    selfchecks + JSON manifest validation + a spec-vs-code consistency test
    (`bench/check_consistency.py`) that fails on drift between the `routing.md` tier
    table, `_AGENT_ROUTING`, and agent `model:` frontmatter.
  - **G22/G15** (`feature/spec-clarify`): documented the architect→builder execution
    handoff (read-only architect → orchestrator routes execution to builder),
    distinct from the circuit breaker; gated the ultrathink advice after verifying
    thinking doesn't cross the Task boundary.
  - Mirrored upstream in the ongoing sync PR #24; fork-only `repository`/version
    pinned to upstream values there.
- **Full divergence (2026-06-18):** upstream stayed silent through all 11 issues,
  PRs #10–#23, and the long-lived sync PR #24. We closed #24, deleted the
  `upstream-sync` branch, and now run as a hard fork — no upstream mirroring or
  scheduled tracking. The `upstream` remote stays configured (dormant) in case the
  maintainer revives the project; re-engagement is pull-only and on demand (see
  `CLAUDE.md` → "If upstream revives"). The `repository`/version lines are now just
  the fork's own identity, not a divergence from anything we publish.

## What it does

5-agent tiered routing system that injects a routing policy at SessionStart and escalates automatically:

| Tier | Agent              | Model  | Use for |
|------|--------------------|--------|---------|
| T0   | gearbox:scout      | haiku  | exploration, search, reading, summarising |
| T0   | gearbox:grunt      | haiku  | mechanical edits, 1-2 files, zero design decisions |
| T1   | gearbox:builder    | sonnet | features, bug fixes, tests, refactors ≤5 files |
| T2   | gearbox:architect  | opus   | cross-cutting design, concurrency, migrations, security, perf |
| —    | gearbox:verifier   | haiku  | independent review after every T1/T2 that edits files |

Routing policy is injected via SessionStart hook (~2.5KB of context). Delegations are logged to `.claude/gearbox-log.jsonl` in each project.

## How we integrated it

- Removed `~/.claude/agents/researcher.md` and `implementer.md` (superseded by scout/builder)
- Removed `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` from settings.json (premature)
- Trimmed CLAUDE.md Delegation section — tier selection now deferred to gearbox
- Updated Backpressure section — verifier handles post-delegation review
- Status line: the gearbox savings segment is composed into our `statusline.sh` wrapper (`~/.claude/statusline` symlinks to repo `statusline/`), defaulting to token-weighted savings (`GEARBOX_STATUSLINE_UNIT`; export `=usd` for dollars). Plugins can't own the main `statusLine` and `settings.json` `env` doesn't reach the statusLine subprocess, so the unit is set at the wrapper's invocation.

## Issues we filed

All 11 implemented in the fork. The maintainer never responded, so we **closed all 11
issues and PRs #10–#23**, then on **2026-06-18 closed the sync PR #24** and stopped
contributing upstream entirely (full divergence — see the "Fork" section). The table
below is historical record.

| # | Title | Status |
|---|-------|--------|
| [#1](https://github.com/Adityaraj0421/gearbox/issues/1) | doctor: CHECK 7 should scan ~/.claude/agents/ for user-level agent conflicts | fork ✓ · PR [#10](https://github.com/Adityaraj0421/gearbox/pull/10) closed |
| [#2](https://github.com/Adityaraj0421/gearbox/issues/2) | docs: add integration guide for existing CLAUDE.md delegation rules | fork ✓ · PR [#11](https://github.com/Adityaraj0421/gearbox/pull/11) closed |
| [#3](https://github.com/Adityaraj0421/gearbox/issues/3) | routing: add circuit breaker after T2 failure — escalation ladder has no stop condition | fork ✓ · PR [#12](https://github.com/Adityaraj0421/gearbox/pull/12) closed |
| [#4](https://github.com/Adityaraj0421/gearbox/issues/4) | verifier: clarify scope policy for formatting-only changes in declared file set | fork ✓ · PR [#13](https://github.com/Adityaraj0421/gearbox/pull/13) closed |
| [#5](https://github.com/Adityaraj0421/gearbox/issues/5) | feat(log): enrich gearbox-log.jsonl with post-completion metrics (cost, turns, tokens) | fork ✓ · PR [#15](https://github.com/Adityaraj0421/gearbox/pull/15) closed |
| [#6](https://github.com/Adityaraj0421/gearbox/issues/6) | bench: add outcome-labeling runner to collect training data for v0.3.0 learned router (depends on #5) | fork ✓ · PR [#16](https://github.com/Adityaraj0421/gearbox/pull/16) closed |
| [#7](https://github.com/Adityaraj0421/gearbox/issues/7) | scout: grant read-only Bash for gh/git/log recon | fork ✓ · PR [#14](https://github.com/Adityaraj0421/gearbox/pull/14) closed |
| [#8](https://github.com/Adityaraj0421/gearbox/issues/8) | verifier: flag masked failures (success:false / unchecked exit codes) | fork ✓ · PR [#13](https://github.com/Adityaraj0421/gearbox/pull/13) closed |
| [#9](https://github.com/Adityaraj0421/gearbox/issues/9) | builder/grunt: update config before deleting referenced files (avoid self-lockout) | fork ✓ · PR [#14](https://github.com/Adityaraj0421/gearbox/pull/14) closed |
| [#20](https://github.com/Adityaraj0421/gearbox/issues/20) | scout: require command-derived counts, ref pinning, and confidence tags | fork ✓ · PR [#21](https://github.com/Adityaraj0421/gearbox/pull/21) closed |
| [#22](https://github.com/Adityaraj0421/gearbox/issues/22) | feat(log): record resolved model, tier, and verifier verdict for reward signal | fork ✓ · PR [#23](https://github.com/Adityaraj0421/gearbox/pull/23) closed |

## Roadmap

Forward work lives in GitHub as `epic` issues with decomposed children, not in
in-repo roadmap docs. Shipped milestones (v0.1.4 → v0.7.1) are in
[CHANGELOG.md](../CHANGELOG.md).

**Open epics** ([all](https://github.com/dividedby/gearbox/issues?q=is%3Aopen+label%3Aepic)):

| Epic | Theme |
|------|-------|
| #6 | Concurrency & correctness hardening *(near-term; decomposed)* |
| #7 | Single source of truth — rates, tier map & log schema *(decomposed)* |
| #8 | v0.8.0 — Prompt-cache-aware routing *(decomposed)* |
| #9 | v0.9.0 — Graded reward (the moat) *(decomposed)* |
| #10 | v1.0.0 — Production / adoption bar |
| #11 | v1.2.0 — Semantic routing refinement |
| #12 | v1.4.0 — Calibration & benchmark hardening |
| #13 | v1.6.0 — Parallel orchestration |
| #14 | v1.8.0 — Ecosystem & integration |
| #15 | v2.0.0 — Safe closed-loop self-improvement |

Sequencing: #6 (latent bugs, unblocks #13) and #7 (clean cost math, unblocks #8/#9)
come first; then the version ladder #8 → #15. Strategic spine (from the prior-art
verdict): make routing **credible → controllable → visible → efficient →
self-improving** on the graded-verifier signal only gearbox has, before earning 1.0
and climbing to semantic routing refinement. Source tags carried on each epic: `[PA]`
prior-art · `[CC]` Claude Code features · `[KB]` agent-research.

## Known limitations (fork v0.7.1)

- ~~Dirty-file false rejects: verifier needs a BASELINE snapshot; if omitted, pre-existing uncommitted changes may trigger false REJECTs.~~ — fixed in fork v0.2.0 (G21): a PreToolUse hook auto-captures the BASELINE to `.claude/gearbox-baseline.txt` before T1/T2 dispatches and the verifier reads it. ~~Parallel-dispatch baseline collision: two concurrent T1/T2 dispatches clobber each other's single baseline file, causing the verifier for the first dispatch to diff against the second's pre-edit state.~~ — fixed in fork (issue #16): the orchestrator mints a short `baseline_id` token per implementer dispatch (parallel path only), embeds `[gearbox-baseline-id=<id>]` in the Task prompt, and passes the same id to the matching verifier. The hook writes a keyed `.claude/gearbox-baseline-<id>.txt` alongside the always-present legacy file. Sequential dispatches require no orchestrator action (legacy file suffices).
- ~~Doctor CHECK 8 (version freshness) read `CLAUDE_PLUGIN_ROOT` from `os.environ` inside its python subprocess, but the command's shell doesn't carry that env var — root came back empty and Step B silently compared the installed version against the *upstream* repo instead of the fork's manifest.~~ — fixed in fork v0.6.2: the substituted `${CLAUDE_PLUGIN_ROOT}` token (the same resolution CHECK 0 uses) is passed as `argv[1]`, so version + repository read from the real installed manifest; empty argv still degrades to `NO_PLUGIN_ROOT`.
- ~~Doctor CHECK 6 Step-C (live-dispatch log recount) iterated the `Path` object (`for l in p`) instead of the open file, raising `TypeError` when the check ran.~~ — fixed in fork v0.7.1: the snippet now iterates `p.open()`, matching Step A.
- Agents only load at session start — editing agent files mid-session has no effect until restart. (Inherent Claude Code constraint; documented, not on the roadmap ladder.)
- ~~`ultrathink` in T2 prompts is experimental; propagation to subagents unverified.~~ — resolved in fork v0.2.0 (G15): verified that thinking does not cross the Task boundary, so the advice was removed; tier/model selection (architect = opus) is the lever.
- ~~SessionStart hook injection may vary across Claude Code surfaces.~~ — investigated in fork v1.0.0 (G30, #59): **ruled out** as a defect. The SessionStart hook (`inject-routing.py`, registered unconditionally in `hooks/hooks.json` — no surface-detection code) injects the routing policy via `additionalContext`; observed live on the **terminal CLI** this session. Per Claude Code docs, hooks are a *local-execution* feature: the **VS Code and JetBrains** integrations share `~/.claude/settings.json` and run the same engine, so SessionStart fires identically there. The only cross-surface difference is by-design platform isolation — **claude.ai on the web** runs on cloud VMs that load only repo-committed `.claude/settings.json`, not user-level `~/.claude` config, so a *user-scoped* plugin's injection is absent there unless committed to the repo. Not a gearbox defect, and already mitigated by the existing project-local path: `inject-routing.py` prefers a repo-committed `.claude/routing.md` (from `/gearbox:init`), which **does** carry into cloud sessions. No follow-up fix issue filed (no defect observed); no surface-detection code added.
- Must reference agents by full names: `gearbox:scout`, `gearbox:grunt`, etc.
- ~~No stop condition after T2 failure (issue #3)~~ — fixed in fork (circuit breaker terminates the ladder at T2).
- ~~Secret-leakage path (audit G1)~~ — fixed in fork v0.1.8: `prompt_head` is secret-scrubbed at write time (PEM keys, AWS ids, secret-like `key=value`, long tokens) and `bench/training-data.jsonl` is gitignored.
- ~~`cost_usd` in the log is always estimated (`cost_estimated: true`)~~ — **fixed in fork v0.5.0 (R2):** the logger reads the real `tool_response.usage` split (`input_tokens` / `output_tokens` / `cache_read_input_tokens` / `cache_creation_input_tokens`, with a 5m/1h cache-write sub-breakdown — confirmed against live session transcripts) and computes **exact** per-component cost. The four new fields are logged; `cost_estimated` is now `false` whenever the split is present, falling back to the (re-pinned) blended estimate only for split-less payloads. `bench/eval.py` consumes the exact router cost against three re-pinned modeled baselines.
- ~~The benchmark baselines are **modeled**, not measured~~ — **measured counterfactual shipped in fork v0.6.0 (R1-live):** `bench/run-live.py` re-runs the fixed task set under each policy via headless `claude -p`, forcing each baseline with R6's forced-tier profiles (always-Opus via an edit-capable `always-opus-build` builder@opus profile, since `always-t2` routes to the read-only architect) on a committed `bench/fixtures/toy-cli/` fixture, and captures **real per-policy cost (R2) + a deterministic acceptability grade** into `bench/training-data.jsonl` — a measured cost-at-equal-acceptability comparison, not an assumed-equal one. The benchmark is local-maintainer-only (spends real money, `bypassPermissions`); CI runs only its offline `--selfcheck`. `bench/training-data.jsonl` is gitignored and **populated on demand by a local pass** (no longer "stays empty"). The three named `eval.py` baselines (always-Sonnet / always-Opus / escalate-on-fail) remain *modeled* token-rate projections — the right place for escalate-on-fail, a counterfactual you can't run live since the live router already escalates.
- The routing prior (v0.4.0) is reward-sparse: the `{task-class × tier}` prior only earns a recommendation where verifier verdicts exist (T1/T2 edits), so early on most cells are `low-n` and unrecommended (first real run: 47 dispatches, only 3 with a verdict). It sharpens as the log accumulates verdicts; until then it mostly confirms the cheap-tier defaults. — roadmap: **v0.9.0** (R13 graded-verifier reward + R14/G32 transcript negative signal) densify it; **v1.2.0** (G27) replaces the keyword classifier.

## How to switch our install to the fork (one-time)

Run inside a Claude Code session (these are `/plugin` UI actions, not shell):

```text
/plugin marketplace remove gearbox
/plugin marketplace add dividedby/gearbox
/plugin install gearbox@gearbox
```
Restart the session, then `/gearbox:doctor` to confirm all checks pass. Because the
fork marketplace keeps `autoUpdate`, future fork-`main` changes flow in automatically.

## How to update (already on the fork)

Fork `main` auto-updates. To force it: `/plugin install gearbox@gearbox`, restart,
`/gearbox:doctor`. Each fork release ships a lightweight semver git tag (`vX.Y.Z`)
placed at the release commit; tag and push separately after the release docs commit
lands on `main`: `git tag vX.Y.Z <commit>` then `git push origin vX.Y.Z`.

## How to check issue status

```bash
gh issue list --repo dividedby/gearbox --json number,title,state --jq '.[] | [.number, .state, .title] | @tsv'
```
(The historical upstream issues #1–#22 live on `Adityaraj0421/gearbox` and are all closed.)

## Project-local customisation

Run `/gearbox:init` in any project to create `.claude/routing.md` — a copy of the routing policy you can extend with project-specific hard floors (e.g. "never delegate auth changes below T2"). The SessionStart hook prefers the local copy over the plugin default.
