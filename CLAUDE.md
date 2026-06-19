# Gearbox maintenance

This repo **is** our fork of the **gearbox** plugin (`dividedby/gearbox`). We run
it as a **hard fork** — `Adityaraj0421/gearbox` is abandoned (single maintainer,
never responded to our 11 issues or the sync PR). We no longer mirror changes
upstream or track upstream activity on a schedule. `maintenance/README.md` is the
living record: installed version, how we integrated it, and limitations. Keep it
accurate — it's the source of truth, not just notes.

> History: 2026-06-14 we forked to ship fixes while offering them back; we filed
> 11 issues + per-theme PRs (#10–#23) and kept one long-lived sync PR (#24). All
> went unanswered. 2026-06-18 we closed #24, deleted the `upstream-sync` branch,
> and declared full divergence. The `upstream` remote stays configured (dormant)
> in case the maintainer ever revives the project — see "If upstream revives".

## Routine check (run when asked, or on a maintenance pass)

The fork is the only thing we track now. No upstream PR/commit/release polling.

1. **Installed vs latest** — `maintenance/README.md` records the installed version.
   Compare against fork `main` / the latest fork release. If behind, see "How to
   update" in `maintenance/README.md` (`/plugin install gearbox@gearbox`, restart,
   `/gearbox:doctor`), then bump the version line in `maintenance/README.md` and
   record any new doctor warnings.

2. **Doctor health** — run `/gearbox:doctor`; record new WARN/FAIL in
   `maintenance/README.md` ("Doctor status").

## When you change things

- New work we ship → add a `CHANGELOG.md` entry; forward/planned work lives in GitHub
  issues + `epic`s, not in-repo roadmap docs. Update `maintenance/README.md` when the
  installed version or limitations change. No upstream PR to fold it into anymore.
- Don't hand-edit installed files under `~/.claude/plugins/` (the plugin cache) —
  fix in the fork repo, merge, and reinstall. We patch via the fork, never local
  cache edits.

## How we work every change

We run our install off our fork **`dividedby/gearbox`** — this repo, checked out at
`~/repos/gearbox` (`origin` = fork; `upstream` = `Adityaraj0421/gearbox`, dormant).

- **One thematic `feature/*` branch per concern**, cut from fork `main`. Never
  bundle unrelated changes.
- **Capture ground truth before fixing undocumented behavior.** When a fix depends
  on something not in the docs (e.g. a hook payload schema), observe the real data
  first — the session transcript at `~/.claude/projects/<proj>/<session>.jsonl`
  records actual tool results/`toolUseResult` — then pin to the real shape. Never
  ship a fix built on a guessed schema; that's how we found the real
  `tool_response` keys (`totalTokens`/`totalToolUseCount`/`totalDurationMs`).
- **Verifier-gate code changes** (`gearbox:verifier`); mechanical edits are lead
  self-checked and run. Non-trivial logic leaves one runnable check (e.g. a
  `--selfcheck`).
- **Merge into fork `main` with merge commits only** (`git merge --no-ff`); never
  squash/rebase (matches our branching policy).
- Conventional commit subjects; co-author trailer.

**Fork identity (was the only "upstream divergence"):** `plugin.json` `repository`
points to `dividedby/gearbox` and `version` is the fork's own — doctor's freshness
check (CHECK 8 reads `repository`) tracks the fork. No longer anything to "pin back"
to upstream values, since we no longer produce an upstream PR.

## If upstream revives

The `upstream` remote is still configured but we don't poll it. If the maintainer
ever resumes and ships something worth having:
1. `git -C ~/repos/gearbox fetch upstream` and review what landed.
2. Cherry-pick / merge only the wanted commits onto a `feature/*` branch off fork
   `main`, resolve conflicts in our favor (our fork has diverged substantially),
   merge-commit into `main`, bump `version`, reinstall, `/gearbox:doctor`.
3. Re-opening a contribution PR is optional and only if they're actually engaging.

## Conventions

This repo is issue-tracked on GitHub under the dividedby harness.

- **Domain vocabulary** — `CONTEXT.md` (gearbox routing/tier terms). Architectural
  decisions are recorded as ADRs under `docs/adr/` (`NNNN-kebab-title.md`).
- **Issue triage** — the `triage` skill drives a state machine over the label
  vocabulary. Role↔label mapping: `docs/agents/triage-labels.md`; full installed set
  and colors: `docs/agents/labels.md`. `needs-info` is intentionally absent.
- **Intake** — file loose ideas in the single `idea-inbox` issue; file shaped work as
  a normal labelled issue. Drain protocol: `docs/agents/idea-inbox.md`.
- **Branching & merge** — library/trunk tier: `feature/*` → PR → `main`, merge-commit
  only, auto-delete on merge. Global policy: `~/.claude/branching-flow.md`.
- **Plugin caveat** — gearbox is a distributed plugin. Do **not** commit a
  consumer-style `.claude/settings.json` or hooks here; that harness stays local and
  uncommitted. Only the repo-tracking harness (labels, docs, ADRs) is committed.

## Out of scope here

- `.claude/gearbox-log.jsonl` is per-project telemetry the plugin writes; it's
  gitignored and not maintained by hand.
- The routing policy itself is injected at SessionStart by the plugin — read it
  there, don't duplicate it in this repo.
