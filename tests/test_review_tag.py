"""The step calls that let a review make its tag: a check that accepts a
walk that left an item unprinted would tag a review that never did it, and
nothing in a run would show it."""

from pathlib import Path

import pytest

from handbook.checklist import Checklist
from tests.conftest import script

review_tag = script("review_tag")

CHECKLIST = """+ document-size-budget: 1000

# Diff the trees
- Diff them.

# Find the line-level places
- Find them.

# Judge the places
- Judge each defect place.

# Report
- Report.
"""


@pytest.fixture
def checklist(tmp_path: Path) -> Checklist:
    agents = tmp_path / "prompts" / "agents"
    (agents / "code-reviewer").mkdir(parents=True)
    (agents / "code-reviewer.md").write_text("---\nname: code-reviewer\n---\n- R.\n")
    (agents / "code-reviewer" / "checklist.md").write_text(CHECKLIST)
    return Checklist("code-reviewer", tmp_path)


def run(calls: list[tuple[str, str, str]]) -> list[dict]:
    out: list[dict] = []
    for n, (tool, command, result) in enumerate(calls):
        out += [{"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "id": f"t{n}", "name": tool,
                     "input": {"command": command}}]}},
                {"type": "user", "toolUseResult": {"stdout": result}, "message": {"content": [
                    {"type": "tool_result", "tool_use_id": f"t{n}", "content": result}]}}]
    return out


def walk(c: Checklist) -> list[str]:
    return [c.first(), c.after("diff-the-trees"), c.after("find-the-line-level-places")]


STEP = "cd /m && uv run python scripts/step.py code-reviewer"


def test_a_walk_to_the_item_after_lets_the_tag_be_made(checklist: Checklist) -> None:
    calls = [("Bash", STEP, r + "\n\n") for r in walk(checklist)]
    assert review_tag.step_gap(run(calls), checklist, "Find the line-level places") is None


@pytest.mark.parametrize("tool, command", [
    ("Bash", "uv run python scripts/step.py code-editor find-the-line-level-places"),
    ("Bash", STEP + " | cat"),
    ("Bash", STEP + "; echo done"),
    ("Bash", STEP + "; " + STEP),
    ("Bash", "grep -A3 'Judge the places' prompts/agents/code-reviewer/checklist.md"),
    ("Read", "/m/prompts/agents/code-reviewer/checklist.md"),
])
def test_a_result_of_no_step_call_of_the_reviewer_is_refused(
        checklist: Checklist, tool: str, command: str) -> None:
    results = walk(checklist)
    calls = [("Bash", STEP, r) for r in results[:2]] + [(tool, command, results[2])]
    gap = review_tag.step_gap(run(calls), checklist, "Find the line-level places")
    assert gap is not None and gap.item.heading.text == "Judge the places"


def test_an_item_cut_short_is_refused(checklist: Checklist) -> None:
    results = walk(checklist)
    results[1] = results[1].split("\n", 1)[1]
    gap = review_tag.step_gap(run([("Bash", STEP, r) for r in results]), checklist,
                              "Find the line-level places")
    assert gap is not None and gap.item.heading.text == "Find the line-level places"


@pytest.mark.parametrize('command', [
    "python /tmp/step.py code-reviewer",
    "printf '%s' 'uv run python scripts/step.py code-reviewer'",
    "python -c \"print('uv run python scripts/step.py code-reviewer')\"",
    "cat <<'REPORT'\nuv run python scripts/step.py code-reviewer\nREPORT",
])
def test_quoted_step_output_does_not_certify_a_walk(checklist, command):
    assert review_tag.step_gap(run([('Bash', command, '\n'.join(walk(checklist)))]),
                               checklist, 'Find the line-level places') is not None


def test_shell_wrapped_step_supplies_baseline_results(checklist):
    import shlex
    command = '/bin/zsh -lc ' + shlex.quote(STEP)
    assert review_tag.step_gap(run([('Bash', command, '\n'.join(walk(checklist)))]),
                               checklist, 'Find the line-level places') is None
