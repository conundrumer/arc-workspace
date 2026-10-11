"""The list prices of the tokens a request uses, in dollars per million tokens, keyed by the model ids the transcripts give, and the token cost of a run's requests at those prices.

- Source: Anthropic's pricing page and release notes, https://platform.claude.com/docs/en/release-notes/overview, which carry price changes the bundled claude-api skill lags. 5-minute cache writes are 1.25x input and 1-hour cache writes 2x input.
- A request is the entries of one message id, and an entry with no message id makes the cost unknown. Its usage is, for each count, the most any of its entries gives, where an entry gives its top-level counts, or the sum over its `iterations` where that sum is larger.
"""

from dataclasses import dataclass, fields
from typing import Any

from controlled_markdown import mctx
from transcripts import epoch


@dataclass(frozen=True)
class Usage:
    """Token counts, or prices per million tokens, of each kind a request is billed for."""
    input: float
    write_5m: float
    write_1h: float
    cache_read: float
    output: float

    def most(self, other: "Usage") -> "Usage":
        return Usage(*(max(getattr(self, f.name), getattr(other, f.name))
                       for f in fields(Usage)))

    def total(self) -> float:
        return sum(getattr(self, f.name) for f in fields(Usage))

    def cost(self, price: "Usage") -> float:
        return sum(getattr(self, f.name) * getattr(price, f.name)
                   for f in fields(Usage)) / 1e6


def price(input: float, output: float, cache_read: float) -> Usage:
    return Usage(input, input * 1.25, input * 2, cache_read, output)


@dataclass(frozen=True)
class Price:
    """A model's prices: `base`, and `over` for a request whose input tokens
    (`request_input`) are past `above`, where the model gives a second tier."""
    base: Usage
    above: float | None = None
    over: Usage | None = None

    def at(self, request_input: float) -> Usage:
        if self.above is not None and self.over is not None and request_input > self.above:
            return self.over
        return self.base


PRICES: dict[str, Price] = {
    "claude-fable-5-1": Price(price(10, 50, 0.25)),
    "claude-opus-5-5": Price(price(4, 20, 0.20)),
    "claude-opus-5": Price(price(5, 25, 0.50)),
    "claude-sonnet-5-5": Price(price(2, 10, 0.10)),
    "claude-haiku-5-5": Price(price(0.10, 0.50, 0.01), 100_000, price(0.50, 2.50, 0.05)),
    "claude-haiku-4-5-20251001": Price(price(1, 5, 0.10)),
}


def counts(usage: dict[str, Any]) -> Usage:
    """The token counts one `usage` object, or one of its `iterations`, gives.
    A usage with cache writes and no `cache_creation` split gives them all as
    5-minute writes, and `unpriced` names it."""
    split = usage.get("cache_creation") or {}
    if not split:
        split = {"ephemeral_5m_input_tokens": usage.get("cache_creation_input_tokens")}
    return Usage(usage.get("input_tokens") or 0,
                 split.get("ephemeral_5m_input_tokens") or 0,
                 split.get("ephemeral_1h_input_tokens") or 0,
                 usage.get("cache_read_input_tokens") or 0,
                 usage.get("output_tokens") or 0)


def request_input(usage: dict[str, Any]) -> float:
    """The input tokens of the request a `usage` gives: input, cache writes and
    cache reads, from its last iteration, or from its top level where it has
    no iteration or that iteration gives none."""
    iterations = [i for i in usage.get("iterations") or [] if isinstance(i, dict)]
    for u in [*iterations[-1:], usage]:
        c = counts(u)
        if total := c.input + c.write_5m + c.write_1h + c.cache_read:
            return total
    return 0


def entry_counts(usage: dict[str, Any]) -> Usage:
    top = counts(usage)
    parts = [counts(i) for i in usage.get("iterations") or [] if isinstance(i, dict)]
    summed = Usage(*(sum(getattr(p, f.name) for p in parts) for f in fields(Usage)))
    return summed if summed.total() > top.total() else top


def unpriced(usage: dict[str, Any]) -> str | None:
    """The field of a `usage` that changes its price and that the table does
    not price, or None."""
    if usage.get("service_tier") not in (None, "standard"):
        return mctx("service_tier {tier}").format(tier=usage.get("service_tier"))
    if usage.get("speed") not in (None, "standard"):
        return mctx("speed {speed}").format(speed=usage.get("speed"))
    if any((usage.get("server_tool_use") or {}).values()):
        return mctx("server_tool_use")
    if (usage.get("cache_creation_input_tokens") or 0) and not usage.get("cache_creation"):
        return mctx("cache_creation_input_tokens without cache_creation")
    return None


def model_price(model: Any, undecided: list[str]) -> Price | None:
    """The prices of `model`, or None where the table gives none, with an
    `undecided` line for it."""
    if model not in PRICES:
        undecided.append(mctx("token cost unknown: no price for model {model}").format(model=model))
        return None
    return PRICES[model]


def grouped(entries: list[dict[str, Any]]) -> dict[str | None, list[dict[str, Any]]]:
    """The assistant entries that give a usage, by message id, None for an
    entry with no message id."""
    groups: dict[str | None, list[dict[str, Any]]] = {}
    for e in entries:
        message = e.get("message") or {}
        if e.get("type") == "assistant" and isinstance(message.get("usage"), dict):
            groups.setdefault(message.get("id"), []).append(e)
    return groups


def requests(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The first entry of each group `grouped` gives."""
    return [g[0] for g in grouped(entries).values()]


def priced_requests(entries: list[dict[str, Any]],
                    undecided: list[str]) -> dict[str, list[dict[str, Any]]] | None:
    """The groups `grouped` gives, or None where an entry has no message id,
    with an `undecided` line for it."""
    groups = grouped(entries)
    if None in groups:
        undecided.append(mctx("token cost unknown: no message id"))
        return None
    return {k: v for k, v in groups.items() if k is not None}


def run_cost(entries: list[dict[str, Any]], undecided: list[str],
             at: str | None = None) -> float | None:
    """The token cost in dollars of the requests `priced_requests` gives,
    each at the prices of the model that made it, at the tier of its largest
    `request_input`, or of the model `at` where one is given, or None where a
    request that used tokens has no price, with an `undecided` line for it."""
    groups = priced_requests(entries, undecided)
    if groups is None:
        return None
    total = 0.0
    known = True
    for group in groups.values():
        used: Usage | None = None
        size = 0.0
        table: Price | None = None
        for entry in group:
            message = entry["message"]
            usage = message["usage"]
            got = entry_counts(usage)
            if not got.total():
                continue
            table = model_price(message.get("model") if at is None else at, undecided)
            field = unpriced(usage)
            if field is not None:
                undecided.append(mctx("token cost unknown: no price for {field} of model {model}").format(
                    field=field, model=message.get("model")))
            if table is None or field is not None:
                known = False
                continue
            used = got if used is None else used.most(got)
            size = max(size, request_input(usage))
        if used is not None and table is not None:
            total += used.cost(table.at(size))
    return total if known else None


def span_cost(entries: list[dict[str, Any]], start: float, end: float,
              undecided: list[str]) -> float | None:
    """The token cost in dollars of the span from `start` to `end`, in epoch
    seconds, of a run: its requests in the span, priced as `run_cost`
    prices them, plus the growth of its context across the span, from the
    last request before the span to the first after it, at the cache-read
    price of the run's model once for each request after the span. None
    where `run_cost` gives None, with its `undecided` line."""
    entries = [e for e in entries if e.get("timestamp")]
    inside = [e for e in entries if start <= epoch(e["timestamp"]) <= end]
    cost = run_cost(inside, undecided)
    groups = priced_requests(entries, undecided) if cost is not None else None
    if cost is None or groups is None:
        return None
    firsts = [g[0] for g in groups.values()]
    before = [e for e in firsts if epoch(e["timestamp"]) < start]
    after = [e for e in firsts if epoch(e["timestamp"]) > end]
    if not before or not after:
        return cost
    message = after[0]["message"]
    table = model_price(message.get("model"), undecided)
    if table is None:
        return None
    size = request_input(message["usage"])
    growth = max(0.0, size - request_input(before[-1]["message"]["usage"]))
    return cost + growth * table.at(size).cache_read / 1e6 * len(after)
