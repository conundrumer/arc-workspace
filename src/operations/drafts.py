"""The review of draft `change` tickets: ticket reviewers on the drafts
ready for one, and a ticket analyst on the drafts whose log holds findings
or suggestions. The findings and suggestions it reads are the log lines a
ticket reviewer wrote whose note opens with `finding` or `suggestion`; a
line of an analyst or the coordinator that opens so is none.

The drafts given to the operator are the `change` tickets under
`tickets/draft/` that `State.mine` gives, those the coordinator names, those a
ticket analyst an operator launched files, and those of `taking.purview`
of another session whose index `SessionsRead.idle` holds. A draft is
ready for a ticket reviewer once its log holds a `filed` or a `revised`
line and no line after the last of them is the coordinator's or moves it
out of `tickets/draft/`, as where the agent that filed or revised it
records its decision on a line of its own below it; or once the
coordinator gives it to review after its last line, as after the
coordinator moves it back into `tickets/draft/` and revises it. A draft
waits while an agent of the operators' whose agent id a line of its log
gives runs, and, where its last `filed` or `revised` line is a ticket
analyst's that gives no agent id, while a ticket analyst of the operators'
launched before that line runs.

A draft waits for a ticket analyst where its log holds findings after its
last `filed` or `revised` line and after the last line that moves it out
of `tickets/draft/` (`findings_start`), and no ticket reviewer or ticket
analyst runs on it; a line of the operator's that moves a change past its cost
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
`Op decision:` line rules it with one of the choices the command gives it
(`directives.ruling`). A ticket reviewer that ended with no report
(`Agent.unreported`) and wrote no line on the draft is no review of it,
and the draft is ready for another, unless an earlier ticket reviewer
launched on it since its last `filed` or `revised` line also ended so."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from controlled_markdown import mctx
from operations import briefs, messages
from operations.change_budget import OVERRUN_FINDING, left_draft
from operations.taking import STALLED, purview
from operations.directives import Decision, Directive, named, numbers, ruling
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
    """The drafts of `taking.purview` that `State.mine` leaves out."""
    return [t for n in sorted(purview(state)) if (t := state.tracker.tickets.get(n)) is not None
            and draft_change(state, t) and t.session is not None and not state.mine(t)]


def drafts(state: State) -> list[Ticket]:
    names = named(state)
    analysed = {n for _, p, nums in state.analysts() if p is not Purpose.TRIAGE for n in nums}
    idle = {t.number for t in elsewhere(state) if t.session in state.sessions.idle}
    return sorted((t for t in state.tracker.tickets.values()
                   if draft_change(state, t)
                   and (state.mine(t) or t.number in names or t.number in analysed
                        or t.number in idle
                        or ((ln := operator_finding(t, findings_start(t))) is not None
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


def findings_start(t: Ticket) -> float:
    """The time from which `t`'s findings and suggestions count: the later
    of `base` and `change_budget.left_draft`."""
    return max(base(t), left_draft(t))


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
    """The number of `t`, the line of `overrun_line` since `findings_start`,
    and what the last item checker launched on `t` before that line leaves
    for a decision, or None where no such line is."""
    ln = overrun_line(t, findings_start(t))
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
    at: dict[str, float] = {}
    for t in drafts(state):
        s = draft_step(state, t)
        if isinstance(s, Joined):
            (ready if s.group is Group.READY else waiting).append(t)
            at[t.number] = s.at
        elif s is not None and not repeated(s, state):
            return s
    if ready:
        nums = [t.number for t in ready]
        return Launch(Role.TICKET_REVIEWER, joined(nums), briefs.ticket_review(nums, state.me),
                      items=len(nums), occasion=occasion(ready, at))
    if waiting:
        group = linked(waiting[0], waiting)
        nums = [t.number for t in group]
        last = [t.number for t in group if at_cap(t)]
        overruns = [o for t in group if (o := overrun(state, t)) is not None]
        return Launch(Role.TICKET_ANALYST, analyst_subject(Purpose.DRAFT, joined(nums)),
                      briefs.revise(nums, last, state.me, overruns), items=len(nums),
                      occasion=occasion(group, at))
    return None


def occasion(group: list[Ticket], at: dict[str, float]) -> str:
    """The occasion of a launch on the drafts `group`, which joined
    `ready` or `waiting` with the ruling times `at` (`draft_step`)."""
    return str(max(max(t.last_time, at[t.number]) for t in group))


def due(state: State) -> set[str]:
    """The drafts on which a step of the review is due."""
    return {t.number for t in drafts(state)
            if (s := draft_step(state, t)) is not None and not isinstance(s, Undecided)}


def analyst_writes(state: State, t: Ticket) -> bool:
    """Whether the last `filed` or `revised` line of `t` is a ticket
    analyst's with no agent id and a ticket analyst of the operators'
    launched before that line still runs, which may be the one that wrote
    it."""
    i = last_index(t, FILED_OR_REVISED)
    if i < 0 or t.log[i].agent != Role.TICKET_ANALYST or t.log[i].agent_id is not None:
        return False
    return any(a.pending and a.launched < t.log[i].time for a, _, _ in state.analysts())


class Group(Enum):
    """A group of drafts that one launch takes: those ready for a ticket
    reviewer, or those waiting for a ticket analyst."""
    READY = "ready"
    WAITING = "waiting"


@dataclass(frozen=True)
class Joined:
    """A draft that joins `group`, with `at`, the time of the ruling it
    joins on (`directives.Ruling`), the time of the launch or last resume
    of the ticket reviewer whose end with no report it joins after, or
    0.0."""
    group: Group
    at: float


def alone(state: State, t: Ticket) -> Step | None:
    """The step on the draft `t` alone, or None where it waits or joins a
    group (`draft_step`)."""
    s = draft_step(state, t)
    return None if isinstance(s, Joined) else s


def draft_step(state: State, t: Ticket) -> Step | Joined | None:
    """The step on the draft `t` alone, the group it joins, or None where
    it waits."""
    agents = on(state, t)
    last_line = t.log[-1]
    for a in agents:
        if (a.pending and a.agent_id and last_line.time > a.launched
                and last_line.agent == COORDINATOR):
            message = messages.stop_work(t.number)
            if not sent(state, a.agent_id, message):
                return Send(a.agent_id, message, f"stop {t.number}")
    writers = {ln.agent_id for ln in t.log if ln.agent_id}
    if (any(a.pending for a in agents)
            or any(a.pending and a.agent_id in writers for a in state.transcripts.agents)
            or analyst_writes(state, t)):
        return None
    since = findings_start(t)
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
                return Send(writer.agent_id, message, f"suggestions {t.number} {t.last_time}")
            analyst_done = [writer]
        if not analyst_done:
            return Joined(Group.WAITING, 0.0)
        what = mctx("the revision of draft {number} by ticket analyst {agent} is "
                    "unfinished").format(number=t.number, agent=analyst_done[-1].agent_id)
        r = ruling(state, what, {Decision.AGAIN: mctx("launch another ticket analyst to revise it")})
        return r if isinstance(r, Undecided) else Joined(Group.WAITING, r.time)
    if log_ready(t) and t.log[last_i].note.startswith(Note.REVISED) and at_cap(t):
        return open_last(t)
    by_log = log_ready(t)
    if not by_log and not given_after(state, t):
        return None
    given = since if by_log else t.log[-1].time
    reviewed = [a for a in agents if a.role is Role.TICKET_REVIEWER and a.launched > since
                and a.launched >= given]
    silent = [a for a in reviewed if a.unreported and a.agent_id not in writers]
    if not reviewed:
        return Joined(Group.READY, 0.0)
    if silent == [reviewed[-1]]:
        return Joined(Group.READY, reviewed[-1].since)
    what = mctx("ticket reviewer {agent} left draft {number} under `tickets/draft/` with "
                "no finding").format(agent=reviewed[-1].agent_id, number=t.number)
    r = ruling(state, what, {Decision.AGAIN: mctx("launch another ticket reviewer on it"),
                             Decision.OPEN: mctx("move it to `tickets/open/`")})
    if isinstance(r, Undecided):
        return r
    if r.choice is Decision.OPEN:
        return Bash(log(t.number, Status.OPEN, Status.DRAFT,
                        f"opened by the decision {decision_key(what)}", None),
                    f"{t.number} open", occasion=str(t.last_time))
    return Joined(Group.READY, r.time)


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
                    f"{Note.LAST_REVISION}: opens with no further ticket review", None),
                f"{t.number} open", occasion=str(t.last_time))


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

