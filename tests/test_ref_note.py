"""The ref_note hook: notes on tool calls that touch unratified solvers."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.hookrun import run_hook

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "console" / "ref_note.py"


@pytest.fixture(scope="session")
def fixed_repo(tmp_path_factory):
    """The three solvers every test reads, committed once for the whole run.
    No test writes to the repo; only the state dir varies."""
    root = tmp_path_factory.mktemp("fixed") / "repo"
    solvers = root / "programs" / "solvers"
    solvers.mkdir(parents=True)
    git = ["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*git, "init", "-q"], check=True)
    (solvers / "aaaa1111.dl").write_text("// committed\n")
    (solvers / "bbbb2222.dl").write_text("// committed\n")
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "solvers"], check=True)
    (solvers / "bbbb2222.dl").write_text("// edited\n")
    (solvers / "cccc3333.dl").write_text("// never committed\n")
    return root


@pytest.fixture
def repo(tmp_path, fixed_repo):
    """The shared repo reached through a per-test parent, so each test gets
    its own state dir beside it."""
    root = tmp_path / "repo"
    root.symlink_to(fixed_repo)
    (tmp_path / "state").mkdir()
    return root


def env_for(repo, task=""):
    return {**os.environ, "CONSOLE_ROOT": str(repo),
            "CONSOLE_STATE_DIR": str(repo.parent / "state"),
            "CONSOLE_TASK": task}


def hook(repo, payload, task=""):
    _, out, _ = run_hook(SCRIPT, json.dumps(payload), env_for(repo, task))
    out = out.strip()
    return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""


def grep_of(*ids, session="s1"):
    return {"session_id": session, "tool_name": "Bash",
            "tool_input": {"command": "grep -rn Reach programs/solvers"},
            "tool_response": "\n".join(
                f"programs/solvers/{i}.dl:3:  Reach(x, y)" for i in ids)}


def test_an_uncommitted_solver_gets_the_note(repo):
    note = hook(repo, grep_of("cccc3333"))
    assert note == ("note: cccc3333.dl is not approved — don't use it as "
                    "reference; it still counts as a survey caller.")


def test_a_clean_committed_solver_is_silent(repo):
    assert hook(repo, grep_of("aaaa1111")) == ""


def test_edits_on_a_committed_solver_get_the_soft_note(repo):
    note = hook(repo, grep_of("bbbb2222"))
    assert note == ("note: bbbb2222.dl has uncommitted edits — the committed "
                    "version is the ratified reference.")


def test_an_approved_id_is_silent(repo):
    (repo.parent / "state" / "approved.txt").write_text("cccc3333\n")
    assert hook(repo, grep_of("cccc3333")) == ""


def test_the_workers_own_task_is_exempt(repo):
    assert hook(repo, grep_of("cccc3333"), task="cccc3333") == ""


def test_a_note_lands_once_per_session(repo):
    assert hook(repo, grep_of("cccc3333")) != ""
    assert hook(repo, grep_of("cccc3333")) == ""
    assert hook(repo, grep_of("cccc3333", session="s2")) != ""


def test_the_command_side_is_scanned_too(repo):
    payload = {"session_id": "s1", "tool_name": "Bash",
               "tool_input": {"command": "cat programs/solvers/cccc3333.dl"},
               "tool_response": "// never committed"}
    assert "not approved" in hook(repo, payload)


def test_notes_cover_each_id_once(repo):
    note = hook(repo, grep_of("bbbb2222", "cccc3333", "aaaa1111"))
    assert note.count("note:") == 2
    assert "cccc3333.dl is not approved" in note
    assert "bbbb2222.dl has uncommitted edits" in note


def test_the_script_runs_as_a_hook(repo):
    """The rest of this file drives main() directly; this is the script."""
    p = subprocess.run([sys.executable, str(SCRIPT)],
                       input=json.dumps(grep_of("cccc3333")),
                       capture_output=True, text=True, env=env_for(repo), check=True)
    assert "not approved" in p.stdout
