"""The review of draft `change` tickets: ticket reviewers on the drafts
ready for one, and a ticket analyst on the drafts whose log holds findings
or suggestions. The findings and suggestions it reads are the log lines a
ticket reviewer wrote whose note opens with `finding` or `suggestion`; a
line of an analyst or the coordinator that opens so is none.

The drafts given to the operator are the `change` tickets under
`tickets/draft/` that `State.mine` gives, those the coordinator names, those a
ticket analyst an operator launched files, and those of `taking.scope`
of another session whose index `SessionsRead.idle_indexes` holds. A draft is
ready for a ticket reviewer once its log holds a `filed` or a `revised`
line and no line after the last of them is the coordinator's or moves it
out of `tickets/draft/`, as where the agent that filed or revised it
records its decision on a line of its own below it; or once the
coordinator gives it to review after its last line, as after the
coordinator moves it back into `tickets/draft/` and revises it. A draft
waits while an agent of the operators' that wrote a line of its log runs.

A draft waits for a ticket analyst where its log holds findings after its
last `filed` or `revised` line, and no ticket reviewer or ticket analyst
runs on it; a line of the operator's that moves a change past its cost
budget to `tickets/draft/` (`change_budget.OVERRUN_FINDING`), or that moves
there a change that waits on a ticket that holds it up
(`taking.STALL_FINDING`), counts as findings,
and the analyst's brief gives that line and what the item checker it names leaves
for a decision; one ticket analyst takes each such draft with the others a
chain of `depends-on` links to it. Where the log holds only suggestions
there, the command resumes by SendMessage the ticket analyst that wrote
that last line, where an operator launched it, and otherwise the draft
waits for a ticket analyst as for findings. Where the log gives `CAP` review
rounds with findings or suggestions since the line that filed the draft or
last moved it into `tickets/draft/`, the analyst's brief gives its
revision as the last, and once that revision is written, the command moves
the draft to `tickets/open/`.

Where the coordinator writes a line on a draft after an agent of the
operators' was launched on it, as where it moves the draft back to revise
it, the command tells that agent to write nothing further and to
end. Where a ticket reviewer returned and left a draft in
`tickets/draft/` with no finding and no suggestion, or a ticket analyst
returned with no revision written, the review of that draft holds until a
`Decision:` line rules it with one of the choices the command gives it
(`directives.decided`)."""

from collections.abc import Callable

from controlled_markdown import mctx
from operations import briefs, messages
from operations.change_budget import OVERRUN_FINDING
from operations.taking import STALLED, scope
from operations.directives import Decision, Directive, decided, named, numbers
from operations.roles import Purpose, Role, analyst_subject, joined, subjects
from operations.reports import left_for_decision
from operations.state import Agent, LogLine, State, Ticket
from ticketing.vocabulary import Note, Status, last_move_into
from operations.handled import repeated, sent
from operations.steps import Bash, Launch, Send, Step, Undecided, decision_key
from operations.log_commands import AGENT, log
from operations.tracker import after, exits, last_index
from ticketing.exits import Exit
from ticketing.vocabulary import COORDINATOR

CAP = 3
"""The review rounds with findings or suggestions that close a draft's
review."""

FILED_OR_REVISED = (Note.FILED, Note.REVISED)


def draft_change(state: State, t: Ticket) -> bool:
    return Exit.TICKET_REVIEW in exits(state, t).by


def elsewhere(state: State) -> list[Ticket]:
    """The drafts of `taking.scope` that `State.mine` leaves out."""
    return [t for n in sorted(scope(state)) if (t := state.tracker.tickets.get(n)) is not None
            and draft_change(state, t) and t.session is not None and not state.mine(t)]


def drafts(state: State) -> list[Ticket]:
    names = named(state)
    analysed = {n for _, p, nums in state.analysts() if p is not Purpose.TRIAGE for n in nums}
    idle = {t.number for t in elsewhere(state) if t.session in state.sessions.idle_indexes}
    return sorted((t for t in state.tracker.tickets.values()
                   if draft_change(state, t)
                   and (state.mine(t) or t.number in names or t.number in analysed
                        or t.number in idle
                        or ((ln := operator_finding(t, base(t))) is not None
                            and ln.agent_id in state.operators))),
                  key=lambda t: t.order)


def on(state: State, t: Ticket) -> list[Agent]:
    """The ticket reviewers and draft analysts launched on `t`."""
    out = [a for a in state.agents_of(Role.TICKET_REVIEWER) if t.number in subjects(a.subject)]
    out += [a for a, p, nums in state.analysts() if p is Purpose.DRAFT and t.number in nums]
    return out


def base(t: Ticket) -> float:
    """The time of `t`'s last `filed` or `revised` line."""
    i = last_index(t, FILED_OR_REVISED)
    return t.log[i].time if i >= 0 else t.filed


def log_ready(t: Ticket) -> bool:
    """Whether `t`'s log holds a `filed` or a `revised` line and no line
    after the last of them is the coordinator's or moves `t` out of
    `tickets/draft/`."""
    i = last_index(t, FILED_OR_REVISED)
    return i >= 0 and all(ln.agent != COORDINATOR and ln.status is Status.DRAFT
                          for ln in after(t, i))


def given_after(state: State, t: Ticket) -> bool:
    """Whether the coordinator gave `t` to review after its last line."""
    return any(n == t.number and time >= t.log[-1].time
               for n, time in numbers(state, Directive.DRAFTS))


def by_reviewer(ln: LogLine, opening: str | tuple[str, ...]) -> bool:
    """Whether `ln` is a ticket reviewer's line whose note opens with `opening`, or with one of them."""
    return ln.agent == Role.TICKET_REVIEWER and ln.note.startswith(opening)


def review_lines_after(t: Ticket, since: float, opening: str) -> list[str]:
    """The agent ids of the lines of `t`'s log after `since` whose note
    opens with `opening` and whose agent is a ticket reviewer, in log
    order."""
    return [ln.agent_id or ln.agent for ln in t.log
            if ln.time >= since and by_reviewer(ln, opening)]


def operator_line(t: Ticket, since: float, kept: Callable[[str], bool]) -> LogLine | None:
    """The last line of the operator's in `t`'s log after `since` whose
    note `kept` keeps."""
    return next((ln for ln in reversed(t.log)
                 if ln.time >= since and ln.agent == AGENT and kept(ln.note)), None)


def overrun_line(t: Ticket, since: float) -> LogLine | None:
    """The last line of the operator's in `t`'s log after `since` that
    moves the change past its cost budget to `tickets/draft/`."""
    return operator_line(t, since, overran)


def overran(note: str) -> bool:
    return note.startswith(OVERRUN_FINDING)


def operator_finding(t: Ticket, since: float) -> LogLine | None:
    """The last line of the operator's in `t`'s log after `since` that
    counts as findings: `overrun_line`, or one that moves the change to
    `tickets/draft/` with `taking.STALL_FINDING`."""
    return operator_line(t, since, lambda note: overran(note)
                         or STALLED.match(note) is not None)


def overrun(state: State, t: Ticket) -> tuple[str, str, str | None] | None:
    """The number of `t`, the line of `overrun_line` since its last
    `filed` or `revised` line, and what the last item checker launched on
    `t` before that line leaves for a decision, or None where no such line
    is."""
    ln = overrun_line(t, base(t))
    if ln is None:
        return None
    checkers = [a for a in state.agents_of(Role.ITEM_CHECKER, t.number) if a.launched < ln.time]
    return t.number, ln.note, left_for_decision(checkers[-1]) if checkers else None


def rounds_since_draft(t: Ticket) -> int:
    """The review rounds `t`'s log gives since the line that filed it or
    last moved it into `tickets/draft/`: a round is the ticket reviewer
    lines whose note opens with `finding` or `suggestion` after one `filed`
    or `revised` line, or after that start line before any, whatever agent
    id they give."""
    start = last_move_into([ln.status for ln in t.log], Status.DRAFT) or 0
    rounds: set[int] = set()
    opened = start
    for i in range(start, len(t.log)):
        ln = t.log[i]
        if ln.note.startswith(FILED_OR_REVISED):
            opened = i
        elif by_reviewer(ln, (Note.FINDING, Note.SUGGESTION)):
            rounds.add(opened)
    return len(rounds)


def at_cap(t: Ticket) -> bool:
    return rounds_since_draft(t) >= CAP


def step(state: State) -> Step | None:
    """The next step of the review of the drafts. A held step on one draft
    holds that draft alone."""
    ready: list[Ticket] = []
    waiting: list[Ticket] = []
    for t in drafts(state):
        s = draft_step(state, t, ready, waiting)
        if s is not None and not repeated(s, state):
            return s
    if ready:
        nums = [t.number for t in ready]
        return Launch(Role.TICKET_REVIEWER, joined(nums), briefs.ticket_review(nums, state.me),
                      items=len(nums))
    if waiting:
        group = linked(waiting[0], waiting)
        nums = [t.number for t in group]
        last = [t.number for t in group if at_cap(t)]
        overruns = [o for t in group if (o := overrun(state, t)) is not None]
        return Launch(Role.TICKET_ANALYST, analyst_subject(Purpose.DRAFT, joined(nums)),
                      briefs.revise(nums, last, state.me, overruns), items=len(nums))
    return None


def due(state: State) -> set[str]:
    """The drafts on which a step of the review is due."""
    ready: list[Ticket] = []
    waiting: list[Ticket] = []
    out = {t.number for t in drafts(state)
           if (s := draft_step(state, t, ready, waiting)) is not None
           and not isinstance(s, Undecided)}
    return out | {t.number for t in [*ready, *waiting]}


def draft_step(state: State, t: Ticket, ready: list[Ticket],
               waiting: list[Ticket]) -> Step | None:
    """The step on the draft `t` alone, or None where it waits or joins
    `ready`, the drafts ready for a ticket reviewer, or `waiting`, those
    waiting for a ticket analyst."""
    agents = on(state, t)
    last_line = t.log[-1]
    for a in agents:
        if (a.pending and a.agent_id and last_line.time > a.launched
                and last_line.agent == COORDINATOR):
            message = messages.stop_work(t.number)
            if not sent(state, a.agent_id, message):
                return Send(a.agent_id, message)
    writers = {ln.agent_id for ln in t.log if ln.agent_id}
    if any(a.pending for a in agents) or any(a.pending and a.agent_id in writers
                                             for a in state.transcripts.agents):
        return None
    since = base(t)
    found = review_lines_after(t, since, Note.FINDING)
    overran = operator_finding(t, since) is not None
    suggested = review_lines_after(t, since, Note.SUGGESTION)
    last_i = last_index(t, FILED_OR_REVISED)
    if found or suggested or overran:
        analyst_done = [a for a in agents if a.role is Role.TICKET_ANALYST
                        and a.launched > t.log[-1].time]
        writer = resumable(state, t) if not (found or overran) else None
        if writer is not None and writer.agent_id is not None:
            message = briefs.weigh_suggestions(t.number, list(dict.fromkeys(suggested)),
                                               at_cap(t))
            if not sent(state, writer.agent_id, message):
                return Send(writer.agent_id, message)
            analyst_done = [writer]
        if analyst_done:
            choice = decided(state, mctx("the revision of draft {number} by ticket analyst "
                                       "{agent} is unfinished").format(
                               number=t.number, agent=analyst_done[-1].agent_id),
                           {Decision.AGAIN: mctx("launch another ticket analyst to revise it")})
            if isinstance(choice, Undecided):
                return choice
        waiting.append(t)
        return None
    if log_ready(t) and t.log[last_i].note.startswith(Note.REVISED) and at_cap(t):
        return open_last(t)
    by_log = log_ready(t)
    if not by_log and not given_after(state, t):
        return None
    given = since if by_log else t.log[-1].time
    reviewed = [a for a in agents if a.role is Role.TICKET_REVIEWER and a.launched > since
                and a.launched >= given]
    if reviewed:
        what = mctx("ticket reviewer {agent} left draft {number} under `tickets/draft/` with "
                    "no finding").format(agent=reviewed[-1].agent_id, number=t.number)
        choice = decided(state, what, {Decision.AGAIN: mctx("launch another ticket reviewer on it"),
                                     Decision.OPEN: mctx("move it to `tickets/open/`")})
        if isinstance(choice, Undecided):
            return choice
        if choice is Decision.OPEN:
            return Bash(log(t.number, Status.OPEN, Status.DRAFT,
                            f"opened by the decision {decision_key(what)}", None))
    ready.append(t)
    return None


def resumable(state: State, t: Ticket) -> Agent | None:
    """The ticket analyst that wrote `t`'s last `filed` or `revised` line,
    where an operator launched it."""
    i = last_index(t, FILED_OR_REVISED)
    writer = t.log[i].agent_id if i >= 0 else None
    if writer is None:
        return None
    return next((a for a in state.agents_of(Role.TICKET_ANALYST) if a.agent_id == writer), None)


def open_last(t: Ticket) -> Step:
    """The move of `t`, whose last revision is written, to
    `tickets/open/`."""
    return Bash(log(t.number, Status.OPEN, Status.DRAFT,
                    f"{Note.LAST_REVISION}: opens with no further ticket review", None))


def linked(first: Ticket, waiting: list[Ticket]) -> list[Ticket]:
    """`first` and each draft of `waiting` a chain of `depends-on` links to
    it, either way."""
    by = {t.number: t for t in waiting}
    group = {first.number}
    grew = True
    while grew:
        grew = False
        for t in waiting:
            if t.number in group:
                continue
            if set(t.depends_on) & group or any(t.number in by[g].depends_on for g in group):
                group.add(t.number)
                grew = True
    return [t for t in waiting if t.number in group]


def unended(state: State) -> list[Ticket]:
    """The drafts given to the operators whose review has not ended."""
    return drafts(state)

