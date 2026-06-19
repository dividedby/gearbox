#!/usr/bin/env python3
"""Cache-savings report: quantify the realized prompt-caching saving.

Reads ~/.claude/gearbox-log.jsonl and aggregates, per model, the cache-token
split the harness already produced — caching is automatic and harness-controlled
(see #25/#8): how many input tokens were served from cache (`cache_read`) vs.
written to cache (`cache_creation`), and the net USD that split saved against
paying the full input rate. Read-only: prints a report, writes nothing.
"""
import argparse
import sys
from pathlib import Path

# Resolve hooks/scripts/ relative to this file so rates.py and budget_common are
# importable regardless of the caller's working directory (same pattern as eval.py).
_hooks_scripts = str(Path(__file__).resolve().parent.parent / "hooks" / "scripts")
if _hooks_scripts not in sys.path:
    sys.path.insert(0, _hooks_scripts)

from rates import TOKEN_RATES
from budget_common import read_rows, default_log_path


def _num(v):
    """Coerce a JSON value to a number for summing; bools and non-numbers → 0."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return 0
    return v


def summarize(rows: list) -> dict:
    """Aggregate cache-token split and realized USD saving per model. Pure.

    Per model:
      gross_read_saving = cache_read   × (input_rate − cache_read_rate)
      creation_premium  = cache_creation × (cache_write_5m_rate − input_rate)
      net_saving        = gross_read_saving − creation_premium
    Only rows whose `model` is in the rate card and which carry nonzero cache
    tokens are counted. Returns {"models": {m: {...}}, "totals": {...}}.
    """
    per: dict = {}
    for r in rows:
        m = r.get("model")
        if m not in TOKEN_RATES:
            continue
        cr = _num(r.get("cache_read_tokens"))
        cc = _num(r.get("cache_creation_tokens"))
        if cr == 0 and cc == 0:
            continue
        d = per.setdefault(m, {"cache_read": 0, "cache_creation": 0, "rows": 0})
        d["cache_read"] += cr
        d["cache_creation"] += cc
        d["rows"] += 1

    models: dict = {}
    t_cr = t_cc = t_gross = t_prem = t_rows = 0
    for m, d in per.items():
        rr = TOKEN_RATES[m]
        gross = d["cache_read"] * (rr["input"] - rr["cache_read"]) / 1e6
        # ponytail: charges every cache_creation token at the 5-minute ephemeral
        # write rate. The log record doesn't split 5m/1h writes and 5m is the
        # default TTL; add a 5m/1h split here if the log ever records the TTL.
        prem = d["cache_creation"] * (rr["cache_write_5m"] - rr["input"]) / 1e6
        models[m] = {
            "rows": d["rows"],
            "cache_read": d["cache_read"],
            "cache_creation": d["cache_creation"],
            "gross_read_saving_usd": round(gross, 6),
            "creation_premium_usd": round(prem, 6),
            "net_saving_usd": round(gross - prem, 6),
        }
        t_cr += d["cache_read"]
        t_cc += d["cache_creation"]
        t_gross += gross
        t_prem += prem
        t_rows += d["rows"]

    return {
        "models": models,
        "totals": {
            "rows": t_rows,
            "cache_read": t_cr,
            "cache_creation": t_cc,
            "read_creation_ratio": round(t_cr / t_cc, 3) if t_cc else None,
            "gross_read_saving_usd": round(t_gross, 6),
            "creation_premium_usd": round(t_prem, 6),
            "net_saving_usd": round(t_gross - t_prem, 6),
        },
    }


def format_report(summary: dict) -> str:
    """Render a summarize() result as a fixed-width per-model table + totals."""
    models = summary["models"]
    tot = summary["totals"]
    lines = ["Prompt-caching realized saving (read-only; automatic harness caching)", ""]
    if not models:
        lines.append("No rows with cache tokens found in the log.")
        return "\n".join(lines)
    hdr = f"{'model':8} {'rows':>5} {'cache_read':>14} {'cache_creation':>16} {'net_usd':>12}"
    lines.append(hdr)
    lines.append("-" * len(hdr))
    for m in sorted(models):
        d = models[m]
        lines.append(f"{m:8} {d['rows']:>5} {d['cache_read']:>14,} "
                     f"{d['cache_creation']:>16,} {d['net_saving_usd']:>12.6f}")
    lines.append("-" * len(hdr))
    ratio = tot["read_creation_ratio"]
    ratio_s = f"{ratio:.2f}:1" if ratio is not None else "n/a"
    lines.append(f"{'TOTAL':8} {tot['rows']:>5} {tot['cache_read']:>14,} "
                 f"{tot['cache_creation']:>16,} {tot['net_saving_usd']:>12.6f}")
    lines.append("")
    lines.append(f"read:creation split = {ratio_s}  "
                 f"(gross read saving ${tot['gross_read_saving_usd']:.6f} "
                 f"− creation premium ${tot['creation_premium_usd']:.6f})")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--log", type=Path, default=None,
                        help="path to gearbox-log.jsonl (default: ~/.claude/gearbox-log.jsonl)")
    parser.add_argument("--selfcheck", action="store_true")
    args = parser.parse_args(argv)

    if args.selfcheck:
        _selfcheck()
        return 0

    rows = read_rows(args.log if args.log is not None else default_log_path())
    print(format_report(summarize(rows)))
    return 0


def _selfcheck() -> None:
    rows = [
        # haiku: read 1,000,000 / creation 200,000
        {"model": "haiku", "cache_read_tokens": 600_000, "cache_creation_tokens": 200_000},
        {"model": "haiku", "cache_read_tokens": 400_000, "cache_creation_tokens": 0},
        {"model": "sonnet", "cache_read_tokens": 1_000_000, "cache_creation_tokens": 0},
        {"model": "opus", "cache_read_tokens": None, "cache_creation_tokens": None},  # None-safe, skipped
        {"model": "T0-unknown", "cache_read_tokens": 9, "cache_creation_tokens": 9},  # not a model, skipped
        {"cache_read_tokens": 5},  # no model, skipped
    ]
    s = summarize(rows)

    # haiku: gross = 1e6*(1.00-0.10)/1e6 = 0.90 ; premium = 2e5*(1.25-1.00)/1e6 = 0.05 ; net 0.85
    h = s["models"]["haiku"]
    assert h["rows"] == 2 and h["cache_read"] == 1_000_000 and h["cache_creation"] == 200_000, h
    assert h["gross_read_saving_usd"] == 0.90, h
    assert h["creation_premium_usd"] == 0.05, h
    assert h["net_saving_usd"] == 0.85, h

    # sonnet: gross = 1e6*(3.00-0.30)/1e6 = 2.70 ; no creation
    so = s["models"]["sonnet"]
    assert so["net_saving_usd"] == 2.70, so

    # unknown/opus-None/no-model rows excluded
    assert "opus" not in s["models"] and "T0-unknown" not in s["models"], s["models"]

    # totals
    t = s["totals"]
    assert t["cache_read"] == 2_000_000 and t["cache_creation"] == 200_000, t
    assert t["read_creation_ratio"] == 10.0, t
    assert t["net_saving_usd"] == round(0.85 + 2.70, 6), t

    # empty input → no models, ratio None, no crash
    e = summarize([])
    assert e["models"] == {} and e["totals"]["read_creation_ratio"] is None, e
    assert "No rows" in format_report(e)

    # report renders for the populated case
    rep = format_report(s)
    assert "read:creation split = 10.00:1" in rep, rep

    print("cache-savings selfcheck: OK")


if __name__ == "__main__":
    sys.exit(main())
