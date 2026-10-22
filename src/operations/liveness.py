"""Whether an attempt runs, has ended with or without a result, or is
unknown: one function (`attempt_state`) over the facts the reads gather on
the attempt (`AttemptFacts`), for the attempts of every operator alike.

Stage 1, liveness, with the first condition that holds deciding:

1. The listing gives its work running: `Running`, with the `Waits` its sign
   gives where the sign is pending and `Waits.STILL_RUNNING` where it is not.
2. Each ticket of its subject closed after its launch: `Ended`.
3. It is an end candidate: its sign is not pending, a stall alert fired on
   it, it is of another operator and its work is no longer open, or its
   turn ended idle while its sign is at work or still running. Where its
   Codex read is `LIVE` it is `Running` with `Waits.STILL_RUNNING`, where
   that is `UNKNOWN` it is `Unknown`, and where it is `DONE` or `DEAD`, or
   the attempt is no Codex attempt, it is `Ended`. No other attempt is read
   for Codex.
4. Otherwise `Running` with the `Waits` its sign gives, which includes
   `Waits.LIMITED` for an attempt the usage limit stopped.

Stage 2, the refusal, for an `Ended` attempt alone: `Ended.refused` is the
time of the SendMessage to it that the harness refused, where
`completion.refusal_of` gives one.

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
from operations.constants import STUCK_SECONDS
from operations.state import Ended, Report, Running, Unknown, Waits, AttemptState


class CodexEnd(StrEnum):
    DONE = "done"
    DEAD = "dead"
    LIVE = "live"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CodexRead:
    """An attempt's completion or thread state, with the failed walk's reason.
    Where its state is unknown, `scratch` and `rollout`, its scratch
    directory and its Codex rollout, are as far as they were recovered
    before the read failed, and `limits` gives what could not be."""
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
    """What the reads know of one attempt, for `attempt_state`.
    `waits` is what its sign gives (`agent_reports.last_sign`): None where
    the sign is not pending. `report` gives the report an end adds, and
    `codex` its Codex read, each read on use; `written` gives the latest
    write time of its sources, with its Codex rollout `rollout` among them
    where given, and, where `unknown` holds, floored at the time of its
    launch or last resume. `listed` holds where the listing gives its work
    running, `idle` where its own transcript shows its turn ended idle,
    `stalled` where a stall alert fired on it and its final reply ended
    it, `outlived` where each ticket of its subject closed after its
    launch, and `elsewhere` where it is of another operator and its work
    is no longer open. `refused` is the time of its latest refused
    SendMessage (`completion.refusal_of`)."""
    waits: Waits | None
    report: Callable[[], Report | None]
    codex: Callable[[], CodexRead]
    written: Callable[[Path | None, bool], Written]
    refused: float | None = None
    listed: bool = False
    idle: bool = False
    stalled: bool = False
    outlived: bool = False
    elsewhere: bool = False


def lease(w: Written) -> float | None:
    """The lease that the write time of `w` gives, or None."""
    return None if w.time is None else w.time + STUCK_SECONDS


def attempt_state(f: AttemptFacts) -> AttemptState:
    """The state of the attempt `f` gives, by the two stages above."""
    def running() -> Running:
        return Running(f.waits or Waits.STILL_RUNNING, lease(f.written(None, False)))

    if f.listed:
        return running()
    if f.outlived:
        return ended(f)
    candidate = (f.waits is None or f.stalled or f.elsewhere
                 or (f.idle and f.waits in (Waits.AT_WORK, Waits.STILL_RUNNING)))
    if not candidate:
        return running()
    read = f.codex()
    match read.end:
        case CodexEnd.LIVE:
            return Running(Waits.STILL_RUNNING, lease(f.written(read.rollout, False)))
        case CodexEnd.UNKNOWN:
            w = f.written(read.rollout, True)
            return Unknown(unknown_diagnostic(read, (*read.limits, *w.limits)), lease(w))
        case CodexEnd.DONE | CodexEnd.DEAD:
            return ended(f)


def ended(f: AttemptFacts) -> Ended:
    """`Ended` for the attempt `f` gives, with the refusal of stage 2."""
    return Ended(f.report(), f.refused)


def unknown_diagnostic(read: CodexRead, limits: tuple[str, ...]) -> str:
    """The text on a held attempt of unknown state (`unknown_text`), with
    each source of activity that could not be read, where the time
    of its activity then rests on the others and on its launch or last
    resume."""
    if not limits:
        return unknown_text(read)
    return unknown_text(read) + " " + mctx(
        "Its activity time leaves out what could not be read: {limits}.").format(
            limits="; ".join(limits))


def unknown_text(read: CodexRead) -> str:
    """Why an attempt of unknown state counts as running, with the command
    that shows its turn where its scratch path is recovered, and otherwise
    that the path is not."""
    shown = (mctx("`uv run python scripts/codex_agent.py show {scratch}` shows its turn").format(
        scratch=shlex.quote(str(read.scratch))) if read.scratch is not None
        else mctx("its scratch path is not recovered"))
    return mctx("whether a Codex turn runs for it is unknown ({why}), so the attempt counts as "
                "running; {shown}").format(why=read.why, shown=shown)
