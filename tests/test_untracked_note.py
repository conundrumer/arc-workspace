"""The untracked_note hook: the committer stages only what git tracks."""
import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.hookrun import run_hook

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "console" / "untracked_note.py"


def run(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True,
                          capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path):
    """A repo with one tracked file changed and one file git never saw."""
    run(tmp_path, "init", "-q", ".")
    (tmp_path / "tracked.dl").write_text("one\n")
    run(tmp_path, "add", "tracked.dl")
    run(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    (tmp_path / "tracked.dl").write_text("two\n")
    (tmp_path / "new.dl").write_text("new\n")
    return tmp_path


def clean_env(repo, **over):
    """The hook's environment, where the user's git config cannot reach."""
    return {"CLAUDE_PROJECT_DIR": str(repo), "PATH": os.environ["PATH"],
            "HOME": str(repo), "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull, **over}


def hook(repo, payload, **over):
    """One event through the hook."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    code, _, err = run_hook(SCRIPT, text, env=clean_env(repo, **over))
    return code, err


def bash(repo, command, **over):
    return hook(repo, {"tool_name": "Bash", "tool_input": {"command": command}}, **over)


@pytest.mark.parametrize("command", ["git add new.dl", "git add .", "git add -A",
                                     "git add -- new.dl tracked.dl"])
def test_an_add_that_reaches_an_untracked_file_is_refused(repo, command):
    code, err = bash(repo, command)
    assert code == 2
    assert "new.dl" in err


@pytest.mark.parametrize("command", ["git add tracked.dl", "git add -u", "git add -u ."])
def test_an_add_of_tracked_changes_goes_through(repo, command):
    assert bash(repo, command) == (0, "")


def test_a_commit_over_a_staged_untracked_file_is_refused(repo):
    run(repo, "add", "new.dl")
    code, err = bash(repo, "git commit -m 'Add new'")
    assert code == 2
    assert "new.dl" in err
    assert "git restore --staged" in err


def test_a_message_carrying_an_operator_goes_through(repo):
    run(repo, "add", "tracked.dl")
    assert bash(repo, "git commit -m 'Update tracked; keep the rest'") == (0, "")


