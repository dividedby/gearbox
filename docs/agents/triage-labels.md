# Triage Labels

Maps the canonical triage roles (used by the `triage` skill's state machine) to the
actual label strings this repo uses. Full colors and the remove-stock rule live in
`docs/agents/labels.md`.

## State

| Role | Label | Meaning |
|------|-------|---------|
| Needs evaluation | `needs-triage` | Maintainer hasn't looked at it yet |
| Ready for an agent | `ready-for-agent` | Fully specified; an AFK agent can pick it up |
| Needs a human | `ready-for-human` | Requires human implementation/judgement |
| Blocked | `blocked` | Waiting on an external dependency or decision |
| Won't action | `wontfix` | Closed without action |
| Idea intake | `idea-inbox` | The single freeform idea issue (one per repo) |

## Category

| Category | Label | Meaning |
|----------|-------|---------|
| Defect | `bug` | Something is broken |
| Feature | `enhancement` | New capability or improvement |
| Maintenance | `chore` | Tooling/maintenance, no user-facing change |
| Aggregate | `epic` | Groups related child issues |

## Size

| Size | Label | Meaning |
|------|-------|---------|
| Small | `size:S` | < 1 day |
| Medium | `size:M` | 1–2 days |
| Large | `size:L` | 3–5 days |
| Extra large | `size:XL` | > 1 week |

State-label rows can be edited to match this repo's vocabulary as it evolves; keep
`docs/agents/labels.md` as the source of truth for the actual installed set.
