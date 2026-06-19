#!/usr/bin/env python3
"""G20 — Spec-vs-code consistency check for Gearbox routing tiers.

Cross-checks three sources of truth:
  (A) routing/routing.md   — tier table (agent → tier, model)
  (B) log-routing.py       — _AGENT_ROUTING dict (agent → tier, model)
  (C) agents/<name>.md     — frontmatter model: field (agent → model)

Normalises agent names to bare lowercase (strips any "gearbox:" prefix).

Special case: "verifier" carries meta-tier TV in (B) and has a frontmatter
file in (C) but is deliberately ABSENT from the (A) routing table — it is a
quality gate, not a dispatched routing tier.  This is not flagged as a
missing-entry violation.

Exit 0 — all consistent.
Exit 1 — one or more violations found (report printed before exit).
"""
import argparse
import ast
import importlib.util
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Repo root resolution
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    """Return the repo root (parent of this script's bench/ directory)."""
    return Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Source (A): parse routing/routing.md tier table
# ---------------------------------------------------------------------------

def parse_routing_md(path: Path) -> dict:
    """Return {bare_agent: {"tier": str, "model": str}} from the markdown table.

    Expects rows like:
      | T0   | gearbox:scout  | haiku  | ... |
    Only rows where the Tier column matches T\\d or TV are collected.
    """
    result = {}
    in_table = False
    tier_re = re.compile(r"T\d|TV", re.IGNORECASE)

    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            # Detect table header line
            if "Tier" in line and "Agent" in line and "Model" in line and "|" in line:
                in_table = True
                continue
            if not in_table:
                continue
            # Separator row (---|---|...)
            if re.match(r"^\s*\|[-| ]+\|\s*$", line):
                continue
            # Data row
            if "|" not in line:
                in_table = False
                continue
            cols = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cols) < 3:
                continue
            tier_col, agent_col, model_col = cols[0], cols[1], cols[2]
            if not tier_re.match(tier_col):
                continue
            bare = agent_col.removeprefix("gearbox:").strip().lower()
            if not bare:
                continue
            result[bare] = {"tier": tier_col.strip(), "model": model_col.strip().lower()}

    return result


# ---------------------------------------------------------------------------
# Source (B): import log-routing.py and read _AGENT_ROUTING
# ---------------------------------------------------------------------------

def _is_import_safe(path: Path) -> bool:
    """Return True if the module has a `if __name__ == "__main__":` guard.

    A guard means top-level code (stdin reads, network calls) is gated and
    the module can be imported without side effects.
    """
    text = path.read_text(encoding="utf-8")
    return '__name__ == "__main__"' in text or "__name__ == '__main__'" in text


def load_agent_routing_import(path: Path) -> dict:
    """Import log-routing.py and return its _AGENT_ROUTING dict."""
    spec = importlib.util.spec_from_file_location("_log_routing_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return dict(getattr(mod, "_AGENT_ROUTING"))


def load_agent_routing_ast(path: Path) -> dict:
    """Extract _AGENT_ROUTING via ast.literal_eval without executing the file."""
    text = path.read_text(encoding="utf-8")
    # Find the assignment: _AGENT_ROUTING: dict = { ... }
    # Capture from the opening brace to the matching closing brace.
    match = re.search(r"_AGENT_ROUTING\s*(?::\s*dict\s*)?=\s*(\{)", text)
    if not match:
        raise ValueError("Could not locate _AGENT_ROUTING assignment in log-routing.py")
    start = match.start(1)
    # Walk forward to find the matching closing brace.
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                literal = text[start : i + 1]
                return ast.literal_eval(literal)
    raise ValueError("Unmatched brace in _AGENT_ROUTING literal")


def parse_agent_routing(path: Path) -> dict:
    """Return {bare_agent: {"tier": str, "model": str}} from _AGENT_ROUTING.

    Prefers import (module has __main__ guard) over AST extraction.
    Normalises keys to bare lowercase.
    """
    if _is_import_safe(path):
        raw = load_agent_routing_import(path)
    else:
        raw = load_agent_routing_ast(path)

    result = {}
    for key, val in raw.items():
        bare = key.removeprefix("gearbox:").strip().lower()
        result[bare] = {
            "tier": str(val.get("tier", "")).strip(),
            "model": str(val.get("model", "")).strip().lower(),
        }
    return result


# ---------------------------------------------------------------------------
# Source (C): parse agents/*.md frontmatter
# ---------------------------------------------------------------------------

def parse_frontmatter_model(path: Path) -> str | None:
    """Return the `model:` value from YAML frontmatter between --- delimiters.

    Returns None if no frontmatter or no model key found.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    in_front = False
    for line in lines:
        if line.strip() == "---":
            if not in_front:
                in_front = True
                continue
            else:
                break  # end of frontmatter
        if in_front:
            m = re.match(r"^model\s*:\s*(.+)$", line.strip())
            if m:
                return m.group(1).strip().lower()
    return None


def parse_agent_frontmatters(agents_dir: Path) -> dict:
    """Return {bare_agent: model} from all agents/*.md frontmatters."""
    result = {}
    for md_file in sorted(agents_dir.glob("*.md")):
        bare = md_file.stem.lower()
        model = parse_frontmatter_model(md_file)
        if model is not None:
            result[bare] = model
    return result


# ---------------------------------------------------------------------------
# Source (D): derived TIER_MODEL exported by log-routing.py
# ---------------------------------------------------------------------------

def load_tier_model(log_routing_path: Path) -> dict:
    """Import log-routing.py and return its TIER_MODEL dict.

    TIER_MODEL is derived from _AGENT_ROUTING (routing tiers T0/T1/T2 only);
    this check asserts that derivation is consistent with what _AGENT_ROUTING
    itself says (i.e. every routing-tier agent maps to the right model).

    Delegates to routing_loader.load_log_routing() so importlib boilerplate
    lives in one place (hooks/scripts/routing_loader.py).
    """
    _scripts_dir = str(log_routing_path.parent)
    if _scripts_dir not in sys.path:
        sys.path.insert(0, _scripts_dir)
    from routing_loader import load_log_routing
    return dict(load_log_routing().TIER_MODEL)


def compare_tier_model(agent_routing: dict, tier_model: dict) -> list:
    """Return violations where TIER_MODEL disagrees with _AGENT_ROUTING.

    For every routing-tier (non-TV) agent in agent_routing, check that
    tier_model[tier] == agent's model.  Also check for tiers present in
    tier_model but absent from any agent in agent_routing (should not happen
    if _build_tier_model is correct, but guards future drift).
    """
    violations = []

    _routing_tiers = {"T0", "T1", "T2"}

    # Build expected mapping from _AGENT_ROUTING directly.
    expected: dict = {}
    for agent, info in agent_routing.items():
        tier = info["tier"]
        model = info["model"]
        if tier not in _routing_tiers:
            continue
        expected[tier] = model  # intra-tier consistency already asserted in log-routing.py

    for tier, model in sorted(expected.items()):
        if tier not in tier_model:
            violations.append(
                f"[tier-model-missing] tier={tier!r} present in _AGENT_ROUTING "
                f"but absent from TIER_MODEL"
            )
        elif tier_model[tier] != model:
            violations.append(
                f"[tier-model-mismatch] tier={tier!r}: "
                f"_AGENT_ROUTING says model={model!r} but TIER_MODEL has {tier_model[tier]!r}"
            )

    for tier in sorted(set(tier_model) - set(expected)):
        violations.append(
            f"[tier-model-extra] tier={tier!r} in TIER_MODEL but no routing-tier agent "
            f"in _AGENT_ROUTING maps to it"
        )

    return violations


# ---------------------------------------------------------------------------
# Comparison logic
# ---------------------------------------------------------------------------

# Agents that are deliberately absent from the (A) routing table.
# verifier is a quality-gate meta-tier (TV), not a routing tier.
_ROUTING_TABLE_EXCEPTIONS = frozenset({"verifier"})


def compare(
    routing_md: dict,   # (A) agent → {tier, model}
    agent_routing: dict, # (B) agent → {tier, model}
    frontmatters: dict,  # (C) agent → model
) -> list:
    """Return a list of human-readable violation strings.

    Empty list → consistent.
    """
    violations = []

    # Collect every agent name mentioned in any source.
    all_agents = set(routing_md) | set(agent_routing) | set(frontmatters)

    for agent in sorted(all_agents):
        in_a = agent in routing_md
        in_b = agent in agent_routing
        in_c = agent in frontmatters

        a = routing_md.get(agent)
        b = agent_routing.get(agent)
        c_model = frontmatters.get(agent)

        is_exception = agent in _ROUTING_TABLE_EXCEPTIONS

        # --- Presence checks ---

        # Every agent with an agents/*.md file must have a (B) entry, and vice versa,
        # EXCEPT the deliberate exceptions are still allowed to have both.
        if in_c and not in_b:
            violations.append(
                f"[missing-B] agent={agent!r}: has agents/{agent}.md but no _AGENT_ROUTING entry"
            )
        if in_b and not in_c:
            violations.append(
                f"[missing-C] agent={agent!r}: has _AGENT_ROUTING entry but no agents/{agent}.md"
            )

        # Every agent in the tier table (A) must appear in (B).
        # Exception agents are expected to be absent from (A) — skip (A)-absence check for them.
        if in_a and not in_b:
            violations.append(
                f"[missing-B] agent={agent!r}: in routing.md tier table but no _AGENT_ROUTING entry"
            )
        if in_b and not in_a and not is_exception:
            violations.append(
                f"[missing-A] agent={agent!r}: in _AGENT_ROUTING but absent from routing.md tier table"
            )

        # --- Value checks: (B) vs (C) ---
        if in_b and in_c:
            b_model = b["model"]
            if b_model != c_model:
                violations.append(
                    f"[model-mismatch B/C] agent={agent!r}: "
                    f"_AGENT_ROUTING model={b_model!r} vs frontmatter model={c_model!r}"
                )

        # --- Value checks: (A) vs (B) ---
        if in_a and in_b:
            a_tier, a_model = a["tier"], a["model"]
            b_tier, b_model = b["tier"], b["model"]
            if a_tier != b_tier:
                violations.append(
                    f"[tier-mismatch A/B] agent={agent!r}: "
                    f"routing.md tier={a_tier!r} vs _AGENT_ROUTING tier={b_tier!r}"
                )
            if a_model != b_model:
                violations.append(
                    f"[model-mismatch A/B] agent={agent!r}: "
                    f"routing.md model={a_model!r} vs _AGENT_ROUTING model={b_model!r}"
                )

        # --- Value checks: (A) vs (C) ---
        if in_a and in_c:
            a_model = a["model"]
            if a_model != c_model:
                violations.append(
                    f"[model-mismatch A/C] agent={agent!r}: "
                    f"routing.md model={a_model!r} vs frontmatter model={c_model!r}"
                )

    return violations


# ---------------------------------------------------------------------------
# Selfcheck — synthetic inputs only, never touches real repo files
# ---------------------------------------------------------------------------

def _run_selfcheck() -> None:
    """Assert-based tests on the compare() function. Exits 0 on success."""

    # --- Consistent set → no violations ---
    a_ok = {
        "scout":    {"tier": "T0", "model": "haiku"},
        "grunt":    {"tier": "T0", "model": "haiku"},
        "builder":  {"tier": "T1", "model": "sonnet"},
        "architect": {"tier": "T2", "model": "opus"},
    }
    b_ok = {
        "scout":    {"tier": "T0", "model": "haiku"},
        "grunt":    {"tier": "T0", "model": "haiku"},
        "verifier": {"tier": "TV", "model": "haiku"},
        "builder":  {"tier": "T1", "model": "sonnet"},
        "architect": {"tier": "T2", "model": "opus"},
    }
    c_ok = {
        "scout":    "haiku",
        "grunt":    "haiku",
        "verifier": "haiku",
        "builder":  "sonnet",
        "architect": "opus",
    }
    v = compare(a_ok, b_ok, c_ok)
    assert v == [], f"consistent set must produce no violations, got: {v}"

    # --- Model mismatch between (B) and (C) → detected ---
    c_bad = dict(c_ok, builder="opus")  # builder frontmatter says opus, B says sonnet
    v2 = compare(a_ok, b_ok, c_bad)
    assert any("builder" in x and "model-mismatch B/C" in x for x in v2), \
        f"B/C model mismatch for builder must be detected, got: {v2}"
    # Also flagged A/C mismatch
    assert any("builder" in x and "model-mismatch A/C" in x for x in v2), \
        f"A/C model mismatch for builder must be detected, got: {v2}"

    # --- Model mismatch between (A) and (B) → detected ---
    a_bad = dict(a_ok)
    a_bad["scout"] = {"tier": "T0", "model": "sonnet"}  # A says sonnet, B says haiku
    v3 = compare(a_bad, b_ok, c_ok)
    assert any("scout" in x and "model-mismatch A/B" in x for x in v3), \
        f"A/B model mismatch for scout must be detected, got: {v3}"

    # --- Tier mismatch between (A) and (B) → detected ---
    a_tier_bad = dict(a_ok)
    a_tier_bad["builder"] = {"tier": "T0", "model": "sonnet"}  # wrong tier in A
    v4 = compare(a_tier_bad, b_ok, c_ok)
    assert any("builder" in x and "tier-mismatch A/B" in x for x in v4), \
        f"A/B tier mismatch for builder must be detected, got: {v4}"

    # --- Missing _AGENT_ROUTING entry → detected ---
    b_missing = {k: v for k, v in b_ok.items() if k != "grunt"}
    v5 = compare(a_ok, b_missing, c_ok)
    assert any("grunt" in x and "missing-B" in x for x in v5), \
        f"grunt missing from B must be detected, got: {v5}"

    # --- Missing frontmatter entry → detected ---
    c_missing = {k: v for k, v in c_ok.items() if k != "architect"}
    v6 = compare(a_ok, b_ok, c_missing)
    assert any("architect" in x and "missing-C" in x for x in v6), \
        f"architect missing from C must be detected, got: {v6}"

    # --- verifier meta-tier exception: present in B and C, absent from A → NOT flagged as missing-A ---
    v7 = compare(a_ok, b_ok, c_ok)  # a_ok has no verifier
    assert not any("verifier" in x and "missing-A" in x for x in v7), \
        f"verifier absent from A must NOT be flagged as missing-A, got: {v7}"

    # --- verifier in B with meta-tier TV and haiku in C → no model-mismatch ---
    assert not any("verifier" in x and "mismatch" in x for x in v7), \
        f"verifier B/C consistent (both haiku) must not be flagged, got: {v7}"

    # --- Agent in A but not in B → detected ---
    a_extra = dict(a_ok, newagent={"tier": "T3", "model": "haiku"})
    v8 = compare(a_extra, b_ok, c_ok)
    assert any("newagent" in x and "missing-B" in x for x in v8), \
        f"agent in A but not B must be detected, got: {v8}"

    # --- Agent in B (non-exception) but not in A → detected ---
    b_extra = dict(b_ok, ghost={"tier": "T1", "model": "sonnet"})
    c_extra = dict(c_ok, ghost="sonnet")
    v9 = compare(a_ok, b_extra, c_extra)
    assert any("ghost" in x and "missing-A" in x for x in v9), \
        f"non-exception agent in B but not A must be detected, got: {v9}"

    # ---------------------------------------------------------------------------
    # compare_tier_model tests
    # ---------------------------------------------------------------------------

    tm_ok = {"T0": "haiku", "T1": "sonnet", "T2": "opus"}

    # Consistent TIER_MODEL → no violations
    vt1 = compare_tier_model(b_ok, tm_ok)
    assert vt1 == [], f"consistent TIER_MODEL must produce no violations, got: {vt1}"

    # TIER_MODEL has wrong model for T1 → detected
    tm_bad_model = dict(tm_ok, T1="opus")
    vt2 = compare_tier_model(b_ok, tm_bad_model)
    assert any("T1" in x and "tier-model-mismatch" in x for x in vt2), \
        f"TIER_MODEL T1 model mismatch must be detected, got: {vt2}"

    # TIER_MODEL missing a routing tier → detected
    tm_missing = {k: v for k, v in tm_ok.items() if k != "T2"}
    vt3 = compare_tier_model(b_ok, tm_missing)
    assert any("T2" in x and "tier-model-missing" in x for x in vt3), \
        f"TIER_MODEL missing T2 must be detected, got: {vt3}"

    # TIER_MODEL has an extra tier not in _AGENT_ROUTING → detected
    tm_extra = dict(tm_ok, T3="haiku")
    vt4 = compare_tier_model(b_ok, tm_extra)
    assert any("T3" in x and "tier-model-extra" in x for x in vt4), \
        f"TIER_MODEL extra tier T3 must be detected, got: {vt4}"

    # TV leakage: a TIER_MODEL that wrongly includes TV must be flagged as extra
    tm_tv_leak = dict(tm_ok, TV="haiku")
    vt5 = compare_tier_model(b_ok, tm_tv_leak)
    assert any("TV" in x and "tier-model-extra" in x for x in vt5), \
        f"TIER_MODEL with TV entry must be flagged as extra, got: {vt5}"

    print("selfcheck OK")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Real check
# ---------------------------------------------------------------------------

def run_real_check() -> None:
    root = _repo_root()

    routing_md_path = root / "routing" / "routing.md"
    log_routing_path = root / "hooks" / "scripts" / "log-routing.py"
    agents_dir = root / "agents"

    routing_md = parse_routing_md(routing_md_path)
    agent_routing = parse_agent_routing(log_routing_path)
    frontmatters = parse_agent_frontmatters(agents_dir)
    tier_model = load_tier_model(log_routing_path)

    violations = compare(routing_md, agent_routing, frontmatters)
    violations += compare_tier_model(agent_routing, tier_model)

    if violations:
        print("CONSISTENCY VIOLATIONS FOUND:")
        for v in violations:
            print(f"  {v}")
        sys.exit(1)
    else:
        print("All routing sources consistent.")
        sys.exit(0)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cross-check routing.md, _AGENT_ROUTING, and agent frontmatters for consistency."
    )
    parser.add_argument(
        "--selfcheck",
        action="store_true",
        help="Run assert-based unit tests on synthetic inputs and exit.",
    )
    args = parser.parse_args()

    if args.selfcheck:
        _run_selfcheck()

    run_real_check()


if __name__ == "__main__":
    main()
