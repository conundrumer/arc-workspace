#!/usr/bin/env python3
"""Runs the OpenAI Codex CLI as a console worker.

The console speaks the Claude Code stream-json protocol: one user event per
turn on stdin, assistant and result events on stdout. `codex exec` runs one
turn per process with a schema of its own, so this adapter keeps the session,
spawns a codex child per turn, resumes the thread on later turns, and
translates between the two schemas.

    codex_worker.py --append <file> [--resume <thread>] [--model M] [--effort E]

Env:
    CONSOLE_CODEX      codex binary (default: codex)
"""

import argparse
import json
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

type Json = dict[str, object]

CODEX = os.environ.get("CONSOLE_CODEX", "codex")
SANDBOX = "workspace-write"
KILL_GRACE = 5      # seconds from the interrupt's SIGINT to the SIGKILL
STDERR_TAIL = 600   # bytes of codex stderr kept for a failed turn's feed line
STOP = object()

# The running totals codex reports at the end of every turn.
USAGE_KEYS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens",
              "output_tokens", "reasoning_output_tokens")

SHELL = re.compile(r"^\S*(?:ba|z)?sh\s+-l?c\s+(.*)$", re.S)

OUT = threading.Lock()


def emit(obj: Json) -> None:
    with OUT:
        sys.stdout.write(json.dumps(obj) + "\n")
        sys.stdout.flush()


def unwrap(command: str) -> str:
    """codex reports a command as the argv it runs it through."""
    m = SHELL.match(command.strip())
    if not m:
        return command
    body = m.group(1).strip()
    if len(body) > 1 and body[0] == body[-1] == "'":
        return body[1:-1].replace("'\\''", "'")
    return body


def message_text(ev: Json) -> str:
    content = (ev.get("message") or {}).get("content", "")
    if isinstance(content, list):
        return "".join(x.get("text", "") for x in content if isinstance(x, dict))
    return str(content)


class Worker:
    def __init__(self, args) -> None:
        self.codex = args.codex
        self.model = args.model
        self.effort = args.effort
        self.add_dirs = args.add_dir or []
        self.append = args.append
        self.session = args.resume
        # codex reports the thread's running totals, and a resumed thread
        # starts this process above zero.
        self.baseline = None if args.resume else dict.fromkeys(USAGE_KEYS, 0)
        self.lock = threading.Lock()
        self.proc = None
        self.interrupted = False
        self.turn = 0
        self.seq = 0
        self.text = ""
        self.emitted: set[str] = set()
        self.result_sent = True
        self.init_sent = False
        self.started = time.time()

    # ---------- codex side ----------

    def argv(self) -> list[str]:
        """`codex exec resume` takes no sandbox or directory flags, so a
        resumed turn passes the same settings as config overrides."""
        cmd = [self.codex, "exec"]
        if self.session:
            cmd += ["resume", self.session]
        cmd += ["-", "--json", "--skip-git-repo-check", "-c", 'approval_policy="never"']
        if self.session:
            cmd += ["-c", f'sandbox_mode="{SANDBOX}"']
            if self.add_dirs:
                cmd += ["-c", "sandbox_workspace_write.writable_roots="
                        + json.dumps(self.add_dirs)]
        else:
            cmd += ["--sandbox", SANDBOX]
            for path in self.add_dirs:
                cmd += ["--add-dir", path]
        if self.model:
            cmd += ["--model", self.model]
        if self.effort:
            cmd += ["-c", f'model_reasoning_effort="{self.effort}"']
        return cmd

    def prompt(self, message: str) -> str:
        """codex exec has no system-prompt append, so the appendix opens the
        thread's first message."""
        if self.session or not self.append:
            return message
        return self.append.read_text().rstrip() + "\n\n" + message

    def interrupt(self) -> None:
        with self.lock:
            self.interrupted = True
            proc = self.proc
        if proc is None or proc.poll() is not None:
            return
        # The signal goes to the group: codex runs commands in child shells.
        for sig, delay in ((signal.SIGINT, 0), (signal.SIGKILL, KILL_GRACE)):
            timer = threading.Timer(delay, self.signal_group, (proc, sig))
            timer.daemon = True
            timer.start()

    @staticmethod
    def signal_group(proc: subprocess.Popen, sig: int) -> None:
        if proc.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(proc.pid), sig)
        except (OSError, ProcessLookupError):
            pass

    # ---------- console side ----------

    def init(self) -> None:
        self.init_sent = True
        emit({"type": "system", "subtype": "init", "session_id": self.session,
              "model": self.model or ""})

    def assistant(self, blocks: list[Json]) -> None:
        self.seq += 1
        emit({"type": "assistant",
              "message": {"id": f"codex-{self.turn}-{self.seq}", "content": blocks}})

    def note(self, text: str) -> None:
        if text.strip():
            self.assistant([{"type": "text", "text": text}])

    def result(self, reason: str, text: str = "", usage: Json | None = None) -> None:
        if self.result_sent:
            return
        self.result_sent = True
        ev = {"type": "result",
              "subtype": "success" if reason == "completed" else "error_during_execution",
              "terminal_reason": reason, "result": text,
              "is_error": reason != "completed", "session_id": self.session,
              "duration_ms": int((time.time() - self.started) * 1000)}
        if usage:
            ev["usage"] = usage
        emit(ev)

    def step(self, totals: Json) -> Json | None:
        """One turn's usage. codex reports the thread's running totals, so the
        turn is the step since the last one; a process that resumed a thread it
        did not open has no baseline and reports nothing for its first turn."""
        current = {k: int(totals.get(k) or 0) for k in USAGE_KEYS}
        base, self.baseline = self.baseline, current
        if base is None:
            return None
        step = {k: max(0, current[k] - base[k]) for k in USAGE_KEYS}
        read = step["cached_input_tokens"]
        written = step["cache_write_input_tokens"]
        # codex counts the cached and freshly written prompt inside its input
        # figure; the console reads the three apart.
        entry = {"input_tokens": max(0, step["input_tokens"] - read - written),
                 "output_tokens": step["output_tokens"],
                 "cache_read_input_tokens": read,
                 "cache_creation_input_tokens": written}
        return {**entry, "iterations": [entry]}

    # ---------- translation ----------

    def tool_blocks(self, item: Json) -> list[Json]:
        kind = item.get("type")
        if kind == "command_execution":
            command = item.get("command")
            if not command:
                return []
            return [{"name": "Bash", "input": {"command": unwrap(str(command))}}]
        if kind == "file_change":
            blocks = []
            for change in item.get("changes") or []:
                path = change.get("path")
                if path:
                    name = "Write" if change.get("kind") == "add" else "Edit"
                    blocks.append({"name": name, "input": {"file_path": str(path)}})
            return blocks
        if kind == "mcp_tool_call":
            name = f"mcp__{item.get('server', '?')}__{item.get('tool', '?')}"
            return [{"name": name, "input": item.get("arguments") or {}}]
        if kind == "web_search":
            return [{"name": "WebSearch", "input": {"query": item.get("query", "")}}]
        return []

    def item(self, item: Json, event_type: str) -> None:
        kind, item_id = item.get("type"), str(item.get("id") or "")
        if kind == "agent_message":
            if event_type == "item.completed" and str(item.get("text", "")).strip():
                self.text = str(item["text"]).strip()
                self.assistant([{"type": "text", "text": self.text}])
            return
        if kind == "error":
            if item_id not in self.emitted:
                self.emitted.add(item_id)
                self.note(f"⚠ codex error: {item.get('message', '')}")
            return
        blocks = self.tool_blocks(item)
        if not blocks or item_id in self.emitted:
            return
        self.emitted.add(item_id)
        self.assistant([{"type": "tool_use", "id": f"{item_id}-{n}", **block}
                        for n, block in enumerate(blocks)])

    def translate(self, ev: Json) -> None:
        kind = ev.get("type")
        if kind == "thread.started":
            self.session = ev.get("thread_id") or self.session
            if not self.init_sent:
                self.init()
        elif kind in ("item.started", "item.updated", "item.completed"):
            self.item(ev.get("item") or {}, str(kind))
        elif kind == "turn.completed":
            self.result("completed", self.text, self.step(ev.get("usage") or {}))
        elif kind == "turn.failed":
            self.note("⚠ codex turn failed: "
                      + str((ev.get("error") or {}).get("message", "")))
            self.result("error_during_execution")
        elif kind == "error":
            self.note("⚠ codex error: " + str(ev.get("message", "")))

    # ---------- turns ----------

    def run_turn(self, message: str) -> None:
        self.turn += 1
        self.seq = 0
        self.text = ""
        self.emitted = set()
        self.result_sent = False
        self.init_sent = False
        self.started = time.time()
        if self.session:
            self.init()
        prompt = self.prompt(message)
        try:
            proc = subprocess.Popen(self.argv(), stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, start_new_session=True)
        except OSError as exc:
            self.note(f"⚠ codex failed to start: {exc}")
            self.result("error_during_execution")
            return
        with self.lock:
            self.proc = proc
            pending = self.interrupted
        if pending:  # an interrupt that landed while the child was starting
            self.interrupt()
        errors: list[str] = []
        drain = threading.Thread(target=self.drain, args=(proc, errors), daemon=True)
        drain.start()
        try:
            proc.stdin.write(prompt)
            proc.stdin.close()
        except OSError:
            pass
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            try:
                self.translate(ev)
            except Exception as exc:  # a bad event must not cost the turn
                self.note(f"⚠ codex_worker could not read an event: {exc!r}")
        code = proc.wait()
        drain.join(timeout=3)
        with self.lock:
            self.proc = None
            interrupted = self.interrupted
        if self.result_sent:
            return
        if interrupted:
            self.result("aborted_streaming")
            return
        tail = "".join(errors)[-STDERR_TAIL:].strip()
        self.note(f"⚠ codex exited with code {code}" + (f" — {tail}" if tail else ""))
        self.result("error_during_execution")

    @staticmethod
    def drain(proc: subprocess.Popen, errors: list[str]) -> None:
        """codex stderr goes to the console's log for the item, and its tail
        explains a turn that ends without a result."""
        for line in proc.stderr:
            sys.stderr.write(line)
            errors.append(line)
            del errors[:-40]
        sys.stderr.flush()

    def stdin_loop(self, turns: queue.Queue) -> None:
        for line in sys.stdin:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            kind = ev.get("type")
            if kind == "control_request":
                emit({"type": "control_response",
                      "response": {"subtype": "success",
                                   "request_id": ev.get("request_id"),
                                   "response": {}}})
                if (ev.get("request") or {}).get("subtype") == "interrupt":
                    self.interrupt()
            elif kind == "user":
                # Clearing the flag here, and not where the turn starts, keeps
                # an interrupt sent before the child is up from being lost.
                with self.lock:
                    self.interrupted = False
                turns.put(message_text(ev))
        turns.put(STOP)

    def shutdown(self, sig, frame) -> None:
        """The console reaps the adapter, not the codex tree below it."""
        with self.lock:
            proc = self.proc
        if proc is not None:
            self.signal_group(proc, signal.SIGKILL)
        os._exit(128 + sig)

    def run(self) -> None:
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(sig, self.shutdown)
        turns: queue.Queue = queue.Queue()
        reader = threading.Thread(target=self.stdin_loop, args=(turns,), daemon=True)
        reader.start()
        while True:
            item = turns.get()
            if item is STOP:
                return
            self.run_turn(str(item))


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--append", type=Path,
                    help="file whose text opens the session's first message")
    ap.add_argument("--resume", help="codex thread id to continue")
    ap.add_argument("--model")
    ap.add_argument("--effort", help="model_reasoning_effort for every turn")
    ap.add_argument("--add-dir", action="append",
                    help="extra writable directory (repeatable)")
    ap.add_argument("--codex", default=CODEX)
    return ap


def main(argv: list[str] | None = None) -> int:
    Worker(parser().parse_args(argv)).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
