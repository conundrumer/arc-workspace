"""The dollar figure of a change's Cost line, which its cost budget is at
least: a misread gives a budget below the change's own estimate, and its
agents are told to end early."""

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

LINE = ("- Cost: one code editor run on about 500 to 700 lines, beside change 9-1638's 400 to "
        "500 lines at $14 to $25: $18 to $30, and the change's overhead of about $7. Gain: "
        "the mask refuses what the language refuses, worth $90.")


def ticket(design: str | None) -> str:
    middle = "" if design is None else f"## Design\n{design}\n\n"
    return f"---\nkind: change\n---\n# x\n\n## Intent\n- a $50 item\n\n{middle}## Log\n"


@pytest.mark.parametrize(("design", "cost"), [
    (LINE, 30.0),
    ("- Cost: one doc editor run, $12.", 12.0),
    ("- Cost: one line of code: about $4. Each review reads 70 more tokens, under $0.001 a run.",
     4.0),
    ("- Gain, against goal 1: a fix. Cost: about $4 to $8, estimated from the size of the edit.",
     8.0),
    ("- Cost: one rebuild of the environment.", None),
    ("- A line with $40 and no cost.", None),
    (None, None),
])
def test_the_cost_line_gives_the_top_of_its_range_without_overhead_or_gain(
        design: str | None, cost: float | None) -> None:
    scripts_importable()
    assert script("ticket_reads").design_cost(ticket(design)) == cost
