#!/usr/bin/env python3
"""Measure the dollars-per-percent constants in server.py's QUOTA_RATE.

    uv run python tools/console/calibrate.py

Nothing publishes how much usage a rate-limit window holds, so the figures are
derived: price every assistant message that falls inside a window at list
rates, then divide by that window's utilization. Parallel sessions land in the
sum rather than corrupting it, which is why this works where sampling the
utilization around a single turn does not.

This reads one moment. A window sampled early, or one whose model mix differs
from the mix a constant will be applied to, gives a figure that will not hold —
quota.py's samples are what show whether it does.

Utilization is account-wide while the sum covers this machine's transcripts
alone. Usage from claude.ai, Cowork, or another machine raises the percentage
without entering the sum, which biases the constants low.

PRICES needs an entry per model in the mix, and needs updating when rates
change. Any model the script cannot price is reported and skipped.
"""

from collections import defaultdict

import quota

# List rates per million tokens, as (input, output). Cache writes bill at a
# multiple of the input rate and cache reads at a fraction of it.
PRICES = {
    "claude-fable-5": (10.0, 50.0),
    "claude-mythos-5": (10.0, 50.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    "claude-opus-4-5": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
CACHE_WRITE_5M = 1.25
CACHE_WRITE_1H = 2.0
CACHE_READ = 0.1


def price(model: str, usage: dict) -> float | None:
    """Cost of one assistant message, matching what the CLI reports."""
    rates = next((v for k, v in PRICES.items() if model.startswith(k)), None)
    if rates is None:
        return None
    p_in, p_out = rates
    t = quota.tally(usage)
    return (
        t["in"] * p_in
        + t["out"] * p_out
        + t["read"] * p_in * CACHE_READ
        + t["w5m"] * p_in * CACHE_WRITE_5M
        + t["w1h"] * p_in * CACHE_WRITE_1H
    ) / 1e6


def main() -> None:
    wins = quota.windows(force=True)
    spend = defaultdict(lambda: defaultdict(float))  # label -> model -> $
    counted = defaultdict(int)
    unpriced = defaultdict(int)

    for when, model, _, usage in quota.scan():
        cost = price(model, usage)
        if cost is None:
            unpriced[model] += 1
            continue
        for label, (start, end, _, scope) in wins.items():
            if start <= when < end and quota.in_scope(model, scope):
                spend[label][model] += cost
                counted[label] += 1

    print(f"{'window':<8} {'scope':<8} {'msgs':>6} {'spend $':>10} "
          f"{'used %':>7} {'$ / 1%':>9} {'$ / 100%':>10}")
    rates = {}
    for label, (_, _, pct, scope) in wins.items():
        total = sum(spend[label].values())
        rate = total / pct if pct else None
        rates[label] = rate
        print(f"{label:<8} {scope or 'all':<8} {counted[label]:>6} {total:>10.2f} "
              f"{pct:>7} " + (f"{rate:>9.3f} {rate * 100:>10.2f}"
                              if rate else f"{'—':>9} {'—':>10}"))

    print("\nspend by model, per window:")
    for label in wins:
        for model, cost in sorted(spend[label].items(), key=lambda kv: -kv[1]):
            print(f"  {label:<5} {model:<24} {cost:>8.2f}")

    if unpriced:
        print("\nunpriced models, skipped — add them to PRICES:")
        for model, n in sorted(unpriced.items(), key=lambda kv: -kv[1]):
            print(f"  {model} ({n} messages)")

    paste = ", ".join(f'"{k}": {v:.2f}' for k, v in rates.items() if v)
    print(f"\nQUOTA_RATE = {{{paste}}}")


if __name__ == "__main__":
    main()
