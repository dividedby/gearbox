# 3. Front-load verifier loop + graded-reward corpus as durable differentiation

## Status

Accepted (2026-06-19).

## Context

Anthropic may ship native tier-routing inside Claude Code at any time
([anthropics/claude-code#27665](https://github.com/anthropics/claude-code/issues/27665)).
If native routing lands, a plugin whose only value is dispatching to cheaper
models loses its reason to exist: the platform ships the same capability without
an install step.

Gearbox has two things a platform router does not replicate:

1. **The verifier loop** — a mandatory read-only reviewer dispatched after every
   T1/T2 editing task, returning a structured `VERDICT: APPROVE / REJECT`. This is
   a correctness guarantee, not a cost optimisation; a native router that picks the
   right tier still does not verify the output.

2. **The graded-reward corpus** — structured per-dispatch outcome records (R13–R15)
   that accumulate real signal: verifier verdicts, orchestrator corrections,
   escalations, and negative signals from re-dispatches. This corpus is the input
   for the v2.0.0 online-learning epic (#15); no native router ships with it
   pre-populated for a specific user's codebase and workflow.

Sitting out the differentiation question is not an option: if we keep building
toward v2.0.0 without naming what survives a native release, we risk sinking effort
into exactly the parts a platform update obsoletes.

## Decision

Front-load the verifier loop and the graded-reward corpus as the primary,
durable differentiation relative to Anthropic-native routing. These are the parts
we are betting on; they are deliberately placed earlier in the roadmap ladder
than provider hedging (G29) and the online-learning moonshot (v2.0.0 / #15)
precisely because they survive a native-routing release.

We are **not** competing on the bare act of picking a tier. If Anthropic ships
native routing ([#27665](https://github.com/anthropics/claude-code/issues/27665)),
we accept that part of gearbox's value is absorbed and focus engineering effort on
the verifier and corpus, which native routing does not provide.

## Consequences

- The verifier loop and reward-capture hooks (R13–R15) are treated as load-bearing
  features, not optional instrumentation. They are not candidates for removal or
  demotion as the plugin matures.
- The v2.0.0 epic (#15) — online learning fed by the graded-reward corpus — is the
  compound payoff. Its value depends entirely on the corpus being populated; this
  decision is what justifies accumulating that corpus from v0.9.0 onward.
- We explicitly do **not** invest in making gearbox's tier-selection logic a moat.
  Tier selection may be replicated or superseded by the platform; that is an
  acceptable loss.
- If [#27665](https://github.com/anthropics/claude-code/issues/27665) ships before
  v1.0.0, the response is: keep the verifier and corpus hooks, strip or stub the
  routing layer, and continue toward v2.0.0. No architectural rework is required
  because this decision anticipated the scenario.
