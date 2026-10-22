"""Read the live rollout of the Codex thread named by a scratch directory."""

import json
import shlex
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from operations.codex_spend import CodexUsage


def tokens(value: object) -> CodexUsage | None:
    """Decode transport token counts, refusing negative and noninteger counts."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("invalid Codex token usage")
    names = {"input_tokens": "inputTokens", "cached_input_tokens": "cachedInputTokens",
             "output_tokens": "outputTokens", "reasoning_output_tokens": "reasoningOutputTokens",
             "total_tokens": "totalTokens"}
    counts = {}
    for name, camel in names.items():
        count = value.get(name, value.get(camel))
        if count is not None and (type(count) is not int or count < 0):
            raise ValueError("invalid Codex token count")
        counts[name] = count
    return CodexUsage(**counts)


def usage_reason(usage: CodexUsage | None, turn: str | None) -> str | None:
    """Explain the unknown component of a turn measurement."""
    if turn is None:
        return "accepted turn identity unavailable"
    if usage is None:
        return "turn usage unavailable"
    missing = [k for k in CodexUsage.__dataclass_fields__ if getattr(usage, k) is None]
    return "missing token counts: " + ", ".join(missing) if missing else None


def difference(after: CodexUsage, before: CodexUsage) -> CodexUsage:
    """Subtract cumulative boundaries; a reset or absent boundary is unknown."""
    values = {}
    for name in CodexUsage.__dataclass_fields__:
        a, b = getattr(after, name), getattr(before, name)
        values[name] = a - b if a is not None and b is not None and a >= b else None
    return CodexUsage(**values)


class TurnEnd(StrEnum):
    COMPLETE = "task_complete"
    ABORTED = "turn_aborted"


@dataclass
class Turn:
    """A rollout turn's cumulative boundaries and time interval."""
    turn: str
    started: float
    ended: float | None = None
    before: CodexUsage | None = None
    after: CodexUsage | None = None
    activity: list[dict[str, Any]] = field(default_factory=list)
    end_state: TurnEnd | None = None

    @property
    def usage(self) -> CodexUsage | None:
        if self.after is None or self.before is None:
            return None
        return difference(self.after, self.before)


def rollout_files(home: Path, pattern: str = "rollout-*.jsonl") -> list[Path]:
    """Local Codex session rollouts, in path order."""
    return sorted((home / ".codex" / "sessions").rglob(pattern))


def rollout_path(thread: str, home: Path) -> Path:
    if not thread or not all(c.isascii() and (c.isalnum() or c == "-") for c in thread):
        raise ValueError("invalid Codex session id")
    paths = rollout_files(home, f"rollout-*-{thread}.jsonl")
    if len(paths) != 1:
        raise ValueError(f"expected one live rollout for {thread}, found {len(paths)}")
    return paths[0]


def rows(path: Path) -> list[dict[str, Any]]:
    """Read complete JSONL lines, leaving a concurrent append's tail unread."""
    complete = [json.loads(line) for line in path.read_bytes().splitlines(keepends=True)
                if line.endswith(b"\n")]
    if any(not isinstance(row, dict) for row in complete):
        raise ValueError("Codex JSONL row is not an object")
    return complete


def turns(thread: str, home: Path) -> list[Turn]:
    """Usage deltas within accepted turn boundaries, never lifetime totals."""
    return read_turns(rollout_path(thread, home))


def read_turns(path: Path) -> list[Turn]:
    """Read turn activity and usage from the same complete source lines."""
    out: list[Turn] = []
    latest: CodexUsage | None = None
    current: Turn | None = None
    for row in rows(path):
        p = row.get("payload", {})
        if not isinstance(p, dict):
            raise ValueError("Codex rollout payload is not an object")
        kind = p.get("type") if row.get("type") == "event_msg" else None
        if kind == "task_started":
            boundary = latest if current is None else None
            current = Turn(p["turn_id"], datetime.fromisoformat(row["timestamp"]).timestamp(),
                           before=boundary)
            out.append(current)
        if current is not None:
            current.activity.append(row)
        if kind == "token_count" and p.get("info") is not None:
            latest = tokens(p["info"]["total_token_usage"])
            if current is not None:
                if len(out) == 1 and current.after is None and current.before is None:
                    last = tokens(p["info"].get("last_token_usage"))
                    if latest is not None and last is not None and latest == last:
                        current.before = difference(latest, last)
                current.after = latest
        elif kind in ("task_complete", "turn_aborted") and current is not None:
            if p.get("turn_id") == current.turn:
                current.ended = datetime.fromisoformat(row["timestamp"]).timestamp()
                current.end_state = TurnEnd(kind)
                latest = current.after
                current = None
    return out


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
    state = Rollout(thread)
    for row in rows(rollout_path(thread, home)):
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
            usage = tokens(payload["info"]["total_token_usage"])
            state.tokens = None if usage is None else {
                k: v for k in CodexUsage.__dataclass_fields__
                if (v := getattr(usage, k)) is not None}
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


def call_turn(thread: str, home: Path, started: float, ended: float,
              accepted: str | None = None) -> Turn | None:
    """Locate exactly one accepted turn within a call's recorded interval."""
    return select_turn(turns(thread, home), started, ended, accepted)


def select_turn(turns: list[Turn], started: float, ended: float,
                accepted: str | None = None, *, include_end: bool = True) -> Turn | None:
    """Select one accepted identity or one start in the bounded interval."""
    found = [t for t in turns
             if (t.turn == accepted if accepted is not None
                 else started <= t.started and
                 (t.started <= ended if include_end else t.started < ended))]
    return found[0] if len(found) == 1 else None
