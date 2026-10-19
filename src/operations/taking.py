"""The tickets the operators act on (`purview`), the work held and the
session's line of work, and the release of tickets whose holder is not
live.

The operators act on the tickets of the session and on those of the
sessions `SessionsRead.adopted` gives, as `State.mine` gives them. Which session
is the main one, `file_ticket.py main --help` states; which sessions are
idle, `idle_sessions.read_sessions` gives.

The work already held (`held_work`), the tickets an allow line of the
session gives (`allowed`) and the session's line of work (`own_work`) are
what the `Op pause.` and `Op scope:` lines admit, as `admission` gives
it. A ticket whose title refers to a file that line changed is of it only
once a ticket analyst judges that the line needs it (`follow_ups`,
`admission.judging`).

A change that waits for a ticket that holds it up moves to
`tickets/draft/` with a line whose note is `STALL_FINDING` on that ticket,
which `drafts` reads as findings (`ticket_stall`)."""

import re
from collections.abc import Callable, Mapping
from functools import cache

from controlled_markdown import form, mctx
from operations.directives import Directive, named, NUMBER, numbers_in, session_lines
from operations.final_reply import live_holder
from operations.log_commands import log
from operations.merging import merge_commit
from operations.state import LogLine, State, Ticket, kept_across_reads, memoized
from operations.steps import Bash, Step
from operations.tracker import exits, final_run, wait_line
from ticketing.exits import Exit
from ticketing.links import link_targets
from ticketing.references import Referring
from ticketing.vocabulary import COORDINATOR, Domain, Kind, Status


@memoized
def purview(state: State) -> frozenset[str]:
    """The tickets the operators release and take changes among: those
    `State.mine` gives, those the coordinator gives in a line to the operator `me`,
    and each ticket a chain of links reaches from one of those, with those
    of `allowed`. A chain from the tickets `State.mine` gives steps to a
    ticket only where `State.mine` gives it, its session is idle
    (`SessionsRead.idle`), or it belongs to no session."""
    def step(t: Ticket) -> list[str]:
        return [n for n in links(t)
                if (u := state.tracker.tickets.get(n)) is None or state.mine(u)
                or u.session is None or u.session in state.sessions.idle]

    own = closure(state, {n for n, t in state.tracker.tickets.items() if state.mine(t)}, step)
    return frozenset(own | reached(state, named(state)) | allowed(state))


def reached(state: State, start: set[str]) -> set[str]:
    """`start` and each ticket a chain of links reaches from one of its
    tickets, a link as
    [Change tickets](prompts/agents/notes/tickets.md#change-tickets) defines
    one."""
    return closure(state, start, links)


def closure(state: State, start: set[str], step: Callable[[Ticket], list[str]]) -> set[str]:
    """`start` and each ticket a chain of steps reaches from one of its
    tickets, where `step` gives the tickets one step reaches from a ticket
    the tracker holds."""
    out = set(start)
    todo = sorted(out)
    while todo:
        t = state.tracker.tickets.get(todo.pop())
        if t is None:
            continue
        for d in step(t):
            if d not in out:
                out.add(d)
                todo.append(d)
    return out


def links(t: Ticket) -> list[str]:
    line = wait_line(t)
    on = line.on_change if line is not None else None
    return link_targets(t.depends_on, on)


def served(state: State, start: set[str]) -> set[str]:
    """`start` and each ticket a chain of steps reaches from one of its
    tickets, a step from a ticket to each ticket of its `links` and, from
    a ticket that is not a `change`, to each `change` whose Motivation
    gives its number."""
    def step(t: Ticket) -> list[str]:
        return [*links(t), *([] if t.kind is Kind.CHANGE else
                             (f.number for f in filed_for(state).get(t.number, ())
                              if f.kind is Kind.CHANGE and t.number in f.motivation))]

    return closure(state, start, step)


def expedited(state: State) -> set[str]:
    """The tickets of `served` from the tickets an `Op expedite:` line to
    any operator of the session gives, which the operator takes ahead of
    the others, so that an expedite outlives the operator it was sent
    to."""
    return served(state, {n for n, _ in numbers_in(session_lines(state), Directive.EXPEDITE)})


def taken_before(t: Ticket) -> bool:
    """Whether a line of `t`'s log moves it into `tickets/assigned/`, so
    that taking it again is no new take: a hold that ended moved it to
    `tickets/released/`."""
    return any(ln.status is Status.ASSIGNED for ln in t.log)


def held_work(state: State) -> set[str]:
    """The work held, with each change it waits on: each change taken
    before, each ticket under `tickets/released/`, and each `interference`
    ticket not closed."""
    return reached(state, {n for n, t in state.tracker.tickets.items()
                           if (t.kind is Kind.CHANGE and taken_before(t))
                           or t.status is Status.RELEASED
                           or (t.kind is Kind.INTERFERENCE and t.status is not Status.CLOSED)})


def allowed(state: State) -> set[str]:
    """The tickets `Op pause.` admits past the work held, and `Op scope: own.`
    past the session's line of work: those of `served` from the tickets
    with an allow line of the operator's session (`Ticket.allowers`)."""
    return served(state, {n for n, t in state.tracker.tickets.items()
                          if state.session in t.allowers})


COMMIT_WORD = re.compile(r"\b[0-9a-f]{7,40}\b")
"""A word of a log line that may give the hash of a commit."""

FOLLOWS = frozenset({Kind.CHANGE, Kind.QUESTION, Kind.VALIDATION})
"""The kinds of the tickets of `filed_for` that `own_work` steps to: a
`change` filed for a ticket, and a question on a change or the check of a
request."""


OWN = mctx("own: {judgment}")
"""The note of the line a ticket analyst logs on a ticket of `follow_ups`
that it judges the session's line of work needs, for `judgment`."""

NOT_OWN = mctx("not own: {judgment}")
"""The note of the line a ticket analyst logs on a ticket of `follow_ups`
that it judges the session's line of work does not need, for
`judgment`."""

OWN_LINE = re.compile(form(OWN, {"judgment": r".+"}))
NOT_OWN_LINE = re.compile(form(NOT_OWN, {"judgment": r".+"}))


def own_step(state: State) -> Callable[[Ticket], list[str]]:
    """The tickets that a step of `own_work` reaches from a ticket."""
    below = filed_for(state)
    return lambda t: [*links(t), *(f.number for f in below.get(t.number, ()) if f.kind in FOLLOWS)]


@memoized
def line_of_work(state: State) -> set[str]:
    """The session's line of work as the coordinator's own tickets give
    it, with no ticket analyst's judgment."""
    return closure(state, {n for n, t in state.tracker.tickets.items()
                           if state.mine(t) and t.filer == COORDINATOR
                           and t.kind in (Kind.REQUEST, Kind.CHANGE)}, own_step(state))


def judged(state: State, pattern: re.Pattern[str]) -> set[str]:
    """The tickets a line of whose log has a note that `pattern` matches."""
    return {n for n, t in state.tracker.tickets.items()
            if log_matches((n, pattern), t.log, pattern)}


@kept_across_reads
def log_matches(log: tuple[LogLine, ...], pattern: re.Pattern[str]) -> bool:
    """Whether a line of `log` has a note that `pattern` matches."""
    return any(pattern.fullmatch(ln.note) for ln in log)


@memoized
def own_work(state: State) -> set[str]:
    """The session's line of work: the tickets of `line_of_work`, and each
    ticket whose log holds a line of the form `OWN`, with each ticket a
    chain of steps of `own_step` reaches from one."""
    return closure(state, line_of_work(state) | judged(state, OWN_LINE),
                   own_step(state)) & state.tracker.tickets.keys()


@memoized
def follow_ups(state: State) -> set[str]:
    """The tickets a ticket analyst judges for the session's line of work:
    each ticket outside `tickets/closed/` and outside `own_work` whose title
    refers, as `references.Referring` judges it, to a file of `touched` of
    `line_of_work`, and whose log holds no line of the form `OWN` or
    `NOT_OWN`."""
    refers = title_refers(touched(state, line_of_work(state)))
    out = {n for n, t in state.tracker.tickets.items()
           if t.status is not Status.CLOSED and refers(t.title)}
    return out - own_work(state) - judged(state, NOT_OWN_LINE)


@cache
def title_refers(files: frozenset[str]) -> Callable[[str], bool]:
    """`references.Referring` of `files`, built once for each set of files
    of a process, with each title judged once, as each read gives
    `follow_ups` the same files and titles again."""
    refers = Referring(files)
    seen: dict[str, bool] = {}

    def judged_once(title: str) -> bool:
        if title not in seen:
            seen[title] = refers(title)
        return seen[title]

    return judged_once


def touched(state: State, numbers: set[str]) -> frozenset[str]:
    """The files the tickets `numbers` edited: of a `change`, the files of
    its `merging.merge_commit`, none where it has none; of a `request`, the files of each commit of `GitRead.commits`
    whose hash a word of `COMMIT_WORD` in a log line of the coordinator
    gives, as the line that gives a hotfix's commit once it is on
    `master`."""
    out: set[str] = set()
    for n in numbers:
        t = state.tracker.tickets.get(n)
        if t is None:
            continue
        if t.kind is Kind.CHANGE:
            commit = merge_commit(state, t)
            out |= commit.files if commit is not None else frozenset()
        elif t.kind is Kind.REQUEST:
            words = {w for ln in t.log if ln.agent == COORDINATOR for w in COMMIT_WORD.findall(ln.note)}
            out.update(f for c in state.git.commits if any(c.hash.startswith(w) for w in words)
                       for f in c.files)
    return frozenset(out)


@memoized
def filed_for(state: State) -> dict[str, list[Ticket]]:
    """The tickets that give each ticket's number, by that number: those
    of domain `change` or `ticket` whose subject is that number, and each
    `change` whose Motivation gives it."""
    return held_filed_for((), state.tracker.tickets)


@kept_across_reads
def held_filed_for(tickets: Mapping[str, Ticket]) -> dict[str, list[Ticket]]:
    out: dict[str, list[Ticket]] = {}
    for t in tickets.values():
        on = {t.subject} if t.domain in (Domain.CHANGE, Domain.TICKET) else set()
        if t.kind is Kind.CHANGE:
            on |= set(t.motivation)
        for p in on:
            out.setdefault(p, []).append(t)
    return out


RELEASED = mctx("released: holder {holder} is not live")
RELEASED_LINE = re.compile(form(RELEASED, {"holder": r"\S+"}))


def release(state: State) -> Step | None:
    """The move to `tickets/released/` of each ticket of `purview` under
    `tickets/assigned/` whose holder is not live (`live_holder`), in one
    command whose moves run apart (`moves`)."""
    released = {n: t for n in sorted(purview(state))
                if (t := state.tracker.tickets.get(n)) is not None
                and Exit.RELEASE in exits(state, t).by
                and (t.holder is None or not live_holder(state, t.holder))}
    return moves([log(n, Status.RELEASED, Status.ASSIGNED,
                      RELEASED.format(holder=t.holder or 'none'), None)
                  for n, t in released.items()], f"release {' '.join(released)}",
                 str(max((t.last_time for t in released.values()), default=0.0)))


def moves(commands: list[str], about: str, occasion: str) -> Bash | None:
    """One step that runs each of `commands`, or None where there is none.
    The commands are joined with `;`, so a move that `file_ticket.py log`
    refuses leaves the others to run, and the next step reads the tracker
    as they left it. `about` and `occasion` are the step's (`steps.Bash`)."""
    return Bash(" ; ".join(commands), about, occasion=occasion) if commands else None


STALL_FINDING = mctx("finding: {number} holds up this change: {reason}")
"""The note of the line that moves to `tickets/draft/` a change that waits
for the ticket `number`, which holds it up for `reason`."""

STALLED = re.compile(form(STALL_FINDING, {"number": rf"(?P<number>{NUMBER.pattern})",
                                          "reason": r".*"}))


def status_since(t: Ticket) -> float:
    """The time of the last move of `t` into its status, or the time it was
    filed where no line of its log moves it there."""
    start, _ = final_run(t)
    return t.log[start].time if start < len(t.log) else t.filed
