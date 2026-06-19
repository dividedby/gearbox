#!/usr/bin/env python3
"""Transcript correction miner (R14).

Mines Claude Code session transcripts (~/.claude/projects/<proj>/<session>.jsonl)
for negative-reward signals that the structured routing log cannot see:
  - orchestrator corrections ("scout was wrong", re-dispatch after failure)
  - tier escalations detected from escalation markers in prompts
  - re-dispatches of the same task to a different dispatch

Joins signals to dispatch-log records by session_id and dispatch_id, and writes
a correction-signals JSONL (~/.claude/bench-correction-signals.jsonl or --out)
that bench/recommend.py can consume.

Output schema per record (no raw transcript text):
  schema_version     int     always 1
  session_id         str     Claude session UUID
  dispatch_id        str     tool_use_id from the transcript (= dispatch_id in log)
  corrected          bool    True if a subsequent dispatch followed a correction in this session
  correction_count   int     number of correction signals detected for this dispatch
  escalation_marker  bool    True if this dispatch's prompt begins with [gearbox-escalation ...]
  escalated_from     str|None  e.g. "T0"
  escalated_to       str|None  e.g. "T1"
  prompt_head        str     first 200 chars of scrubbed prompt (no raw text)

Usage:
  python3 bench/mine-corrections.py [--log PATH] [--transcripts DIR] [--out PATH]
  python3 bench/mine-corrections.py --selfcheck
"""
import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Import shared helpers from routing_loader (which delegates to log-routing.py)
# ---------------------------------------------------------------------------

_hooks_scripts = str(Path(__file__).resolve().parent.parent / "hooks" / "scripts")
if _hooks_scripts not in sys.path:
    sys.path.insert(0, _hooks_scripts)

from routing_loader import scrub_secrets as _scrub_secrets, parse_escalation as _parse_escalation

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SCHEMA_VERSION = 1
_PROMPT_HEAD_CAP = 200

# Names Claude Code uses for the subagent dispatch tool (varies by version).
_TASK_TOOL_NAMES = frozenset({"Task", "Agent"})

# Keywords in orchestrator text (assistant messages between dispatches) that
# signal a correction or negative verdict on the preceding dispatch.
# Matched case-insensitively against the lower-cased assistant text.
_CORRECTION_KEYWORDS = [
    "needs escalation",
    "scout was wrong",
    "was wrong",
    "incorrect",
    "redispatch",
    "re-dispatch",
    "dispatch another",
    "escalating",
    "escalat",          # catches "escalating", "escalated", "escalation"
    "failed twice",
    "failed again",
    "rejected",         # verifier reject surfaced in orchestrator reasoning
    "needs a fix",
]

# ---------------------------------------------------------------------------
# Transcript parsing
# ---------------------------------------------------------------------------

def _iter_transcripts(transcripts_dir: Path):
    """Yield (session_id, path) for every .jsonl under transcripts_dir."""
    if not transcripts_dir.exists():
        return
    for proj_dir in transcripts_dir.iterdir():
        if not proj_dir.is_dir():
            continue
        for p in proj_dir.glob("*.jsonl"):
            # Session ID is the filename stem (UUID).
            yield p.stem, p


def _extract_task_dispatches(session_path: Path) -> list:
    """Return ordered list of dispatch dicts from a session transcript.

    Each dict contains:
      tool_use_id   str   the tool_use id (= dispatch_id in log)
      prompt        str   raw prompt text (NOT stored in output — used only for analysis)
      preceding_text str  concatenated assistant text blocks appearing before this dispatch
                          in the session (used for correction detection)
      index         int   position in the session

    Only Task/Agent tool_use entries are returned.  Malformed lines are skipped.
    """
    dispatches = []
    accumulated_assistant_text = []  # text blocks since last Task dispatch
    index = 0

    try:
        with session_path.open(encoding="utf-8") as f:
            for raw_line in f:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    obj = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                msg_type = obj.get("type")

                if msg_type == "assistant":
                    msg = obj.get("message", {})
                    if not isinstance(msg, dict):
                        continue
                    content = msg.get("content", [])
                    if not isinstance(content, list):
                        continue
                    for item in content:
                        if not isinstance(item, dict):
                            continue
                        if item.get("type") == "text":
                            t = item.get("text", "")
                            if t:
                                accumulated_assistant_text.append(t)
                        elif item.get("type") == "tool_use" and item.get("name") in _TASK_TOOL_NAMES:
                            inp = item.get("input", {})
                            if not isinstance(inp, dict):
                                continue
                            prompt = inp.get("prompt", "") or ""
                            dispatches.append({
                                "tool_use_id": item.get("id", ""),
                                "prompt": prompt,
                                "preceding_text": " ".join(accumulated_assistant_text),
                                "index": index,
                            })
                            index += 1
                            accumulated_assistant_text = []  # reset after each dispatch

    except (OSError, UnicodeDecodeError):
        pass

    return dispatches


def _has_correction_language(text: str) -> bool:
    """Return True if the text contains any correction keyword."""
    low = text.lower()
    return any(kw in low for kw in _CORRECTION_KEYWORDS)


def _count_correction_signals(preceding_text: str) -> int:
    """Count distinct correction keywords found in preceding_text."""
    low = preceding_text.lower()
    return sum(1 for kw in _CORRECTION_KEYWORDS if kw in low)


def _build_dispatch_signal(session_id: str, dispatch: dict) -> dict:
    """Build a correction-signal record for one dispatch.

    Never stores raw prompt text — only scrubbed+capped prompt_head.
    """
    prompt = dispatch["prompt"]
    preceding = dispatch["preceding_text"]

    esc, esc_from, esc_to = _parse_escalation(prompt)

    # prompt_head: scrubbed + capped (same rule as log-routing.py build_record)
    prompt_head = _scrub_secrets(prompt)[:_PROMPT_HEAD_CAP]

    # 'corrected': True if there was correction language in the text leading
    # up to this dispatch (i.e. the orchestrator was correcting a prior result).
    corrected = _has_correction_language(preceding)
    correction_count = _count_correction_signals(preceding) if corrected else 0

    return {
        "schema_version": _SCHEMA_VERSION,
        "session_id": session_id,
        "dispatch_id": dispatch["tool_use_id"],
        "corrected": corrected,
        "correction_count": correction_count,
        "escalation_marker": esc,
        "escalated_from": esc_from,
        "escalated_to": esc_to,
        "prompt_head": prompt_head,
    }


# ---------------------------------------------------------------------------
# Join to routing log
# ---------------------------------------------------------------------------

def load_log_records(log_path: Path) -> dict:
    """Return {(session_id, dispatch_id): record} index from the routing log.

    Records without a dispatch_id are indexed by uid as fallback.
    """
    index: dict = {}
    if not log_path.exists():
        return index
    with log_path.open(encoding="utf-8") as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                rec = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            session_id = rec.get("session_id", "")
            dispatch_id = rec.get("dispatch_id") or rec.get("uid", "")
            if session_id and dispatch_id:
                index[(session_id, dispatch_id)] = rec
    return index


def join_signals(signals: list, log_index: dict) -> list:
    """Return signals enriched with log fields where a join succeeds.

    Adds 'tier', 'subagent_type' from the log record when found.
    Signals with no matching log record are kept (join is left-outer).
    """
    enriched = []
    for sig in signals:
        key = (sig["session_id"], sig["dispatch_id"])
        log_rec = log_index.get(key)
        enriched_sig = dict(sig)
        if log_rec:
            enriched_sig["tier"] = log_rec.get("tier")
            enriched_sig["subagent_type"] = log_rec.get("subagent_type")
        else:
            enriched_sig["tier"] = None
            enriched_sig["subagent_type"] = None
        enriched.append(enriched_sig)
    return enriched


# ---------------------------------------------------------------------------
# Public API (importable by recommend.py and others)
# ---------------------------------------------------------------------------

def load_correction_signals(signals_path: Path) -> dict:
    """Load correction signals and return {(session_id, dispatch_id): signal}.

    Returns an empty dict if the file does not exist.
    Importable by bench/recommend.py to factor negative signals into the prior.
    """
    result: dict = {}
    if not signals_path.exists():
        return result
    with signals_path.open(encoding="utf-8") as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                sig = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            session_id = sig.get("session_id", "")
            dispatch_id = sig.get("dispatch_id", "")
            if session_id and dispatch_id:
                result[(session_id, dispatch_id)] = sig
    return result


def mine_transcripts(
    transcripts_dir: Path,
    log_path: Path,
) -> list:
    """Mine all transcripts and return enriched correction signal records.

    Pure function (no I/O side effects beyond reading files).
    """
    log_index = load_log_records(log_path)
    signals = []

    for session_id, session_path in _iter_transcripts(transcripts_dir):
        dispatches = _extract_task_dispatches(session_path)
        for dispatch in dispatches:
            sig = _build_dispatch_signal(session_id, dispatch)
            signals.append(sig)

    return join_signals(signals, log_index)


# ---------------------------------------------------------------------------
# Selfcheck
# ---------------------------------------------------------------------------

def _run_selfcheck() -> None:
    """Assert-based tests on pure helpers with synthetic fixtures.

    No real transcripts or log files are read.  Exits 0 on success.
    """
    import tempfile

    # --- _has_correction_language ---
    assert _has_correction_language("needs escalation from scout") is True
    assert _has_correction_language("the scout was wrong about this") is True
    assert _has_correction_language("looks good, dispatch another") is True
    assert _has_correction_language("this is a normal message") is False
    assert _has_correction_language("") is False

    # --- _count_correction_signals ---
    assert _count_correction_signals("needs escalation, was wrong") >= 2
    assert _count_correction_signals("nothing here") == 0

    # --- _parse_escalation (delegated via routing_loader) ---
    esc, frm, to = _parse_escalation("[gearbox-escalation from=T0 to=T1]\nRe-run with more context.")
    assert esc is True, f"expected escalation=True, got {esc}"
    assert frm == "T0", f"expected from=T0, got {frm}"
    assert to == "T1", f"expected to=T1, got {to}"

    esc2, frm2, to2 = _parse_escalation("Normal prompt, no marker.")
    assert esc2 is False, f"expected escalation=False, got {esc2}"
    assert frm2 is None
    assert to2 is None

    # --- _scrub_secrets (delegated via routing_loader) ---
    scrubbed = _scrub_secrets("token=abc123def456ghi789jkl012mno345pqr")
    assert "abc123def456ghi789jkl012mno345pqr" not in scrubbed, \
        "scrub_secrets must redact long token-shaped value"

    # --- _build_dispatch_signal: no raw text in output ---
    raw_prompt = "Do the thing now token=AKIA1234567890ABCDEF1234"
    dispatch = {
        "tool_use_id": "toolu_test_001",
        "prompt": raw_prompt,
        "preceding_text": "The scout was wrong, needs escalation.",
        "index": 0,
    }
    sig = _build_dispatch_signal("sess-abc", dispatch)

    # Must not contain the raw AWS key
    assert "AKIA1234567890ABCDEF1234" not in sig["prompt_head"], \
        "raw AWS key must not appear in prompt_head"
    # prompt_head must be capped at 200 chars
    assert len(sig["prompt_head"]) <= _PROMPT_HEAD_CAP, \
        f"prompt_head length {len(sig['prompt_head'])} exceeds cap {_PROMPT_HEAD_CAP}"
    # corrected must be True (preceding text has correction language)
    assert sig["corrected"] is True, "corrected must be True for correction language in preceding_text"
    assert sig["correction_count"] >= 2, \
        f"expected >=2 correction signals, got {sig['correction_count']}"
    assert sig["session_id"] == "sess-abc"
    assert sig["dispatch_id"] == "toolu_test_001"

    # --- _build_dispatch_signal: escalation marker detected ---
    esc_dispatch = {
        "tool_use_id": "toolu_esc_001",
        "prompt": "[gearbox-escalation from=T0 to=T1]\nPrevious scout attempt failed: OOM error.",
        "preceding_text": "The scout reported needs escalation.",
        "index": 1,
    }
    esc_sig = _build_dispatch_signal("sess-esc", esc_dispatch)
    assert esc_sig["escalation_marker"] is True, "escalation_marker must be True"
    assert esc_sig["escalated_from"] == "T0"
    assert esc_sig["escalated_to"] == "T1"
    assert esc_sig["corrected"] is True  # preceding text also has correction language

    # --- _build_dispatch_signal: no correction, no escalation ---
    clean_dispatch = {
        "tool_use_id": "toolu_clean_001",
        "prompt": "Implement the feature as described.",
        "preceding_text": "Great, let's proceed with the implementation.",
        "index": 0,
    }
    clean_sig = _build_dispatch_signal("sess-clean", clean_dispatch)
    assert clean_sig["corrected"] is False
    assert clean_sig["correction_count"] == 0
    assert clean_sig["escalation_marker"] is False

    # --- join_signals: enriches with log fields ---
    log_index = {
        ("sess-abc", "toolu_test_001"): {
            "tier": "T1",
            "subagent_type": "gearbox:builder",
        }
    }
    joined = join_signals([sig], log_index)
    assert joined[0]["tier"] == "T1"
    assert joined[0]["subagent_type"] == "gearbox:builder"

    # --- join_signals: no match → tier=None, subagent_type=None ---
    joined_no_match = join_signals([clean_sig], {})
    assert joined_no_match[0]["tier"] is None
    assert joined_no_match[0]["subagent_type"] is None

    # --- load_correction_signals round-trip ---
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        tmp = Path(f.name)
        f.write(json.dumps(sig) + "\n")
        f.write(json.dumps(clean_sig) + "\n")
    try:
        loaded = load_correction_signals(tmp)
        key1 = (sig["session_id"], sig["dispatch_id"])
        key2 = (clean_sig["session_id"], clean_sig["dispatch_id"])
        assert key1 in loaded, f"key {key1} not found in loaded signals"
        assert key2 in loaded, f"key {key2} not found in loaded signals"
        assert loaded[key1]["corrected"] is True
        assert loaded[key2]["corrected"] is False
    finally:
        tmp.unlink(missing_ok=True)

    # --- synthetic transcript fixture: _extract_task_dispatches ---
    # Build a temp JSONL that mimics a Claude session with two Task dispatches.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        tmp_t = Path(f.name)
        # First assistant message: text + tool_use (Task)
        f.write(json.dumps({
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I'll dispatch a scout."},
                    {"type": "tool_use", "name": "Task", "id": "toolu_s1",
                     "input": {"prompt": "Explore the codebase briefly.", "subagent_type": "gearbox:scout"}},
                ],
            },
            "uuid": "u1",
            "sessionId": "sess-synth",
        }) + "\n")
        # Second assistant message: correction text + tool_use (Task again)
        f.write(json.dumps({
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "The scout was wrong. Needs escalation."},
                    {"type": "tool_use", "name": "Task", "id": "toolu_b1",
                     "input": {
                         "prompt": "[gearbox-escalation from=T0 to=T1]\nFix the bug properly.",
                         "subagent_type": "gearbox:builder",
                     }},
                ],
            },
            "uuid": "u2",
            "sessionId": "sess-synth",
        }) + "\n")

    try:
        dispatches = _extract_task_dispatches(tmp_t)
        assert len(dispatches) == 2, f"expected 2 dispatches, got {len(dispatches)}"

        # First dispatch: no preceding text → not corrected
        sig_s1 = _build_dispatch_signal("sess-synth", dispatches[0])
        assert sig_s1["dispatch_id"] == "toolu_s1"
        assert sig_s1["corrected"] is False, \
            "first dispatch has no preceding correction text"
        assert sig_s1["escalation_marker"] is False

        # Second dispatch: preceding text has correction language → corrected
        sig_b1 = _build_dispatch_signal("sess-synth", dispatches[1])
        assert sig_b1["dispatch_id"] == "toolu_b1"
        assert sig_b1["corrected"] is True, \
            "second dispatch follows correction language → corrected=True"
        assert sig_b1["escalation_marker"] is True, \
            "second dispatch has escalation marker in prompt"
        assert sig_b1["escalated_from"] == "T0"
        assert sig_b1["escalated_to"] == "T1"

        # NO raw transcript text in any signal output
        for s in [sig_s1, sig_b1]:
            dumped = json.dumps(s)
            # The full prompt text should not appear verbatim
            assert "Explore the codebase briefly." not in dumped or len("Explore the codebase briefly.") <= _PROMPT_HEAD_CAP, \
                "raw prompt text must not appear beyond cap"
            assert "The scout was wrong. Needs escalation." not in dumped, \
                "preceding_text (correction context) must not appear in output"
            assert "Fix the bug properly." not in dumped or len("Fix the bug properly.") <= _PROMPT_HEAD_CAP, \
                "raw prompt beyond cap must not appear in output"

    finally:
        tmp_t.unlink(missing_ok=True)

    print("selfcheck OK")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mine session transcripts for correction/escalation signals and join to routing log."
    )
    parser.add_argument(
        "--log",
        default=os.path.expanduser("~/.claude/gearbox-log.jsonl"),
        metavar="PATH",
        help="Routing log to join against (default: ~/.claude/gearbox-log.jsonl)",
    )
    parser.add_argument(
        "--transcripts",
        default=os.path.expanduser("~/.claude/projects"),
        metavar="DIR",
        help="Root transcript directory (default: ~/.claude/projects)",
    )
    parser.add_argument(
        "--out",
        default=os.path.expanduser("~/.claude/bench-correction-signals.jsonl"),
        metavar="PATH",
        help="Output signals file (default: ~/.claude/bench-correction-signals.jsonl)",
    )
    parser.add_argument(
        "--selfcheck",
        action="store_true",
        help="Run assert-based self-tests and exit (no real files read).",
    )
    args = parser.parse_args()

    if args.selfcheck:
        _run_selfcheck()

    transcripts_dir = Path(args.transcripts)
    log_path = Path(args.log)
    out_path = Path(args.out)

    signals = mine_transcripts(transcripts_dir, log_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for sig in signals:
            f.write(json.dumps(sig, ensure_ascii=False) + "\n")

    n_corrected = sum(1 for s in signals if s["corrected"])
    n_escalated = sum(1 for s in signals if s["escalation_marker"])
    print(
        f"Wrote {len(signals)} signals ({n_corrected} corrected, "
        f"{n_escalated} with escalation marker) → {out_path}"
    )


if __name__ == "__main__":
    main()
