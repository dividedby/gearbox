# 2. Declare full divergence from upstream

## Status

Accepted (2026-06-18). Extends [ADR 0001](0001-hard-fork-from-upstream.md).

## Context

Four days after forking, every contribution-back channel was still dead: the 11
issues, the per-theme PRs (#10–#23), and the long-lived sync PR (#24) all went
unanswered. Maintaining mirror-able, upstream-shaped changes imposed ongoing cost
(pinning values back to upstream, keeping the sync branch alive) for no realised
benefit, since the fork had already diverged substantially.

## Decision

Declare full divergence. Close the sync PR (#24), delete the `upstream-sync` branch,
and stop polling upstream PRs/commits/releases on a schedule. Keep the `upstream`
remote configured but dormant. The fork is now the only thing we track.

## Consequences

- No more upstream-shaped constraints: we ship the change that's best for the fork.
- New work updates `maintenance/README.md` + `maintenance/docs/roadmap.md`; there's no
  upstream PR to fold it into.
- If the maintainer ever revives the project, recovery is `git fetch upstream` →
  cherry-pick wanted commits onto a `feature/*` branch, resolving conflicts in our
  favour (see CLAUDE.md "If upstream revives").
