"""The harness's delivery of a message and of a report: the forms of a
SendMessage result and of a SubagentHandback result, and the time of the
latest entry it delivered into a run."""

from enum import Enum
from pathlib import Path
from typing import Any

from transcript_entries import epoch
from session_changes import timed_entries


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
