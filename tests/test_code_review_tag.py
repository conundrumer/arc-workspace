"""The read of the second stage that lets a code review make its tag: a
read that accepts a call that did not give the whole stage would tag a
review that never read it, and nothing in a run would show it."""

import pytest

from tests.conftest import script

code_review_tag = script("code_review_tag")

NAME = "stage/next.md"
STAGE = "# Code reviewer: second stage\n- a step\n- another step\n"


def run(tool, command, result):
    return [{"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "t1", "name": tool, "input": {"command": command}}]}},
            {"type": "user", "toolUseResult": {"stdout": result}, "message": {"content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": result}]}}]


@pytest.mark.parametrize("tool, command, result, read", [
    ("Bash", f'ls; cat "/m/{NAME}"', "x\n" + STAGE + "\n\n", True),
    ("Bash", f"head -1 /m/{NAME}", STAGE.splitlines()[0], False),
    ("Bash", "cat prompts/agents/code-reviewer-next.md", STAGE, False),
    ("Bash", f"cat tickets/open/t.md  # {NAME}", "quoted: " + STAGE[:40], False),
    ("Read", f"/m/{NAME}", STAGE, False),
])
def test_read_whole(tool, command, result, read):
    assert code_review_tag.read_whole(run(tool, command, result), NAME, STAGE) is read
