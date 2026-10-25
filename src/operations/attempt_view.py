"""What the record of an attempt (`operations.attempts.Attempt`) gives of an
`state.Agent`, for the agents of every operator and session alike: the time
of its launch or last resume (`since`), the operator its notification goes to
(`notified`), its reports (`claude_reports`, `recorded_reports`), the
refusal of a message to it (`refused_at`), and whether an operator's message
reaches it (`reachable`). Each is a function of the record alone, so a
launch read from a transcript and a native child read from a store get the
same values."""

from collections.abc import Sequence

from operations import attempts as a
from operations.state import Report


def activation(attempt: a.Attempt) -> a.Launched | a.Resumed | None:
    """The latest launch or resume of `attempt`, or None where its record
    holds none."""
    return next((e for e in reversed(attempt.events) if isinstance(e, (a.Launched, a.Resumed))), None)


def since(attempt: a.Attempt) -> float | None:
    """The time of the latest launch or resume of `attempt`, or None where
    its record holds none."""
    latest = activation(attempt)
    return None if latest is None else latest.at


def notified(attempt: a.Attempt) -> str | None:
    """The agent that launched or last resumed `attempt`, whose notification
    of its end and whose messages the attempt answers, or None where its
    record holds no launch or resume."""
    latest = activation(attempt)
    return None if latest is None else latest.parent


def claude_reports(attempt: a.Attempt) -> tuple[Report, ...]:
    """The reports of a Claude attempt, one for each stretch from a launch
    or a resume to the next: the latest handback of the stretch, or, where
    it has none, the text of its latest stop that has text."""
    out: list[Report] = []
    best: a.HandedBack | a.Stopped | None = None
    for event in attempt.events:
        if isinstance(event, (a.Launched, a.Resumed)):
            if best is not None:
                out.append(Report(best.at, best.text))
            best = None
        elif isinstance(event, a.HandedBack) or (isinstance(event, a.Stopped) and event.text.strip()):
            if not isinstance(best, a.HandedBack) or isinstance(event, a.HandedBack):
                best = event
    if best is not None:
        out.append(Report(best.at, best.text))
    return tuple(out)


def current_revision(attempt: a.Attempt) -> int | None:
    """The revision of the latest work reservation of `attempt`, or None
    where it has none."""
    return max((e.revision for e in attempt.events if isinstance(e, a.Reserved)), default=None)


def recorded_reports(attempt: a.Attempt) -> tuple[tuple[a.Reported, bool], ...]:
    """The validated reports of a native attempt, each with whether it is the
    current report: one of its latest revision, whose latest turn
    completed. An interruption or a later revision invalidates the report of
    an earlier turn, which stays among the earlier reports."""
    revision = current_revision(attempt)
    tokens = {e.reservation for e in attempt.events if isinstance(e, a.Reserved) and e.revision == revision}
    ends = [e for e in attempt.events if isinstance(e, a.TurnEnded) and e.reservation in tokens]
    complete = bool(ends) and ends[-1].status is a.Terminal.COMPLETED
    return tuple((e, e.revision == revision and complete)
                 for e in attempt.events if isinstance(e, a.Reported))


def refused_at(attempt: a.Attempt, launched: float, reports: Sequence[Report]) -> float | None:
    """The time of the latest message to `attempt` that the record holds,
    where the harness refused it, it is later than `launched`, the time of
    its launch or last resume, and no report of `reports` is later than it,
    and None otherwise: a message the harness took after a refusal gives no
    refusal."""
    latest = attempt.inbound[-1] if attempt.inbound else None
    if (latest is not None and latest.outcome is a.Outcome.REFUSED and latest.at > launched
            and not any(r.time > latest.at for r in reports)):
        return latest.at
    return None


def reachable(attempt: a.Attempt) -> bool:
    """Whether an operator's SendMessage reaches `attempt`: a Claude attempt,
    a Codex launcher included. A native child takes a message only from its
    sender in its native tree (`codex_ticket.Store.target`)."""
    return attempt.launch is None or attempt.launch.transport is a.Transport.CLAUDE


def sent_to(attempt: a.Attempt) -> frozenset[str]:
    """The agents that `attempt` sent a message the harness took."""
    return frozenset(e.recipient for e in attempt.events
                     if isinstance(e, a.Message) and e.outcome is a.Outcome.ACCEPTED)
