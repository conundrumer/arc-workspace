"""A change whose front matter gives `budget: none` carries no cost budget:
its take gives no dollars and no spend is past it, and the field takes no
other value."""

from pathlib import Path

import pytest

from tests.conftest import script

LOG = ("## Log\n2026-10-17T02:14:06Z draft [ticket-analyst]: filed\n"
       "2026-10-17T02:23:18Z open [ticket-reviewer ab225add95550521a]: reviewed\n"
       "2026-10-17T02:23:56Z assigned [operator aef519b953a4e20ed]: {take}\n")


def change(tmp_path: Path, budget: str, take: str) -> Path:
    path = tmp_path / "assigned" / "9-1_change_x_ticket-analyst.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nkind: change\neditors: code-editor\n{budget}---\n# x: y\n\n"
                    + LOG.format(take=take))
    return path


@pytest.mark.parametrize("take", ["taking: no cost budget",
                                  "taking: budget 2.43 dollars, 1951 s"])
def test_a_change_with_no_cost_budget_is_never_past_it(tmp_path: Path, take: str) -> None:
    script("file_ticket")
    from operations.change_budget import past_budget, taken
    from operations.state import Spend
    t = script("ticket_reads").held_ticket(change(tmp_path, "budget: none\n", take))
    took = taken(t)
    assert took is not None and took.dollars is None
    assert not past_budget(took, Spend(1000.0, 0.0, {}))


def test_a_change_with_a_cost_budget_is_past_it_once_spent(tmp_path: Path) -> None:
    script("file_ticket")
    from operations.change_budget import past_budget, taken
    from operations.state import Spend
    t = script("ticket_reads").held_ticket(
        change(tmp_path, "", "taking: budget 2.43 dollars, 1951 s"))
    took = taken(t)
    assert took is not None and took.dollars == 2.43
    assert past_budget(took, Spend(2.55, 0.0, {}))


def test_budget_takes_no_value_but_none(tmp_path: Path) -> None:
    script("file_ticket")
    form = script("ticket_form")
    text = "---\nkind: change\neditors: code-editor\nbudget: 5\n---\n# x: y\n"
    with pytest.raises(form.Refused, match="`budget` `5` is not `none`"):
        form.checked_kind(tmp_path, "ticket-analyst", text)
