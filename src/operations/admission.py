"""The admission of an untaken ticket, and of a ticket a ticket analyst
judges for the session's line of work, under the run scripts' `takes`,
the `Op pause.` and `Op scope:` lines and the usage pace, with the hold
(`parties.Hold`) that refuses each ticket it does not admit.

The run scripts' `takes` admit the tickets of `taking.expedited` and
those a run script gives, and every ticket where no script defines
`takes` (`passing`). While an `Op scope: own.` line stands, or no
`Op scope:` line came (`directives.own_scope`), the `Op scope:` line
admits only those of `taking.held_work`, of `taking.allowed` and of
`taking.own_work`; while an `Op pause.` line stands
(`directives.paused`), only those of `taking.held_work` and of
`taking.allowed` (`scope_admits`). Past the usage pace
(`start_holds.past_pace`), it admits none."""

from collections.abc import Callable

from operations.directives import own_scope, paused
from operations.pacing import Pace
from operations.parties import Hold
from operations.start_holds import past_pace
from operations.state import State, memoized
from operations.taking import allowed, expedited, follow_ups, held_work, own_work


def scope_hold(state: State) -> Hold:
    """The line of the user that holds a ticket the `Op pause.` and
    `Op scope:` lines do not admit."""
    return Hold.PAUSE if paused(state) else Hold.OWN_SCOPE


@memoized
def refusal(state: State) -> Callable[[str], Hold | None]:
    """The hold that refuses to admit an untaken ticket, the first that
    does of the run scripts' `takes` (`passing`), the `Op pause.` and
    `Op scope:` lines (`scope_admits`), and the usage pace, or None where
    the operator may admit it."""
    passes, held = passing(state)
    clear = scope_admits(state)
    past = past_pace(state)
    scope = scope_hold(state)

    def of(n: str) -> Hold | None:
        if not passes(n):
            return Hold.TAKES
        if not held(n) and not clear(n):
            return scope
        return Hold.PACE if past else None
    return of


@memoized
def admits(state: State) -> Callable[[str], bool]:
    """Whether the operator may admit an untaken ticket: `refusal` gives no
    hold of it."""
    refused = refusal(state)
    return lambda n: refused(n) is None


def unpaced(state: State, clear: Callable[[str], bool]) -> Callable[[str], bool]:
    """Whether the lines other than `Op pace:` admit a ticket that `clear`
    admits: one `passing` passes, of `held_work` or of `allowed` always,
    and any other that `clear` admits."""
    passes, held = passing(state)
    return lambda n: passes(n) and (held(n) or clear(n))


@memoized
def scope_admits(state: State) -> Callable[[str], bool]:
    """Whether the `Op pause.` and `Op scope:` lines admit a ticket: one of
    `allowed` while an `Op pause.` line stands; otherwise, while
    `directives.own_scope` holds, one of `allowed` or of `own_work`, and
    any where it does not."""
    if paused(state):
        return allowed(state).__contains__
    if not own_scope(state):
        return lambda _: True
    return in_scope(state).__contains__


def in_scope(state: State) -> set[str]:
    """The tickets the `Op scope: own.` line admits: those of `allowed` and
    of `own_work`."""
    return allowed(state) | own_work(state)


@memoized
def passing(state: State) -> tuple[Callable[[str], bool], Callable[[str], bool]]:
    """Whether the `takes` of the run scripts admit a ticket, with those of
    `expedited`, every ticket where no script defines `takes`, and whether
    it is one of `held_work` or of `allowed`."""
    admitted = state.computed.admitted()
    runs = None if admitted is None else set(admitted) | expedited(state)
    held = held_work(state) | allowed(state)
    return (lambda n: runs is None or n in runs), held.__contains__


def pace_held(state: State, numbers: list[str]) -> Pace | None:
    """The pace, where it alone holds back one of `numbers`: one `admits`
    or `judging` would pass but for the pace."""
    if not past_pace(state):
        return None
    clear = unpaced(state, scope_admits(state))
    pending = judge_scope(state)
    judge = unpaced(state, pending)
    return (state.computed.pace if any(clear(n) or (pending(n) and judge(n)) for n in numbers)
            else None)


def judge_hold(state: State) -> Callable[[str], Hold | None]:
    """The hold that keeps the operator from launching a ticket analyst to
    judge whether the session's line of work needs a ticket: the line of
    the user where `judge_scope` does not give it, the run scripts'
    `takes` where `unpaced` does not pass it, and the usage pace past it
    (`start_holds.past_pace`); None where none does."""
    pending = judge_scope(state)
    rule = unpaced(state, pending)
    past = past_pace(state)
    scope = scope_hold(state)

    def of(n: str) -> Hold | None:
        if not pending(n):
            return scope
        if not rule(n):
            return Hold.TAKES
        return Hold.PACE if past else None
    return of


def judging(state: State) -> Callable[[str], bool]:
    """Whether the operator may launch a ticket analyst to judge whether
    the session's line of work needs a ticket: `judge_hold` gives no hold
    of it."""
    held = judge_hold(state)
    return lambda n: held(n) is None


def judge_scope(state: State) -> Callable[[str], bool]:
    """Whether a ticket is one of `follow_ups` while `directives.own_scope`
    holds and no `Op pause.` line stands."""
    if not own_scope(state) or paused(state):
        return lambda _: False
    return follow_ups(state).__contains__
