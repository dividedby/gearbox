#!/usr/bin/env python3
"""Shared loader for log-routing.py.

log-routing.py has a hyphen in its name so it cannot be imported directly
as a Python identifier.  This module provides a single importlib-based helper
used by bench/eval.py, bench/run-live.py, and bench/check_consistency.py,
eliminating duplicate importlib boilerplate across those consumers.
"""
import importlib.util
from pathlib import Path

# One fixed module-name token for the importlib registry; callers that need
# to load the module more than once in a single process should call
# load_log_routing() each time — importlib.util re-executes the module fresh.
_MODULE_NAME = "_log_routing_shared"


def load_log_routing():
    """Load hooks/scripts/log-routing.py and return the module object.

    Resolves the path relative to this file so it works regardless of the
    caller's working directory.
    """
    path = Path(__file__).resolve().parent / "log-routing.py"
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def tier_model() -> dict:
    """Return a copy of TIER_MODEL from log-routing.py.

    TIER_MODEL is {tier: model} for routing tiers T0/T1/T2 only
    (TV is excluded by log-routing._build_tier_model).
    """
    return dict(load_log_routing().TIER_MODEL)


def scrub_secrets(text: str) -> str:
    """Delegate to log-routing._scrub_secrets.

    Callers outside hooks/scripts/ use this so the scrubber stays in one place.
    """
    return load_log_routing()._scrub_secrets(text)


def parse_escalation(prompt_text: str) -> tuple:
    """Delegate to log-routing.parse_escalation.

    Returns (escalation: bool, escalated_from: str|None, escalated_to: str|None).
    """
    return load_log_routing().parse_escalation(prompt_text)
