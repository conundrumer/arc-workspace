"""The step call that lets a code review make its tag: a check that
accepts a call that did not complete the line-level step would tag a
review that never did it, and nothing in a run would show it."""

import pytest

from tests.conftest import script

code_review_tag = script("code_review_tag")

ITEM = "Find the line-level places"
FOLLOWING = "# Judge the places\n- Judge each defect place.\n"
CHECKLIST = "prompts/agents/code-reviewer/checklist.md"


def run(tool, command, result):
    return [{"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "t1", "name": tool, "input": {"command": command}}]}},
            {"type": "user", "toolUseResult": {"stdout": result}, "message": {"content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": result}]}}]


@pytest.mark.parametrize("tool, command, result, done", [
    ("Bash", "cd /m && uv run python scripts/step.py code-reviewer find-the-line-level-places",
     FOLLOWING + "\n\n", True),
    ("Bash", 'uv run python scripts/step.py code-reviewer "Find the line-level places"',
     FOLLOWING, True),
    ("Bash", "uv run python scripts/step.py code-reviewer find-the-line-level-places",
     "no item named `find-the-line-level-places`; the items are a, b", False),
    ("Bash", "uv run python scripts/step.py code-reviewer judge-the-places", FOLLOWING, False),
    ("Bash", "uv run python scripts/step.py code-editor find-the-line-level-places",
     FOLLOWING, False),
    ("Bash", f"grep -A3 'Find the line-level places' {CHECKLIST}", FOLLOWING, False),
    ("Read", f"/m/{CHECKLIST}", FOLLOWING, False),
])
def test_step_done(tool, command, result, done):
    assert code_review_tag.step_done(run(tool, command, result), code_review_tag.Role.CODE_REVIEWER, ITEM, FOLLOWING) is done

