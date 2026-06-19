# Idea Inbox — drain protocol

<!-- agent-protocol: this repo's single idea-intake issue carries the `idea-inbox` label -->

One freeform issue per repo collects half-formed ideas before they're worth a tracked
issue. File loose thoughts there; file fully-shaped work as a normal labelled issue.

## Capture (enriched intake)

Add an unchecked item at the TOP of the issue's `## Ideas` list. Capture the idea
**and** its ambient context: the source (file `path:line`, issue/PR, link) and the
one-line rationale — enough that a later drain pass doesn't have to reconstruct it.

## How to drain

1. **Dedup / relate** — fold duplicates; link ideas that belong to one theme.
2. **Pick the step** the idea needs — grill it, write a PRD, cut tracked issues, or
   design it — based on how formed it is.
3. **Label** the resulting tracked issue per `docs/agents/triage-labels.md`.
4. **Aim for a strong brief** — a drained idea should leave behind a `ready-for-agent`
   or `ready-for-human` issue, not a vaguer restatement.
5. **Move to Actioned** — check the item off and move it into the collapsed
   `✅ Actioned` section with a `→ #<issue>` pointer.

Never delete an idea silently. Prune the Actioned section to roughly the 8 most recent.
