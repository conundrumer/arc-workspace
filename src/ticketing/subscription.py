"""The subscription plans and the conversion of usage to subscription dollars: a cost is the share of a plan's weekly usage window that work uses, times the plan's price per week. `scripts/token_prices.py` prices Claude requests through these constants and `codex_cost` prices Codex turns.

- The plans: Claude $200 and Codex $100 a month (request 11-3127, Grounds), each limited by a weekly usage window. A plan's price per week is its price per month times 12/52.
- Claude's window weighs tokens by their list prices, which `scripts/token_prices.py` holds.
"""

from math import floor, log10
from typing import TYPE_CHECKING

from controlled_markdown import mctx

if TYPE_CHECKING:
    from operations.codex_spend import CodexUsage

CLAUDE_WEEK_PRICE = 200 * 12 / 52
"""The Claude plan's price per week, in dollars: $200 a month."""

CODEX_WEEK_PRICE = 100 * 12 / 52
"""The Codex plan's price per week, in dollars: $100 a month."""

CLAUDE_WEEK_LIST = 2100.0
"""The Claude weekly usage window at list prices, in dollars: 483 transcripts
of the window since 2026-10-21T23:59:59Z, priced at `token_prices.PRICES`,
sum to $148.88 at `seven_day.used_pct` 7, a range of about $1,985 to $2,290
for 6.5% to 7.5% (the coordinator's check of 2026-10-22). The figure rests on
one whole-percent reading, so a later reading near 50% to 100% used refines
it in this one constant. Such a refinement rescales by the ratio of the old
to the new value the subscription-dollar figures that log lines hold: case
and budget lines of tickets outside `tickets/closed/`. Spend records hold
list-price Claude costs and need no rewrite."""

CLAUDE_LIST_TO_SUBSCRIPTION = CLAUDE_WEEK_PRICE / CLAUDE_WEEK_LIST
"""The subscription dollars of one dollar of Claude list-price cost."""

CODEX_WEEK_CREDITS = 6200
"""The credits of the Codex weekly usage window (request 11-3127, Grounds,
2026-10-22T13:35:43Z)."""

CODEX_CREDITS: dict[str, tuple[float, float, float]] = {
    "gpt-6.1-sol": (50, 2.5, 250),
    "gpt-6-luna": (2.5, 0.25, 12.5),
}
"""The credits per million tokens of a Codex model: fresh input, cached input
and output (request 11-3127, Grounds, 2026-10-22T13:35:43Z). The rates and the
window's credits fit 874 rollouts to within about 1 point of the window
percent."""


def codex_cost(usage: "CodexUsage", model: str | None, undecided: list[str]) -> float | None:
    """The subscription dollars of one Codex turn's `usage` at the rates of
    `model`, or None, with an `undecided` line, where the table lacks the
    model or a count is unknown. Cached input is included in input and
    reasoning output in output."""
    if model not in CODEX_CREDITS:
        undecided.append(mctx("Codex cost unknown: no credit rates for model {model}").format(
            model=model))
        return None
    if usage.input_tokens is None or usage.cached_input_tokens is None \
            or usage.output_tokens is None:
        undecided.append(mctx("Codex cost unknown: token counts unknown"))
        return None
    fresh, cached, output = CODEX_CREDITS[model]
    credits = ((usage.input_tokens - usage.cached_input_tokens) * fresh
               + usage.cached_input_tokens * cached + usage.output_tokens * output) / 1e6
    return credits * CODEX_WEEK_PRICE / CODEX_WEEK_CREDITS


def figure(dollars: float) -> str:
    """`dollars` written with two places or, below 10, at least three
    significant digits, with no exponent, so that a small figure stays
    readable."""
    places = max(2, 2 - floor(log10(dollars))) if dollars > 0 else 2
    return f"{dollars:.{places}f}"
