"""The step command refuses what an agent's checklist does not hold."""

from pathlib import Path

import pytest

from handbook.checklist import Checklist

CHECKLIST = """+ budget: 1000

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


def test_refuses_a_call_that_links_no_part_file(root: Path) -> None:
    path = root / "prompts" / "agents" / "a" / "checklist.md"
    path.write_text(CHECKLIST.replace(" [Split](prompts/agents/a/split.md)", ""))
    with pytest.raises(SystemExit):
        Checklist("a", root)
