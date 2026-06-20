#!/usr/bin/env python3
"""Gearbox UserPromptSubmit classifier hook.

Fires before every prompt turn.  Classifies the incoming prompt via
recommend.py's bucket_task_class(), derives a recommended tier (from the
routing prior when available, falling back to the static policy defaults),
and injects a one-line advisory into Claude's context.

Advisory is capture-only — it must not be read as overriding the routing
policy's hard floors or max-dimension rule.  This hook never blocks a prompt
and exits 0 on any error so it cannot stall a session.
"""
import json
import os
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Task-class registry loader (direct JSON read — no dependency on recommend.py).
# ---------------------------------------------------------------------------

def _load_static_tier_from_registry() -> dict:
    """Build the static tier map by reading bench/task-classes.json directly.

    Resolves relative to this file: hooks/scripts/ → ../../bench/task-classes.json.
    Falls back to a hard-coded minimal dict on any read/parse failure so the
    hook never stalls a session.
    """
    _fallback = {
        "mechanical-edit": "T0",
        "explore/read": "T0",
        "test": "T1",
        "design/debug-hard": "T2",
        "implement/fix": "T1",
        "other": "T1",
    }
    try:
        registry_path = Path(__file__).resolve().parent.parent.parent / "bench" / "task-classes.json"
        with registry_path.open(encoding="utf-8") as f:
            data = json.load(f)
        return {entry["name"]: entry["tier"] for entry in data["classes"]}
    except Exception:
        return _fallback


# ---------------------------------------------------------------------------
# Static fallback tier map (used when the routing prior has no data for a class).
# Loaded from bench/task-classes.json — the canonical registry.
# ---------------------------------------------------------------------------

_STATIC_TIER: dict = _load_static_tier_from_registry()


def _load_recommend():
    """Return the recommend module, or None on any import failure.

    recommend.py has no hyphen so a normal import works once the bench/
    directory is on sys.path.  We resolve relative to this file so the hook
    works regardless of cwd.
    """
    try:
        bench_dir = str(Path(__file__).resolve().parent.parent.parent / "bench")
        if bench_dir not in sys.path:
            sys.path.insert(0, bench_dir)
        import recommend  # noqa: PLC0415
        return recommend
    except Exception:
        return None


def classify(prompt: str) -> tuple:
    """Return (task_class, recommended_tier).

    Tries to use recommend.py + routing prior.  Falls back gracefully at
    every step — the returned tuple always contains strings.
    """
    rec_mod = _load_recommend()

    # Classify the task class.
    if rec_mod is not None:
        try:
            task_class = rec_mod.bucket_task_class(prompt.lower())
        except Exception:
            task_class = "other"
    else:
        task_class = "other"

    # Derive recommended tier from the routing prior when available.
    recommended_tier = None
    if rec_mod is not None:
        try:
            log_path = Path(os.path.expanduser("~/.claude/gearbox-log.jsonl"))
            records = rec_mod.load_records(log_path)
            if records:
                prior = rec_mod.recommended_tiers(records)
                recommended_tier = prior.get(task_class)
        except Exception:
            pass

    # Fall back to static policy defaults.
    if recommended_tier is None:
        recommended_tier = _STATIC_TIER.get(task_class, "T1")

    return task_class, recommended_tier


def make_advisory(task_class: str, recommended_tier: str) -> str:
    """Return the advisory line injected into context."""
    return (
        f"[gearbox-classify] advisory: looks like a {recommended_tier} task "
        f"(class: {task_class}). "
        "This is a pre-turn signal only — it does not override hard floors, "
        "max-dimension routing, or the circuit breaker."
    )


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

    prompt = payload.get("prompt") or ""
    if not prompt.strip():
        # No prompt to classify (empty or missing field) — emit nothing.
        sys.exit(0)

    try:
        task_class, recommended_tier = classify(prompt)
        advisory = make_advisory(task_class, recommended_tier)
        output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": advisory,
            }
        }
        print(json.dumps(output))
    except Exception:
        pass  # never stall a session

    sys.exit(0)


# ---------------------------------------------------------------------------
# Self-check
# ---------------------------------------------------------------------------

def _selfcheck() -> None:
    import io
    import contextlib

    # --- static tier map must exactly match the registry ---
    # Load the registry directly to verify _STATIC_TIER was populated from it.
    registry_path = Path(__file__).resolve().parent.parent.parent / "bench" / "task-classes.json"
    with registry_path.open(encoding="utf-8") as _f:
        _reg_data = json.load(_f)
    _registry_tier_map = {entry["name"]: entry["tier"] for entry in _reg_data["classes"]}
    assert _STATIC_TIER == _registry_tier_map, (
        f"_STATIC_TIER does not match registry.\n"
        f"  _STATIC_TIER: {_STATIC_TIER}\n"
        f"  registry:     {_registry_tier_map}"
    )
    # Also verify via recommend module (belt-and-suspenders: registry and recommend agree).
    rec_mod = _load_recommend()
    assert rec_mod is not None, "recommend module must be importable for selfcheck"
    assert set(_STATIC_TIER) >= set(rec_mod.CLASS_ORDER), (
        f"_STATIC_TIER is missing keys: {set(rec_mod.CLASS_ORDER) - set(_STATIC_TIER)}"
    )

    # --- classify() produces the right classes for representative prompts ---
    tc, tier = classify("fix the typo in the README")
    assert tc == "mechanical-edit", f"expected mechanical-edit, got {tc!r}"
    assert tier in ("T0", "T1", "T2"), f"tier not in expected set: {tier!r}"
    # mechanical-edit should prefer T0 from static defaults
    assert tier == "T0", f"expected T0 for mechanical-edit, got {tier!r}"

    tc2, tier2 = classify("design a migration with a race condition in the auth system")
    assert tc2 == "design/debug-hard", f"expected design/debug-hard, got {tc2!r}"
    assert tier2 == "T2", f"expected T2 for design/debug-hard, got {tier2!r}"

    tc3, tier3 = classify("implement the new payment endpoint")
    assert tc3 == "implement/fix", f"expected implement/fix, got {tc3!r}"
    assert tier3 == "T1", f"expected T1 for implement/fix, got {tier3!r}"

    tc4, tier4 = classify("read and summarize the current architecture")
    assert tc4 == "explore/read", f"expected explore/read, got {tc4!r}"
    assert tier4 == "T0", f"expected T0 for explore/read, got {tier4!r}"

    # --- advisory must not echo raw prompt ---
    prompt = "fix the typo in the README and do something extremely verbose about it"
    tc5, tier5 = classify(prompt)
    advisory = make_advisory(tc5, tier5)
    assert prompt not in advisory, "advisory must not echo the raw prompt"
    assert "advisory:" in advisory, "advisory should contain 'advisory:'"
    assert "class:" in advisory, "advisory should contain 'class:'"
    assert tier5 in advisory, "advisory should contain the tier"

    # --- graceful no-op on empty/missing prompt ---
    import subprocess
    result = subprocess.run(
        [sys.executable, __file__],
        input=json.dumps({}),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"empty payload exited non-zero: {result.returncode}"
    assert result.stdout.strip() == "", f"unexpected stdout on empty prompt: {result.stdout!r}"

    result2 = subprocess.run(
        [sys.executable, __file__],
        input=json.dumps({"prompt": ""}),
        capture_output=True,
        text=True,
    )
    assert result2.returncode == 0, f"empty string prompt exited non-zero: {result2.returncode}"
    assert result2.stdout.strip() == "", f"unexpected stdout on empty string prompt: {result2.stdout!r}"

    # --- normal prompt produces hookSpecificOutput JSON ---
    result3 = subprocess.run(
        [sys.executable, __file__],
        input=json.dumps({"prompt": "fix the typo", "hook_event_name": "UserPromptSubmit"}),
        capture_output=True,
        text=True,
    )
    assert result3.returncode == 0, f"normal prompt exited non-zero: {result3.returncode}"
    out = json.loads(result3.stdout)
    assert "hookSpecificOutput" in out, "expected hookSpecificOutput in output"
    hso = out["hookSpecificOutput"]
    assert hso.get("hookEventName") == "UserPromptSubmit"
    ctx = hso.get("additionalContext", "")
    assert "advisory:" in ctx, f"advisory missing from context: {ctx!r}"
    assert "fix the typo" not in ctx, "raw prompt must not appear in advisory"

    # --- graceful on malformed stdin ---
    result4 = subprocess.run(
        [sys.executable, __file__],
        input="not-json-at-all",
        capture_output=True,
        text=True,
    )
    assert result4.returncode == 0, f"malformed stdin exited non-zero: {result4.returncode}"
    assert result4.stdout.strip() == "", f"unexpected stdout on malformed stdin: {result4.stdout!r}"

    # --- static fallback when recommend unavailable ---
    # Test the static-tier fallback directly — simulating a None rec_mod path.
    # (sys.path manipulation is fragile across Python installs; test the
    # actual code path: when task_class is "other" and prior has no data,
    # _STATIC_TIER["other"] == "T1" is the fallback.)
    assert _STATIC_TIER["other"] == "T1", "static fallback for 'other' should be T1"
    assert _STATIC_TIER["mechanical-edit"] == "T0", "static fallback for mechanical-edit should be T0"
    assert _STATIC_TIER["design/debug-hard"] == "T2", "static fallback for design/debug-hard should be T2"
    # Verify the advisory for "other" class with T1 tier has no raw prompt.
    adv_fallback = make_advisory("other", "T1")
    assert "T1" in adv_fallback, "advisory should contain T1"
    assert "other" in adv_fallback, "advisory should contain class name"

    print("classify-prompt selfcheck: OK")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    main()
