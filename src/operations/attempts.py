"""Immutable attempt evidence and its order-independent lifecycle projection.

Source identities deduplicate retries. Occurrence times order transitions; an
unresolved submission or incomplete history never proves terminal execution.
"""

from dataclasses import dataclass
from enum import StrEnum
from collections.abc import Iterable

from operations.roles import Described


class Transport(StrEnum):
    CLAUDE = 'claude'
    NATIVE = 'native'


class Terminal(StrEnum):
    COMPLETED = 'completed'
    FAILED = 'failed'
    INTERRUPTED = 'interrupted'


class Outcome(StrEnum):
    ACCEPTED = 'accepted'
    REFUSED = 'refused'


@dataclass(frozen=True, kw_only=True)
class Evidence:
    source: str
    at: float
    agent: str


@dataclass(frozen=True, kw_only=True)
class Launched(Evidence):
    seat: Described
    parent: str | None
    agent_type: str
    transport: Transport
    scratch: str | None = None


@dataclass(frozen=True, kw_only=True)
class Resumed(Evidence):
    parent: str | None


@dataclass(frozen=True, kw_only=True)
class Stopped(Evidence):
    text: str
    killed: bool = False


@dataclass(frozen=True, kw_only=True)
class HandedBack(Evidence):
    text: str


@dataclass(frozen=True, kw_only=True)
class Reserved(Evidence):
    reservation: str
    revision: int


@dataclass(frozen=True, kw_only=True)
class Accepted(Evidence):
    reservation: str
    thread: str
    turn: str
    runtime: str | None = None


@dataclass(frozen=True, kw_only=True)
class RuntimeBound(Evidence):
    thread: str
    runtime: str


@dataclass(frozen=True, kw_only=True)
class TurnEnded(Evidence):
    reservation: str
    status: Terminal


@dataclass(frozen=True, kw_only=True)
class Refused(Evidence):
    reservation: str


@dataclass(frozen=True, kw_only=True)
class Interrupted(Evidence):
    reservation: str


@dataclass(frozen=True, kw_only=True)
class Reported(Evidence):
    revision: int
    digest: str
    text: str | None


@dataclass(frozen=True, kw_only=True)
class Message(Evidence):
    recipient: str
    text: str
    outcome: Outcome
    delivery: str
    call: str
    handback: bool = False


@dataclass(frozen=True, kw_only=True)
class Received(Evidence):
    delivery: str
    revision: int
    thread: str
    turn: str


@dataclass(frozen=True, kw_only=True)
class Coverage(Evidence):
    complete: bool
    reason: str
    producer: bool
    change: str | None = None


type Event = (Launched | Resumed | Stopped | HandedBack | Reserved | Accepted |
              RuntimeBound | TurnEnded | Refused | Interrupted | Reported | Message | Received | Coverage)
EVENTS = (Launched, Resumed, Stopped, HandedBack, Reserved, Accepted, RuntimeBound, TurnEnded,
          Refused, Interrupted, Reported, Message, Received, Coverage)


@dataclass(frozen=True)
class Attempt:
    agent: str
    launch: Launched | None
    events: tuple[Event, ...]
    unresolved: frozenset[str]
    outstanding: tuple[Message, ...]
    receipts: tuple[Received, ...]
    coverage: Coverage | None
    stopped: bool
    inbound: tuple[Message, ...] = ()

    @property
    def held(self) -> bool:
        return bool(self.unresolved) or (self.coverage is not None and (
            not self.coverage.complete or self.coverage.producer))


def fold(events: Iterable[Event]) -> dict[str, Attempt]:
    """Project all endpoints without allowing late evidence to undo a transition."""
    sources: dict[str, Event] = {}
    for event in events:
        old = sources.setdefault(event.source, event)
        if old != event:
            raise ValueError('conflicting attempt source identity')
    ordered = tuple(sorted(sources.values(), key=lambda e: (e.at, e.source)))
    by_agent: dict[str, list[Event]] = {}
    to_agent: dict[str, list[Message]] = {}
    for e in ordered:
        by_agent.setdefault(e.agent, []).append(e)
        if isinstance(e, Message):
            to_agent.setdefault(e.recipient, []).append(e)
    out = {}
    for agent in sorted(by_agent.keys() | to_agent.keys()):
        own = tuple(by_agent.get(agent, ()))
        launches = [e for e in own if isinstance(e, Launched)]
        if launches and any((e.seat, e.parent, e.transport) != (
                launches[0].seat, launches[0].parent, launches[0].transport) for e in launches):
            raise ValueError('conflicting attempt identity')
        reservations = {e.reservation for e in own if isinstance(e, (Reserved, Accepted))}
        resolved = {e.reservation for e in own if isinstance(e, (TurnEnded, Refused))}
        receipts = tuple(e for e in own if isinstance(e, Received))
        inbound = tuple(e for e in to_agent.get(agent, ()) if not e.handback)
        incoming = tuple(e for e in inbound if e.outcome is Outcome.ACCEPTED)
        delivered = {e.delivery for e in receipts}
        coverage = [e for e in own if isinstance(e, Coverage)]
        transitions = [e for e in own if isinstance(e, (Launched, Resumed, Stopped, HandedBack))]
        out[agent] = Attempt(agent, launches[0] if launches else None, own,
            frozenset(reservations - resolved), tuple(e for e in incoming if e.delivery not in delivered),
            receipts, coverage[-1] if coverage else None,
            bool(transitions and isinstance(transitions[-1], (Stopped, HandedBack))), inbound)
    return out
