"""Read the live rollout of the Codex thread named by a scratch directory."""

import json
import shlex
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Rollout:
    """The latest turn, cumulative tokens and recent activity on a thread."""

    thread: str
    turn: str | None = None
    started: float | None = None
    tokens: dict[str, int] | None = None
    commands: list[tuple[str, Any]] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)

    def show(self) -> str:
        state = (
            f"turn {self.turn} running for {max(0, time.time() - self.started):.1f}s"
            if self.turn and self.started is not None
            else "no turn running"
        )
        tokens = json.dumps(self.tokens) if self.tokens is not None else "not reported yet"
        return "\n".join(
            [
                f"thread {self.thread}: {state}",
                f"tokens: {tokens}",
                *[
                    f"command (exit {code}): {short(command)}"
                    for command, code in self.commands[-5:]
                ],
                *[f"agent: {short(message)}" for message in self.messages[-3:]],
            ]
        )


def short(text: str) -> str:
    """A single line, bounded for a coordinator's status display."""
    text = " ".join(text.split())
    return text[:397] + "..." if len(text) > 400 else text


def read(scratch: Path, home: Path) -> Rollout:
    """Read complete JSONL lines only; a concurrent append may leave a tail."""
    thread = (scratch / "codex-session").read_text().strip()
    if not thread or not all(c.isascii() and (c.isalnum() or c == "-") for c in thread):
        raise ValueError("invalid Codex session id")
    paths = list((home / ".codex" / "sessions").rglob(f"rollout-*-{thread}.jsonl"))
    if len(paths) != 1:
        raise ValueError(f"expected one live rollout for {thread}, found {len(paths)}")
    state = Rollout(thread)
    for line in paths[0].read_bytes().splitlines(keepends=True):
        if not line.endswith(b"\n"):
            break
        row = json.loads(line)
        if row["type"] != "event_msg":
            continue
        payload = row["payload"]
        kind = payload["type"]
        if kind == "task_started":
            state.turn = payload["turn_id"]
            state.started = datetime.fromisoformat(row["timestamp"]).timestamp()
        elif kind in ("task_complete", "turn_aborted") and payload.get("turn_id") == state.turn:
            state.turn = None
            state.started = None
        elif kind == "token_count" and payload.get("info") is not None:
            state.tokens = payload["info"]["total_token_usage"]
        elif kind == "item_completed":
            item = payload["item"]
            if item["type"] == "CommandExecution":
                command = item["command"]
                state.commands.append(
                    (
                        shlex.join(command) if isinstance(command, list) else command,
                        item["exit_code"],
                    )
                )
            elif item["type"] == "AgentMessage":
                state.messages.append("\n".join(c["text"] for c in item["content"] if "text" in c))
        elif kind == "exec_command_end":
            state.commands.append((shlex.join(payload["command"]), payload["exit_code"]))
        elif kind == "agent_message":
            state.messages.append(payload["message"])
    return state
