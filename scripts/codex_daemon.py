"""A JSON-RPC client of the shared Codex daemon, through its WebSocket proxy.

Closing this client stops only its proxy process, never the shared daemon.
"""

import base64
import hashlib
import json
import os
import select
import struct
import subprocess
import tempfile
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

from handbook.context import CODEX_PROFILE, codex_permissions


class Refused(ValueError):
    """An RPC response explicitly rejected a request, before it could run."""


class Proxy:
    """The proxy's WebSocket transport and ordered JSON-RPC notifications."""

    def __init__(self):
        self.errors = tempfile.TemporaryFile()
        try:
            self.process = subprocess.Popen(
                ["codex", "app-server", "proxy"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self.errors,
                bufsize=0,
            )
        except OSError:
            self.errors.close()
            raise
        assert self.process.stdin is not None and self.process.stdout is not None
        self.input = self.process.stdin
        self.output = self.process.stdout
        self.buffer = b""
        self.pending: deque[dict[str, Any]] = deque()
        self.serial = 0
        try:
            key = base64.b64encode(os.urandom(16)).decode()
            self.input.write(
                (
                    "GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\n"
                    "Connection: Upgrade\r\nSec-WebSocket-Version: 13\r\n"
                    f"Sec-WebSocket-Key: {key}\r\n\r\n"
                ).encode()
            )
            deadline = time.monotonic() + 10
            while b"\r\n\r\n" not in self.buffer:
                self.fill(deadline)
            headers, self.buffer = self.buffer.split(b"\r\n\r\n", 1)
            accept = base64.b64encode(
                hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
            )
            if not headers.startswith(b"HTTP/1.1 101 ") or accept not in headers:
                raise ValueError("Codex proxy refused WebSocket upgrade")
            self.call("initialize", {"clientInfo": {"name": "arc_codex_agent", "version": "1"},
                                     "capabilities": {"experimentalApi": True}})
            self.send({"method": "initialized", "params": {}})
        except BaseException:
            self.close()
            raise

    def fill(self, deadline: float | None):
        timeout = None if deadline is None else max(0, deadline - time.monotonic())
        if not select.select([self.output], [], [], timeout)[0]:
            raise TimeoutError("Codex proxy response timed out")
        data = os.read(self.output.fileno(), 65536)
        if not data:
            self.errors.seek(0)
            raise OSError(
                "Codex proxy closed: " + self.errors.read().decode(errors="replace").strip()
            )
        self.buffer += data

    def send(self, message: dict[str, Any], opcode: int = 1):
        self.frame(json.dumps({"jsonrpc": "2.0", **message}).encode(), opcode)

    def frame(self, data: bytes, opcode: int):
        size = len(data)
        length = (
            bytes([size | 128])
            if size < 126
            else b"\xfe" + struct.pack(">H", size)
            if size < 65536
            else b"\xff" + struct.pack(">Q", size)
        )
        mask = os.urandom(4)
        packet = memoryview(
            bytes([128 | opcode])
            + length
            + mask
            + bytes(byte ^ mask[i % 4] for i, byte in enumerate(data))
        )
        while packet:
            written = self.input.write(packet)
            if not written:
                raise OSError("Codex proxy write failed")
            packet = packet[written:]

    def receive(self, deadline: float | None = None) -> dict[str, Any]:
        fragments = bytearray()
        while True:
            while len(self.buffer) < 2:
                self.fill(deadline)
            first, second = self.buffer[:2]
            size, offset = second & 127, 2
            extra = 2 if size == 126 else 8 if size == 127 else 0
            while len(self.buffer) < offset + extra:
                self.fill(deadline)
            if extra:
                size = int.from_bytes(self.buffer[offset : offset + extra], "big")
                offset += extra
            if second & 128:
                raise ValueError("masked server WebSocket frame")
            while len(self.buffer) < offset + size:
                self.fill(deadline)
            data, self.buffer = self.buffer[offset : offset + size], self.buffer[offset + size :]
            opcode = first & 15
            if opcode == 8:
                raise OSError("Codex proxy WebSocket closed")
            if opcode == 9:
                self.frame(data, 10)
            elif opcode in (0, 1):
                fragments.extend(data)
                if first & 128:
                    return json.loads(fragments)

    def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.serial += 1
        self.send({"id": self.serial, "method": method, "params": params})
        deadline = time.monotonic() + 30
        while True:
            message = self.receive(deadline)
            if message.get("id") == self.serial and "method" not in message:
                if "error" in message:
                    raise Refused(f"{method}: {message['error']}")
                return message["result"]
            self.pending.append(message)

    def event(self) -> dict[str, Any]:
        return self.pending.popleft() if self.pending else self.receive()

    def close(self):
        self.input.close()
        if self.process.poll() is None:
            self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.output.close()
        self.errors.close()


def start(
    client: Any, thread: str | None, cwd: Path, model: str, effort: str, writable: list[Path],
    instructions: str | None = None,
) -> dict[str, Any]:
    """Load a thread and check effective settings before starting any work."""
    config = {
        "project_doc_max_bytes": 0,
        "model_reasoning_effort": effort,
        **codex_permissions([*writable, cwd / ".codex"]),
    }
    if instructions is not None:
        config["developer_instructions"] = instructions
    params = {
        "cwd": str(cwd),
        "model": model,
        "approvalPolicy": "never",
        "permissions": CODEX_PROFILE,
        "config": config,
    }
    if thread is not None:
        params["threadId"] = thread
    result = client.call("thread/resume" if thread else "thread/start", params)
    policy = result.get("sandbox") or {}
    if (
        result["model"] != model
        or result["cwd"] != str(cwd)
        or result["approvalPolicy"] != "never"
        or result["reasoningEffort"] != effort
        or result.get("activePermissionProfile") != {"id": CODEX_PROFILE, "extends": ":workspace"}
        or policy.get("type") != "workspaceWrite"
        or policy.get("networkAccess") is not True
        or not set(map(str, [*writable, cwd / ".codex"])) <= set(policy.get("writableRoots") or [])
        or result.get("instructionSources") != []
    ):
        raise ValueError("shared daemon did not apply the requested Codex settings")
    return result


def collect(
    client: Any, thread: str, turn: str, emit: Callable[[dict[str, Any]], None]
) -> tuple[str, bool]:
    """Save CLI-shaped command evidence and return the final answer and status."""
    message = ""
    final_message = ""
    first_input = True
    output_deltas: dict[str, list[str]] = {}
    while True:
        event = client.event()
        params = event.get("params", {})
        if params.get("threadId") != thread:
            continue
        method = event.get("method")
        if method == "thread/tokenUsage/updated" and params.get("turnId") == turn:
            emit({"type": "usage.updated", "turn_id": turn,
                  "cumulative": params.get("tokenUsage", {}).get("total")})
        elif method == "item/commandExecution/outputDelta" and params.get("turnId") == turn:
            output_deltas.setdefault(params["itemId"], []).append(params["delta"])
        elif method == "item/completed" and params.get("turnId") == turn:
            item = params["item"]
            if item["type"] == "agentMessage":
                message = item["text"]
                if item.get("phase") == "final_answer":
                    final_message = message
                emit(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "agent_message",
                            "text": item["text"],
                            "phase": item.get("phase"),
                        },
                    }
                )
            elif item["type"] == "commandExecution":
                deltas = output_deltas.pop(item.get("id"), [])
                output = item.get("aggregatedOutput")
                if output is None:
                    output = "".join(deltas)
                emit(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": item["command"],
                            "aggregated_output": output,
                            "exit_code": item["exitCode"],
                            "status": item["status"],
                        },
                    }
                )
            elif item["type"] == "userMessage":
                if first_input:
                    first_input = False
                else:
                    emit(
                        {
                            "type": "input",
                            "text": "\n".join(
                                c["text"] for c in item["content"] if c["type"] == "text"
                            ),
                        }
                    )
        elif method == "turn/completed" and params["turn"]["id"] == turn:
            completed = params["turn"]
            ok = completed["status"] == "completed"
            emit(
                {
                    "type": "turn.completed" if ok else "turn.failed",
                    "status": completed["status"],
                    "turn_id": turn,
                    "error": completed.get("error"),
                }
            )
            return (final_message if ok else message), ok
