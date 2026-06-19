# 1. Hard fork from abandoned upstream

## Status

Accepted (2026-06-14). Extended by [ADR 0002](0002-full-divergence.md).

## Context

`gearbox` originated as `Adityaraj0421/gearbox`. The single maintainer was
unresponsive: 11 filed issues and a sync PR went unanswered. We needed to ship fixes
across the routing policy, agents, hooks, and doctor checks without waiting on a
maintainer who never engaged.

## Decision

Fork to `dividedby/gearbox` and run our install off the fork. Point `plugin.json`
`repository` at `dividedby/gearbox` and carry the fork's own `version`, so doctor's
freshness check (CHECK 8) tracks the fork. Offer fixes back via per-theme PRs
(#10–#23) and one long-lived sync PR (#24) while keeping the `upstream` remote
configured.

## Consequences

- We control the release cadence; fixes ship immediately via `/plugin install gearbox@gearbox`.
- Contribution-back stayed open as long as it cost little (the sync PR), but was never
  load-bearing.
- `maintenance/README.md` becomes the source of truth for installed version and
  integration limitations.
