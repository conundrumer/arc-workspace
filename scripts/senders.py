"""Who a message an agent's run receives is from: its parent, an agent it did
not launch, another sender, or one that is unknown, as
`profile_runs.py --help messages` gives them."""

from enum import Enum
from pathlib import Path

from run_reads import (AGENT_MESSAGE, MAIN, NOTIFICATION, member, message_text,
                       text_of, type_in)
from transcript_entries import Entry

# The start of the text of the entry the harness writes where the user
# interrupts a run.
INTERRUPTED = "[Request interrupted by user"


def is_interrupt_note(entry: Entry) -> bool:
    """Whether `entry` is the harness's note that the user interrupted the
    run."""
    return entry.get("type") == "user" and text_of(
        (entry.get("message") or {}).get("content")).startswith(INTERRUPTED)


class Origin(Enum):
    """The kinds of origin the harness gives a message it delivers to an
    agent's run: a notification of the agent's backgrounded work, and a
    message from the coordinator, the user or another agent."""
    TASK_NOTIFICATION = "task-notification"
    COORDINATOR = "coordinator"
    HUMAN = "human"
    PEER = "peer"


def origin(entry: Entry) -> tuple[str | None, Origin | None]:
    """The origin kind the harness gives `entry`, on the entry or, for a
    message queued while the model worked, on its attachment, with its
    member of `Origin`, None where it is no member."""
    given = (entry.get("attachment") or {}) if entry.get("type") == "attachment" else entry
    kind = (given.get("origin") or {}).get("kind")
    return kind, member(Origin, kind)


def is_notification(entry: Entry) -> bool:
    """Whether `entry` is a notification of the agent's backgrounded work."""
    return (origin(entry)[1] is Origin.TASK_NOTIFICATION
            or bool(NOTIFICATION.search(message_text(entry))))


def is_harness_note(entry: Entry) -> bool:
    """Whether `entry` is a note the harness writes into the run, such as a
    system reminder or a hook's feedback, which no sender sent."""
    return bool(entry.get("isMeta")) and origin(entry)[0] is None


class Sender(Enum):
    """Who a message after a run's brief is from, as `profile_runs.py --help messages` gives it."""
    PARENT = "parent"
    AGENT = "agent"
    OTHER = "other"
    UNKNOWN = "unknown"


def sender(entry: Entry, parent: str, children: frozenset[str],
           sessions: list[Path]) -> Sender:
    """Who a message after a run's brief is from, where `parent` is the
    agent id of the run's parent or `main`, `children` the agent ids of
    the agents the run launched, and `sessions` the sessions of the run."""
    text = message_text(entry)
    queued = entry.get("type") == "attachment"
    kind, given = origin(entry)
    if kind is not None and given is None:
        return Sender.UNKNOWN
    from_main = Sender.PARENT if parent == MAIN else Sender.OTHER
    if is_notification(entry):
        return Sender.OTHER
    if given is Origin.COORDINATOR:
        return from_main
    if given is Origin.HUMAN:
        return Sender.OTHER
    if given is Origin.PEER or queued:
        m = AGENT_MESSAGE.search(text)
        if m:
            return sent_by(m.group(1), parent, children, sessions)
        if queued:
            return from_main
        return Sender.UNKNOWN
    if entry.get("isMeta") or entry.get("isCompactSummary") or is_interrupt_note(entry):
        return Sender.OTHER
    return Sender.UNKNOWN


def sent_by(agent: str, parent: str, children: frozenset[str],
            sessions: list[Path]) -> Sender:
    """Who a message the agent `agent` sent is from, for a run whose parent
    is `parent` and which launched the agents `children`."""
    if agent == parent:
        return Sender.PARENT
    if agent in children:
        return Sender.OTHER
    if type_in(sessions, agent) is None:
        return Sender.UNKNOWN
    return Sender.AGENT
