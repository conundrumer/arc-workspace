"""The take of untaken changes, and the party each change ready to take
waits on where a step takes it not (`left`).

A change of `taking.purview` is ready once each ticket of its
`depends-on` is closed (`ready`). The operator takes the ready changes
that `admission.admits` passes or that were taken before, those of `lead`
first (`takeable`), and none past the usage pace. While an `Op pause.`
line stands, a step takes, of the changes neither of `lead` nor taken
before, only the first (`batch`), and a step takes the changes of `batch`
up to the first whose budget `Computed.budgets` does not give (`reach`).
A change under `tickets/blocked/` is taken back on an `Op merge:` line
that came after its last move there (`take`)."""

from collections.abc import Callable, Mapping

from controlled_markdown import mctx
from operations import rank
from operations.admission import refusal
from operations.change_budget import TAKE_NOTE, budget_fields, with_cost
from operations.directives import Directive, numbers, paused
from operations.log_commands import log
from operations.parties import Hold, OnTicket, Party
from operations.start_holds import past_pace
from operations.state import State, Ticket, memoized
from operations.steps import Bash, Step, Undecided
from operations.taking import expedited, moves, purview, status_since, taken_before
from operations.tracker import closed, exits, wait_line
from ticketing.exits import Exit
from ticketing.vocabulary import Kind, Status


def boosted(state: State) -> set[str]:
    """The changes that settle an `interference` ticket, which the
    operator takes ahead of the others."""
    out: set[str] = set()
    for t in state.tracker.tickets.values():
        line = wait_line(t) if t.kind is Kind.INTERFERENCE else None
        if line is not None and line.on_change is not None:
            out.add(line.on_change)
    return out


def ready(state: State) -> list[Ticket]:
    """The untaken changes of `purview` whose `depends-on` are closed."""
    return [t for t, awaited in awaiting(state) if not awaited]


def awaiting(state: State) -> list[tuple[Ticket, list[str]]]:
    """Each ticket of `purview` that `Exit.TAKE` takes out of its status,
    with the tickets of its `depends-on` that are not closed."""
    return [(t, [d for d in t.depends_on if not closed(state, d)]) for n in sorted(purview(state))
            if (t := state.tracker.tickets.get(n)) is not None and Exit.TAKE in exits(state, t).by]


def lead(state: State) -> set[str]:
    """The changes the operator takes ahead of the others."""
    return boosted(state) | expedited(state)


def ready_hold(state: State) -> Callable[[Ticket], Hold | None]:
    """The hold that keeps a change of `ready` out of `takeable`: the hold
    `admission.refusal` gives of a change not taken before, and otherwise
    the usage pace past it; None where none does."""
    refused = refusal(state)
    past = past_pace(state)

    def of(t: Ticket) -> Hold | None:
        if not taken_before(t) and (h := refused(t.number)) is not None:
            return h
        return Hold.PACE if past else None
    return of


def takeable(state: State) -> list[Ticket]:
    """The changes of `ready` that `ready_hold` holds not, `lead` first,
    then in rank order (`rank.ranking`)."""
    held = ready_hold(state)
    found = [t for t in ready(state) if held(t) is None]
    if not found:
        return []
    first = lead(state)
    key = rank.ranking(state)
    return sorted(found, key=lambda t: (t.number not in first, key(t)))


def waiting(state: State) -> list[tuple[str, list[str]]]:
    """Each untaken `change` of `purview` not taken for its `depends-on`, with
    the tickets it waits for."""
    return [(t.number, awaited) for t, awaited in awaiting(state) if awaited]


@memoized
def batched(state: State) -> tuple[tuple[Ticket, ...], Mapping[str, Hold]]:
    """The changes of `takeable` that one step of `take` takes, as `take`
    gives them, and each change of `takeable` it leaves out, by number,
    with the `Op pause.` line that holds it."""
    free = not paused(state)
    first = lead(state)
    out: list[Ticket] = []
    left: dict[str, Hold] = {}
    paced = False
    for t in takeable(state):
        if t.number in first or taken_before(t):
            out.append(t)
        elif free or not paced:
            out.append(t)
            paced = True
        else:
            left[t.number] = Hold.PAUSE
    return tuple(out), left


def batch(state: State) -> list[Ticket]:
    """The changes of `takeable` that one step of `take` takes (`batched`)."""
    return list(batched(state)[0])


@memoized
def reach(state: State) -> tuple[Ticket, ...]:
    """The changes of `batch` that one step of `take` acts on: each before
    the first whose budget `Computed.budgets` does not give, or, where the
    first of `batch` has no budget, that change alone."""
    out: list[Ticket] = []
    for t in batch(state):
        if t.number not in state.computed.budgets:
            return tuple(out or [t])
        out.append(t)
    return tuple(out)


@memoized
def left(state: State) -> Mapping[str, Party]:
    """The party each change of `ready` that `reach` leaves out waits on,
    by number: the hold of `ready_hold`, the `Op pause.` line where
    `batched` leaves it out, and otherwise the first change of `reach`."""
    held = ready_hold(state)
    out: dict[str, Party] = {t.number: h for t in ready(state) if (h := held(t)) is not None}
    kept, paused_out = batched(state)
    out.update(paused_out)
    taken = reach(state)
    out.update({t.number: OnTicket(taken[0].number) for t in kept[len(taken):]})
    return out


def take(state: State) -> Step | None:
    """The take of each change of `takeable`, in its order, up to the first
    whose budget `Computed.budgets` does not give (`reach`), or, where the
    first has no budget, `Undecided` on it. Where an `Op pause.` line
    stands, a step takes, of the changes neither of `lead` nor
    `taken_before`, only the first, so that the pause is read again before
    each further take."""
    commands: list[str] = []
    taken: list[str] = []
    for t in reach(state):
        b = state.computed.budgets.get(t.number)
        if b is None:
            return Undecided(mctx("the budget of change {number} is unknown").format(
                number=t.number))
        note = TAKE_NOTE.format(**budget_fields(with_cost(b, t.cost)))
        commands.append(log(t.number, Status.ASSIGNED, t.status, note, state.me))
        taken.append(t.number)
    if commands:
        return moves(commands, f"take {' '.join(taken)}", str(max(
            state.tracker.tickets[n].last_time for n in taken)))
    for n, time in numbers(state, Directive.MERGE):
        t = state.tracker.tickets.get(n)
        if (t is not None and Exit.MERGE_LINE in exits(state, t).by
                and time > status_since(t)):
            return Bash(log(n, Status.ASSIGNED, Status.BLOCKED,
                            "taking: the coordinator's `Op merge:` line rules the merge", state.me),
                        f"{n} merge line", occasion=str(time))
    return None
