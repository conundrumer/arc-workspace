"""The harness's delivery of a message and of a report: the forms of a
SendMessage result and of a SubagentHandback result, and whether a message
to a run that the harness accepted waits for delivery."""

from enum import Enum
from pathlib import Path
from typing import Any

from run_reads import (blocks, read_meta, run_sessions)
from transcripts import agent_id
from transcript_entries import epoch, read_entries
from session_changes import changed_since, timed_entries


class Delivery(Enum):
    """What the harness did with a SendMessage call's message, by the
    opening of the message of its result: it resumed the agent it was sent
    to, or queued the message to a running one."""
    RESUMED = "Resuming agent"
    QUEUED = "Message queued"


def delivery(result: dict[str, Any]) -> Delivery | None:
    """What the harness did with the message of the SendMessage call whose
    result is `result`, or None where its message opens with neither."""
    message = str(result.get("message", ""))
    return next((d for d in Delivery if message.startswith(d.value)), None)


DELIVERED = "Report delivered"
"""The opening of the message of a SubagentHandback result where the
harness accepted the report."""


def succeeded(result: dict[str, Any]) -> bool:
    return result.get("success") is True


def report_delivered(result: dict[str, Any]) -> bool:
    """Whether the message of `result`, the result of a SubagentHandback
    call that succeeded, says the harness accepted its report."""
    return str(result.get("message", "")).startswith(DELIVERED)


def handback_accepted(result: dict[str, Any]) -> bool:
    """Whether `result`, a tool result, is that of a SubagentHandback call
    whose report the harness accepted."""
    return succeeded(result) and report_delivered(result)


def last_delivered(path: Path) -> float:
    """The time of the latest entry the harness delivered into the run at
    `path`, its latest timestamped `user` entry, or 0 where it has none."""
    return max((epoch(e["timestamp"]) for e in timed_entries(path) if e.get("type") == "user"),
               default=0.0)


def accepted_after(path: Path, since: float, undecided: list[str]) -> bool:
    """Whether a transcript of the sessions of the run at `path` holds a
    message to that run that the harness accepted after `since`, as
    `operate.py --help next` gives one."""
    # `agent_launches` reads, through `agent_resumes`, the forms of a result
    # this module gives, so it is imported here, at the call.
    from agent_launches import callees
    names = {agent_id(path)}
    if (name := (read_meta(path) or {}).get("name")):
        names.add(str(name))
    mine = callees(path, undecided)
    for p in changed_since(run_sessions(path), since):
        hands_back = agent_id(p) in mine
        words = names | {d.value for d in Delivery}
        if hands_back:
            words |= {"SubagentHandback", DELIVERED}
        entries = [e for e in read_entries(p, naming=words) if e.get("timestamp")]
        results = {b.get("tool_use_id", ""): (r, epoch(e["timestamp"])) for e in entries
                   if e.get("type") == "user" and isinstance(r := e.get("toolUseResult"), dict)
                   for b in blocks(e, "tool_result")}
        for e in entries:
            if e.get("type") != "assistant":
                continue
            for b in blocks(e, "tool_use"):
                r, t = results.get(b.get("id", ""), ({}, 0.0))
                if t <= since or not succeeded(r):
                    continue
                if b.get("name") == "SubagentHandback" and hands_back and report_delivered(r):
                    return True
                if (b.get("name") == "SendMessage"
                        and str((b.get("input") or {}).get("to", "")) in names
                        and delivery(r) is not None):
                    return True
    return False
