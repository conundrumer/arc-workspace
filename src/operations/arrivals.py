"""The messages that arrived at the session's operators: those of their
transcripts and the lines of the session's store (`line_store`), each
line attributed to the operator it would have reached as a message."""

from collections.abc import Mapping
from dataclasses import dataclass

from operations.line_store import recorded_lines
from operations.state import Message, State, memoized_by_transcripts


def arrived(state: State) -> list[Message]:
    """`State.transcripts.messages` and the lines of the session's store
    (`stored_messages`), in the order they arrived."""
    return sorted([*state.transcripts.messages, *stored_messages(state)], key=lambda m: m.time)


def received(state: State) -> list[Message]:
    """The messages that reached `me`, its brief included, or an operator
    of `State.taken_up`, the lines of the store `recipient` gives either
    included, in the order they arrived."""
    return [m for m in arrived(state) if m.operator == state.me or m.operator in state.taken_up]


@memoized_by_transcripts
def stored_messages(state: State) -> tuple[Message, ...]:
    """Each line of the session's store, read once for each read of the
    transcripts, as a message of the coordinator's to the operator
    `recipient` gives at the time of its record."""
    spans = operator_spans(state)
    return tuple(Message(recipient(state, spans, t), t, None, text, stored=True)
                 for t, text in recorded_lines(state.main_tree, state.session))


@dataclass(frozen=True)
class Span:
    """The time of an operator's launch, the time of its first message of
    `TranscriptsRead.messages`, its brief, and the time of its last call,
    or of its launch where it made none."""
    launched: float
    last_call: float


def operator_spans(state: State) -> dict[str, Span]:
    """The `Span` of each operator of `State.operators` that has a
    message."""
    ops = set(state.operators)
    launched: dict[str, float] = {}
    for m in state.transcripts.messages:
        if m.operator in ops:
            launched[m.operator] = min(launched.get(m.operator, m.time), m.time)
    last = dict(launched)
    for c in state.transcripts.calls:
        if c.operator in last:
            last[c.operator] = max(last[c.operator], c.time)
    return {o: Span(t, last[o]) for o, t in launched.items()}


def recipient(state: State, spans: Mapping[str, Span], time: float) -> str:
    """The operator a line of the coordinator's recorded at `time` goes to,
    as it would in a message to the running operator launcher at that
    time: of the operators of `State.operators` with a span in `spans`,
    the one launched last at or before `time` that ran at `time`, or,
    where none ran, the first one launched after it, or `me` where
    neither is one. An operator ran at `time` where it is `me`, its work
    is open, or its last call is at or after `time`."""
    known = [o for o in state.operators if o in spans]
    ran = [o for o in known if spans[o].launched <= time
           and (o == state.me or o in state.open_operators or spans[o].last_call >= time)]
    if ran:
        return ran[-1]
    return next((o for o in known if spans[o].launched > time), state.me)
