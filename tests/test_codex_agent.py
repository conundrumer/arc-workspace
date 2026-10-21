"""Daemon refusals, interrupted turns and walk evidence, without a Codex call."""

import io
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from handbook.paths import scripts_importable
from tests.codex_run import turn
from tests.conftest import script

scripts_importable()
agent = script("codex_agent")
reads = script("codex_reads")


class Transport:
    def __init__(self, status="completed", refuse=None, ignored=None, disconnect=False,
                 initialized=True):
        self.calls = []
        self.events = []
        self.closed = False
        self.status = status
        self.refuse = refuse
        self.ignored = ignored
        self.disconnect = disconnect
        self.experimental_api = False
        if initialized:
            self.call("initialize", {"capabilities": {"experimentalApi": True}})

    def call(self, method, params):
        if method == "initialize":
            self.experimental_api = params.get("capabilities", {}).get("experimentalApi") is True
            return {}
        self.calls.append((method, params))
        if "permissions" in params and not self.experimental_api:
            raise agent.codex_daemon.Refused("permissions requires capabilities.experimentalApi")
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


@pytest.mark.parametrize("capabilities", [{}, {"experimentalApi": False}])
def test_transport_permissions_require_experimental_api(capabilities):
    transport = Transport(initialized=False)
    transport.call("initialize", {"capabilities": capabilities})
    with pytest.raises(agent.codex_daemon.Refused, match="experimentalApi"):
        transport.call("thread/start", {"permissions": "project"})


def test_proxy_declares_experimental_api(files, monkeypatch):
    daemon = agent.codex_daemon
    transport = Transport(initialized=False)
    process = SimpleNamespace(stdin=io.BytesIO(), stdout=io.BytesIO(),
                              poll=lambda: 0, wait=lambda timeout: 0)
    monkeypatch.setattr(daemon.subprocess, "Popen", lambda *a, **kw: process)

    def fill(proxy, deadline):
        key = proxy.input.getvalue().split(b"Sec-WebSocket-Key: ", 1)[1].split(b"\r\n", 1)[0]
        accept = daemon.base64.b64encode(
            daemon.hashlib.sha1(key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest()
        )
        proxy.buffer = (
            b"HTTP/1.1 101 Switching Protocols\r\nSec-WebSocket-Accept: " + accept + b"\r\n\r\n"
        )

    monkeypatch.setattr(daemon.Proxy, "fill", fill)
    monkeypatch.setattr(
        daemon.Proxy, "call", lambda self, method, params: transport.call(method, params)
    )
    proxy = daemon.Proxy()
    try:
        assert transport.experimental_api
        daemon.start(proxy, None, files[0], "gpt-6.1-sol", "low", [files[-1]],
                     {"shell_environment_policy.set.CLAUDE_CODE_SESSION_ID": "test-session"})
    finally:
        proxy.close()


@pytest.fixture
def files(tmp_path, monkeypatch):
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "test-session")
    root, home = tmp_path / "repo", tmp_path / "home"
    root.mkdir()
    (root / "CLAUDE.md").write_text("+ lib: none\n- repo instructions\n")
    brief = tmp_path / "brief.md"
    brief.write_text("brief body")
    scratch = tmp_path / "scratch"
    monkeypatch.setattr(agent.checkout, "git_out", lambda *_: str(root / ".git"))
    monkeypatch.setattr(agent.checkout, "ROOT", root)
    monkeypatch.setattr(agent.checkout, "main_worktree", lambda _: root)
    monkeypatch.setattr(agent.Path, "home", lambda: home)
    monkeypatch.setattr(agent.sys, "stdin", io.StringIO("first item"))
    return root, home, brief, scratch


def run(files, transport, runner=None, *, resume=False):
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
        resume=resume,
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
        [agent.PREAMBLE, "- repo instructions\n"]
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
    assert run(files, transport, resume=True) == "reply"
    assert transport.calls[0][0] == "thread/resume"
    assert transport.calls[0][1]["threadId"] == "thread"
    assert "developer_instructions" not in transport.calls[0][1]["config"]
    assert transport.calls[1][1]["input"][0]["text"] == "first item"


@pytest.mark.parametrize("refuse", ["thread/start", "turn/start"])
def test_refusal_falls_back_and_keeps_walk_record(files, refuse, capsys):
    root, home, brief, scratch = files
    scratch.mkdir()
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
    assert "resume" not in calls[0]
    overrides = [arg for arg in calls[0] if arg.startswith("developer_instructions=")]
    assert json.loads(overrides[0].split("=", 1)[1]) == "\n\n".join(
        [agent.PREAMBLE, "- repo instructions\n"]
    )
    assert calls[0][-1] == "brief body\n\nfirst item"
    record = json.loads((scratch / "codex-events.jsonl").read_text())
    assert record["ok"] is True and record["input"] == "first item"
    assert json.loads(record["output"].splitlines()[-1])["type"] == "turn.completed"


@pytest.mark.parametrize("refuse", ["thread/resume", "turn/start"])
def test_refused_resume_raises_without_exec(files, refuse, capsys):
    scratch = files[-1]
    scratch.mkdir()
    (scratch / "codex-session").write_text("thread\n")
    transport = Transport(refuse=refuse)
    with pytest.raises(ValueError, match="^already has an active writer$"):
        run(files, transport, resume=True)
    assert transport.closed
    assert (scratch / "codex-session").read_text() == "thread\n"
    assert not (scratch / "codex-events.jsonl").exists()
    assert "falling back" not in capsys.readouterr().err


@pytest.mark.parametrize("refuse,ignored,error", [
    ("thread/resume", None, "already has an active writer"),
    ("turn/start", None, "already has an active writer"),
    (None, ("", "model"), "shared daemon did not apply the requested Codex settings"),
])
def test_resumed_daemon_failure_exits_nonzero(files, monkeypatch, capsys, refuse, ignored, error):
    root, home, brief, scratch = files
    scratch.mkdir()
    (scratch / "codex-session").write_text("thread\n")
    transport = Transport(refuse=refuse, ignored=ignored)
    real_run = agent.run

    def no_exec(_):
        pytest.fail("work was replayed through exec")

    monkeypatch.setattr(
        agent, "run", lambda *a, **kw: real_run(*a, **kw, runner=no_exec, transport=lambda: transport)
    )
    assert agent.main([
        "code-reviewer", str(scratch), str(brief), "gpt-6.1-sol", "low",
        "--agent-type", "general-purpose", "--cwd", str(root), "--resume",
    ]) == 1
    assert capsys.readouterr().err == f"codex_agent: {error}\n"
    assert transport.closed


@pytest.mark.parametrize("resume", [False, True])
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
def test_silently_ignored_options_refuse_work(files, ignored, resume):
    transport = Transport(ignored=ignored)
    scratch = files[-1]
    scratch.mkdir()

    def attempt():
        return agent.daemon_turn(
            scratch,
            "thread" if resume else None,
            "prompt",
            "input",
            files[0],
            "gpt-6.1-sol",
            "low",
            [scratch],
            lambda: transport,
            {"shell_environment_policy.set.CLAUDE_CODE_SESSION_ID": "test-session"},
        )

    if resume:
        with pytest.raises(ValueError, match="shared daemon did not apply the requested Codex settings"):
            attempt()
    else:
        assert attempt() is None
    assert [m for m, _ in transport.calls] == ["thread/resume" if resume else "thread/start"]
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


@pytest.mark.parametrize("resume", [False, True])
def test_unavailable_daemon_falls_back_to_exec(files, capsys, resume):
    scratch = files[-1]
    scratch.mkdir()

    def unavailable():
        raise OSError("no socket")

    def attempt():
        return agent.daemon_turn(
            scratch, "thread" if resume else None, "prompt", "input", files[0],
            "gpt-6.1-sol", "low", [scratch], unavailable,
            {"shell_environment_policy.set.CLAUDE_CODE_SESSION_ID": "test-session"}
        )

    assert attempt() is None
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


@pytest.mark.parametrize("history", ["codex-session", "codex-events.jsonl"])
def test_fresh_launch_refuses_history_without_changing_evidence(files, history, capsys):
    scratch = files[-1]
    scratch.mkdir()
    for name in (history, "codex-last.md", agent.DONE):
        (scratch / name).write_text("saved evidence")
    before = {p.name: p.read_bytes() for p in scratch.iterdir()}
    assert agent.main(["code-reviewer", str(scratch), str(files[2]), "model", "low"]) == 1
    assert "no thread or turn accepted" in capsys.readouterr().err
    assert {p.name: p.read_bytes() for p in scratch.iterdir()} == before


def test_resume_requires_saved_thread(files):
    transport = Transport()
    with pytest.raises(OSError):
        run(files, transport, resume=True)
    assert not transport.calls
    assert not files[-1].exists()


@pytest.mark.parametrize("phase", ["instructions", "brief", "git", "session"])
def test_preparation_failure_is_proved_without_turn_history_and_can_retry(
        files, monkeypatch, capsys, phase):
    from controlled_markdown.nodes import ControlledMarkdownError, Rule

    root, home, brief, scratch = files
    transport = Transport()
    real_run = agent.run

    def no_exec(_):
        pytest.fail("preparation failure reached exec")

    monkeypatch.setattr(agent, "run", lambda *a, **kw: real_run(
        *a, **kw, runner=no_exec, transport=lambda: transport))
    with monkeypatch.context() as preparation:
        def fail(*_):
            if phase == "instructions":
                raise ControlledMarkdownError("/home/CLAUDE.md", 3, Rule.NO_MARKER, "bad line")
            raise OSError("git directory unavailable")

        if phase == "session":
            preparation.delenv("CLAUDE_CODE_SESSION_ID")
        elif phase == "instructions":
            preparation.setattr(agent, "role_instructions", fail)
        elif phase == "brief":
            brief.unlink()
        else:
            preparation.setattr(agent.checkout, "git_out", fail)
        assert agent.main([
            "code-reviewer", str(scratch), str(brief), "model", "low",
            "--agent-type", "general-purpose", "--cwd", str(root),
        ]) == 1
    stderr = capsys.readouterr().err
    assert "launch failed before Codex started" in stderr
    failure = json.loads((scratch / "codex-launch-failures.jsonl").read_text())
    assert failure["id"] in stderr and failure["error"] in stderr
    assert failure["started"] <= failure["ended"]
    assert not transport.calls
    assert not (scratch / "codex-session").exists()
    assert not (scratch / "codex-events.jsonl").exists()
    assert (scratch / agent.DONE).exists()

    entry = turn(scratch.parent / "launcher", [])
    entry["message"]["content"][0]["input"]["command"] = (
        f"python scripts/codex_agent.py code-reviewer {scratch} {brief} model low")
    result = {"type": "user", "message": {"content": [{
        "type": "tool_result", "tool_use_id": "codex", "content": "Exit code 1\n" + stderr}]}}
    assert reads.walk_entries([entry, result], "code-reviewer") == []

    brief.write_text("brief body")
    monkeypatch.setattr(agent, "run", real_run)
    assert run(files, transport) == "reply"
    retry = json.loads(json.dumps(entry))
    retry["message"]["content"][0]["id"] = "retry"
    evidence = reads.walk_entries([entry, result, retry], "code-reviewer")
    assert evidence[2]["message"]["content"][0]["content"] == "first item"
