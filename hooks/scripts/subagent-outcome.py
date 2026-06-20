#!/usr/bin/env python3
"""Gearbox SubagentStop outcome capture hook.

SubagentStop hook: fires when any subagent finishes. Extracts verdict and
quality_score from the subagent's final message (same regexes as log-routing.py)
and writes a structured outcome record to ~/.claude/gearbox-subagent-outcomes.jsonl.

Capture-only: exits 0 always, never blocks the subagent.  Any error → silent
exit 0.  A logging hook must never break the session.

The sidecar log is intended for downstream consumers (e.g. label.py,
recommend.py) that want per-completion outcome signals without parsing
PostToolUse tool_response text, which is fragile and only fires for Task/Agent
dispatches.  Future wiring: read gearbox-subagent-outcomes.jsonl, correlate on
session_id + agent_id, and feed verdict/score into routing recommendations.

SubagentStop payload fields (confirmed against live docs 2026-06-19):
  Common: session_id, transcript_path, cwd, permission_mode, hook_event_name
  Specific: stop_hook_active, agent_id, agent_type, agent_transcript_path,
            last_assistant_message

All fields read via .get() with safe fallbacks — schema-tolerant against future
field renames or absent keys.
"""
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: load log-routing.py via importlib (hyphen in filename prevents
# direct import).  Reuses _VERDICT_RE, _SCORE_RE, and _scrub_secrets from
# the canonical source — no copy-paste.
# ---------------------------------------------------------------------------
_scripts_dir = str(Path(__file__).resolve().parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

_ROUTING_MOD = None


def _routing():
    """Lazy-load log-routing module; cached after first load."""
    global _ROUTING_MOD
    if _ROUTING_MOD is None:
        path = Path(__file__).resolve().parent / "log-routing.py"
        spec = importlib.util.spec_from_file_location("_log_routing_shared_sao", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _ROUTING_MOD = mod
    return _ROUTING_MOD


def _extract_verdict_score(text: str) -> tuple:
    """Extract (verdict, quality_score) from last_assistant_message text.

    Applies the same regex + clamping rules as log-routing.resolve_routing()
    for consistency.  Returns (verdict, quality_score) where:
      verdict: "approve" | "reject" | None
      quality_score: int 0-3 | None
    """
    if not text:
        return None, None

    mod = _routing()
    verdict_m = mod._VERDICT_RE.search(text)
    score_m = mod._SCORE_RE.search(text)

    verdict = verdict_m.group(1).lower() if verdict_m else None
    quality_score = None

    if verdict == "reject":
        quality_score = 0
    elif verdict == "approve":
        if score_m:
            parsed = int(score_m.group(1))
            # approve + SCORE 0 is a contradiction → treat as absent
            quality_score = parsed if parsed >= 1 else None
        else:
            quality_score = None
    # verdict is None → quality_score stays None

    return verdict, quality_score


def build_outcome(event: dict) -> dict:
    """Build the outcome record from a SubagentStop event dict.  Pure function."""
    session_id = event.get("session_id") or ""
    agent_id = event.get("agent_id") or ""
    agent_type = event.get("agent_type") or ""
    raw_message = event.get("last_assistant_message") or ""

    verdict, quality_score = _extract_verdict_score(raw_message)

    mod = _routing()
    scrubbed = mod._scrub_secrets(raw_message)
    message_head = scrubbed[:200]

    return {
        "ts": int(time.time()),
        "session_id": session_id,
        "agent_id": agent_id,
        "agent_type": agent_type,
        "verdict": verdict,
        "quality_score": quality_score,
        "message_head": message_head,
    }


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except Exception:
        return  # never block on logger failure

    try:
        record = build_outcome(event)
        log_path = Path.home() / ".claude" / "gearbox-subagent-outcomes.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass  # logging must never break the session


def _selfcheck() -> None:
    import io
    import tempfile

    # --- 1. Verdict + score extraction: APPROVE with SCORE ---
    verdict, score = _extract_verdict_score("Work reviewed.\n\nVERDICT: APPROVE\nSCORE: 3\n\nAll checks pass.")
    assert verdict == "approve", f"expected approve, got {verdict!r}"
    assert score == 3, f"expected score=3, got {score!r}"

    # --- 2. REJECT forces score=0, ignores emitted SCORE ---
    verdict, score = _extract_verdict_score("VERDICT: REJECT\nSCORE: 2\nMissing tests.")
    assert verdict == "reject", f"expected reject, got {verdict!r}"
    assert score == 0, f"reject must force score=0, got {score!r}"

    # --- 3. APPROVE + SCORE 0 contradiction → score None ---
    verdict, score = _extract_verdict_score("VERDICT: APPROVE\nSCORE: 0")
    assert verdict == "approve", f"expected approve, got {verdict!r}"
    assert score is None, f"approve+score-0 must yield None, got {score!r}"

    # --- 4. APPROVE with no SCORE ---
    verdict, score = _extract_verdict_score("VERDICT: APPROVE\nLooks good.")
    assert verdict == "approve", f"expected approve, got {verdict!r}"
    assert score is None, f"approve+no-score must yield None, got {score!r}"

    # --- 5. No verdict at all ---
    verdict, score = _extract_verdict_score("The implementation looks reasonable but I cannot render a verdict.")
    assert verdict is None, f"expected None, got {verdict!r}"
    assert score is None, f"expected score=None, got {score!r}"

    # --- 6. Empty / None message ---
    verdict, score = _extract_verdict_score("")
    assert verdict is None and score is None, "empty text must yield (None, None)"

    # --- 7. build_outcome: scrub+cap applied, raw message never persisted ---
    event_secret = {
        "session_id": "s-test",
        "agent_id": "agent-abc123",
        "agent_type": "gearbox:verifier",
        "last_assistant_message": (
            "Use key AKIAIOSFODNN7EXAMPLE to auth.\n\nVERDICT: APPROVE\nSCORE: 2"
        ),
    }
    rec = build_outcome(event_secret)
    assert "AKIAIOSFODNN7EXAMPLE" not in rec["message_head"], \
        f"raw AWS key must not appear in message_head: {rec['message_head']!r}"
    assert "[REDACTED]" in rec["message_head"], \
        f"message_head must contain [REDACTED]: {rec['message_head']!r}"
    assert len(rec["message_head"]) <= 200, \
        f"message_head must be capped at 200 chars, got {len(rec['message_head'])}"
    assert rec["verdict"] == "approve", f"expected approve, got {rec['verdict']!r}"
    assert rec["quality_score"] == 2, f"expected score=2, got {rec['quality_score']!r}"
    assert rec["session_id"] == "s-test"
    assert rec["agent_id"] == "agent-abc123"
    assert rec["agent_type"] == "gearbox:verifier"
    assert "ts" in rec

    # --- 8. build_outcome: 200-char cap on message_head ---
    long_msg = "x" * 500 + "\nVERDICT: APPROVE\nSCORE: 1"
    rec_long = build_outcome({"session_id": "s2", "agent_id": "a2", "agent_type": "t",
                              "last_assistant_message": long_msg})
    assert len(rec_long["message_head"]) <= 200, \
        f"message_head must be capped at 200, got {len(rec_long['message_head'])}"
    # verdict+score still extracted from the full (pre-cap) text
    assert rec_long["verdict"] == "approve", f"expected approve, got {rec_long['verdict']!r}"
    assert rec_long["quality_score"] == 1, f"expected score=1, got {rec_long['quality_score']!r}"

    # --- 9. Missing fields: graceful fallback (no KeyError) ---
    rec_empty = build_outcome({})
    assert rec_empty["session_id"] == ""
    assert rec_empty["agent_id"] == ""
    assert rec_empty["agent_type"] == ""
    assert rec_empty["verdict"] is None
    assert rec_empty["quality_score"] is None
    assert rec_empty["message_head"] == ""

    # --- 10. End-to-end main(): writes to temp HOME, exits clean ---
    orig_home = os.environ.get("HOME")
    orig_stdin = sys.stdin
    try:
        with tempfile.TemporaryDirectory() as home:
            os.environ["HOME"] = home
            Path(home, ".claude").mkdir()
            payload = {
                "session_id": "e2e-session",
                "agent_id": "agent-xyz",
                "agent_type": "gearbox:verifier",
                "last_assistant_message": "VERDICT: APPROVE\nSCORE: 3\nAll good.",
                "hook_event_name": "SubagentStop",
                "stop_hook_active": False,
            }
            sys.stdin = io.StringIO(json.dumps(payload))
            main()
            out = Path(home, ".claude", "gearbox-subagent-outcomes.jsonl")
            assert out.exists(), "outcome file not written"
            written = json.loads(out.read_text().strip())
            assert written["session_id"] == "e2e-session"
            assert written["agent_id"] == "agent-xyz"
            assert written["verdict"] == "approve"
            assert written["quality_score"] == 3
            # Confirm raw full message not stored
            full_msg = payload["last_assistant_message"]
            assert "last_assistant_message" not in written, \
                "raw full message field must not appear in record"
            # message_head present and capped
            assert "message_head" in written
            assert len(written["message_head"]) <= 200
    finally:
        sys.stdin = orig_stdin
        if orig_home is not None:
            os.environ["HOME"] = orig_home
        else:
            os.environ.pop("HOME", None)

    # --- 11. Invalid stdin: main() exits silently (no crash) ---
    sys.stdin = io.StringIO("not json at all")
    try:
        main()  # must not raise
    finally:
        sys.stdin = orig_stdin

    print("subagent-outcome selfcheck: OK")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selfcheck":
        _selfcheck()
        sys.exit(0)
    main()
