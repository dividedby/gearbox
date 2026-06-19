#!/usr/bin/env python3
"""Gearbox PreCompact snapshot hook.

Fires before compaction (manual or auto). Snapshots the current session's
routing/cost ledger — aggregated from ~/.claude/gearbox-log.jsonl — plus the
raw PreCompact payload, to ~/.claude/gearbox-precompact-<session_id>.json so the
post-compaction session can recover what it spent before the in-context tally
was dropped.

Side-effecting only: never blocks compaction, emits nothing on stdout, and is
fail-open (any error → exit 0, no snapshot). The consumer (re-inject the ledger
at the post-compact SessionStart) is R32, tracked separately in #13.

# ponytail: snapshots the whole stdin payload verbatim so the hook survives
# PreCompact schema drift (trigger field has been named both `trigger` and
# `triggered_by` across docs); we don't hard-depend on any one field name.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_scripts_dir = str(Path(__file__).resolve().parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from budget_common import read_rows, session_total


def _num(v):
    """Coerce a JSON value to a number for summing; bools and non-numbers → 0."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return 0
    return v


def summarize_session(rows: list, session_id: str) -> dict:
    """Aggregate one session's log rows into a recoverable ledger. Pure."""
    sel = [r for r in rows if r.get("session_id") == session_id]

    def col(key):
        return sum(_num(r.get(key)) for r in sel)

    tiers: dict = {}
    for r in sel:
        t = r.get("tier")
        if t is not None:
            tiers[str(t)] = tiers.get(str(t), 0) + 1

    return {
        "dispatches": len(sel),
        "cost_usd": round(col("cost_usd"), 6),
        "weighted_tokens": round(session_total(rows, session_id, "wtok"), 3),
        "total_tokens": col("total_tokens"),
        "input_tokens": col("input_tokens"),
        "output_tokens": col("output_tokens"),
        "cache_read_tokens": col("cache_read_tokens"),
        "cache_creation_tokens": col("cache_creation_tokens"),
        "tier_breakdown": tiers,
    }


def _slug(session_id: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "")
    return s or "unknown"


def snapshot_path(session_id: str) -> Path:
    return Path.home() / ".claude" / f"gearbox-precompact-{_slug(session_id)}.json"


def build_snapshot(payload: dict, rows: list) -> dict:
    session_id = payload.get("session_id") or ""
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "ledger": summarize_session(rows, session_id),
        "payload": payload,
    }


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return
        rows = read_rows()
        snap = build_snapshot(payload, rows)
        path = snapshot_path(payload.get("session_id") or "")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snap, indent=2), encoding="utf-8")
    except Exception:
        pass  # fail-open: never block compaction
    # side-effecting: no stdout, allow compaction (exit 0)


def _selfcheck() -> None:
    import tempfile

    rows = [
        {"session_id": "s1", "tier": "T0", "cost_usd": 0.01, "total_tokens": 100,
         "input_tokens": 80, "output_tokens": 20,
         "cache_read_tokens": 50, "cache_creation_tokens": 10},
        {"session_id": "s1", "tier": "T1", "cost_usd": 0.30, "total_tokens": 900,
         "input_tokens": 700, "output_tokens": 200,
         "cache_read_tokens": 400, "cache_creation_tokens": 90},
        {"session_id": "s2", "tier": "T0", "cost_usd": 5.0, "total_tokens": 1},  # other session
        {"session_id": "s1", "tier": "T0", "cost_usd": None, "total_tokens": None},  # None-safe
    ]
    led = summarize_session(rows, "s1")
    assert led["dispatches"] == 3, led
    assert abs(led["cost_usd"] - 0.31) < 1e-9, led
    assert led["total_tokens"] == 1000, led
    assert led["cache_read_tokens"] == 450, led
    assert led["cache_creation_tokens"] == 100, led
    assert led["tier_breakdown"] == {"T0": 2, "T1": 1}, led
    # weighted_tokens = (0.01 + 0.30) * 1e6 / 1.00
    assert abs(led["weighted_tokens"] - 310000.0) < 0.01, led

    # empty / unknown session → zeroed ledger, no crash
    assert summarize_session(rows, "nope")["dispatches"] == 0

    # _slug strips unsafe chars, never empty
    assert _slug("abc-123_DEF") == "abc-123_DEF"
    assert _slug("a/b c:d") == "a_b_c_d"
    assert _slug("") == "unknown"

    # build_snapshot keeps the raw payload verbatim
    snap = build_snapshot({"session_id": "s1", "trigger": "auto", "x": 1}, rows)
    assert snap["payload"]["trigger"] == "auto" and snap["payload"]["x"] == 1
    assert snap["ledger"]["dispatches"] == 3

    # end-to-end main(): writes the snapshot under a temp HOME, exits clean
    import io
    import os as _os
    orig_home = _os.environ.get("HOME")
    orig_stdin = sys.stdin
    try:
        with tempfile.TemporaryDirectory() as home:
            _os.environ["HOME"] = home
            Path(home, ".claude").mkdir()
            log = Path(home, ".claude", "gearbox-log.jsonl")
            log.write_text("\n".join(json.dumps(r) for r in rows if r.get("cost_usd") is not None))
            sys.stdin = io.StringIO(json.dumps({"session_id": "s1", "trigger": "manual",
                                                "hook_event_name": "PreCompact"}))
            main()
            out = snapshot_path("s1")
            assert out.exists(), "snapshot file not written"
            written = json.loads(out.read_text())
            assert written["session_id"] == "s1"
            assert written["payload"]["trigger"] == "manual"
            assert written["ledger"]["dispatches"] == 2  # the None-cost row was filtered from the log
    finally:
        sys.stdin = orig_stdin
        if orig_home is not None:
            _os.environ["HOME"] = orig_home
        else:
            _os.environ.pop("HOME", None)

    print("snapshot-precompact selfcheck: OK")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selfcheck":
        _selfcheck()
        sys.exit(0)
    main()
