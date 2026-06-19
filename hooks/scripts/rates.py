#!/usr/bin/env python3
"""Gearbox rate card: single source of truth for model pricing.

Per-component USD-per-million-tokens rates and blended fallback rates.
Imported by hooks/scripts/ modules directly and by bench/ modules via
sys.path insertion (same pattern as bench/run-live.py → bench/eval.py).

# Rate card confirmed 2026-06-19
"""
import sys

# ---------------------------------------------------------------------------
# Per-component rates (USD per million tokens), 2026-06 Anthropic rate card.
# Keys: input, output, cache_read, cache_write_5m, cache_write_1h.
# ---------------------------------------------------------------------------

TOKEN_RATES: dict = {
    "haiku":  {"input": 1.00, "output":  5.00, "cache_read": 0.10, "cache_write_5m": 1.25, "cache_write_1h":  2.00},
    "sonnet": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write_5m": 3.75, "cache_write_1h":  6.00},
    "opus":   {"input": 5.00, "output": 25.00, "cache_read": 0.50, "cache_write_5m": 6.25, "cache_write_1h": 10.00},
}

# ---------------------------------------------------------------------------
# Blended fallback rates (USD per million tokens), 2026-06 Anthropic rate card.
# Used only when the per-component token split is absent.
# ---------------------------------------------------------------------------

BLENDED_RATES: dict = {
    "haiku":  1.5,
    "sonnet": 5.0,
    "opus":   8.0,
}

# ---------------------------------------------------------------------------
# Haiku reference rate: denominator for weighted-token math.
# A pure-input Haiku dispatch of N tokens costs N weighted tokens.
# ---------------------------------------------------------------------------

HAIKU_REF: float = TOKEN_RATES["haiku"]["input"]  # 1.00 USD/M


# ---------------------------------------------------------------------------
# Selfcheck
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Rates module selfcheck.")
    parser.add_argument("--selfcheck", action="store_true")
    args = parser.parse_args()

    if not args.selfcheck:
        parser.print_help()
        sys.exit(0)

    # --- Per-component Haiku rates ---
    assert TOKEN_RATES["haiku"]["input"]         == 1.00, f"haiku input: {TOKEN_RATES['haiku']['input']}"
    assert TOKEN_RATES["haiku"]["output"]        == 5.00, f"haiku output: {TOKEN_RATES['haiku']['output']}"
    assert TOKEN_RATES["haiku"]["cache_read"]    == 0.10, f"haiku cache_read: {TOKEN_RATES['haiku']['cache_read']}"
    assert TOKEN_RATES["haiku"]["cache_write_5m"]== 1.25, f"haiku cache_write_5m: {TOKEN_RATES['haiku']['cache_write_5m']}"
    assert TOKEN_RATES["haiku"]["cache_write_1h"]== 2.00, f"haiku cache_write_1h: {TOKEN_RATES['haiku']['cache_write_1h']}"

    # --- Per-component Sonnet rates ---
    assert TOKEN_RATES["sonnet"]["input"]         == 3.00, f"sonnet input: {TOKEN_RATES['sonnet']['input']}"
    assert TOKEN_RATES["sonnet"]["output"]        == 15.00, f"sonnet output: {TOKEN_RATES['sonnet']['output']}"
    assert TOKEN_RATES["sonnet"]["cache_read"]    == 0.30, f"sonnet cache_read: {TOKEN_RATES['sonnet']['cache_read']}"
    assert TOKEN_RATES["sonnet"]["cache_write_5m"]== 3.75, f"sonnet cache_write_5m: {TOKEN_RATES['sonnet']['cache_write_5m']}"
    assert TOKEN_RATES["sonnet"]["cache_write_1h"]== 6.00, f"sonnet cache_write_1h: {TOKEN_RATES['sonnet']['cache_write_1h']}"

    # --- Per-component Opus rates ---
    assert TOKEN_RATES["opus"]["input"]         == 5.00, f"opus input: {TOKEN_RATES['opus']['input']}"
    assert TOKEN_RATES["opus"]["output"]        == 25.00, f"opus output: {TOKEN_RATES['opus']['output']}"
    assert TOKEN_RATES["opus"]["cache_read"]    == 0.50, f"opus cache_read: {TOKEN_RATES['opus']['cache_read']}"
    assert TOKEN_RATES["opus"]["cache_write_5m"]== 6.25, f"opus cache_write_5m: {TOKEN_RATES['opus']['cache_write_5m']}"
    assert TOKEN_RATES["opus"]["cache_write_1h"]== 10.00, f"opus cache_write_1h: {TOKEN_RATES['opus']['cache_write_1h']}"

    # --- Blended rates ---
    assert BLENDED_RATES["haiku"]  == 1.5, f"blended haiku: {BLENDED_RATES['haiku']}"
    assert BLENDED_RATES["sonnet"] == 5.0, f"blended sonnet: {BLENDED_RATES['sonnet']}"
    assert BLENDED_RATES["opus"]   == 8.0, f"blended opus: {BLENDED_RATES['opus']}"

    # --- Haiku reference rate ---
    assert HAIKU_REF == 1.00, f"HAIKU_REF: {HAIKU_REF}"
    # HAIKU_REF must equal haiku input rate (it is derived from it)
    assert HAIKU_REF == TOKEN_RATES["haiku"]["input"], \
        f"HAIKU_REF must equal TOKEN_RATES['haiku']['input'], got {HAIKU_REF}"

    print("rates selfcheck: OK")
    sys.exit(0)
