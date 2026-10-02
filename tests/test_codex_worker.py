"""codex_worker: the adapter's lifetime against a stubbed codex binary.

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


@pytest.fixture(scope="session")
def stub(tmp_path_factory):
    """One stub binary for the whole run: macOS verifies a newly written
    executable on its first exec, and that costs more than a test does."""
    path = tmp_path_factory.mktemp("bin") / "codex"
    path.write_text(f"#!{sys.executable}\n" + STUB)
    path.chmod(0o755)
    return path


@pytest.fixture
def codex(tmp_path, stub):
    """Writes a turn's event script and launches the adapter against it."""
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


def test_an_interrupt_that_beats_the_spawn_still_cuts_the_turn(codex):
    codex.script(1, {"type": "thread.started", "thread_id": "th-1"}, {"_sleep": 60})
    worker = codex.start()
    worker.send({"type": "user", "message": {"role": "user", "content": "go"}})
    worker.interrupt()
    assert worker.until("result")[-1]["terminal_reason"] == "aborted_streaming"


def test_stdin_close_ends_the_adapter(codex):
    codex.script(1, {"type": "thread.started", "thread_id": "th-1"},
                 message("done"), usage())
    worker = codex.start()
    worker.turn("go")
    worker.proc.stdin.close()
    assert worker.proc.wait(timeout=10) == 0
