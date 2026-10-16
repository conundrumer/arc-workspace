"""The kill_note hook: a shell kill comes back with the way to stop a task."""
import json
from pathlib import Path

import pytest

from tests.hookrun import run_hook

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "console" / "kill_note.py"


def hook(payload):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    code, _, err = run_hook(SCRIPT, text)
    return code, err


def bash(command):
    return {"session_id": "s1", "tool_name": "Bash",
            "tool_input": {"command": command}}


@pytest.mark.parametrize("command", ["pkill -f souffle", "killall claude",
                                     "uv run x || pkill -9 -f run_dl"])
def test_a_shell_kill_is_refused_with_the_note(command):
    code, err = hook(bash(command))
    assert code == 2
    assert "TaskStop" in err
    assert 'ToolSearch "select:TaskStop"' in err
