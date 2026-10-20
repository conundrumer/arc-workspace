"""The Codex prompt, invocation and failed-turn handling, with no CLI run."""

import json
import io
import subprocess
from pathlib import Path

import pytest

from tests.conftest import script

agent = script("codex_agent")


@pytest.fixture
def files(tmp_path: Path):
    root, home = tmp_path / "repo", tmp_path / "home"
    docs = root / ".claude" / "agents"
    docs.mkdir(parents=True)
    (docs / "code-editor.md").write_text("---\nmodel: opus\n---\nagent body")
    (root / "CLAUDE.md").write_text("repo instructions")
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "CLAUDE.md").write_text("user instructions")
    brief = tmp_path / "brief.md"
    brief.write_text("brief body")
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True, env={})
    return root, home, brief, tmp_path / "scratch"


def test_start_then_resume(files):
    root, home, brief, scratch = files
    calls = []

    def runner(argv):
        calls.append(argv)
        Path(argv[argv.index("-o") + 1]).write_text("done")
        return subprocess.CompletedProcess(argv, 0, '{"type":"thread.started","thread_id":"t1"}\n', "")

    def run(item):
        return agent.run("code-editor", scratch, brief, "gpt-6-astra", "high", item,
                         root, home, root, root, runner)

    assert run("first item") == "done"
    assert (scratch / "codex-session").read_text().strip() == "t1"
    argv = calls[0]
    assert argv[:-1] == ["codex", "exec", "-m", "gpt-6-astra", "-c", 'model_reasoning_effort="high"',
                        "-c", "project_doc_max_bytes=0", "-s", "workspace-write",
                        "-c", "sandbox_workspace_write.network_access=true",
                        "-c", 'approval_policy="never"', "--add-dir", str(root / "tickets"),
                        "--add-dir", str(root / ".git"), "--add-dir", str(root / ".cache"),
                        "--add-dir", str(home / ".cache" / "uv"), "--add-dir", str(home / ".cargo"),
                        "--add-dir", str(scratch), "--skip-git-repo-check", "-C", str(root),
                        "-o", str(scratch / "codex-last.md"), "--json"]
    assert argv[-1] == "\n\n".join([agent.PREAMBLE, "agent body", "repo instructions",
                                    "user instructions", "brief body", "first item"])
    brief.unlink()
    assert run("later result") == "done"
    assert calls[1] == [*argv[:-1], "resume", "t1", "later result"]


def test_no_user_document(files):
    root, home, brief, _ = files
    (home / ".claude" / "CLAUDE.md").unlink()
    assert agent.first_prompt(root, home, "code-editor", brief, "item").endswith(
        "repo instructions\n\nbrief body\n\nitem")


def test_worktree_git_dir_is_writable(files):
    root, home, brief, scratch = files
    subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c",
                    "user.email=test@example.com", "-c", "commit.gpgsign=false",
                    "commit", "--allow-empty", "-m", "initial"],
                   check=True, capture_output=True, env={})
    worktree = root.parent / "worktree"
    subprocess.run(["git", "-C", str(root), "worktree", "add", "--detach", str(worktree)],
                   check=True, capture_output=True, env={})
    git_dir = root / ".git" / "worktrees" / worktree.name
    calls = []

    def runner(argv):
        calls.append(argv)
        Path(argv[argv.index("-o") + 1]).write_text("done")
        return subprocess.CompletedProcess(argv, 0, '{"thread_id":"t1"}', "")

    assert agent.run("code-editor", scratch, brief, "gpt-6.1-sol", "high", "item",
                     root, home, root, worktree, runner) == "done"
    argv = calls[0]
    writable = [argv[i + 1] for i, arg in enumerate(argv) if arg == "--add-dir"]
    assert str(root / ".git") in writable
    assert str(git_dir) in writable
    assert argv[argv.index("-C") + 1] == str(worktree)


@pytest.mark.parametrize("explicit", [False, True])
def test_cwd(files, monkeypatch, explicit):
    root, home, brief, scratch = files
    worktree = root / ".claude" / "worktrees" / "change"
    worktree.mkdir(parents=True)
    monkeypatch.chdir(root)
    monkeypatch.setattr(agent.checkout, "ROOT", root)
    monkeypatch.setattr(agent.checkout, "main_worktree", lambda _: root)
    monkeypatch.setattr(agent.Path, "home", lambda: home)
    monkeypatch.setattr(agent.sys, "stdin", io.StringIO("item"))
    calls = []

    def runner(argv):
        calls.append(argv)
        Path(argv[argv.index("-o") + 1]).write_text("done")
        return subprocess.CompletedProcess(argv, 0, '{"thread_id":"t1"}', "")

    subprocess_run = subprocess.run
    monkeypatch.setattr(agent.subprocess, "run", lambda argv, **kwargs:
                        runner(argv) if argv[0] == "codex" else subprocess_run(argv, **kwargs))
    args = ["code-editor", str(scratch), str(brief), "gpt-6.1-sol", "high"]
    assert agent.main([*args, *(["--cwd", str(worktree)] if explicit else [])]) == 0
    assert (scratch / agent.DONE).exists()
    argv = calls[0]
    assert argv[argv.index("-C") + 1] == str(worktree if explicit else root)
    assert argv[-1] == "\n\n".join([agent.PREAMBLE, "agent body", "repo instructions",
                                    "user instructions", "brief body", "item"])


def test_cli_stdin_is_closed(monkeypatch):
    def runner(argv, *, stdin, capture_output, text):
        assert stdin == subprocess.DEVNULL
        assert capture_output and text
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(agent.subprocess, "run", runner)
    assert agent.execute(["codex", "exec", "prompt"]).returncode == 0


@pytest.mark.parametrize("code,event,message", [
    (1, {}, ""), (0, {"type": "turn.failed", "error": {"message": "usage limit reached"}}, "partial"),
    (0, {"type": "error", "message": "usage limit reached"}, "partial"), (0, {}, "")])
def test_failure_does_not_return_stale_message(files, code, event, message):
    root, home, brief, scratch = files
    scratch.mkdir()
    (scratch / "codex-last.md").write_text("stale success")

    def runner(argv):
        if message:
            (scratch / "codex-last.md").write_text(message)
        stream = json.dumps({"type": "thread.started", "thread_id": "failed-thread"})
        return subprocess.CompletedProcess(argv, code, stream + "\n" + json.dumps(event), "CLI error")

    with pytest.raises(ValueError, match="CLI error"):
        agent.run("code-editor", scratch, brief, "gpt-6-astra", "medium", "item",
                  root, home, root, root, runner)
    assert (scratch / "codex-session").read_text().strip() == "failed-thread"
