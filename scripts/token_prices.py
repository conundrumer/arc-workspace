"""The list prices of the tokens a request uses, in dollars per million tokens, keyed by the model ids the transcripts give, and the token cost of a run's requests at those prices.

- Source: the bundled claude-api skill. `shared/models.md` gives input, output and cache-read prices; `shared/prompt-caching.md` gives 5-minute cache writes at 1.25x input, 1-hour cache writes at 2x input, and cache reads at 0.1x input where a model's line gives no read price; `python/claude-api/README.md` gives Claude Haiku 4.5.
- A request is the entries of one message id. Its usage is, for each count, the most any of its entries gives, where an entry gives its top-level counts, or the sum over its `iterations` where that sum is larger.
"""

from dataclasses import dataclass, fields
from typing import Any


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


PRICES: dict[str, Usage] = {
    "claude-fable-5-1": price(10, 50, 0.25),
    "claude-opus-5-5": price(4, 20, 0.20),
    "claude-opus-5": price(5, 25, 0.50),
    "claude-sonnet-5-5": price(2, 10, 0.20),
    "claude-haiku-4-5-20251001": price(1, 5, 0.10),
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
        return f"service_tier {usage.get('service_tier')}"
    if usage.get("speed") not in (None, "standard"):
        return f"speed {usage.get('speed')}"
    if any((usage.get("server_tool_use") or {}).values()):
        return "server_tool_use"
    if (usage.get("cache_creation_input_tokens") or 0) and not usage.get("cache_creation"):
        return "cache_creation_input_tokens without cache_creation"
    return None


def run_cost(entries: list[dict[str, Any]], undecided: list[str]) -> float | None:
    """The token cost in dollars of the requests the assistant entries give,
    or None where a request that used tokens has no price, with an
    `undecided` line for it."""
    requests: dict[str, tuple[str, Usage]] = {}
    known = True
    for entry in entries:
        message = entry.get("message") or {}
        usage = message.get("usage")
        if entry.get("type") != "assistant" or not isinstance(usage, dict):
            continue
        got = entry_counts(usage)
        if not got.total():
            continue
        model = message.get("model")
        ident = message.get("id")
        field = unpriced(usage)
        if model not in PRICES or ident is None or field is not None:
            reason = (f"no price for model {model}" if model not in PRICES
                      else "no message id" if ident is None
                      else f"no price for {field} of model {model}")
            undecided.append(f"token cost unknown: {reason}")
            known = False
            continue
        before = requests.get(ident)
        requests[ident] = (model, got if before is None else before[1].most(got))
    if not known:
        return None
    return sum(u.cost(PRICES[m]) for m, u in requests.values())
