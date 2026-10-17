"""The step call that lets a review make its tag: a check that accepts a
call that did not complete the item the tag needs would tag a review that
never did it, and nothing in a run would show it."""

import pytest

from tests.conftest import script

review_tag = script("review_tag")

FOLLOWING = "# Judge the places\n- Judge each defect place.\n"


def run(tool, command, result):
    return [{"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "t1", "name": tool, "input": {"command": command}}]}},
            {"type": "user", "toolUseResult": {"stdout": result}, "message": {"content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": result}]}}]


CODE = [
    ("Bash", "cd /m && uv run python scripts/step.py code-reviewer find-the-line-level-places",
     FOLLOWING + "\n\n", True),
    ("Bash", 'uv run python scripts/step.py code-reviewer "Find the line-level places"',
     FOLLOWING, True),
    ("Bash", "uv run python scripts/step.py code-reviewer find-the-line-level-places",
     "no item named `find-the-line-level-places`; the items are a, b", False),
    ("Bash", "uv run python scripts/step.py code-reviewer judge-the-places", FOLLOWING, False),
    ("Bash", "uv run python scripts/step.py code-editor find-the-line-level-places",
     FOLLOWING, False),
    ("Bash", "grep -A3 'Find the line-level places' prompts/agents/code-reviewer/checklist.md",
     FOLLOWING, False),
    ("Read", "/m/prompts/agents/code-reviewer/checklist.md", FOLLOWING, False),
]
LIB = [
    ("Bash", "uv run python scripts/step.py lib-reviewer find-the-places", FOLLOWING, True),
    ("Bash", "uv run python scripts/step.py code-reviewer find-the-places", FOLLOWING, False),
    ("Bash", "uv run python scripts/step.py lib-reviewer find-the-line-level-places", FOLLOWING, False),
]


@pytest.mark.parametrize("review, tool, command, result, done",
                         [(review_tag.Review.CODE, *c) for c in CODE] + [(review_tag.Review.LIB, *c) for c in LIB])
def test_step_done(review, tool, command, result, done):
    assert review_tag.step_done(run(tool, command, result), review.role, review_tag.ITEMS[review],
                                FOLLOWING) is done
