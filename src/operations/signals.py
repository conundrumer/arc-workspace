"""The audit signals on a watched agent's run as of a time: the signs a
script can read from the transcripts and the tree that an auditor's
finding may rest on. The monitor's steps do not read them.

Each signal fires, stays quiet, or is undecided with its reason, where the
reads the run's facts come from did not decide an input it needs. A fact
a read left unknown is an `Unknown` with that read's reason."""

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from controlled_markdown import mctx
from operations import reports
from operations.roles import Role
from operations.state import Agent


class Signal(StrEnum):
    """`stall`: its latest turn ended with its work open and no report to
    its parent since that turn began. `over-budget`: its active time is
    past its budget. `unfinished`: its latest reply gives work as left
    open, by a fixed form of the replies of its role. `refused-or-hung`: a
    call of it was refused, or ran past `monitor.HUNG_FACTOR` times its
    usual time. `repeated`: it ran the same Bash command more than once.
    `out-of-scope`: it is an editor
    of a change, and its worktree changed a file its change's Scope does
    not give."""
    STALL = "stall"
    OVER_BUDGET = "over-budget"
    UNFINISHED = "unfinished"
    REFUSED_OR_HUNG = "refused-or-hung"
    REPEATED = "repeated"
    OUT_OF_SCOPE = "out-of-scope"


@dataclass(frozen=True)
class Unknown:
    reason: str


type Known[T] = T | Unknown


@dataclass(frozen=True)
class RunAt:
    """A watched agent's run as of the time `at`. `agent` is its launch,
    with the reports that reached its parent by `at`. `turn` is the start
    and the end of its latest turn by `at`, with None as the end where that
    turn had not ended by `at`, and `open_at_end` whether its own work
    still ran at that end. `active` and `budget` are in seconds, with None
    as the budget where none is in force. `refused` counts its calls the
    harness or the permission classifier refused by `at`, and `hung`
    counts its calls that ran past `monitor.HUNG_FACTOR` times their usual
    time by `at`. `commands` are the Bash commands it ran by `at`, in
    order. `changed` are the files its worktree changed by `at`, and
    `scope` the paths its change's Scope gives, each None where it is no
    editor of a change."""
    agent: Agent
    at: float
    turn: Known[tuple[float, float | None]]
    open_at_end: Known[bool]
    active: Known[float]
    budget: Known[float | None]
    refused: Known[int]
    hung: Known[int]
    commands: Known[tuple[str, ...]]
    changed: Known[frozenset[str]] | None
    scope: Known[frozenset[str]] | None


@dataclass(frozen=True)
class Reading:
    """What a signal gave on a run: whether it fired, or None with the
    reason where it is undecided."""
    signal: Signal
    fired: bool | None
    reason: str | None = None


def decided(signal: Signal, *facts: object) -> Reading | None:
    """The undecided reading of `signal`, on the first of `facts` a read
    left unknown, or None where every one is known."""
    for f in facts:
        if isinstance(f, Unknown):
            return Reading(signal, None, f.reason)
    return None


def stall(r: RunAt) -> Reading:
    if (u := decided(Signal.STALL, r.turn)) is not None:
        return u
    assert not isinstance(r.turn, Unknown)
    start, end = r.turn
    if end is None:
        return Reading(Signal.STALL, False)
    if (u := decided(Signal.STALL, r.open_at_end)) is not None:
        return u
    reported = any(start <= x.time <= r.at for x in r.agent.reports)
    return Reading(Signal.STALL, r.open_at_end is True and not reported)


def over_budget(r: RunAt) -> Reading:
    if (u := decided(Signal.OVER_BUDGET, r.active, r.budget)) is not None:
        return u
    assert not isinstance(r.active, Unknown) and not isinstance(r.budget, Unknown)
    return Reading(Signal.OVER_BUDGET, r.budget is not None and r.active > r.budget)


NO_FORM = mctx("its latest reply is in no fixed form that gives an item as unfinished")


def unfinished(r: RunAt) -> Reading:
    """By the fixed forms `reports` reads: a ticket analyst's reply with an
    item labeled `reports.Label.UNFINISHED`, and a code editor's reply that
    opens with `reports.BUDGET_PASSED`. No form gives an editor's reply
    as finished, so an editor's other replies are undecided, as are the
    replies of the roles no form covers."""
    a = r.agent
    if a.last_report is None:
        return Reading(Signal.UNFINISHED, False)
    if a.role is Role.CODE_EDITOR and reports.budget_passed(a):
        return Reading(Signal.UNFINISHED, True)
    if a.role is Role.TICKET_ANALYST:
        return Reading(Signal.UNFINISHED,
                       reports.items_of(a, [reports.Label.UNFINISHED]) is not None)
    return Reading(Signal.UNFINISHED, None, NO_FORM)


def refused_or_hung(r: RunAt) -> Reading:
    if (u := decided(Signal.REFUSED_OR_HUNG, r.refused, r.hung)) is not None:
        return u
    assert not isinstance(r.refused, Unknown) and not isinstance(r.hung, Unknown)
    return Reading(Signal.REFUSED_OR_HUNG, r.refused + r.hung > 0)


def repeated(r: RunAt) -> Reading:
    if (u := decided(Signal.REPEATED, r.commands)) is not None:
        return u
    assert not isinstance(r.commands, Unknown)
    return Reading(Signal.REPEATED, any(n > 1 for n in Counter(r.commands).values()))


IN_SCOPE_PROSE = mctx("each file it changed is under a path its Scope gives, and the "
                      "Scope's prose decides whether it may change")


BASH_CHANGES = mctx("it ran a Bash command, which may have changed a file")


def out_of_scope(r: RunAt) -> Reading | None:
    """Fires where a changed file is under no path the Scope gives. Where
    each is under one, the Scope's prose, which may give a path as read
    and not changed, decides, so it is undecided. `changed` holds no file a
    Bash command changed, so it is quiet only where the run ran no Bash
    command. None where the agent is no editor of a change."""
    if r.changed is None or r.scope is None:
        return None
    if (u := decided(Signal.OUT_OF_SCOPE, r.changed, r.scope)) is not None:
        return u
    assert not isinstance(r.changed, Unknown) and not isinstance(r.scope, Unknown)
    scope = r.scope
    if any(not any(f == p or f.startswith(f"{p}/") for p in scope) for f in r.changed):
        return Reading(Signal.OUT_OF_SCOPE, True)
    if r.changed:
        return Reading(Signal.OUT_OF_SCOPE, None, IN_SCOPE_PROSE)
    if (u := decided(Signal.OUT_OF_SCOPE, r.commands)) is not None:
        return u
    if r.commands:
        return Reading(Signal.OUT_OF_SCOPE, None, BASH_CHANGES)
    return Reading(Signal.OUT_OF_SCOPE, False)


def signals(r: RunAt) -> tuple[Reading, ...]:
    """The reading of each signal on `r`, in the order of `Signal`."""
    found = [stall(r), over_budget(r), unfinished(r), refused_or_hung(r), repeated(r),
             out_of_scope(r)]
    return tuple(x for x in found if x is not None)
