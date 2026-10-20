"""The step command refuses what an agent's checklist does not hold."""

from pathlib import Path

import pytest

from handbook.checklist import Checklist

CHECKLIST = """+ document-size-budget: 1000

# Read the ticket
- Read it.

# Review a split
- Where the change splits a module, enter this part. [Split](prompts/agents/a/split.md)

## Check the split
- Check it.

# Report
- Report.
"""


@pytest.fixture
def root(tmp_path: Path) -> Path:
    agents = tmp_path / "prompts" / "agents"
    (agents / "a").mkdir(parents=True)
    (agents / "a.md").write_text("---\nname: a\n---\n- A.\n")
    (agents / "b.md").write_text("---\nname: b\n---\n- B.\n")
    (agents / "a" / "checklist.md").write_text(CHECKLIST)
    (agents / "a" / "split.md").write_text("# Split\n- How to split.\n")
    return tmp_path


def test_refuses_an_agent_with_no_checklist(root: Path) -> None:
    with pytest.raises(SystemExit):
        Checklist("b", root)


def test_refuses_an_item_the_checklist_does_not_hold(root: Path) -> None:
    with pytest.raises(SystemExit):
        Checklist("a", root).after("nope")


def test_refuses_to_enter_an_item_that_calls_no_part(root: Path) -> None:
    with pytest.raises(SystemExit):
        Checklist("a", root).enter("read-the-ticket")


def test_refuses_to_reenter_an_item_that_calls_no_part(root: Path) -> None:
    with pytest.raises(SystemExit):
        Checklist("a", root).reenter("read-the-ticket")


def test_reenter_prints_the_first_item_without_the_part_file(root: Path) -> None:
    c = Checklist("a", root)
    out = c.reenter("review-a-split")
    assert "Check it." in out
    assert "How to split." not in out
    assert "How to split." in c.enter("review-a-split")


def test_a_later_round_that_reenters_a_part_leaves_no_gap(root: Path) -> None:
    c = Checklist("a", root)
    later = [c.first(), c.after("read-the-ticket"), c.reenter("review-a-split"),
             c.after("check-the-split")]
    assert c.gap([*walk_results(c, True), *later]) is None


def test_a_part_reentered_but_never_entered_leaves_a_gap_to_the_last_item(root: Path) -> None:
    c = Checklist("a", root)
    out = [c.first(), c.after("read-the-ticket"), c.reenter("review-a-split"),
           c.after("check-the-split")]
    gap = c.gap(out)
    assert gap is not None
    assert gap.item.heading.text == "Check the split"
    assert gap.calls == ("uv run python scripts/step.py a --enter review-a-split",
                         "uv run python scripts/step.py a check-the-split")


def test_refuses_a_call_that_links_no_part_file(root: Path) -> None:
    path = root / "prompts" / "agents" / "a" / "checklist.md"
    path.write_text(CHECKLIST.replace(" [Split](prompts/agents/a/split.md)", ""))
    with pytest.raises(SystemExit):
        Checklist("a", root)


def walk_results(c: Checklist, enter: bool) -> list[str]:
    """The results of the step calls of a whole walk, the part entered or
    skipped."""
    out = [c.first(), c.after("read-the-ticket")]
    if enter:
        return [*out, c.enter("review-a-split"), c.after("check-the-split")]
    return [*out, c.after("review-a-split")]


@pytest.mark.parametrize("enter", [True, False])
def test_a_whole_walk_leaves_no_gap(root: Path, enter: bool) -> None:
    c = Checklist("a", root)
    assert c.gap(walk_results(c, enter)) is None


def test_a_gap_gives_the_first_unprinted_item_and_its_call(root: Path) -> None:
    c = Checklist("a", root)
    gap = c.gap([c.first(), c.after("read-the-ticket")])
    assert gap is not None
    assert gap.item.heading.text == "Report"
    assert gap.calls == ("uv run python scripts/step.py a review-a-split",)


def test_an_entered_part_puts_its_items_in_the_walk(root: Path) -> None:
    c = Checklist("a", root)
    gap = c.gap(walk_results(c, True)[:3])
    assert gap is not None
    assert gap.calls == ("uv run python scripts/step.py a check-the-split",)


def test_a_result_cut_short_leaves_its_item_unprinted(root: Path) -> None:
    c = Checklist("a", root)
    results = walk_results(c, False)
    results[0] = results[0].splitlines()[0]
    gap = c.gap(results)
    assert gap is not None
    assert gap.calls == ("uv run python scripts/step.py a",
                         "uv run python scripts/step.py a read-the-ticket")


def test_a_walk_up_to_an_item_ignores_the_rest(root: Path) -> None:
    c = Checklist("a", root)
    assert c.gap([c.first()], "read-the-ticket") is None


def test_a_later_round_that_stops_early_leaves_a_gap(root: Path) -> None:
    c = Checklist("a", root)
    gap = c.gap([*walk_results(c, False), c.after("read-the-ticket")])
    assert gap is not None
    assert gap.item.heading.text == "Report"
    assert gap.calls == ("uv run python scripts/step.py a review-a-split",)


def test_one_result_holds_each_item_it_prints_in_order(root: Path) -> None:
    c = Checklist("a", root)
    assert c.gap(["\n".join(walk_results(c, True))]) is None


def test_an_item_out_of_order_in_one_result_holds_nothing(root: Path) -> None:
    c = Checklist("a", root)
    first, second, *_ = walk_results(c, False)
    gap = c.gap([second + "\n" + first])
    assert gap is not None
    assert gap.item.heading.text == "Review a split"


def test_a_gap_gives_the_calls_through_a_part_call(root: Path) -> None:
    c = Checklist("a", root)
    gap = c.gap([])
    assert gap is not None
    assert gap.command == ("uv run python scripts/step.py a ; "
                           "uv run python scripts/step.py a read-the-ticket")

