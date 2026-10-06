"""Who a message to a running agent is from: its parent, an agent it did
not launch, another sender, or one that is unknown, as the HELP of
`profile_runs` gives them."""

from enum import Enum

from run_reads import AGENT_MESSAGE, MAIN, NOTIFICATION, message_text
from transcripts import Entry

# The start of the text of the entry the harness writes where the user
# interrupts a run.
INTERRUPTED = "[Request interrupted by user"


class Origin(Enum):
    """The kinds of origin the harness gives a message it delivers to a
    running agent: a notification of the agent's backgrounded work, and a
    message from the coordinator, the user or another agent."""
    TASK_NOTIFICATION = "task-notification"
    COORDINATOR = "coordinator"
    HUMAN = "human"
    PEER = "peer"


class Sender(Enum):
    """Who a message after a run's brief is from, as HELP gives it."""
    PARENT = "parent"
    AGENT = "agent"
    OTHER = "other"
    UNKNOWN = "unknown"


def sender(entry: Entry, parent: str, children: frozenset[str]) -> Sender:
    """Who a message after a run's brief is from, where `parent` is the
    agent id of the run's parent or `main`, and `children` the agent ids of
    the agents the run launched."""
    text = message_text(entry)
    queued = entry.get("type") == "attachment"
    given = (entry.get("attachment") or {}) if queued else entry
    kind = (given.get("origin") or {}).get("kind")
    if kind is not None and kind not in Origin:
        return Sender.UNKNOWN
    origin = None if kind is None else Origin(kind)
    from_main = Sender.PARENT if parent == MAIN else Sender.OTHER
    if origin is Origin.TASK_NOTIFICATION or NOTIFICATION.search(text):
        return Sender.OTHER
    if origin is Origin.COORDINATOR:
        return from_main
    if origin is Origin.HUMAN:
        return Sender.OTHER
    if origin is Origin.PEER or queued:
        m = AGENT_MESSAGE.search(text)
        if m:
            return sent_by(m.group(1), parent, children)
        if queued:
            return from_main
        return Sender.UNKNOWN
    if entry.get("isMeta") or entry.get("isCompactSummary") or text.startswith(INTERRUPTED):
        return Sender.OTHER
    return Sender.UNKNOWN


def sent_by(agent: str, parent: str, children: frozenset[str]) -> Sender:
    """Who a message the agent `agent` sent is from, for a run whose parent
    is `parent` and which launched the agents `children`."""
    if agent == parent:
        return Sender.PARENT
    return Sender.OTHER if agent in children else Sender.AGENT
