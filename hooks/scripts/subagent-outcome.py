#!/usr/bin/env python3
"""Gearbox SubagentStop outcome capture hook.

SubagentStop hook: fires when any subagent finishes. Extracts verdict and
quality_score from the subagent's final message and writes a structured
outcome record to ~/.claude/gearbox-subagent-outcomes.jsonl.

Capture-only: exits 0 always, never blocks the subagent.  Any error → silent
exit 0.  A logging hook must never break the session.

The sidecar log is intended for downstream consumers (e.g. label.py,
recommend.py) that want per-completion outcome signals without parsing
PostToolUse tool_response text, which is fragile and only fires for Task/Agent
dispatches.  Future wiring: read gearbox-subagent-outcomes.jsonl, correlate on
session_id + agent_id, and feed verdict/score into routing recommendations.

SubagentStop payload fields (documented 2026-06-19, code.claude.com/docs/en/hooks.md):
  Common: session_id, transcript_path, cwd, permission_mode, hook_event_name
  Specific: stop_hook_active, agent_id, agent_type
  Undocumented at time of writing (may be present at runtime): last_assistant_message,
    agent_transcript_path.

ponytail: last_assistant_message is the fast-path but undocumented; the documented
reliable path is reading the subagent jsonl transcript (transcript_path sibling
dir subagents/agent-<agent_id>.jsonl).  Both are attempted in order.
"""
import json
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: load log-routing.py via routing_loader (shared helper — avoids
# duplicate importlib boilerplate).  Reuses _VERDICT_RE, _SCORE_RE,
# _scrub_secrets, and clamp_quality_score from the canonical source.
# ---------------------------------------------------------------------------
_scripts_dir = str(Path(__file__).resolve().parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import routing_loader as _routing_loader


def _mod():
    """Load log-routing module (fresh load each call — cheap, stateless)."""
    return _routing_loader.load_log_routing()


# ---------------------------------------------------------------------------
# Transcript fallback: read the final assistant text from the subagent jsonl.
# Layout (verified against real transcripts 2026-06-19):
#   ~/.claude/projects/<proj>/<session-uuid>/          ← transcript_path dir parent
#   ~/.claude/projects/<proj>/<session-uuid>.jsonl     ← transcript_path (the file)
#   ~/.claude/projects/<proj>/<session-uuid>/subagents/agent-<agent_id>.jsonl
# The subagents/ directory is a sibling of the session uuid directory, which is
# itself the parent of the transcript_path without the .jsonl extension.
# ---------------------------------------------------------------------------

def _read_agent_transcript(transcript_path: str, agent_id: str,
                            agent_transcript_path: str | None) -> str:
    """Return the final assistant text from the subagent's transcript jsonl.

    Preference order for the agent file path:
      1. agent_transcript_path if present in payload (undocumented but free to use).
      2. Derived: transcript_path (the session .jsonl file) → strip .jsonl →
         that directory → subagents/agent-<agent_id>.jsonl.

    Returns empty string on any error or if no text block found.
    """
    try:
        agent_file: Path | None = None

        if agent_transcript_path:
            candidate = Path(agent_transcript_path)
            if candidate.is_file():
                agent_file = candidate

        if agent_file is None and transcript_path and agent_id:
            # transcript_path is the session .jsonl file, e.g.:
            #   ~/.claude/projects/-Users-…/<uuid>.jsonl
            # Strip .jsonl to get the session directory, then descend into subagents/.
            session_dir = Path(transcript_path).with_suffix("")  # drop .jsonl
            candidate = session_dir / "subagents" / f"agent-{agent_id}.jsonl"
            if candidate.is_file():
                agent_file = candidate

        if agent_file is None:
            return ""

        last_text = ""
        with agent_file.open(encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    entry = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                # Entry shape: {type: "assistant", message: {role: "assistant", content: [...]}}
                if entry.get("type") != "assistant":
                    continue
                msg = entry.get("message") or {}
                if not isinstance(msg, dict) or msg.get("role") != "assistant":
                    continue
                for block in msg.get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "text":
                        last_text = block["text"]
        return last_text
    except Exception:
        return ""


def _get_message_text(event: dict) -> str:
    """Return the best available final assistant message text.

    ponytail: last_assistant_message is an undocumented field; the documented
    reliable fallback reads the subagent transcript jsonl directly.
    """
    # Primary: undocumented field — cheap if present.
    fast = event.get("last_assistant_message") or ""
    if fast:
        return fast

    # Fallback (documented path): read from transcript.
    return _read_agent_transcript(
        transcript_path=event.get("transcript_path") or "",
        agent_id=event.get("agent_id") or "",
        agent_transcript_path=event.get("agent_transcript_path") or None,
    )


def _extract_verdict_score(text: str) -> tuple:
    """Extract (verdict, quality_score) from final message text.

    Uses the shared regexes and clamp from log-routing.py for consistency.
    Returns (verdict, quality_score) where:
      verdict: "approve" | "reject" | None
      quality_score: int 0-3 | None
    """
    if not text:
        return None, None

    mod = _mod()
    verdict_m = mod._VERDICT_RE.search(text)
    score_m = mod._SCORE_RE.search(text)

    verdict = verdict_m.group(1).lower() if verdict_m else None
    raw_score = int(score_m.group(1)) if score_m else None
    quality_score = mod.clamp_quality_score(verdict, raw_score)

    return verdict, quality_score


def build_outcome(event: dict) -> dict:
    """Build the outcome record from a SubagentStop event dict.  Pure function."""
    session_id = event.get("session_id") or ""
    agent_id = event.get("agent_id") or ""
    agent_type = event.get("agent_type") or ""

    raw_message = _get_message_text(event)
    verdict, quality_score = _extract_verdict_score(raw_message)

    mod = _mod()
    # ponytail: regex best-effort scrub — not a full secret scanner; misses
    # obfuscated/encoded credentials and values that split across the 200-char cap.
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

    # --- 10. Transcript fallback: no last_assistant_message → read from jsonl ---
    with tempfile.TemporaryDirectory() as tmpdir:
        # Reproduce observed layout:
        #   <tmpdir>/<uuid>.jsonl          ← transcript_path
        #   <tmpdir>/<uuid>/subagents/agent-<agent_id>.jsonl
        session_uuid = "test-session-uuid"
        agent_id_val = "testAgentId123"
        session_dir = Path(tmpdir) / session_uuid
        subagents_dir = session_dir / "subagents"
        subagents_dir.mkdir(parents=True)
        transcript_path = Path(tmpdir) / f"{session_uuid}.jsonl"
        transcript_path.write_text("")  # parent session (not read by hook)

        # Write a synthetic subagent jsonl with two entries; last one has the verdict.
        agent_file = subagents_dir / f"agent-{agent_id_val}.jsonl"
        entries = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Checking the code now."}],
                },
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "VERDICT: APPROVE\nSCORE: 3\nAll good."}],
                },
            },
        ]
        with agent_file.open("w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        event_no_msg = {
            "session_id": "s-fallback",
            "agent_id": agent_id_val,
            "agent_type": "gearbox:verifier",
            "transcript_path": str(transcript_path),
            # no last_assistant_message
        }
        rec_fb = build_outcome(event_no_msg)
        assert rec_fb["verdict"] == "approve", \
            f"transcript fallback: expected approve, got {rec_fb['verdict']!r}"
        assert rec_fb["quality_score"] == 3, \
            f"transcript fallback: expected score=3, got {rec_fb['quality_score']!r}"
        assert "VERDICT" in rec_fb["message_head"] or len(rec_fb["message_head"]) > 0, \
            f"transcript fallback: message_head must be non-empty: {rec_fb['message_head']!r}"

    # --- 11. Transcript fallback: agent_transcript_path preferred over derived path ---
    with tempfile.TemporaryDirectory() as tmpdir:
        # Put the real agent file at an arbitrary path (simulates agent_transcript_path field)
        arbitrary = Path(tmpdir) / "explicit-agent.jsonl"
        entries = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "VERDICT: REJECT\nTests missing."}],
                },
            },
        ]
        with arbitrary.open("w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        event_explicit = {
            "session_id": "s-explicit",
            "agent_id": "some-id",
            "agent_type": "gearbox:verifier",
            # no last_assistant_message; agent_transcript_path points directly
            "agent_transcript_path": str(arbitrary),
            "transcript_path": "/nonexistent/path/session.jsonl",
        }
        rec_explicit = build_outcome(event_explicit)
        assert rec_explicit["verdict"] == "reject", \
            f"agent_transcript_path: expected reject, got {rec_explicit['verdict']!r}"
        assert rec_explicit["quality_score"] == 0, \
            f"agent_transcript_path: expected score=0, got {rec_explicit['quality_score']!r}"

    # --- 12. All-empty graceful path: no message from any source → null verdict/score ---
    event_all_empty = {
        "session_id": "s-empty",
        "agent_id": "nofile",
        "agent_type": "gearbox:builder",
        "transcript_path": "/nonexistent/path.jsonl",
        # no last_assistant_message, no agent_transcript_path, no real file
    }
    rec_all_empty = build_outcome(event_all_empty)
    assert rec_all_empty["verdict"] is None, \
        f"all-empty: expected verdict=None, got {rec_all_empty['verdict']!r}"
    assert rec_all_empty["quality_score"] is None, \
        f"all-empty: expected quality_score=None, got {rec_all_empty['quality_score']!r}"
    assert rec_all_empty["message_head"] == "", \
        f"all-empty: expected empty message_head, got {rec_all_empty['message_head']!r}"

    # --- 13. End-to-end main(): writes to temp HOME, exits clean ---
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

    # --- 14. Invalid stdin: main() exits silently (no crash) ---
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
