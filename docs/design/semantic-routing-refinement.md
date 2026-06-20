# Semantic routing refinement — Design Plan

status: active · 2026-06-19 · epic: #11

## Context

v1.2.0 enriches the data-derived routing prior with per-(class, model) capability
resolution, and (later, blocked) with semantic class refinement, while keeping the
per-prompt path pure-Python with no network cost (ADR-0004). Routing advisories become
cost-discriminating at the model level rather than assuming tier jumps.

## Domain Vocabulary Used

routing prior, capability grid, keyword classifier, semantic class refinement,
task-class, tier, hard floors, routing log (all per `CONTEXT.md`).

## Module Map

| Module | Responsibility (one reason to change) | Interface | Seams |
|--------|----------------------------------------|-----------|-------|
| **A — capability grid** (producer) | how routing-log outcomes aggregate into per-(class, model) acceptability + cost | `build_grid(records, K) → Grid`; `regenerate()` writes the artifact | writes grid artifact |
| **B — routing advisor** (consumer) | the decision rule | `advise(task_class, grid, floors, K, θ) → tier` | reads grid artifact; reads task-class registry |
| **C — grid observability** (read-only consumer) | reporting grid health + per-model mix | doctor check; `dashboard.py` rollup; status-line segment | reads grid artifact + log |
| **D — semantic class refinement** (offline producer, BLOCKED) | refine task-class boundaries from embedded `prompt_head`s | offline pass at regeneration | writes task-class registry |

## Seams

- **Grid artifact** (A → B, A → C): the serialized per-(class, model) grid. Prod adapter =
  artifact file; test adapter = in-memory `Grid` fixture. This is the ADR-0004 offline/online
  boundary.
- **Task-class registry** (`bench/task-classes.json`) (D → A, D → keyword classifier): the
  shared class vocabulary; D mutates it offline, A and the keyword classifier read it.

## Invariants and Contracts

- Every grid cell carries its sample count n; cells with n<K are marked low-n, never silently
  dropped.
- `advise()` never recommends below a hard floor; is advisory-only (never alters floors,
  max-dimension routing, or the circuit breaker); is deterministic for a fixed (grid, prompt).
- Routing degrades to the keyword static tier whenever no cell qualifies.
- Cost is canonical USD via `bench/rates.py`.

## Testing Strategy

| Module | Entry point | Level | Fake |
|--------|-------------|-------|------|
| A | `build_grid` | unit (pure) | synthetic record list |
| B | `advise` | unit (pure) — **tracer test** | in-memory `Grid` |
| seam | artifact write → read | contract | temp-file round-trip |
| C | doctor check fn | unit | temp artifact (present/stale/malformed) |

## Issue Index

- **#69** — A+B tracer: grid producer + routing advisor + full decision rule.
- **#71** — C: doctor + observability (blocked by #69).
- **#70** — D: semantic class refinement (BLOCKED on R29/R1/corpus; design deferred).

## Open Questions

- θ default value — deferred to v1.4.0 (R20/R21 calibration).
- Corpus-volume threshold N before G27 refinement is meaningful — deferred to v1.4.0.
- Grid artifact format — extend `gearbox-recommendations.md` vs a separate JSON the hook
  parses; decide at #69 implementation (JSON likely, for machine-read).
