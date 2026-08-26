"""codex_worker: the console protocol against a stubbed codex binary.

The stub replays a canned event stream per turn and records the argv and the
prompt it was called with, so no test reaches the real CLI.
"""

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "tools" / "console" / "codex_worker.py"

STUB = '''
import json, os, sys, time

argv = sys.argv[1:]
prompt = sys.stdin.read()
count = os.environ["STUB_COUNT"]
turn = 0
if os.path.exists(count):
    turn = int(open(count).read())
turn += 1
open(count, "w").write(str(turn))
with open(os.environ["STUB_LOG"], "a") as fh:
    fh.write(json.dumps({"argv": argv, "prompt": prompt}) + "\\n")

script = os.path.join(os.environ["STUB_DIR"], f"{turn}.jsonl")
if not os.path.exists(script):
    script = os.path.join(os.environ["STUB_DIR"], "1.jsonl")
try:
    for line in open(script):
        line = line.strip()
        if not line:
            continue
        step = json.loads(line)
        if "_sleep" in step:
            time.sleep(step["_sleep"])
        elif "_stderr" in step:
            sys.stderr.write(step["_stderr"])
            sys.stderr.flush()
        elif "_exit" in step:
            sys.exit(step["_exit"])
        else:
            print(json.dumps(step), flush=True)
except KeyboardInterrupt:
    sys.exit(130)
'''


class Adapter:
    """The adapter as the console runs it: JSON lines in, JSON lines out."""

    def __init__(self, proc):
        self.proc = proc
        self.events = queue.Queue()
        self.thread = threading.Thread(target=self.pump, daemon=True)
        self.thread.start()

    def pump(self):
        for line in self.proc.stdout:
            line = line.strip()
            if line:
                self.events.put(json.loads(line))
        self.events.put(None)

    def send(self, obj):
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def turn(self, text):
        self.send({"type": "user", "message": {"role": "user", "content": text}})
        return self.until("result")

    def interrupt(self):
        self.send({"type": "control_request", "request_id": "r1",
                   "request": {"subtype": "interrupt"}})

    def until(self, kind, timeout=20):
        """Every event up to and including the first of `kind`."""
        seen, deadline = [], time.time() + timeout
        while True:
            ev = self.events.get(timeout=max(.1, deadline - time.time()))
            assert ev is not None, f"adapter exited before {kind}: {seen}"
            seen.append(ev)
            if ev.get("type") == kind:
                return seen

    def close(self):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def usage(**over):
    figures = {"input_tokens": 0, "cached_input_tokens": 0,
               "cache_write_input_tokens": 0, "output_tokens": 0,
               "reasoning_output_tokens": 0}
    figures.update(over)
    return {"type": "turn.completed", "usage": figures}


def message(text):
    return {"type": "item.completed",
            "item": {"id": "item_0", "type": "agent_message", "text": text}}


@pytest.fixture
def codex(tmp_path):
    """Writes a turn's event script and launches the adapter against it."""
    stub = tmp_path / "codex"
    stub.write_text(f"#!{sys.executable}\n" + STUB)
    stub.chmod(0o755)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    log = tmp_path / "calls.jsonl"
    env = {**os.environ, "STUB_DIR": str(scripts), "STUB_LOG": str(log),
           "STUB_COUNT": str(tmp_path / "count")}
    started = []

    class Harness:
        root = tmp_path

        def script(self, turn, *events):
            (scripts / f"{turn}.jsonl").write_text(
                "".join(json.dumps(e) + "\n" for e in events))

        def start(self, *args):
            proc = subprocess.Popen(
                [sys.executable, str(ADAPTER), "--codex", str(stub), *args],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, env=env, cwd=tmp_path)
            adapter = Adapter(proc)
            started.append(adapter)
            return adapter

        def calls(self):
            return [json.loads(x) for x in log.read_text().splitlines() if x.strip()]

    yield Harness()
    for adapter in started:
        adapter.close()


def texts(events):
    out = []
    for ev in events:
        for block in (ev.get("message") or {}).get("content", []):
            if block.get("type") == "text":
                out.append(block["text"])
    return out


def tools(events):
    out = []
    for ev in events:
        for block in (ev.get("message") or {}).get("content", []):
            if block.get("type") == "tool_use":
                out.append((block["name"], block["input"]))
    return out


def test_init_reports_the_codex_thread_id(codex):
    codex.script(1, {"type": "thread.started", "thread_id": "th-1"},
                 message("hi"), usage(output_tokens=5))
    events = codex.start().turn("go")
    assert events[0] == {"type": "system", "subtype": "init",
                         "session_id": "th-1", "model": ""}
    assert events[-1]["session_id"] == "th-1"


def test_text_and_commands_reach_the_feed(codex):
    codex.script(1, {"type": "thread.started", "thread_id": "th-1"},
                 message("working on it"),
                 {"type": "item.started",
                  "item": {"id": "item_1", "type": "command_execution",
                           "command": "/bin/zsh -lc 'uv run pytest -q'",
                           "status": "in_progress"}},
                 {"type": "item.completed",
                  "item": {"id": "item_1", "type": "command_execution",
                           "command": "/bin/zsh -lc 'uv run pytest -q'",
                           "exit_code": 0, "status": "completed"}},
                 {"type": "item.completed",
                  "item": {"id": "item_2", "type": "file_change",
                           "status": "completed",
                           "changes": [{"path": "programs/solvers/x.dl", "kind": "add"},
                                       {"path": "programs/lib.dl", "kind": "update"}]}},
                 message("done"), usage(output_tokens=9))
    events = codex.start().turn("go")
    assert texts(events) == ["working on it", "done"]
    assert tools(events) == [
        ("Bash", {"command": "uv run pytest -q"}),
        ("Write", {"file_path": "programs/solvers/x.dl"}),
        ("Edit", {"file_path": "programs/lib.dl"})]
    assert events[-1]["result"] == "done"
    assert events[-1]["terminal_reason"] == "completed"


def test_result_splits_the_cached_prompt_out_of_the_input(codex):
    codex.script(1, {"type": "thread.started", "thread_id": "th-1"},
                 message("done"),
                 usage(input_tokens=31851, cached_input_tokens=26112,
                       cache_write_input_tokens=1000, output_tokens=111))
    events = codex.start().turn("go")
    assert events[-1]["usage"] == {
        "input_tokens": 4739, "output_tokens": 111,
        "cache_read_input_tokens": 26112, "cache_creation_input_tokens": 1000,
        "iterations": [{"input_tokens": 4739, "output_tokens": 111,
                        "cache_read_input_tokens": 26112,
                        "cache_creation_input_tokens": 1000}]}


def test_a_later_turn_reports_its_step_not_the_thread_total(codex):
    codex.script(1, {"type": "thread.started", "thread_id": "th-1"},
                 message("one"), usage(input_tokens=31851,
                                       cached_input_tokens=26112, output_tokens=111))
    codex.script(2, {"type": "thread.started", "thread_id": "th-1"},
                 message("two"), usage(input_tokens=47874,
                                       cached_input_tokens=41216, output_tokens=116))
    worker = codex.start()
    worker.turn("go")
    events = worker.turn("again")
    assert events[-1]["usage"]["output_tokens"] == 5
    assert events[-1]["usage"]["cache_read_input_tokens"] == 15104
    assert events[-1]["usage"]["input_tokens"] == 16023 - 15104


def test_first_turn_opens_with_the_appendix_and_a_writable_sandbox(codex):
    append = codex.root / "append.md"
    append.write_text("APPENDIX TEXT\n")
    codex.script(1, {"type": "thread.started", "thread_id": "th-1"},
                 message("done"), usage())
    codex.start("--append", str(append), "--add-dir", "/ref",
                "--model", "gpt-5.1-codex", "--effort", "xhigh").turn("solve it")
    call = codex.calls()[0]
    assert call["argv"] == ["exec", "-", "--json", "--skip-git-repo-check",
                            "-c", 'approval_policy="never"',
                            "--sandbox", "workspace-write", "--add-dir", "/ref",
                            "--model", "gpt-5.1-codex",
                            "-c", 'model_reasoning_effort="xhigh"']
    assert call["prompt"] == "APPENDIX TEXT\n\nsolve it"


def test_later_turns_resume_the_thread_without_the_appendix(codex):
    append = codex.root / "append.md"
    append.write_text("APPENDIX TEXT\n")
    for turn in (1, 2):
        codex.script(turn, {"type": "thread.started", "thread_id": "th-1"},
                     message("done"), usage())
    worker = codex.start("--append", str(append), "--add-dir", "/ref")
    worker.turn("solve it")
    worker.turn("now refine")
    call = codex.calls()[1]
    assert call["argv"] == ["exec", "resume", "th-1", "-", "--json",
                            "--skip-git-repo-check", "-c", 'approval_policy="never"',
                            "-c", 'sandbox_mode="workspace-write"',
                            "-c", 'sandbox_workspace_write.writable_roots=["/ref"]']
    assert call["prompt"] == "now refine"


def test_a_resumed_process_reports_the_session_before_codex_answers(codex):
    codex.script(1, {"type": "thread.started", "thread_id": "th-1"},
                 message("done"), usage(input_tokens=99, output_tokens=9))
    events = codex.start("--resume", "th-1").turn("go")
    assert events[0]["session_id"] == "th-1"
    assert codex.calls()[0]["argv"][:3] == ["exec", "resume", "th-1"]
    # The thread's totals started above zero, so the step is unknown.
    assert "usage" not in events[-1]


def test_interrupt_cuts_the_turn_and_kills_the_child(codex):
    codex.script(1, {"type": "thread.started", "thread_id": "th-1"},
                 message("thinking"), {"_sleep": 60})
    worker = codex.start()
    worker.send({"type": "user", "message": {"role": "user", "content": "go"}})
    worker.until("assistant")
    worker.interrupt()
    events = worker.until("result")
    assert any(ev["type"] == "control_response" for ev in events)
    assert events[-1]["terminal_reason"] == "aborted_streaming"
    assert events[-1]["is_error"] is True


def test_a_worker_stays_usable_after_an_interrupt(codex):
    codex.script(1, {"type": "thread.started", "thread_id": "th-1"}, {"_sleep": 60})
    codex.script(2, {"type": "thread.started", "thread_id": "th-1"},
                 message("second"), usage(output_tokens=4))
    worker = codex.start()
    worker.send({"type": "user", "message": {"role": "user", "content": "go"}})
    worker.until("system")
    worker.interrupt()
    worker.until("result")
    events = worker.turn("again")
    assert events[-1]["terminal_reason"] == "completed"
    assert events[-1]["result"] == "second"


def test_an_interrupt_that_beats_the_spawn_still_cuts_the_turn(codex):
    codex.script(1, {"type": "thread.started", "thread_id": "th-1"}, {"_sleep": 60})
    worker = codex.start()
    worker.send({"type": "user", "message": {"role": "user", "content": "go"}})
    worker.interrupt()
    assert worker.until("result")[-1]["terminal_reason"] == "aborted_streaming"


def test_a_child_that_dies_mid_turn_still_lands_a_result(codex):
    codex.script(1, {"type": "thread.started", "thread_id": "th-1"},
                 message("half"), {"_stderr": "stream error: connection reset\n"},
                 {"_exit": 3})
    events = codex.start().turn("go")
    assert events[-1]["terminal_reason"] == "error_during_execution"
    assert events[-1]["result"] == ""
    assert any("code 3" in t and "connection reset" in t for t in texts(events))


def test_a_failed_turn_reports_the_codex_error(codex):
    codex.script(1, {"type": "thread.started", "thread_id": "th-1"},
                 {"type": "turn.failed", "error": {"message": "usage limit reached"}})
    events = codex.start().turn("go")
    assert any("usage limit reached" in t for t in texts(events))
    assert events[-1]["terminal_reason"] == "error_during_execution"


def test_stdin_close_ends_the_adapter(codex):
    codex.script(1, {"type": "thread.started", "thread_id": "th-1"},
                 message("done"), usage())
    worker = codex.start()
    worker.turn("go")
    worker.proc.stdin.close()
    assert worker.proc.wait(timeout=10) == 0
