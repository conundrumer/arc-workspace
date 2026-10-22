"""The `show` and `wait` commands of the Codex agent script and its refusal to launch over saved history or a busy scratch, without a Codex call."""

import io
import json
from types import SimpleNamespace

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()
agent = script("codex_agent")
reads = script("codex_reads")


@pytest.fixture
def files(tmp_path, monkeypatch):
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "test-session")
    root, home = tmp_path / "repo", tmp_path / "home"
    root.mkdir()
    (root / "CLAUDE.md").write_text("+ lib: none\n- repo instructions\n")
    native = root / "prompts/agents/notes/native-agents.md"
    native.parent.mkdir(parents=True)
    native.write_text("## Native tools\n- Native tools.\n")
    brief = tmp_path / "brief.md"
    brief.write_text("brief body")
    scratch = tmp_path / "scratch"
    monkeypatch.setattr(agent.checkout, "git_out", lambda *_: str(root / ".git"))
    monkeypatch.setattr(agent.checkout, "ROOT", root)
    monkeypatch.setattr(agent.checkout, "main_worktree", lambda _: root)
    monkeypatch.setattr(agent.Path, "home", lambda: home)
    monkeypatch.setattr(agent.sys, "stdin", io.StringIO("first item"))
    return root, home, brief, scratch


def rollout(files, completed=False):
    root, home, brief, scratch = files
    scratch.mkdir()
    (scratch / "codex-session").write_text("thread\n")
    directory = home / ".codex" / "sessions" / "2026" / "10" / "20"
    directory.mkdir(parents=True)
    path = directory / "rollout-now-thread.jsonl"
    payloads = [
        {"type": "task_started", "turn_id": "turn"},
        {
            "type": "token_count",
            "info": {
                "total_token_usage": {"input_tokens": 12, "output_tokens": 3, "total_tokens": 15}
            },
        },
        {
            "type": "item_completed",
            "item": {"type": "CommandExecution", "command": ["false"], "exit_code": 1},
        },
        {
            "type": "item_completed",
            "item": {"type": "AgentMessage", "content": [{"text": "x" * 1000}]},
        },
    ]
    if completed:
        payloads.append({"type": "turn_aborted", "turn_id": "turn"})
    path.write_text(
        "".join(
            json.dumps({"timestamp": "2026-10-20T00:00:00Z", "type": "event_msg", "payload": p})
            + "\n"
            for p in payloads
        )
        + '{"partial'
    )
    return scratch, path


def test_show_reads_live_rollout_with_partial_tail(files, capsys):
    scratch, path = rollout(files)
    before = path.read_bytes()
    assert agent.control(["show", str(scratch)]) == 0
    out = capsys.readouterr().out
    assert "running for" in out and '"total_tokens": 15' in out
    assert "command (exit 1): false" in out and "x" * 1000 not in out
    assert path.read_bytes() == before


@pytest.mark.parametrize("history", ["codex-session", "codex-events.jsonl"])
def test_fresh_launch_refuses_history_without_changing_evidence(files, history, capsys):
    scratch = files[-1]
    scratch.mkdir()
    for name in (history, "codex-last.md", agent.DONE):
        (scratch / name).write_text("saved evidence")
    before = {p.name: p.read_bytes() for p in scratch.iterdir()}
    assert agent.main(["code-reviewer", str(scratch), str(files[2]), "model", "low",
                       "--agent-id", "a123456789abcdef0"]) == 1
    assert "no thread or turn accepted" in capsys.readouterr().err
    assert {p.name: p.read_bytes() for p in scratch.iterdir()} == before


def test_contending_work_preserves_owner_evidence(files):
    import fcntl

    root, home, brief, scratch = files
    scratch.mkdir()
    for name in ('codex-session', 'codex-last.md', agent.DONE, 'codex-events.jsonl'):
        (scratch / name).write_text('owner evidence')
    before = {p.name: p.read_bytes() for p in scratch.iterdir()}
    with (scratch.parent / ('.' + scratch.name + '.codex-work.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match='scratch is busy'):
            agent.run('code-reviewer', scratch, brief, 'model', 'low', 'input',
                      root, home, root, root,
                      agent_id='a123456789abcdef0',
                      transport=lambda: pytest.fail('contender submitted work'))
    assert {p.name: p.read_bytes() for p in scratch.iterdir()} == before


@pytest.mark.parametrize("acquire,release,expected", [
    (None, None, 3), (0, 0.5, 0.5), (1, 2, 2), (0, None, 60),
])
def test_wait_observes_work_lock_without_reading_output(
        tmp_path, monkeypatch, capsys, acquire, release, expected):
    import fcntl

    scratch = tmp_path / "work"
    now = 0.0
    held = False
    with (tmp_path / ".work.codex-work.lock").open("a") as owner:
        def interleave(seconds):
            nonlocal now, held
            now += seconds
            if acquire is not None and now >= acquire and not held:
                fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
                held = True
            if release is not None and now >= release and held:
                fcntl.flock(owner, fcntl.LOCK_UN)
                held = False

        interleave(0)
        monkeypatch.setattr(agent, "time", SimpleNamespace(
            monotonic=lambda: now, sleep=interleave))
        assert agent.main(["wait", str(scratch)]) == 0
        assert now == pytest.approx(expected, abs=0.1)
        assert not scratch.exists()
        assert capsys.readouterr() == ("", "")


def test_wait_is_bounded_while_admission_lock_is_held(tmp_path, monkeypatch, capsys):
    import fcntl

    scratch = tmp_path / "work"
    now = 0.0

    def advance(seconds):
        nonlocal now
        now += seconds

    with (tmp_path / ".work.codex-work.probe.lock").open("a") as admission:
        fcntl.flock(admission, fcntl.LOCK_EX | fcntl.LOCK_NB)
        monkeypatch.setattr(agent, "time", SimpleNamespace(
            monotonic=lambda: now, sleep=advance))
        assert agent.main(["wait", str(scratch)]) == 0
        assert now == pytest.approx(60)
        assert capsys.readouterr() == ("", "")
