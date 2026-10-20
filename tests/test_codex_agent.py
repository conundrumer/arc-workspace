"""The Codex prompt, invocation and failed-turn handling, with no CLI run."""

import json
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
                        "-c", 'approval_policy="never"', "--add-dir", str(root / "tickets"),
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
