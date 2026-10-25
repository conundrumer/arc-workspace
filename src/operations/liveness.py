"""Whether an attempt runs, has ended or is unknown: one function
(`attempt_state`) over the record of the attempt (`attempts.Attempt`) and
the facts the reads gather outside it (`AttemptFacts`), for the attempts of
every operator and session alike, Claude and native Codex.

With the first condition that holds deciding:

1. The record holds no launch, its coverage is incomplete or an old
   producer may still write (`attempts.Coverage`), a native attempt has no
   work reservation, or a work reservation has no recorded acceptance or
   refusal, so that the submission is uncertain: `Unknown`, held.
2. A work reservation was accepted and has no recorded end. Where its turn
   read (`AttemptFacts.turn`) gives `LIVE`, the attempt is `Running` with
   `Waits.STILL_RUNNING`; where it gives `UNKNOWN`, it is `Unknown`, held;
   where it gives terminal evidence, the turn is over.
3. A descendant of the attempt runs or is unknown, or its own work is
   running (`AttemptFacts.working`): `Running` with `Waits.STILL_RUNNING`.
4. Each ticket of its subject closed after its launch: `Ended`.
5. A Claude attempt whose latest launch, resume, work reservation, stop or
   handback is a stop or handback, and a native attempt, are `Ended`: a
   native attempt's work reservations are all resolved or over by terminal
   evidence.
6. Otherwise `Running`, with `Waits.LIMITED` where the usage limit stopped
   it and `Waits.AT_WORK` where it did not.

A record without a stop or a terminal turn event never ends an attempt, a
stall alert and a lost observer do not, and no read appends one. The
transcript supplies only the lease write times and the usage-limit fact,
and the listing the work of the attempt's own that runs
(`AttemptFacts.working`).

`Ended.refused` is the time of the message to an ended attempt that the
harness refused (`attempt_view.refused_at`).

A `Running` or `Unknown` attempt has a lease (`Running.until`): the latest
write of its transcript, of its descendants' transcripts and of its Codex
rollout, plus `STUCK_SECONDS`.
"""

import shlex
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from controlled_markdown import mctx
from operations import attempts as a
from operations.constants import STUCK_SECONDS
from operations.state import Ended, Running, Unknown, Waits, AttemptState


class CodexEnd(StrEnum):
    DONE = "done"
    DEAD = "dead"
    LIVE = "live"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CodexRead:
    """The read of an attempt's accepted turn: `LIVE` where the turn runs,
    `DEAD` where terminal evidence ends it, `UNKNOWN` where it cannot be
    read, with the failed read's reason. Where its state is unknown,
    `scratch` and `rollout`, its scratch directory and its Codex rollout, are
    as far as they were recovered before the read failed, and `limits` gives
    what could not be."""
    end: CodexEnd
    why: str = ""
    scratch: Path | None = None
    rollout: Path | None = None
    limits: tuple[str, ...] = ()


@dataclass(frozen=True)
class Written:
    """The latest write time of an attempt's sources, `time`, or None where
    none is known, with what could not be read of them (`limits`)."""
    time: float | None
    limits: tuple[str, ...] = ()


@dataclass(frozen=True)
class AttemptFacts:
    """What the reads know of one attempt beside its record, for
    `attempt_state`. `turn` gives the read of its accepted turn with no
    recorded end, called only where there is one; `written` gives the latest
    write time of its sources, with its Codex rollout among them where
    given, and, where `unknown` holds, floored at the time of its launch or
    last resume. `descendants` holds where an agent it launched runs or is
    unknown, `working` where the listing gives work of its own running,
    `outlived` where each ticket of its subject closed after its launch, and
    `limited` where the usage limit stopped it and it has not run since."""
    turn: Callable[[], CodexRead]
    written: Callable[[Path | None, bool], Written]
    descendants: bool = False
    working: bool = False
    outlived: bool = False
    limited: bool = False


def lease(w: Written) -> float | None:
    """The lease that the write time of `w` gives, or None."""
    return None if w.time is None else w.time + STUCK_SECONDS


def uncertain(attempt: a.Attempt) -> str | None:
    """Why the record of `attempt` does not show whether it ran to an end,
    or None where it shows it."""
    if attempt.launch is None:
        return mctx("the record of its attempt shows no launch of it")
    coverage = attempt.coverage
    if coverage is not None and not coverage.complete:
        return mctx("the history imported into the record of its attempt is incomplete ({reason})").format(reason=coverage.reason)
    if coverage is not None and coverage.producer:
        return mctx("an older version of the tool may still be writing the record of its attempt")
    reserved = {e.reservation for e in attempt.events if isinstance(e, a.Reserved)}
    if attempt.launch.transport is a.Transport.NATIVE and not reserved:
        return mctx("the record of its attempt shows no Codex work started for it")
    accepted = {e.reservation for e in attempt.events if isinstance(e, a.Accepted)}
    if reserved & attempt.unresolved - accepted:
        return mctx("the record of its attempt shows neither that Codex took up the work sent for it nor that it refused it")
    return None


def accepted_open(attempt: a.Attempt) -> bool:
    """Whether `attempt` has a work reservation accepted and not recorded as
    ended."""
    return any(isinstance(e, a.Accepted) and e.reservation in attempt.unresolved for e in attempt.events)


def over(attempt: a.Attempt) -> bool:
    """Whether the record of `attempt`, which holds a launch, shows its work
    over: a native attempt has only resolved work reservations or reservations
    over by terminal evidence, and a Claude attempt's latest launch, resume,
    work reservation, stop or handback is a stop or handback."""
    assert attempt.launch is not None
    if attempt.launch.transport is a.Transport.NATIVE:
        return True
    marks = [e for e in attempt.events
             if isinstance(e, (a.Launched, a.Resumed, a.Reserved, a.Stopped, a.HandedBack))]
    return bool(marks) and isinstance(marks[-1], (a.Stopped, a.HandedBack))


def attempt_state(attempt: a.Attempt | None, f: AttemptFacts) -> AttemptState:
    """The state of `attempt`, where it has a record, by the conditions
    above. An attempt with no record is held as unknown."""
    def running(waits: Waits, rollout: Path | None = None) -> Running:
        return Running(waits, lease(f.written(rollout, False)))

    def unknown(why: str, rollout: Path | None = None, limits: tuple[str, ...] = ()) -> Unknown:
        w = f.written(rollout, True)
        return Unknown(unknown_diagnostic(why, (*limits, *w.limits)), lease(w))

    why = mctx("it has no record") if attempt is None else uncertain(attempt)
    if attempt is None or why is not None:
        return unknown(record_text(why or ""))
    if accepted_open(attempt):
        read = f.turn()
        match read.end:
            case CodexEnd.LIVE:
                return running(Waits.STILL_RUNNING, read.rollout)
            case CodexEnd.UNKNOWN:
                return unknown(unknown_text(read), read.rollout, read.limits)
            case CodexEnd.DONE | CodexEnd.DEAD:
                pass
    if f.descendants or f.working:
        return running(Waits.STILL_RUNNING)
    if f.outlived or over(attempt):
        return Ended()
    return running(Waits.LIMITED if f.limited else Waits.AT_WORK)


def unknown_diagnostic(text: str, limits: tuple[str, ...]) -> str:
    """The text `text` on a held attempt of unknown state, with each source
    of activity that could not be read, where the time of its activity then
    rests on the others and on its launch or last resume."""
    if not limits:
        return text
    return text + " " + mctx(
        "Its activity time leaves out what could not be read: {limits}.").format(
            limits="; ".join(limits))


def record_text(why: str) -> str:
    """Why an attempt whose record does not show an end counts as running."""
    return mctx("whether it runs is unknown ({why}), so the attempt counts as running").format(why=why)


def unknown_text(read: CodexRead) -> str:
    """Why an attempt of unknown state counts as running, with the command
    that shows its turn where its scratch path is recovered, and otherwise
    that the path is not."""
    shown = (mctx("`uv run python scripts/codex_agent.py show {scratch}` shows its turn").format(
        scratch=shlex.quote(str(read.scratch))) if read.scratch is not None
        else mctx("its scratch path is not recovered"))
    return mctx("whether a Codex turn runs for it is unknown ({why}), so the attempt counts as "
                "running; {shown}").format(why=read.why, shown=shown)
