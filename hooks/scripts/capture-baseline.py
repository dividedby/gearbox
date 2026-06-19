#!/usr/bin/env python3
"""Gearbox baseline capture.

PreToolUse hook for the Task/Agent tool. Fires before a T1/T2 implementer
(builder/architect) is dispatched and writes a git status snapshot to
.claude/gearbox-baseline.txt in the project directory. The verifier reads
this file as the pre-edit BASELINE to diff the working tree against.

For parallel T1/T2 dispatches, the orchestrator may mint a short baseline_id
token, embed it in the implementer's Task prompt as [gearbox-baseline-id=<id>],
and pass the same id to the matching verifier. When this hook detects such a
marker, it ALSO writes .claude/gearbox-baseline-<baseline_id>.txt so the
verifier can read the correct, per-dispatch baseline even under concurrency.

Note on correlation IDs: baseline_id (this module) solves baseline isolation
across two separate orchestrator-authored dispatches (implementer + verifier).
dispatch_id / tool_use_id in log-routing.py solves a different problem: it
correlates cost/timing data within a single PostToolUse event. The two IDs
serve different purposes and must not be conflated.

Silent allow: this hook never prints a permission decision or blocks dispatch.
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_BASELINE_ID_RE = re.compile(r"\[gearbox-baseline-id=([A-Za-z0-9_-]{1,64})\]")


def should_capture(tool_input: dict) -> bool:
    """Return True if this dispatch warrants a baseline capture.

    Fires for builder/architect (T1/T2 implementers) and for the general-purpose
    fallback proxy when paired with a T1/T2 model (sonnet/opus). Never fires for
    verifier dispatches — that would clobber the baseline we're protecting.
    """
    subagent_type = str(tool_input.get("subagent_type", "")).lower()
    model = str(tool_input.get("model", "")).lower()

    if "verifier" in subagent_type:
        return False  # never clobber the baseline on a verifier dispatch

    if "builder" in subagent_type or "architect" in subagent_type:
        return True

    if "sonnet" in model or "opus" in model:
        return True  # fallback proxy: bare "sonnet"/"opus" or a full id like claude-sonnet-4-6

    return False  # scout/grunt/haiku/anything else


def resolve_base_dir(payload: dict) -> Path:
    """Resolve the project root directory.

    Priority: CLAUDE_PROJECT_DIR env (if valid dir) > payload cwd (if valid dir) > cwd.
    Mirrors log-routing.py's resolution pattern.
    """
    env_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if env_dir and os.path.isdir(env_dir):
        return Path(env_dir)
    cwd_field = payload.get("cwd", "")
    if cwd_field and os.path.isdir(cwd_field):
        return Path(cwd_field)
    return Path(os.getcwd())


def git_status(root: Path) -> str:
    """Run `git -C <root> status --short` and return its stdout.

    Returns a single-line error message if git is missing, errors, or the
    directory is not a git repository.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "status", "--short"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return "(baseline unavailable: not a git repository)"
        return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return "(baseline unavailable: not a git repository)"


def extract_baseline_id(tool_input: dict) -> str:
    """Extract the orchestrator-minted baseline_id from the Task prompt, if present.

    Returns the id string when the prompt contains [gearbox-baseline-id=<id>]
    with a token matching ^[A-Za-z0-9_-]{1,64}$; returns "" otherwise.
    """
    m = _BASELINE_ID_RE.search(tool_input.get("prompt", "") or "")
    return m.group(1) if m else ""


def build_body(subagent_type: str, status_output: str, baseline_id: str = "") -> str:
    """Build the full baseline file contents."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = f"# gearbox baseline | {ts} | subagent_type={subagent_type}"
    if baseline_id:
        header += f" | baseline_id={baseline_id}"
    return header + "\n\n" + status_output


def cleanup_stale_baselines(claude_dir: Path, max_age_s: int = 3600) -> None:
    """Remove per-dispatch baseline files older than max_age_s seconds.

    Only touches gearbox-baseline-*.txt (keyed files); never removes the legacy
    gearbox-baseline.txt fallback (it is managed by overwrite, not by age).
    """
    try:
        cutoff = time.time() - max_age_s
        for p in claude_dir.glob("gearbox-baseline-*.txt"):
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink(missing_ok=True)
            except OSError:
                pass
    except Exception:
        pass  # cleanup is best-effort; never raise


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # never block on parse failure

    tool_input = payload.get("tool_input", {}) or {}

    if not should_capture(tool_input):
        sys.exit(0)

    try:
        root = resolve_base_dir(payload)
        status_output = git_status(root)
        subagent_type = str(tool_input.get("subagent_type", ""))
        baseline_id = extract_baseline_id(tool_input)

        body = build_body(subagent_type, status_output, baseline_id)

        claude_dir = root / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)

        # Legacy file: always written; preserves today's behavior for sequential
        # dispatches and verifiers that have no baseline_id context.
        legacy_path = claude_dir / "gearbox-baseline.txt"
        legacy_path.write_text(body, encoding="utf-8")

        # Keyed file: written ONLY when the orchestrator supplied a baseline_id.
        # Never written with a fallback/pid-time name — an unaddressable file is
        # garbage and would never be read by the verifier.
        if baseline_id:
            keyed_path = claude_dir / f"gearbox-baseline-{baseline_id}.txt"
            keyed_path.write_text(body, encoding="utf-8")

        # Clean up stale keyed baselines so files don't accumulate unbounded.
        cleanup_stale_baselines(claude_dir)
    except Exception:
        pass  # robustness: never block or delay a Task dispatch

    sys.exit(0)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selfcheck":
        import tempfile as _tf

        # --- should_capture: named agent cases ---
        assert should_capture({"subagent_type": "gearbox:builder"}) is True, \
            "gearbox:builder must capture"
        assert should_capture({"subagent_type": "gearbox:architect"}) is True, \
            "gearbox:architect must capture"
        assert should_capture({"subagent_type": "gearbox:verifier"}) is False, \
            "gearbox:verifier must NOT capture"
        assert should_capture({"subagent_type": "gearbox:verifier", "model": "opus"}) is False, \
            "gearbox:verifier with opus must NOT capture"
        assert should_capture({"subagent_type": "gearbox:scout"}) is False, \
            "gearbox:scout must NOT capture"
        assert should_capture({"subagent_type": "gearbox:grunt"}) is False, \
            "gearbox:grunt must NOT capture"

        # --- should_capture: general-purpose fallback proxy ---
        assert should_capture({"subagent_type": "general-purpose", "model": "sonnet"}) is True, \
            "general-purpose+sonnet must capture (T1 fallback proxy)"
        assert should_capture({"subagent_type": "general-purpose", "model": "haiku"}) is False, \
            "general-purpose+haiku must NOT capture (T0 fallback proxy)"

        # --- should_capture: empty/missing fields ---
        assert should_capture({}) is False, "empty tool_input must NOT capture"
        assert should_capture({"subagent_type": "", "model": ""}) is False, \
            "empty strings must NOT capture"

        # --- extract_baseline_id: present ---
        assert extract_baseline_id({"prompt": "x [gearbox-baseline-id=b1] y"}) == "b1", \
            "must extract id from embedded marker"
        # --- extract_baseline_id: absent ---
        assert extract_baseline_id({"prompt": "no marker here"}) == "", \
            "must return empty string when marker absent"
        assert extract_baseline_id({}) == "", \
            "must return empty string when prompt key missing"
        # --- extract_baseline_id: empty marker value ---
        assert extract_baseline_id({"prompt": "[gearbox-baseline-id=]"}) == "", \
            "empty marker value must return empty string (regex requires 1+ chars)"
        # --- extract_baseline_id: too-long token (>64 chars) ---
        long_token = "a" * 65
        assert extract_baseline_id({"prompt": f"[gearbox-baseline-id={long_token}]"}) == "", \
            "token exceeding 64 chars must not match"
        # --- extract_baseline_id: bad chars ---
        assert extract_baseline_id({"prompt": "[gearbox-baseline-id=bad!char]"}) == "", \
            "token with bad chars must not match"

        # --- build_body: file format (no baseline_id) ---
        sample_status = " M hooks/hooks.json\n?? hooks/scripts/capture-baseline.py\n"
        body = build_body("gearbox:builder", sample_status)
        lines = body.split("\n")
        assert lines[0].startswith("# gearbox baseline | "), \
            f"header must start with '# gearbox baseline | ': {lines[0]!r}"
        assert "subagent_type=gearbox:builder" in lines[0], \
            f"header must include subagent_type: {lines[0]!r}"
        assert lines[1] == "", f"second line must be blank: {lines[1]!r}"
        assert sample_status in body, "git status output must appear verbatim in body"

        # --- build_body: baseline_id appears in header when provided ---
        body_with_id = build_body("gearbox:builder", sample_status, "b1")
        assert "baseline_id=b1" in body_with_id.split("\n")[0], \
            f"baseline_id must appear in header: {body_with_id.split(chr(10))[0]!r}"

        # --- build_body: no baseline_id field when empty string ---
        body_no_id = build_body("gearbox:builder", sample_status, "")
        assert "baseline_id=" not in body_no_id.split("\n")[0], \
            f"baseline_id must be absent when empty: {body_no_id.split(chr(10))[0]!r}"

        # --- resolve_base_dir: falls back to cwd when env unset ---
        import os as _os
        orig_env = _os.environ.pop("CLAUDE_PROJECT_DIR", None)
        try:
            result_path = resolve_base_dir({"cwd": "/tmp"})
            assert result_path == Path("/tmp"), \
                f"payload cwd='/tmp' must resolve to /tmp, got {result_path}"
            result_no_cwd = resolve_base_dir({})
            assert result_no_cwd == Path(_os.getcwd()), \
                f"empty payload must fall back to os.getcwd(), got {result_no_cwd}"
        finally:
            if orig_env is not None:
                _os.environ["CLAUDE_PROJECT_DIR"] = orig_env

        # --- integration: with baseline_id → both keyed and legacy files exist ---
        with _tf.TemporaryDirectory() as _tmpdir:
            _claude_dir = Path(_tmpdir) / ".claude"
            _claude_dir.mkdir()
            _bid = "impl-abc"
            _keyed = _claude_dir / f"gearbox-baseline-{_bid}.txt"
            _legacy = _claude_dir / "gearbox-baseline.txt"
            _body = build_body("gearbox:builder", "M foo.py\n", _bid)
            _legacy.write_text(_body, encoding="utf-8")
            _keyed.write_text(_body, encoding="utf-8")
            assert _legacy.exists(), "legacy baseline file must exist"
            assert _keyed.exists(), "keyed baseline file must exist"
            assert _bid in _keyed.name, "keyed filename must contain the baseline_id token"
            assert f"baseline_id={_bid}" in _keyed.read_text(), \
                "keyed file must contain baseline_id in header"

        # --- integration: without baseline_id → only legacy exists, no keyed files ---
        with _tf.TemporaryDirectory() as _tmpdir2:
            _cd2 = Path(_tmpdir2) / ".claude"
            _cd2.mkdir()
            _legacy2 = _cd2 / "gearbox-baseline.txt"
            _body2 = build_body("gearbox:builder", "M bar.py\n")
            _legacy2.write_text(_body2, encoding="utf-8")
            _keyed_glob = list(_cd2.glob("gearbox-baseline-*.txt"))
            assert _legacy2.exists(), "legacy baseline file must exist when no baseline_id"
            assert _keyed_glob == [], \
                f"no keyed files must exist when baseline_id absent, found: {_keyed_glob}"

        # --- cleanup_stale_baselines: old keyed file is removed, fresh and legacy survive ---
        with _tf.TemporaryDirectory() as _tmpdir3:
            _cd = Path(_tmpdir3) / ".claude"
            _cd.mkdir()
            import time as _time
            # Create a stale keyed file (mtime set 2 hours in the past)
            _stale = _cd / "gearbox-baseline-stale123.txt"
            _stale.write_text("old", encoding="utf-8")
            _stale_time = _time.time() - 7200
            _os.utime(str(_stale), (_stale_time, _stale_time))
            # Create a fresh keyed file (just written)
            _fresh = _cd / "gearbox-baseline-fresh456.txt"
            _fresh.write_text("new", encoding="utf-8")
            # Create the legacy file (must never be touched by cleanup)
            _leg = _cd / "gearbox-baseline.txt"
            _leg.write_text("legacy", encoding="utf-8")
            # Run cleanup with 1-hour threshold
            cleanup_stale_baselines(_cd, max_age_s=3600)
            assert not _stale.exists(), "stale keyed file must be removed"
            assert _fresh.exists(), "fresh keyed file must survive"
            assert _leg.exists(), "legacy file must never be removed by cleanup"

        print("selfcheck OK")
        sys.exit(0)

    main()
