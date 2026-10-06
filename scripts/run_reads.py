"""Read the run of an agent from its Claude Code transcripts: its
`.meta.json`, its entries and the blocks, texts, call results, messages and
notifications they give, and the session its transcripts belong to."""

import json
import re
from dataclasses import dataclass
from enum import Enum
from functools import cache
from pathlib import Path
from typing import Any

from controlled_markdown import mctx
from transcripts import (Entry, Refused, agent_id, chain, is_subagent,
                         main_transcript, read_entries, session_directory,
                         subagent_transcripts)

MAIN = "main"
AGENT_MESSAGE = re.compile(r'<agent-message from="([^"]+)"')
AGENT_MESSAGE_END = "</agent-message>"
NOTIFICATION = re.compile(r"<task-notification>(.*?)</task-notification>", re.S)
# The statuses of an Agent call's result where the agent runs in the
# background, and where it ran in the foreground and reported.
BACKGROUND = "async_launched"
FOREGROUND_DONE = "completed"
TAG = re.compile(r"<(task-id|tool-use-id)>([^<]+)</\1>")


class Status(Enum):
    """The statuses the harness gives a notification."""
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"
    STOPPED = "stopped"
    RUNNING = "running"


@dataclass
class Notification:
    """A notification the harness gives a run: the task id and tool-use id
    it names, its status as it words it, its note and its result, each None
    where it gives none."""
    ids: list[str]
    status_text: str | None
    note: str | None
    result: str | None

    @property
    def status(self) -> Status | None:
        """Its status, or None where it gives none or one of no known form."""
        known = {s.value: s for s in Status}
        return known.get(self.status_text or "")


def read_meta(path: Path) -> dict[str, Any] | None:
    """The `.meta.json` of the run of the subagent whose transcript is at
    `path`: each key as the earliest of its transcripts' `.meta.json` files
    that gives the key gives it, or None where none of them has one."""
    metas = [json.loads(m.read_text()) for p in chain(path)
             if (m := p.with_suffix(".meta.json")).is_file()]
    if not metas:
        return None
    out: dict[str, Any] = {}
    for meta in reversed(metas):
        out.update(meta)
    return out


def subagent_meta(path: Path) -> dict[str, Any]:
    """The `.meta.json` of the subagent whose transcript is at `path`, which
    must give its agent type."""
    meta = read_meta(path)
    if meta is None or "agentType" not in meta:
        raise Refused(mctx("the agent type of `{path}` is unknown: its "
                           ".meta.json is absent or gives none").format(path=path))
    return meta


def run_type(path: Path) -> tuple[str, str]:
    if not is_subagent(path):
        return MAIN, ""
    meta = subagent_meta(path)
    return meta["agentType"], meta.get("description", "")


def parent_id(path: Path) -> str:
    """The agent id of the parent of the agent whose transcript is at
    `path`, or `main`, which its `.meta.json` gives by naming no parent."""
    return subagent_meta(path).get("parentAgentId") or MAIN


def run_entries(path: Path) -> list[Entry]:
    """The entries of the run of the agent whose transcript is at `path`,
    across its transcripts."""
    return [e for p in chain(path) for e in read_entries(p)]


def blocks(entry: Entry, kind: str) -> list[dict[str, Any]]:
    content = (entry.get("message") or {}).get("content")
    if not isinstance(content, list):
        return []
    return [b for b in content if isinstance(b, dict) and b.get("type") == kind]


def text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") == "text")
    return ""


def results_by_call(entries: list[Entry]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for e in entries:
        r = e.get("toolUseResult")
        if e.get("type") != "user" or not isinstance(r, dict):
            continue
        for b in blocks(e, "tool_result"):
            out[b.get("tool_use_id", "")] = r
    return out


def session_of(path: Path) -> Path:
    """The session directory a transcript belongs to."""
    session = path.parents[1] if is_subagent(path) else session_directory(path)
    while is_subagent(session):
        session = session.parent
    return session


@cache
def session_agents(session: Path) -> dict[str, Path]:
    return {agent_id(p): p for p in subagent_transcripts(session)}


def session_transcripts(session: Path) -> list[Path]:
    """The transcripts of `session`: its main transcript, where it has one,
    and those of its subagents."""
    main = main_transcript(session)
    return [*([main] if main.is_file() else []), *session_agents(session).values()]


def is_prompt(entry: Entry) -> bool:
    """Whether an entry gives the model a message: a user entry that answers
    no tool call, or a message queued while the model worked."""
    if entry.get("type") == "attachment":
        return (entry.get("attachment") or {}).get("type") == "queued_command"
    return entry.get("type") == "user" and not blocks(entry, "tool_result")


def message_text(entry: Entry) -> str:
    """The text of a user entry, or of a message queued while the model
    worked."""
    if entry.get("type") == "attachment":
        a = entry.get("attachment") or {}
        return text_of(a.get("prompt")) if a.get("type") == "queued_command" else ""
    return text_of((entry.get("message") or {}).get("content"))


def field_text(body: str, name: str) -> str | None:
    m = re.search(rf"<{name}>(.*?)</{name}>", body, re.S)
    return m.group(1) if m else None


def notifications(entry: Entry) -> list[Notification]:
    out: list[Notification] = []
    for body in NOTIFICATION.findall(message_text(entry)):
        status = field_text(body, "status")
        out.append(Notification([v for _, v in TAG.findall(body)],
                                status and status.strip(), field_text(body, "note"),
                                field_text(body, "result")))
    return out


def agent_messages(entry: Entry) -> list[tuple[str, str]]:
    """The agent id of the sender and the text of each message from an
    agent that `entry` gives."""
    text = message_text(entry)
    out: list[tuple[str, str]] = []
    for m in AGENT_MESSAGE.finditer(text):
        start = text.find(">", m.end()) + 1
        end = text.find(AGENT_MESSAGE_END, start)
        out.append((m.group(1), text[start:end if end >= 0 else None].strip()))
    return out


def notified(entry: Entry) -> list[str]:
    return [v for n in notifications(entry) for v in n.ids]


def parent_label(path: Path) -> str:
    return agent_id(path) if is_subagent(path) else MAIN
