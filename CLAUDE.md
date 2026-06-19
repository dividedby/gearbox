# Gearbox maintenance

This repo **is** our fork of the **gearbox** plugin (`dividedby/gearbox`);
upstream is `Adityaraj0421/gearbox`. This file tracks how we maintain the fork.
`maintenance/README.md` is the living record: installed version, how we integrated
it, issues we filed, and limitations. Keep it accurate — it's the source of truth,
not just notes.

> This file and `maintenance/` are **fork-only** — they are our maintenance
> tracking, never sent upstream. See "Fork-only divergences" below for how they
> are kept off the upstream-sync PR.

## Routine check (run when asked, or on a maintenance pass)

1. **Our ongoing sync PR (#24)** — we no longer file issues (the 11 we filed are
   closed; the maintainer never responded). Check #24 for any maintainer activity:
   ```bash
   gh pr view 24 --repo Adityaraj0421/gearbox \
     --json state,mergedAt,comments,reviews \
     --jq '[.state, (.mergedAt//"-"), (.comments|length), (.reviews|length)] | @tsv'
   ```
   - Any review/comment worth acting on → address it, then refresh the PR body.
   - If merged → run the "When upstream merges our PRs" sync (below).

2. **New upstream activity** — commits, PRs, releases since our last pass:
   ```bash
   gh pr list   --repo Adityaraj0421/gearbox --state all --json number,title,state,mergedAt
   gh release list --repo Adityaraj0421/gearbox
   gh api repos/Adityaraj0421/gearbox/commits --jq '.[] | [.sha[0:7], .commit.message] | @tsv' | head -20
   ```
   - A new release affecting our limitations/roadmap → update `maintenance/README.md`, consider upgrading.
   - #24 (or any part of it) merged upstream → run the "When upstream merges our PRs"
     sync (see "Fork & upstream contribution") and mark it in `maintenance/README.md`.

3. **Installed vs latest** — `maintenance/README.md` records the installed version.
   Compare against the latest release tag. If behind, see "How to update" in
   `maintenance/README.md` (`/plugin install gearbox@gearbox`, restart,
   `/gearbox:doctor`), then bump the version line in `maintenance/README.md` and
   record any new doctor warnings.

## When you change things

- New work we ship → fold it into the ongoing sync PR #24 (update its body) and
  `maintenance/README.md` + `maintenance/docs/roadmap.md`. We no longer file
  upstream issues — they go unanswered.
- We adopt an upstream feature / our integration changes → update the relevant
  `maintenance/README.md` section (integration, limitations, roadmap).
- Don't hand-edit installed files under `~/.claude/plugins/` (the plugin cache) —
  fix in the fork repo, merge, and reinstall. We patch via the fork + upstream PRs,
  never local cache edits.

## Fork & upstream contribution

We run our install off our fork **`dividedby/gearbox`** — this repo, checked out at
`~/repos/gearbox` (`origin` = fork, `upstream` = `Adityaraj0421/gearbox`). Upstream
went quiet with our issues unanswered; the fork lets us ship fixes now while still
offering them upstream.

**Being a good contributor — how we work every change:**
- **One thematic `feature/*` branch per concern**, cut from fork `main`. Group
  same-file / same-theme issues; never bundle unrelated changes. Atomic PRs let the
  maintainer accept selectively instead of all-or-nothing.
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
- **Mirror upstream via ONE long-lived PR**, not a PR per change. The single sync
  branch `dividedby:upstream-sync` carries every upstream-worthy commit, with the
  fork-only `version`/`repository` lines pinned to upstream's values so the PR holds
  only substantive changes. It is open as `Adityaraj0421/gearbox` **#24**. To update
  it after fork `main` advances: `git checkout upstream-sync && git merge main`,
  re-pin the two fork-only `plugin.json` lines, **and drop the fork-only maintenance
  files** (`git rm -r --ignore-unmatch CLAUDE.md maintenance`; a modify/delete
  conflict on these paths from `git merge main` resolves the same way — `git rm`
  them), then push — the PR refreshes automatically. **Then
  refresh the PR body so it stays accurate**: its theme list, `Closes #N` refs, and
  the "reflects fork vX.Y.Z" status line. Keep this branch; don't delete it (it is
  the PR head). Cut a separate per-theme upstream PR only if the maintainer asks to
  review something in isolation.
- **Don't spam the quiet repo:** clean, self-contained, conventionally-titled PRs;
  co-author trailer. Conventional commit subjects.

**Fork-only divergences (never send upstream):**
- `plugin.json` `repository` (→ `dividedby/gearbox`) and the `version` line — the
  fork's identity and the one place doctor's freshness check (CHECK 8 reads
  `repository`) is meant to differ.
- `CLAUDE.md` (this file) and `maintenance/` — our maintenance tracking. They live
  on fork `main` but are stripped from the `upstream-sync` branch (see the sync
  ritual above), so PR #24 never carries them.

Everything else should be upstream-PR-able — if a change can't go upstream,
question whether it belongs in the fork at all.

**When upstream merges our PRs (or otherwise moves):**
1. `git -C ~/repos/gearbox fetch upstream`.
2. Merge upstream into fork `main` (merge-commit): `git checkout main && git merge
   upstream/main`. A PR upstream merged identically should apply cleanly; on
   conflict, keep upstream's version (ours is now redundant) and resolve.
3. Drop our now-redundant copy of any merged fix; keep only still-unmerged fixes on
   top, plus the fork-only `repository`/version divergence.
4. Bump the fork `version`, push `main`, reinstall (`/plugin install gearbox@gearbox`,
   `/reload-plugins`), and run `/gearbox:doctor`.
5. In `maintenance/README.md`: mark the issue's row "merged upstream ✓" and drop its
   "fork carries it" note. Confirm the issue actually closed (the merged PR's
   `Closes #N` should have done it).

## Out of scope here

- `.claude/gearbox-log.jsonl` is per-project telemetry the plugin writes; it's
  gitignored and not maintained by hand.
- The routing policy itself is injected at SessionStart by the plugin — read it
  there, don't duplicate it in this repo.
