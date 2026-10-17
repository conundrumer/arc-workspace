"""The release of tickets whose holder is not live, and the take of open
changes.

The operators act on the tickets of the session and on those of the
sessions `SessionsRead.adopted` gives, as `State.mine` gives them. Which session
is the main one, `file_ticket.py main --help` states; which sessions are
idle, `idle_sessions.read_sessions` gives.

While a `Pause.` line stands (`directives.paused`), the operator takes,
of the changes it would take with no pause, only those of `held_work`, so
the work already held reaches its end, and those of `through_pause`, the
tickets an `Allow:` or an `Expedite:` line gives, and each other change
waits for a `Resume.` line. Past the usage pace (`pacing`), the same
changes are taken, and each other one waits until the pace admits it.

A change that waits for a ticket that holds it up moves to
`tickets/draft/` with a line whose note is `STALL_FINDING` on that ticket,
which `drafts` reads as findings (`ticket_stall`). A change under `tickets/blocked/` is taken back on a `Merge:`
line that came after its last move there."""

import re
from collections.abc import Callable

from controlled_markdown import form, mctx
from operations import pacing, rank
from operations.change_budget import TAKE_NOTE, budget_fields
from operations.directives import (Directive, allow_named, named, NUMBER, numbers, numbers_in, paused,
                                   session_lines)
from operations.final_reply import live_holder
from operations.log_commands import log
from operations.pacing import Pace
from operations.state import State, Ticket
from operations.steps import Bash, Step, Undecided
from operations.tracker import closed, exits, final_run, wait_line
from ticketing.exits import Exit
from ticketing.vocabulary import Kind, Status


def scope(state: State) -> set[str]:
    """The tickets the operators release and take changes among: those
    `State.mine` gives, those the coordinator gives in a line to the operator `me`,
    and each ticket a chain of links reaches from one of those."""
    return reached(state, {n for n, t in state.tracker.tickets.items() if state.mine(t)} | named(state))


def reached(state: State, start: set[str]) -> set[str]:
    """`start` and each ticket a chain of links reaches from one of its
    tickets, a link as
    [Change tickets](prompts/agents/notes/tickets.md#change-tickets) defines
    one."""
    out = set(start)
    todo = sorted(out)
    while todo:
        t = state.tracker.tickets.get(todo.pop())
        if t is None:
            continue
        for d in links(t):
            if d not in out:
                out.add(d)
                todo.append(d)
    return out


def links(t: Ticket) -> list[str]:
    line = wait_line(t)
    on = line.on_change if line is not None else None
    return [*t.depends_on, *([on] if on is not None else [])]


def expedited(state: State) -> set[str]:
    """The tickets a chain of links reaches from a ticket an `Expedite:`
    line to any operator of the session gives, which the operator takes
    ahead of the others, so that an expedite outlives the operator it was
    sent to."""
    return reached(state, {n for n, _ in numbers_in(session_lines(state), Directive.EXPEDITE)})


def admits(state: State) -> Callable[[str], bool]:
    """Whether the operator may admit an open ticket: one the `takes` of
    the run scripts admit (`Computed.admitted`), or one of `expedited`,
    or any where no script defines `takes`; of those, one of `held_work`
    or of `through_pause` always, and any other only while no `Pause.`
    line stands and the usage pace admits one (`Computed.pace`)."""
    passes, held = passing(state)
    clear = past_pause(state, held)
    paced = pacing.admits(state.computed.pace, state.now)
    return lambda n: passes(n) and clear(n) and (paced or held(n))


def past_pause(state: State, through: Callable[[str], bool]) -> Callable[[str], bool]:
    """Whether a ticket passes a pause, where `through` gives the tickets
    that pass one."""
    return through if paused(state) else lambda _: True


def passing(state: State) -> tuple[Callable[[str], bool], Callable[[str], bool]]:
    """Whether the `takes` of the run scripts admit a ticket, with those of
    `expedited`, every ticket where no script defines `takes`, and whether
    it is one of `held_work` or of `through_pause`."""
    admitted = state.computed.admitted()
    runs = None if admitted is None else set(admitted) | expedited(state)
    held = held_work(state) | through_pause(state)
    return (lambda n: runs is None or n in runs), held.__contains__


def pace_held(state: State, numbers: list[str]) -> Pace | None:
    """The pace, where it alone holds back one of `numbers`: one `admits`
    would pass but for the pace, with no `Pause.` line standing."""
    pace = state.computed.pace
    if pacing.admits(pace, state.now) or paused(state):
        return None
    passes, held = passing(state)
    return pace if any(passes(n) and not held(n) for n in numbers) else None


def taken_before(t: Ticket) -> bool:
    """Whether a line of `t`'s log moves it into `tickets/assigned/`, so
    that taking it again is no new take: `release` moved it back to
    `tickets/open/` from a holder that is not live."""
    return any(ln.status is Status.ASSIGNED for ln in t.log)


def held_work(state: State) -> set[str]:
    """The work held, with each change it waits on."""
    return reached(state, {n for n, t in state.tracker.tickets.items()
                           if (t.kind is Kind.CHANGE and taken_before(t))
                           or (t.kind is Kind.INTERFERENCE and t.status is not Status.CLOSED)})


def through_pause(state: State) -> set[str]:
    """The tickets that pass a pause: each ticket a chain of links reaches
    from a ticket of `directives.allow_named`, and those of `expedited`."""
    return reached(state, allow_named(state)) | expedited(state)


RELEASED = mctx("released: holder {holder} is not live")
RELEASED_LINE = re.compile(form(RELEASED, {"holder": r"\S+"}))


def release(state: State) -> Step | None:
    """The move back to `tickets/open/` of each ticket of `scope` under
    `tickets/assigned/` whose holder is not live (`live_holder`), in one
    command whose moves run apart (`moves`)."""
    released = {n: t for n in sorted(scope(state))
                if (t := state.tracker.tickets.get(n)) is not None
                and Exit.RELEASE in exits(state, t).by
                and (t.holder is None or not live_holder(state, t.holder))}
    return moves([log(n, Status.OPEN, Status.ASSIGNED,
                      RELEASED.format(holder=t.holder or 'none'), None)
                  for n, t in released.items()], f"release {' '.join(released)}",
                 str(max((t.last_time for t in released.values()), default=0.0)))


def moves(commands: list[str], about: str, occasion: str) -> Bash | None:
    """One step that runs each of `commands`, or None where there is none.
    The commands are joined with `;`, so a move that `file_ticket.py log`
    refuses leaves the others to run, and the next step reads the tracker
    as they left it. `about` and `occasion` are the step's (`steps.Bash`)."""
    return Bash(" ; ".join(commands), about, occasion=occasion) if commands else None


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
    """The open changes of `scope` whose `depends-on` are closed."""
    return [t for t, awaited in awaiting(state) if not awaited]


def awaiting(state: State) -> list[tuple[Ticket, list[str]]]:
    """Each ticket of `scope` that `Exit.TAKE` takes out of its status,
    with the tickets of its `depends-on` that are not closed."""
    return [(t, [d for d in t.depends_on if not closed(state, d)]) for n in sorted(scope(state))
            if (t := state.tracker.tickets.get(n)) is not None and Exit.TAKE in exits(state, t).by]


def lead(state: State) -> set[str]:
    """The changes the operator takes ahead of the others."""
    return boosted(state) | expedited(state)


def takeable(state: State) -> list[Ticket]:
    """The changes of `ready` that `admits` passes or that were taken
    before, `lead` first, then in rank order (`rank.ranking`)."""
    first = lead(state)
    admitted = admits(state)
    key = rank.ranking(state)
    return sorted((t for t in ready(state) if admitted(t.number) or taken_before(t)),
                  key=lambda t: (t.number not in first, key(t)))


def waiting(state: State) -> list[tuple[str, list[str]]]:
    """Each open `change` of `scope` not taken for its `depends-on`, with
    the tickets it waits for."""
    return [(t.number, awaited) for t, awaited in awaiting(state) if awaited]


STALL_FINDING = mctx("finding: {number} holds up this change: {reason}")
"""The note of the line that moves to `tickets/draft/` a change that waits
for the ticket `number`, which holds it up for `reason`."""

STALLED = re.compile(form(STALL_FINDING, {"number": rf"(?P<number>{NUMBER.pattern})",
                                          "reason": r".*"}))


def blocked_since(t: Ticket) -> float:
    """The time of the last move of `t`, which stands under
    `tickets/blocked/`, into `tickets/blocked/`."""
    return t.log[final_run(t)[0]].time if t.log else t.filed


def batch(state: State) -> list[Ticket]:
    """The changes of `takeable` that one step of `take` takes, as `take`
    gives them."""
    free = pacing.admits(state.computed.pace, state.now) and not paused(state)
    first = lead(state)
    out: list[Ticket] = []
    paced = False
    for t in takeable(state):
        if t.number in first or taken_before(t):
            out.append(t)
        elif free or not paced:
            out.append(t)
            paced = True
    return out


def take(state: State) -> Step | None:
    """The take of each change of `takeable`, in its order, up to the first
    whose budget `Computed.budgets` does not give. Where the usage pace does
    not admit a ticket, or a `Pause.` line stands, a step takes, of the
    changes neither of `lead` nor `taken_before`, only the first, so that
    the pace is read again before each further take."""
    commands: list[str] = []
    taken: list[str] = []
    for t in batch(state):
        b = state.computed.budgets.get(t.number)
        if b is None:
            if not commands:
                return Undecided(mctx("the budget of change {number} is unknown").format(
                    number=t.number))
            break
        note = TAKE_NOTE.format(**budget_fields(b))
        commands.append(log(t.number, Status.ASSIGNED, Status.OPEN, note, state.me))
        taken.append(t.number)
    if commands:
        return moves(commands, f"take {' '.join(taken)}", str(max(
            state.tracker.tickets[n].last_time for n in taken)))
    for n, time in numbers(state, Directive.MERGE):
        t = state.tracker.tickets.get(n)
        if (t is not None and Exit.MERGE_LINE in exits(state, t).by
                and time > blocked_since(t)):
            return Bash(log(n, Status.ASSIGNED, Status.BLOCKED,
                            "taking: the coordinator's Merge line rules the merge", state.me),
                        f"{n} merge line", occasion=str(time))
    return None
