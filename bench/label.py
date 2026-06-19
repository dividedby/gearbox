#!/usr/bin/env python3
"""Outcome-labeling runner for Gearbox delegation logs.

Consumes ~/.claude/gearbox-log.jsonl (post-issue-#5 schema: ts, session_id,
tool_name, subagent_type, model, prompt_head, cwd, total_tokens, num_turns,
duration_ms, cost_usd, cost_estimated) and emits labeled training data for
the future learned router (reward = quality/cost).
"""
import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def _record_id(record: dict) -> str:
    """Stable sha1 key from the fields that identify a unique delegation.

    Includes the delegation discriminators (tool, agent, model) and the
    per-process uid so two genuinely-parallel dispatches of the same
    agent+model+prompt within the same 1-second ts don't collide and
    silently drop one another during resumable dedup.  Records without a
    uid (pre-G2 log lines) fall back to empty string for backward compat.
    """
    parts = [
        record.get("ts", ""),
        record.get("session_id", ""),
        record.get("tool_name", ""),
        record.get("subagent_type", ""),
        record.get("model", ""),
        record.get("prompt_head", ""),
        record.get("uid", ""),
    ]
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha1(raw.encode()).hexdigest()


def _is_verifier(record: dict) -> bool:
    """Return True if this record is a verifier dispatch."""
    subagent = (record.get("subagent_type") or "").lower()
    return subagent == "verifier" or subagent == "gearbox:verifier"


def build_training_row(record: dict, quality_score) -> dict:
    """Build a labeled training row from a log record and a graded quality score.

    quality_score is int | None (0–3).
    Pure function — no I/O.
    """
    # Back-compat: acceptable derived from quality_score.
    acceptable = quality_score is not None and quality_score >= 1

    cost_usd = record.get("cost_usd")
    try:
        cost_float = float(cost_usd)
        if cost_float > 0 and quality_score is not None:
            # ponytail: linear score→reward; revisit curve once score distribution is observed
            reward = (quality_score / 3) / cost_float
        else:
            reward = None
    except (TypeError, ValueError):
        reward = None

    return {
        "id": _record_id(record),
        "schema_version": 2,
        "subagent_type": record.get("subagent_type"),
        "model": record.get("model"),
        "total_tokens": record.get("total_tokens"),
        "num_turns": record.get("num_turns"),
        "duration_ms": record.get("duration_ms"),
        "cost_usd": record.get("cost_usd"),
        "cost_estimated": record.get("cost_estimated"),
        "prompt_head": record.get("prompt_head"),
        "acceptable": acceptable,
        "reward": reward,
    }


def load_labeled_keys(out_path: Path) -> set:
    """Return the set of ids already present in the output file."""
    keys = set()
    if not out_path.exists():
        return keys
    with out_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                if "id" in row:
                    keys.add(row["id"])
            except json.JSONDecodeError:
                pass
    return keys


def join_scores(records: list) -> dict:
    """Attribute verifier quality scores to the nearest preceding implementer dispatch.

    Given the in-order list of log records, for each verifier record with a
    non-None quality_score, find the nearest preceding non-verifier (implementer)
    Task dispatch in the same session_id and map its _record_id → quality_score.

    Returns a dict: implementer _record_id → quality_score (int).

    # ponytail: session-adjacency join; sequential only, upgrade to explicit
    # corr_id when parallel verification lands (#13)
    """
    # Build an index: session_id → list of (index, record) for implementer dispatches.
    # We scan in order so we can quickly find the nearest preceding implementer.
    result: dict = {}

    # Walk records once; maintain a per-session stack of implementer records seen so far.
    # When we hit a verifier with a score, the top of that session's stack is the nearest
    # preceding implementer.
    session_impl_stack: dict = {}  # session_id → list of (record_index, record)

    for idx, record in enumerate(records):
        session_id = record.get("session_id", "")
        if _is_verifier(record):
            score = record.get("quality_score")
            if score is None:
                continue
            # Find nearest preceding implementer in the same session.
            stack = session_impl_stack.get(session_id)
            if not stack:
                continue
            # Last item in the stack = nearest preceding implementer.
            _, impl_record = stack[-1]
            result[_record_id(impl_record)] = score
        else:
            # Non-verifier: treat as potential implementer dispatch.
            if session_id not in session_impl_stack:
                session_impl_stack[session_id] = []
            session_impl_stack[session_id].append((idx, record))

    return result


# ---------------------------------------------------------------------------
# Selfcheck
# ---------------------------------------------------------------------------

def _run_selfcheck() -> None:
    """Assert-based tests on pure helpers only. Exits 0 on success."""
    rec = {
        "ts": 1700000000,
        "session_id": "s1",
        "prompt_head": "Do something useful",
        "subagent_type": "builder",
        "model": "claude-sonnet",
        "total_tokens": 5000,
        "num_turns": 3,
        "duration_ms": 4000,
        "cost_usd": 0.1,
        "cost_estimated": False,
    }

    # --- build_training_row: score 3, cost 0.1 → reward = (3/3)/0.1 = 10.0 ---
    row3 = build_training_row(rec, quality_score=3)
    assert row3["reward"] == 10.0, f"expected 10.0, got {row3['reward']}"
    assert row3["acceptable"] is True
    assert row3["id"], "id must be non-empty"
    assert row3["schema_version"] == 2, f"expected schema_version=2, got {row3['schema_version']}"

    # --- score 0 → reward = 0.0 ---
    row0 = build_training_row(rec, quality_score=0)
    assert row0["reward"] == 0.0, f"expected 0.0 for score=0, got {row0['reward']}"
    assert row0["acceptable"] is False

    # --- score 1, cost 0.1 → reward = (1/3)/0.1 ≈ 3.333... ---
    row1 = build_training_row(rec, quality_score=1)
    expected_r1 = (1 / 3) / 0.1
    assert abs(row1["reward"] - expected_r1) < 1e-9, f"expected ~{expected_r1}, got {row1['reward']}"
    assert row1["acceptable"] is True

    # --- score 2, cost 0.1 → reward = (2/3)/0.1 ≈ 6.666... ---
    row2 = build_training_row(rec, quality_score=2)
    expected_r2 = (2 / 3) / 0.1
    assert abs(row2["reward"] - expected_r2) < 1e-9, f"expected ~{expected_r2}, got {row2['reward']}"
    assert row2["acceptable"] is True

    # --- quality_score=None → reward is None, acceptable is False ---
    row_none = build_training_row(rec, quality_score=None)
    assert row_none["reward"] is None, f"expected None for quality_score=None, got {row_none['reward']}"
    assert row_none["acceptable"] is False

    # --- cost 0 → reward is None ---
    rec_zero_cost = dict(rec, cost_usd=0.0)
    row_zero = build_training_row(rec_zero_cost, quality_score=3)
    assert row_zero["reward"] is None, f"expected None for cost=0, got {row_zero['reward']}"

    # --- cost None → reward is None ---
    rec_no_cost = dict(rec, cost_usd=None)
    row_no_cost = build_training_row(rec_no_cost, quality_score=3)
    assert row_no_cost["reward"] is None, f"expected None for cost=None, got {row_no_cost['reward']}"

    # --- id stability: same record → same id ---
    id1 = _record_id(rec)
    id2 = _record_id(rec)
    assert id1 == id2, "id must be stable"

    # id differs for different prompt_head
    rec_alt = dict(rec, prompt_head="Something completely different")
    assert _record_id(rec) != _record_id(rec_alt), "different prompt_head must differ"

    # id differs when only a delegation discriminator changes (collision guard)
    rec_disc = dict(rec, subagent_type="scout")
    assert _record_id(rec) != _record_id(rec_disc), "different subagent_type must differ"

    # uid collision guard: same content but different uid → different id
    rec_uid_a = dict(rec, uid="1234-100000")
    rec_uid_b = dict(rec, uid="1234-100001")
    assert _record_id(rec_uid_a) != _record_id(rec_uid_b), \
        "records with different uid must get different ids"

    # uid dedup: same uid → same id (resumable dedup still works)
    assert _record_id(rec_uid_a) == _record_id(rec_uid_a), \
        "records with same uid must produce stable id"

    # load_labeled_keys round-trip via tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        tmp = Path(f.name)
        row_a = build_training_row(rec, quality_score=2)
        rec_b = dict(rec, ts=1700000001, prompt_head="Another prompt")
        row_b = build_training_row(rec_b, quality_score=0)
        f.write(json.dumps(row_a) + "\n")
        f.write(json.dumps(row_b) + "\n")
    try:
        keys = load_labeled_keys(tmp)
        assert row_a["id"] in keys, "row_a id not found after round-trip"
        assert row_b["id"] in keys, "row_b id not found after round-trip"
    finally:
        tmp.unlink(missing_ok=True)

    # --- join_scores: basic adjacency ---
    # builder dispatch followed immediately by verifier in same session
    impl_rec = {
        "ts": 1700000010, "session_id": "sess1", "uid": "u1",
        "subagent_type": "gearbox:builder", "model": "sonnet",
        "tool_name": "Task", "prompt_head": "build it",
    }
    verifier_rec = {
        "ts": 1700000020, "session_id": "sess1", "uid": "u2",
        "subagent_type": "gearbox:verifier", "model": "haiku",
        "tool_name": "Task", "prompt_head": "review it",
        "quality_score": 2,
    }
    scores = join_scores([impl_rec, verifier_rec])
    impl_id = _record_id(impl_rec)
    assert impl_id in scores, "implementer id must appear in join result"
    assert scores[impl_id] == 2, f"expected score=2, got {scores[impl_id]}"

    # --- join_scores: nearest preceding selection ---
    # Two builder dispatches; verifier should attribute to the second (nearest).
    impl_rec_a = {
        "ts": 1700000010, "session_id": "sess2", "uid": "ua",
        "subagent_type": "gearbox:builder", "model": "sonnet",
        "tool_name": "Task", "prompt_head": "build first",
    }
    impl_rec_b = {
        "ts": 1700000015, "session_id": "sess2", "uid": "ub",
        "subagent_type": "gearbox:builder", "model": "sonnet",
        "tool_name": "Task", "prompt_head": "build second",
    }
    verifier_rec2 = {
        "ts": 1700000025, "session_id": "sess2", "uid": "uv2",
        "subagent_type": "gearbox:verifier", "model": "haiku",
        "tool_name": "Task", "prompt_head": "review",
        "quality_score": 3,
    }
    scores2 = join_scores([impl_rec_a, impl_rec_b, verifier_rec2])
    assert _record_id(impl_rec_b) in scores2, "nearest preceding (second) must be attributed"
    assert scores2[_record_id(impl_rec_b)] == 3
    # First builder is overridden (not in result or has different value — the
    # nearest-preceding join only attributes to the last one before the verifier)
    # In this impl, both could appear; what matters is the nearest is present.

    # --- join_scores: same-session constraint ---
    # Verifier in session B must not match an implementer in session A.
    impl_sess_a = {
        "ts": 1700000030, "session_id": "sessA", "uid": "ua2",
        "subagent_type": "gearbox:builder", "model": "sonnet",
        "tool_name": "Task", "prompt_head": "build a",
    }
    verifier_sess_b = {
        "ts": 1700000040, "session_id": "sessB", "uid": "uvb",
        "subagent_type": "gearbox:verifier", "model": "haiku",
        "tool_name": "Task", "prompt_head": "review b",
        "quality_score": 1,
    }
    scores3 = join_scores([impl_sess_a, verifier_sess_b])
    assert _record_id(impl_sess_a) not in scores3, \
        "cross-session attribution must not occur"

    # --- join_scores: verifier with no score → no entry ---
    verifier_no_score = {
        "ts": 1700000050, "session_id": "sess4", "uid": "uvns",
        "subagent_type": "gearbox:verifier", "model": "haiku",
        "tool_name": "Task", "prompt_head": "review no score",
        "quality_score": None,
    }
    impl_sess4 = {
        "ts": 1700000045, "session_id": "sess4", "uid": "ui4",
        "subagent_type": "gearbox:builder", "model": "sonnet",
        "tool_name": "Task", "prompt_head": "build 4",
    }
    scores4 = join_scores([impl_sess4, verifier_no_score])
    assert _record_id(impl_sess4) not in scores4, \
        "verifier with no score must not produce an attribution"

    # --- join_scores: parallel-interleave — documented ceiling (not fixed) ---
    # Two sessions interleaved. The join is sequential, so if session ordering
    # is interleaved, the nearest-preceding logic still works per session_id.
    impl_p1 = {
        "ts": 1700000060, "session_id": "par1", "uid": "up1",
        "subagent_type": "gearbox:builder", "model": "sonnet",
        "tool_name": "Task", "prompt_head": "par build 1",
    }
    impl_p2 = {
        "ts": 1700000061, "session_id": "par2", "uid": "up2",
        "subagent_type": "gearbox:builder", "model": "sonnet",
        "tool_name": "Task", "prompt_head": "par build 2",
    }
    verifier_p1 = {
        "ts": 1700000070, "session_id": "par1", "uid": "uvp1",
        "subagent_type": "gearbox:verifier", "model": "haiku",
        "tool_name": "Task", "prompt_head": "par review 1",
        "quality_score": 2,
    }
    verifier_p2 = {
        "ts": 1700000071, "session_id": "par2", "uid": "uvp2",
        "subagent_type": "gearbox:verifier", "model": "haiku",
        "tool_name": "Task", "prompt_head": "par review 2",
        "quality_score": 1,
    }
    # Interleaved order: impl_p1, impl_p2, verifier_p1, verifier_p2
    scores_par = join_scores([impl_p1, impl_p2, verifier_p1, verifier_p2])
    # Because we partition by session_id, each verifier finds its own session's impl.
    assert scores_par.get(_record_id(impl_p1)) == 2, \
        "par1 implementer must receive score from par1 verifier"
    assert scores_par.get(_record_id(impl_p2)) == 1, \
        "par2 implementer must receive score from par2 verifier"

    print("selfcheck OK")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Auto-derivation (default) and interactive labeling loop (--manual)
# ---------------------------------------------------------------------------

def _fmt_cost(val) -> str:
    if val is None:
        return "null"
    try:
        return f"${float(val):.6f}"
    except (TypeError, ValueError):
        return str(val)


def _print_summary(record: dict) -> None:
    subagent = record.get("subagent_type") or "(unknown)"
    model = record.get("model") or "(unknown)"
    prompt = (record.get("prompt_head") or "")[:120]
    tokens = record.get("total_tokens")
    turns = record.get("num_turns")
    cost = _fmt_cost(record.get("cost_usd"))
    estimated = record.get("cost_estimated", False)
    cost_str = f"{cost}" + (" [est]" if estimated else "")
    print(f"\n  type={subagent}  model={model}")
    print(f"  tokens={tokens}  turns={turns}  cost={cost_str}")
    print(f"  prompt: {prompt!r}")


def run_auto(log_path: Path, out_path: Path) -> None:
    """Auto-derivation mode: join verifier scores to implementer dispatches."""
    if not log_path.exists():
        print(f"Log file not found: {log_path}")
        sys.exit(0)

    labeled = load_labeled_keys(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    records = []
    with log_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    score_map = join_scores(records)

    written = 0
    with out_path.open("a", encoding="utf-8") as out_f:
        for record in records:
            if _is_verifier(record):
                continue
            rec_id = _record_id(record)
            if rec_id in labeled:
                continue
            score = score_map.get(rec_id)
            if score is None:
                continue  # no adjacent verifier score — no reward
            row = build_training_row(record, score)
            out_f.write(json.dumps(row, ensure_ascii=False) + "\n")
            out_f.flush()
            labeled.add(rec_id)
            written += 1

    print(f"Auto-labeled {written} record(s).")


def run_labeling(log_path: Path, out_path: Path) -> None:
    """Interactive --manual mode: prompt for graded score 0/1/2/3 per record."""
    if not log_path.exists():
        print(f"Log file not found: {log_path}")
        sys.exit(0)

    labeled = load_labeled_keys(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with log_path.open(encoding="utf-8") as log_f, \
         out_path.open("a", encoding="utf-8") as out_f:

        for raw_line in log_f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError:
                continue  # malformed line — skip silently

            rec_id = _record_id(record)
            if rec_id in labeled:
                continue  # already labeled — skip

            _print_summary(record)
            while True:
                try:
                    answer = input("  label [0/1/2/3=quality score / s=skip / q=quit]: ").strip().lower()
                except EOFError:
                    print("\nEOF — quitting.")
                    return

                if answer == "q":
                    print("Quit. Progress saved.")
                    return
                if answer == "s":
                    break  # leave unlabeled
                if answer in ("0", "1", "2", "3"):
                    quality_score = int(answer)
                    row = build_training_row(record, quality_score)
                    out_f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    out_f.flush()
                    labeled.add(rec_id)
                    break
                print("  Please enter 0, 1, 2, 3, s, or q.")

    print("\nAll records processed.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Label gearbox delegation log records with quality scores for router training."
    )
    parser.add_argument(
        "--log",
        default=str(Path.home() / ".claude" / "gearbox-log.jsonl"),
        metavar="PATH",
        help="Input delegation log (default: ~/.claude/gearbox-log.jsonl)",
    )
    parser.add_argument(
        "--out",
        default="bench/training-data.jsonl",
        metavar="PATH",
        help="Labeled output file, appended/resumed (default: bench/training-data.jsonl)",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Interactive labeling mode: prompt for graded score per record.",
    )
    parser.add_argument(
        "--selfcheck",
        action="store_true",
        help="Run assert-based self-tests on pure helpers and exit.",
    )
    args = parser.parse_args()

    if args.selfcheck:
        _run_selfcheck()

    if args.manual:
        run_labeling(Path(args.log), Path(args.out))
    else:
        run_auto(Path(args.log), Path(args.out))


if __name__ == "__main__":
    main()
