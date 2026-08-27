"""The kill_note hook: a shell kill comes back with the way to stop a task."""
import json
import subprocess
import sys
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


@pytest.mark.parametrize("command", ["uv run pytest -q", "cat programs/lib.dl",
                                     "ls .scratch", "grep -rn pkilled docs"])
def test_every_other_command_goes_through(command):
    assert hook(bash(command)) == (0, "")


def test_a_call_from_another_tool_goes_through():
    assert hook({"tool_name": "Read",
                 "tool_input": {"file_path": "pkill.md"}}) == (0, "")


def test_an_unreadable_event_goes_through():
    assert hook("not json") == (0, "")


def test_the_script_runs_as_a_hook():
    """The rest of this file drives main() directly; this is the script."""
    p = subprocess.run([sys.executable, str(SCRIPT)],
                       input=json.dumps(bash("pkill -f souffle")),
                       capture_output=True, text=True)
    assert p.returncode == 2
    assert "TaskStop" in p.stderr
