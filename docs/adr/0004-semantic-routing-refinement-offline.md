# Semantic routing refinement runs offline; the per-prompt hook stays pure-Python

**Status:** accepted

The v1.2.0 epic proposed embedding/similarity + LLM-fallback *classification*, which
reads as a per-prompt operation. We decided the opposite: all embedding/LLM work runs
**offline**, at routing-prior regeneration (`/gearbox:recommend`), producing two
locally-read artifacts — refined `task-classes.json` boundaries and a per-(class, model)
capability grid. The `UserPromptSubmit` hook stays as cheap as today: keyword match →
grid lookup → tier advisory. No runtime embeddings, network call, new dependency, or
API key on the hot path.

## Why

The per-prompt classifier is **advisory only** — it never overrides the hard floors,
max-dimension routing, or the circuit breaker. Adding an embedding/LLM network call
(latency + an API-key dependency + a new failure mode) to a synchronous hook on *every*
prompt, to sharpen a low-stakes advisory, is a poor trade. gearbox is also a
**distributed plugin** installed into other repos; a hot-path network dependency and
wider prompt-text capture are costs borne by every install. Offline computation confines
those costs to a deliberate, batched regeneration step the maintainer runs.

## Consequences

- G27's "embedding/similarity classification" is realized as an offline *corpus-structuring*
  tool (semantic class refinement) that improves the keyword rubric and populates the
  capability grid — not a runtime semantic classifier.
- Training uses the existing 200-char secret-scrubbed `prompt_head`; no logging-schema
  change, smallest privacy surface. Revisit only if R1 shows it under-performs.
- The runtime degrades gracefully to the keyword rubric whenever a (class, model) cell is
  below the min-sample guard.
