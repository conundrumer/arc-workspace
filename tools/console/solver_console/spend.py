"""What a turn spent: its draw on each rate-limit window, the cache and
context figures the UI reads, and the feed line that carries them."""

import time

from calibrate import CACHE_READ, rates

from . import pacing, store

# Dollars of list-price usage per 1% of each rate-limit window. Nothing
# publishes what a window holds, so these come from measurement: price every
# assistant message in the console home's transcripts that falls inside a
# window at list rates, then divide by that window's utilization from the
# OAuth usage API.
# Re-measure when the plan changes; a stale figure scales every readout.
QUOTA_RATE = {"5h": 4.44, "wk": 19.58, "fbl": 6.91}


def quota_note(it: dict, ev: dict, phase: str) -> str:
    """A turn's quota draw, per window. The result event's figures run over
    the whole session, so the turn is the step since the last landing."""
    total = ev.get("total_cost_usd")
    if not isinstance(total, (int, float)):
        return ""
    # The Fable weekly window counts Fable usage alone, so it gets its own sum.
    fable = sum(u.get("costUSD") or 0
                for m, u in (ev.get("modelUsage") or {}).items()
                if isinstance(u, dict) and pacing.is_fable(m))
    seen = it.setdefault("cost_seen", {}).get(phase) or {"total": 0, "fable": 0}
    if total < seen["total"]:  # a fresh session restarted the running totals
        seen = {"total": 0, "fable": 0}
    d_total, d_fable = total - seen["total"], fable - seen["fable"]
    it["cost_seen"][phase] = {"total": total, "fable": fable}
    parts = [f"5h {d_total / QUOTA_RATE['5h']:.2f}%",
             f"wk {d_total / QUOTA_RATE['wk']:.2f}%"]
    if d_fable:
        parts.append(f"fbl {d_fable / QUOTA_RATE['fbl']:.2f}%")
    return " · " + " · ".join(parts)


def limiting_window(model: str) -> str | None:
    """The window a spend by `model` would hit first: the most-used one among
    those the model draws down."""
    rows = pacing.draws(model)
    if not rows:
        return None
    return max(rows, key=lambda u: u["pct"])["label"]


# What pressing compact costs: one call that reads the session's context and
# writes a summary of it. A working session's context is cached, so the read
# bills at the cache-read fraction; the TTL beside the button is what says
# whether that still holds. The next turn's cache write is that turn's cost,
# not this one's. No compaction has been sampled, so the summary size is a
# stand-in — measure one and correct it here.
COMPACT_SUMMARY = 3_000


def compact_pct(used: int, model: str, limiting: str | None) -> float | None:
    """What compacting a context of `used` tokens would draw from its window."""
    pair = rates(model)
    if pair is None or not limiting:
        return None
    cost = (used * pair[0] * CACHE_READ + COMPACT_SUMMARY * pair[1]) / 1_000_000
    return cost / QUOTA_RATE[limiting]


def out_tokens(ev: dict) -> int:
    """What the model generated this segment. The stream's per-message counts
    are placeholders, and the result event is the first true figure — it
    carries one for a segment the interrupt cut short as well."""
    usage = ev.get("usage") or {}
    if isinstance(usage.get("output_tokens"), int):
        return usage["output_tokens"]
    return sum(x.get("output_tokens") or 0
               for x in (usage.get("iterations") or []) if isinstance(x, dict))


def turn_usage(it: dict, ev: dict, phase: str,
               reqs: list | None = None) -> str:
    """Record the request-level cache and context facts used by the UI.
    `reqs` holds the per-request usage collected from the turn's stream
    events; the result event's iterations carry only the final request."""
    requests = [u for u in (reqs or []) if isinstance(u, dict)]
    if not requests:
        iterations = (ev.get("usage") or {}).get("iterations") or []
        requests = [x for x in iterations if isinstance(x, dict)]

    spent = out_tokens(ev)
    # A segment cut before any request usage arrived still generated tokens.
    if not requests:
        return f"out {spent:,}" if spent else ""

    previous = it.setdefault("cache_read", {}).get(phase)
    drops = []
    for request in requests:
        # a request that carried no input at all never reached the model,
        # so it says nothing about the cache
        if not any(request.get(k) for k in ("input_tokens", "cache_read_input_tokens",
                                             "cache_creation_input_tokens")):
            continue
        cache_read = request.get("cache_read_input_tokens")
        if isinstance(cache_read, (int, float)):
            if isinstance(previous, (int, float)) and cache_read < previous:
                drops.append((previous, cache_read))
            previous = cache_read
    it["cache_read"][phase] = previous
    last = requests[-1]
    cache_read = sum(r.get("cache_read_input_tokens") or 0 for r in requests)
    written = sum(r.get("cache_creation_input_tokens") or 0 for r in requests)
    parts = [f"cache r {cache_read:,} w {written:,}"]
    if spent:
        parts.append(f"out {spent:,}")
    if drops:
        before, after = drops[-1]
        parts.append(f"⚠ DROP {before:,}→{after:,}")

    # The final prompt size is the last request's, not the turn's sums.
    used = ((last.get("cache_read_input_tokens") or 0)
            + (last.get("cache_creation_input_tokens") or 0)
            + (last.get("input_tokens") or 0))
    candidates = [(name, usage) for name, usage in (ev.get("modelUsage") or {}).items()
                  if isinstance(usage, dict) and usage.get("contextWindow")]
    if candidates:
        model, model_usage = max(candidates, key=lambda pair:
            (pair[1].get("cacheReadInputTokens") or 0) +
            (pair[1].get("cacheCreationInputTokens") or 0) +
            (pair[1].get("inputTokens") or 0))
        window = model_usage["contextWindow"]
        canonical = model_usage.get("canonicalModel") or model
        limiting = limiting_window(canonical)
        it.setdefault("context", {})[phase] = {
            "used": used, "window": window,
            "percent": used / window * 100,
            "limiting": limiting, "model": canonical,
            "compactPct": compact_pct(used, canonical, limiting),
        }
    return " · ".join(parts)


def think_note(tokens: int, model: str) -> str:
    """Discarded thinking never reaches the CLI's cost accounting, so price
    the estimate at the stage model's output rate. It is measured differently
    from the dollars beside it, so it reads as its own term."""
    pair = rates(model)
    note = f" · lost ~{tokens // 1000}k think"
    if pair is None:
        return note
    cost = tokens * pair[1] / 1_000_000
    return note + f" ≈ {cost / QUOTA_RATE['5h']:.2f}% 5h"


def turn_note(it: dict, ev: dict, phase: str, started: float | None,
              reqs: list | None, lost: int = 0,
              done: bool = True) -> str:
    """One turn segment's draw, for the feed."""
    head = "turn done" if done else "turn cut"
    mins = (time.time() - started) / 60 if started else 0
    note = f"{head} · {mins:.0f}m" if mins >= 1 else f"{head} · <1m"
    # A cut result carries no cost figure. Reading one anyway would reset the
    # session baseline to zero and bill the whole session to the next landing;
    # leaving it be lets that landing's step cover this segment too.
    if ev.get("total_cost_usd"):
        note += quota_note(it, ev, phase)
    if lost:
        note += think_note(lost, store.model_of(it, phase))
    usage = turn_usage(it, ev, phase, reqs)
    return note + (" · " + usage if usage else "")
