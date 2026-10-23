"""`detaches`, which tells a Bash command that leaves a process running past
the call, and the check that denies such a call."""

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()

detached_bash_hook = script("detached_bash_hook")
from operations.command_words import detaches  # noqa: E402


@pytest.mark.parametrize("command", [
    "a &",
    "a | nohup b",
    "a >/dev/null 2>&1 &",
    "(uv run python scripts/agent_timer.py start keep-alive x >/dev/null 2>&1 &); true",
    "nohup a > out 2>&1",
    "setsid a",
    'echo hi > "" ; nohup sleep 100',
    "x; disown",
    "wait & b",
])
def test_detaches(command: str) -> None:
    assert detaches(command)


@pytest.mark.parametrize("command", [
    "a && b",
    "a &> f",
    "a >&2",
    "a 2>&1",
    "a |& b",
    "a & wait",
    "a & b && wait",
    "a &\nb\nwait",
    "echo nohup",
    "grep 'a &' f",
    "grep '&' f",
    'grep "&" f',
    'echo "&"',
    'echo "|" nohup x',
    "cat <<E\na &\nE\n",
    "a 'unbalanced &",
])
def test_does_not_detach(command: str) -> None:
    assert not detaches(command)


def test_check() -> None:
    def call(tool: str, command: str, **inp) -> dict:
        return {"tool_name": tool, "tool_input": {"command": command, **inp}}

    reason = detached_bash_hook.check(call("Bash", "nohup a &", run_in_background=True))
    assert reason is not None and "run_in_background" in reason
    assert detached_bash_hook.check(call("Bash", "a &")) is not None
    assert detached_bash_hook.check(call("Bash", "a", run_in_background=True)) is None
    assert detached_bash_hook.check(call("Monitor", "a &")) is None
