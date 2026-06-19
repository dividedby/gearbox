# Label Convention

The CORE dividedby label set this repo carries. Stock GitHub labels are removed on
onboarding. `needs-info` is intentionally absent (we use `needs-triage`).

## State (workflow position)

| Label | Color | Meaning |
|-------|-------|---------|
| `needs-triage` | `FBCA04` | Maintainer needs to evaluate this issue |
| `ready-for-agent` | `0E8A16` | Fully specified, ready for an AFK agent |
| `ready-for-human` | `1D76DB` | Requires human implementation |
| `blocked` | `E4820A` | Ready to proceed but waiting on an external dependency or decision |
| `wontfix` | `FFFFFF` | Will not be actioned |
| `idea-inbox` | `D4C5F9` | The single freeform idea-intake issue for this repo (one per repo) |

## Category (work type)

| Label | Color | Meaning |
|-------|-------|---------|
| `bug` | `D73A4A` | Something is broken |
| `enhancement` | `84B6EB` | New capability or improvement |
| `chore` | `BFD4F2` | Maintenance or tooling with no user-facing change |
| `epic` | `7057FF` | Aggregate issue grouping related child issues |

## Size (effort estimate)

| Label | Color | Meaning |
|-------|-------|---------|
| `size:S` | `E6E6E6` | Small: < 1 day |
| `size:M` | `C8C8C8` | Medium: 1–2 days |
| `size:L` | `AAAAAA` | Large: 3–5 days |
| `size:XL` | `888888` | Extra large: > 1 week |

gearbox uses the CORE set only. Loop/network labels (`source:*`, cross-repo
channels) are not installed here — add them if gearbox ever adopts a proposal loop.
