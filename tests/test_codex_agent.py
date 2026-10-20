"""Daemon refusals, interrupted turns and walk evidence, without a Codex call."""

import io
import json
import subprocess
from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from tests.codex_run import turn
from tests.conftest import script

scripts_importable()
agent = script("codex_agent")
reads = script("codex_reads")


class Transport:
    def __init__(self, status="completed", refuse=None, ignored=None, disconnect=False):
        self.calls = []
        self.events = []
        self.closed = False
        self.status = status
        self.refuse = refuse
        self.ignored = ignored
        self.disconnect = disconnect

    def call(self, method, params):
        self.calls.append((method, params))
        if method == self.refuse:
            raise agent.codex_daemon.Refused("already has an active writer")
        if method in ("thread/start", "thread/resume"):
            result = {
                "thread": {"id": "thread"},
                "model": params["model"],
                "cwd": params["cwd"],
                "approvalPolicy": params["approvalPolicy"],
                "reasoningEffort": params["config"]["model_reasoning_effort"],
                "instructionSources": [],
                "activePermissionProfile": {"id": params["permissions"], "extends": ":workspace"},
                "sandbox": {
                    "type": "workspaceWrite",
                    "networkAccess": params["config"]["permissions"]["project"]["network"]["enabled"],
                    "writableRoots": [k for k, v in
                                      params["config"]["permissions"]["project"]["filesystem"].items()
                                      if v == "write"],
                },
            }
            if self.ignored:
                target, key = self.ignored
                if key == "codexGrant":
                    result["sandbox"]["writableRoots"].remove(str(Path(params["cwd"]) / ".codex"))
                else:
                    (result["sandbox"] if target == "sandbox" else result)[key] = None
            return result
        if method == "thread/read":
            return {"thread": {"turns": [{"id": "turn", "status": "inProgress"}]}}
        if method == "turn/start":
            self.events = [
                self.event_item({"type": "userMessage", "content": params["input"]}),
                self.event_item(
                    {
                        "type": "commandExecution",
                        "command": "uv run python scripts/step.py code-reviewer",
                        "aggregatedOutput": "first item",
                        "exitCode": 0,
                        "status": "completed",
                    }
                ),
                self.event_item(
                    {"type": "userMessage", "content": [{"type": "text", "text": "change course"}]}
                ),
                self.event_item({"type": "agentMessage", "text": "reply", "phase": "final_answer"}),
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "thread",
                        "turn": {"id": "turn", "status": self.status, "error": None},
                    },
                },
            ]
            return {"turn": {"id": "turn"}}
        return {}

    @staticmethod
    def event_item(item):
        return {
            "method": "item/completed",
            "params": {"threadId": "thread", "turnId": "turn", "item": item},
        }

    def event(self):
        if self.disconnect:
            raise OSError("lost connection")
        return self.events.pop(0)

    def close(self):
        self.closed = True


@pytest.fixture
def files(tmp_path, monkeypatch):
    monkeypatch.delenv("CODEX_HOME", raising=False)
    root, home = tmp_path / "repo", tmp_path / "home"
    root.mkdir()
    (root / "CLAUDE.md").write_text("repo instructions")
    brief = tmp_path / "brief.md"
    brief.write_text("brief body")
    scratch = tmp_path / "scratch"
    monkeypatch.setattr(agent.checkout, "git_out", lambda *_: str(root / ".git"))
    monkeypatch.setattr(agent.checkout, "ROOT", root)
    monkeypatch.setattr(agent.checkout, "main_worktree", lambda _: root)
    monkeypatch.setattr(agent.Path, "home", lambda: home)
    monkeypatch.setattr(agent.sys, "stdin", io.StringIO("first item"))
    return root, home, brief, scratch


def run(files, transport, runner=None):
    root, home, brief, scratch = files

    def no_exec(_):
        pytest.fail("work was replayed through exec")

    return agent.run(
        "code-reviewer",
        scratch,
        brief,
        "gpt-6.1-sol",
        "low",
        "first item",
        root,
        home,
        root,
        root,
        runner or no_exec,
        agent_type="general-purpose",
        transport=lambda: transport,
    )


def test_start_resume_and_walk_record(files):
    root, home, brief, scratch = files
    transport = Transport()
    assert run(files, transport) == "reply"
    assert transport.closed
    assert (scratch / "codex-session").read_text() == "thread\n"
    first = transport.calls[1][1]["input"][0]["text"]
    assert first == "brief body\n\nfirst item"
    assert transport.calls[0][1]["config"]["developer_instructions"] == "\n\n".join(
        [agent.PREAMBLE, "repo instructions"]
    )
    # Supply the real walk reader with the record emitted by the daemon path.
    entry = turn(scratch.parent / "launcher", [])
    entry["message"]["content"][0]["input"]["command"] = (
        f"uv run python scripts/codex_agent.py code-reviewer {scratch} /tmp/b model low"
    )
    evidence = reads.walk_entries([entry], "code-reviewer")
    assert evidence[2]["message"]["content"][0]["content"] == "first item"
    assert evidence[3]["message"]["content"] == "change course"
    brief.unlink()
    transport = Transport()
    assert run(files, transport) == "reply"
    assert transport.calls[0][0] == "thread/resume"
    assert transport.calls[0][1]["threadId"] == "thread"
    assert "developer_instructions" not in transport.calls[0][1]["config"]
    assert transport.calls[1][1]["input"][0]["text"] == "first item"


@pytest.mark.parametrize("refuse", ["thread/start", "thread/resume", "turn/start"])
def test_refusal_falls_back_and_keeps_walk_record(files, refuse, capsys):
    root, home, brief, scratch = files
    scratch.mkdir()
    if refuse == "thread/resume":
        (scratch / "codex-session").write_text("thread\n")
    calls = []

    def runner(argv):
        calls.append(argv)
        Path(argv[argv.index("-o") + 1]).write_text("exec reply")
        return subprocess.CompletedProcess(
            argv, 0, '{"type":"thread.started","thread_id":"thread"}\n{"type":"turn.completed"}', ""
        )

    transport = Transport(refuse=refuse)
    assert run(files, transport, runner) == "exec reply"
    assert transport.closed
    assert "falling back to codex exec" in capsys.readouterr().err
    assert ("resume" in calls[0]) == (refuse == "thread/resume")
    overrides = [arg for arg in calls[0] if arg.startswith("developer_instructions=")]
    if refuse == "thread/resume":
        assert not overrides
        assert calls[0][-1] == "first item"
    else:
        assert json.loads(overrides[0].split("=", 1)[1]) == "\n\n".join(
            [agent.PREAMBLE, "repo instructions"]
        )
        assert calls[0][-1] == "brief body\n\nfirst item"
    record = json.loads((scratch / "codex-events.jsonl").read_text())
    assert record["ok"] is True and record["input"] == "first item"
    assert json.loads(record["output"].splitlines()[-1])["type"] == "turn.completed"


@pytest.mark.parametrize(
    "ignored",
    [
        ("", "model"),
        ("", "cwd"),
        ("", "approvalPolicy"),
        ("", "reasoningEffort"),
        ("", "instructionSources"),
        ("", "activePermissionProfile"),
        ("sandbox", "codexGrant"),
        ("sandbox", "networkAccess"),
        ("sandbox", "writableRoots"),
        ("sandbox", "type"),
    ],
)
def test_silently_ignored_options_refuse_work(files, ignored):
    transport = Transport(ignored=ignored)
    scratch = files[-1]
    scratch.mkdir()
    assert (
        agent.daemon_turn(
            scratch,
            None,
            "prompt",
            "input",
            files[0],
            "gpt-6.1-sol",
            "low",
            [scratch],
            lambda: transport,
        )
        is None
    )
    assert [m for m, _ in transport.calls] == ["thread/start"]
    assert not (scratch / "codex-events.jsonl").exists()


@pytest.mark.parametrize("status", ["failed", "interrupted"])
def test_failed_turn_prints_reply_and_exits_nonzero(files, monkeypatch, status, capsys):
    root, home, brief, scratch = files
    transport = Transport(status=status)
    real_run = agent.run
    monkeypatch.setattr(
        agent, "run", lambda *a, **kw: real_run(*a, **kw, transport=lambda: transport)
    )
    assert (
        agent.main(
            [
                "code-reviewer",
                str(scratch),
                str(brief),
                "gpt-6.1-sol",
                "low",
                "--agent-type",
                "general-purpose",
                "--cwd",
                str(root),
            ]
        )
        == 1
    )
    assert capsys.readouterr().out == "reply\n"
    assert (scratch / agent.DONE).exists()
    assert json.loads((scratch / "codex-events.jsonl").read_text())["ok"] is False
    assert transport.closed


def test_disconnect_after_submission_never_replays(files):
    transport = Transport(disconnect=True)
    with pytest.raises(ValueError, match="not replayed"):
        run(files, transport)
    assert transport.closed
    scratch = files[-1]
    assert (scratch / "codex-session").read_text() == "thread\n"
    assert json.loads((scratch / "codex-events.jsonl").read_text())["ok"] is False


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


@pytest.mark.parametrize("action", ["steer", "interrupt"])
@pytest.mark.parametrize("completed", [False, True])
def test_controls_only_target_running_turn(files, capsys, action, completed):
    scratch, _ = rollout(files, completed)
    transport = Transport()
    assert (
        agent.control(
            [action, str(scratch), *(["new direction"] if action == "steer" else [])],
            lambda: transport,
        )
        == 0
    )
    out = capsys.readouterr().out
    if completed:
        assert "no turn running" in out and not transport.calls
    else:
        method, params = transport.calls[0]
        assert method == "turn/" + action and params["threadId"] == "thread"
        assert params["expectedTurnId" if action == "steer" else "turnId"] == "turn"
        if action == "steer":
            assert params["input"] == [{"type": "text", "text": "new direction"}]
        assert transport.closed


def test_unavailable_daemon_falls_back(files, capsys):
    scratch = files[-1]
    scratch.mkdir()

    def unavailable():
        raise OSError("no socket")

    assert (
        agent.daemon_turn(
            scratch, None, "prompt", "input", files[0], "gpt-6.1-sol", "low", [scratch], unavailable
        )
        is None
    )
    assert "falling back to codex exec" in capsys.readouterr().err


def test_completed_turn_race_reports_no_running_turn(files, capsys):
    scratch, _ = rollout(files)
    transport = Transport()

    def call(method, params):
        if method == "turn/interrupt":
            raise agent.codex_daemon.Refused("turn ended")
        return {"thread": {"turns": []}}

    transport.call = call
    assert agent.control(["interrupt", str(scratch)], lambda: transport) == 0
    assert "no turn running" in capsys.readouterr().out
    assert transport.closed


@pytest.mark.parametrize("action", ["show", "steer", "interrupt"])
def test_no_saved_session_reports_no_turn(files, capsys, action):
    transport = Transport()
    assert (
        agent.control(
            [action, str(files[-1]), *(["message"] if action == "steer" else [])], lambda: transport
        )
        == 0
    )
    assert "no turn running" in capsys.readouterr().out
    assert not transport.calls


def test_interrupt_without_final_answer_prints_last_commentary(files):
    transport = Transport(status="interrupted")
    original_call = transport.call

    def call(method, params):
        result = original_call(method, params)
        if method == "turn/start":
            for event in transport.events:
                item = event.get("params", {}).get("item", {})
                if item.get("type") == "agentMessage":
                    item["phase"] = "commentary"
        return result

    transport.call = call
    with pytest.raises(agent.TurnFailed) as failed:
        run(files, transport)
    assert failed.value.message == "reply"
    assert transport.closed


@pytest.mark.parametrize(
    "completed_output,chunks,expected",
    [
        ({"aggregatedOutput": None}, ["first ", "item"], "first item"),
        ({"aggregatedOutput": None}, [], ""),
        ({}, ["first ", "item"], "first item"),
        ({}, [], ""),
        ({"aggregatedOutput": ""}, ["partial"], ""),
        ({"aggregatedOutput": "complete"}, ["partial"], "complete"),
    ],
)
def test_absent_command_output_keeps_walk_evidence(files, completed_output, chunks, expected):
    scratch = files[-1]
    transport = Transport()
    original_call = transport.call

    def call(method, params):
        result = original_call(method, params)
        if method == "turn/start":
            command = transport.events[1]["params"]["item"]
            command["id"] = "command"
            del command["aggregatedOutput"]
            command.update(completed_output)

            def delta(text, **overrides):
                return {
                    "method": "item/commandExecution/outputDelta",
                    "params": {
                        "threadId": "thread",
                        "turnId": "turn",
                        "itemId": "command",
                        "delta": text,
                        **overrides,
                    },
                }

            transport.events[:0] = [
                delta("other thread", threadId="other"),
                delta("other turn", turnId="other"),
                delta("other command", itemId="other"),
                *[delta(chunk) for chunk in chunks],
            ]
        return result

    transport.call = call
    assert run(files, transport) == "reply"
    entry = turn(scratch.parent / "launcher", [])
    entry["message"]["content"][0]["input"]["command"] = (
        f"uv run python scripts/codex_agent.py code-reviewer {scratch} /tmp/b model low"
    )
    evidence = reads.walk_entries([entry], "code-reviewer")
    assert evidence[2]["message"]["content"][0]["content"] == expected
