"""The release of tickets whose holder is not live, the take of open
changes, and the move to `tickets/draft/` of a change that waits on the
user.

The operators act on the tickets of the session and on those of the
sessions `SessionsRead.adopted` gives, as `State.mine` gives them. Which session
is the main one, `file_ticket.py main --help` states; which sessions are
idle, `idle_sessions.read_sessions` gives.

While a `Pause.` line stands (`directives.paused`), the operator takes,
of the changes it would take with no pause, only those of `held_work`, so
the work already held reaches its end, and those of `through_pause`, the
tickets an `Allow:` or an `Expedite:` line gives, and each other change
waits for a `Resume.` line.

A change that waits for a ticket under `tickets/blocked/` whose last
wait is on the user moves to `tickets/draft/` with a line whose note is
`STALL_FINDING` on that ticket, which `drafts` reads as findings, once
after each move of that ticket into `tickets/blocked/` (`stall`). A
change under `tickets/blocked/` is taken back on a `Merge:` line that
came after its last move there."""

import re
from collections.abc import Callable

from controlled_markdown import form, mctx
from operations.change_budget import TAKE_NOTE
from operations.directives import Directive, allow_named, named, NUMBER, numbers, paused
from operations.final_reply import live_holder
from operations.log_commands import log
from operations.state import State, Ticket
from operations.steps import Bash, Step, Undecided
from operations.tracker import blocked_on_user, closed, exits, final_run, wait_line
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
    line to the operator gives, which the operator takes ahead of the
    others."""
    return reached(state, {n for n, _ in numbers(state, Directive.EXPEDITE)})


def admits(state: State) -> Callable[[str], bool]:
    """Whether the operator may take an open ticket: one the `takes` of
    the run scripts admit (`Computed.admitted`), or one of `expedited`,
    or any where no script defines `takes`; under a pause, only such a
    ticket that is also one of `held_work` or of `through_pause`."""
    admitted = state.computed.admitted()
    passing = None if admitted is None else admitted | expedited(state)
    held = held_work(state) | through_pause(state) if paused(state) else None
    return lambda n: ((passing is None or n in passing)
                      and (held is None or n in held))


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


def release(state: State) -> Step | None:
    """The move back to `tickets/open/` of each ticket of `scope` under
    `tickets/assigned/` whose holder is not live (`live_holder`), in one
    command whose moves run apart (`moves`)."""
    return moves([log(n, Status.OPEN, Status.ASSIGNED,
                      RELEASED.format(holder=t.holder or 'none'), None)
                  for n in sorted(scope(state))
                  if (t := state.tracker.tickets.get(n)) is not None
                  and Exit.RELEASE in exits(state, t).by
                  and (t.holder is None or not live_holder(state, t.holder))])


def moves(commands: list[str]) -> Bash | None:
    """One step that runs each of `commands`, or None where there is none.
    The commands are joined with `;`, so a move that `file_ticket.py log`
    refuses leaves the others to run, and the next step reads the tracker
    as they left it."""
    return Bash(" ; ".join(commands)) if commands else None


def boosted(state: State) -> set[str]:
    """The changes that settle an `interference` ticket, which the
    operator takes ahead of the others."""
    out: set[str] = set()
    for t in state.tracker.tickets.values():
        line = wait_line(t) if t.kind is Kind.INTERFERENCE else None
        if line is not None and line.on_change is not None:
            out.add(line.on_change)
    return out


def takeable(state: State) -> list[Ticket]:
    lead = boosted(state) | expedited(state)
    admitted = admits(state)
    ts = [t for n in scope(state) if (t := state.tracker.tickets.get(n)) is not None
          and Exit.TAKE in exits(state, t).by
          and all(closed(state, d) for d in t.depends_on)
          and (admitted(n) or taken_before(t))]
    return sorted(ts, key=lambda t: (t.number not in lead, -t.priority, t.order))


def waiting(state: State) -> list[tuple[str, list[str]]]:
    """Each open `change` of `scope` not taken for its `depends-on`, with
    the tickets it waits for."""
    return [(n, [d for d in t.depends_on if not closed(state, d)]) for n in sorted(scope(state))
            if (t := state.tracker.tickets.get(n)) is not None
            and Exit.TAKE in exits(state, t).by and not all(closed(state, d) for d in t.depends_on)]


STALL_FINDING = mctx("finding: {number} waits on the user")
"""The note of the line that moves to `tickets/draft/` a change that waits
for the ticket `number`, which waits on the user."""

STALLED = re.compile(form(STALL_FINDING, {"number": rf"(?P<number>{NUMBER.pattern})"}))


def blocked_since(t: Ticket) -> float:
    """The time of the last move of `t`, which stands under
    `tickets/blocked/`, into `tickets/blocked/`."""
    return t.log[final_run(t)[0]].time if t.log else t.filed


def stall(state: State) -> Step | None:
    """The move to `tickets/draft/` of a change of `waiting` that waits for
    a ticket that waits on the user (`blocked_on_user`), where no line of
    its log since that ticket's last move into `tickets/blocked/` gives
    `STALL_FINDING` on it."""
    for n, deps in waiting(state):
        t = state.tracker.tickets[n]
        for d in deps:
            u = state.tracker.tickets.get(d)
            if u is None or blocked_on_user(u) is None:
                continue
            since = blocked_since(u)
            if not any(ln.time >= since and (m := STALLED.match(ln.note)) is not None
                       and m["number"] == d for ln in t.log):
                return Bash(log(n, Status.DRAFT, Status.OPEN, STALL_FINDING.format(number=d),
                                state.me))
    return None


def take(state: State) -> Step | None:
    """The take of each change of `takeable`, in its order, up to the first
    whose budget `Computed.budgets` does not give."""
    commands: list[str] = []
    for t in takeable(state):
        b = state.computed.budgets.get(t.number)
        if b is None:
            if not commands:
                return Undecided(mctx("the budget of change {number} is unknown").format(
                    number=t.number))
            break
        commands.append(log(t.number, Status.ASSIGNED, Status.OPEN,
                            TAKE_NOTE.format(dollars=f"{b.dollars:.2f}",
                                             seconds=f"{b.seconds:.0f}"),
                            state.me))
    if commands:
        return moves(commands)
    for n, time in numbers(state, Directive.MERGE):
        t = state.tracker.tickets.get(n)
        if (t is not None and Exit.MERGE_LINE in exits(state, t).by
                and time > blocked_since(t)):
            return Bash(log(n, Status.ASSIGNED, Status.BLOCKED,
                            "taking: the coordinator's Merge line rules the merge", state.me))
    return None
