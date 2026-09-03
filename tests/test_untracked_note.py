"""The untracked_note hook: the committer stages only what git tracks."""
import json
import os
import subprocess
import sys
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


def test_a_check_that_cannot_run_refuses_the_call(repo):
    """A guard that fails open is no guard, so a broken check stops the call."""
    code, err = bash(repo, "git add .", PATH="")
    assert code == 2
    assert "could not check" in err


@pytest.mark.parametrize("command", ["git add new.dl", "git add .", "git add -A",
                                     "git add -- new.dl tracked.dl"])
def test_an_add_that_reaches_an_untracked_file_is_refused(repo, command):
    code, err = bash(repo, command)
    assert code == 2
    assert "new.dl" in err


@pytest.mark.parametrize("command", ["git add tracked.dl", "git add -u", "git add -u ."])
def test_an_add_of_tracked_changes_goes_through(repo, command):
    assert bash(repo, command) == (0, "")


def test_a_checked_add_leaves_the_index_alone(repo):
    """The check runs the add against a copy, so the real index does not move."""
    assert bash(repo, "git add tracked.dl") == (0, "")
    assert run(repo, "diff", "--cached", "--name-only") == ""


def test_a_commit_over_a_staged_untracked_file_is_refused(repo):
    run(repo, "add", "new.dl")
    code, err = bash(repo, "git commit -m 'Add new'")
    assert code == 2
    assert "new.dl" in err
    assert "git restore --staged" in err


def test_a_commit_over_tracked_changes_goes_through(repo):
    run(repo, "add", "tracked.dl")
    assert bash(repo, "git commit -m 'Update tracked'") == (0, "")


@pytest.mark.parametrize("command", ["git add . && git commit -m x",
                                     "git add .&&git commit -m x",
                                     "git add .; git commit -m x",
                                     "ls | xargs git add"])
def test_staging_beside_another_call_is_refused(repo, command):
    """The index the hook reads is the one before a compound command runs."""
    code, err = bash(repo, command)
    assert code == 2
    assert "one git command per Bash call" in err


@pytest.mark.parametrize("command", ["git -C . add .", "git --git-dir=.git add ."])
def test_an_add_that_moves_the_repo_is_refused(repo, command):
    code, err = bash(repo, command)
    assert code == 2
    assert "from the repo root" in err


def test_a_message_carrying_an_operator_goes_through(repo):
    run(repo, "add", "tracked.dl")
    assert bash(repo, "git commit -m 'Update tracked; keep the rest'") == (0, "")


def test_a_message_built_by_the_shell_goes_through(repo):
    """The committer writes its messages this way, and it stages nothing."""
    run(repo, "add", "tracked.dl")
    command = "git commit -m \"$(cat <<'EOF'\nUpdate tracked\nEOF\n)\""
    assert bash(repo, command) == (0, "")


@pytest.mark.parametrize("command", ["git status --porcelain", "git log --oneline",
                                     "git diff --stat", "git restore --staged new.dl"])
def test_a_call_that_stages_nothing_goes_through(repo, command):
    assert bash(repo, command) == (0, "")


def test_a_call_from_another_tool_goes_through(repo):
    assert hook(repo, {"tool_name": "Read",
                       "tool_input": {"file_path": "new.dl"}}) == (0, "")


def test_an_unreadable_event_goes_through(repo):
    assert hook(repo, "not json") == (0, "")


def test_the_script_runs_as_a_hook(repo):
    """The rest of this file drives main() directly; this is the script."""
    p = subprocess.run([sys.executable, str(SCRIPT)],
                       input=json.dumps({"tool_name": "Bash",
                                         "tool_input": {"command": "git add ."}}),
                       cwd=repo, env=clean_env(repo),
                       capture_output=True, text=True)
    assert p.returncode == 2
    assert "new.dl" in p.stderr
