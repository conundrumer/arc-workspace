"""The review of draft `change` tickets: ticket reviewers on the drafts
ready for one, and a ticket analyst on the drafts whose log holds findings
or suggestions.

The drafts given to the operator are the `change` tickets under
`tickets/draft/` of the session, those the coordinator names, and those a
ticket analyst an operator launched files. A draft is ready for a ticket
reviewer once its log holds a `filed` or a `revised` line and no line
after the last of them is the coordinator's or moves it out of
`tickets/draft/`, as where the agent that filed or revised it records its
decision on a line of its own below it; or once the coordinator gives it to review after
its last line, as after the coordinator moves it back into `tickets/draft/`
and revises it. A draft waits while an agent of the operators' that wrote
a line of its log runs.

A draft waits for a ticket analyst where its log holds findings after its
last `filed` or `revised` line, and no ticket reviewer or ticket analyst
runs on it; one ticket analyst takes each such draft with the others a
chain of `depends-on` links to it. Where the log holds only suggestions
there, the command resumes by SendMessage the ticket analyst that wrote
that last line, where an operator launched it, and otherwise the draft
waits for a ticket analyst as for findings. Where the log gives findings or
suggestions of `CAP` ticket reviewers since the line that filed the draft
or last moved it into `tickets/draft/`, the analyst's brief gives its
revision as the last, and once that revision is written, the command moves
the draft to `tickets/open/`.

Where the coordinator writes a line on a draft after an agent of the
operators' was launched on it, as where it moves the draft back to revise
it, the command tells that agent to write nothing further and to
end. Where a ticket reviewer returned and left a draft in
`tickets/draft/` with no finding and no suggestion, or a ticket analyst
returned with no revision written, the review of that draft holds until the coordinator
rules it with one of the choices the command gives it
(`directives.ruled`)."""

from operating import briefs
from operating.directives import Directive, Ruling, named, numbers, ruled
from operating.roles import Purpose, Role, analyst_subject, joined, subjects
from operating.state import Agent, State, Ticket
from ticketing.vocabulary import FILED, Kind, Status
from operating.steps import Bash, Launch, Send, Step, repeated, ruling_key, sent
from operating.tracker import COORDINATOR, after, last_index, log

CAP = 3
"""The ticket reviewers whose findings or suggestions close a draft's
review rounds."""

REVISED = "revised"
"""The note a ticket analyst writes on a draft it revised."""
FILED_OR_REVISED = (FILED, REVISED)
FINDING = "finding"
SUGGESTION = "suggestion"
LAST = "last revision"


def drafts(state: State) -> list[Ticket]:
    names = named(state)
    analysed = {n for _, p, nums in state.analysts() if p is not Purpose.SETTLE for n in nums}
    return sorted((t for t in state.tickets.values()
                   if t.status is Status.DRAFT and t.kind is Kind.CHANGE
                   and (state.mine(t) or t.number in names or t.number in analysed)),
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


def review_lines_after(t: Ticket, since: float, opening: str) -> list[str]:
    """The agent ids of the lines of `t`'s log after `since` whose note
    opens with `opening`, in log order."""
    return [ln.agent_id or ln.agent for ln in t.log
            if ln.time >= since and ln.note.startswith(opening)]


def reviewers_since_draft(t: Ticket) -> int:
    """The ticket reviewers whose findings or suggestions `t`'s log gives
    since the line that filed it or last moved it into `tickets/draft/`."""
    start = 0
    for i in range(1, len(t.log)):
        if t.log[i].status is Status.DRAFT and t.log[i - 1].status is not Status.DRAFT:
            start = i
    return len({ln.agent_id or ln.agent for ln in t.log[start:]
                if ln.note.startswith((FINDING, SUGGESTION))})


def at_cap(t: Ticket) -> bool:
    return reviewers_since_draft(t) >= CAP


def step(state: State) -> Step | None:
    """The next step of the review of the drafts. A step held for the
    coordinator on one draft holds that draft alone."""
    ready: list[Ticket] = []
    waiting: list[Ticket] = []
    for t in drafts(state):
        s = draft_step(state, t, ready, waiting)
        if s is not None and not repeated(s, state):
            return s
    if ready:
        nums = [t.number for t in ready]
        return Launch(Role.TICKET_REVIEWER, joined(nums), briefs.ticket_review(nums, state.me))
    if waiting:
        group = linked(waiting[0], waiting)
        nums = [t.number for t in group]
        last = [t.number for t in group if at_cap(t)]
        return Launch(Role.TICKET_ANALYST, analyst_subject(Purpose.DRAFT, joined(nums)),
                      briefs.revise(nums, last, state.me))
    return None


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
            message = briefs.stop_work(t.number)
            if not sent(state, a.agent_id, message):
                return Send(a.agent_id, message)
    writers = {ln.agent_id for ln in t.log if ln.agent_id}
    if any(a.pending for a in agents) or any(a.pending and a.agent_id in writers
                                             for a in state.agents):
        return None
    since = base(t)
    found = review_lines_after(t, since, FINDING)
    suggested = review_lines_after(t, since, SUGGESTION)
    last_i = last_index(t, FILED_OR_REVISED)
    if found or suggested:
        analyst_done = [a for a in agents if a.role is Role.TICKET_ANALYST
                        and a.launched > t.log[-1].time]
        writer = resumable(state, t) if not found else None
        if writer is not None and writer.agent_id is not None:
            message = briefs.weigh_suggestions(t.number, list(dict.fromkeys(suggested)),
                                               at_cap(t))
            if not sent(state, writer.agent_id, message):
                return Send(writer.agent_id, message)
            analyst_done = [writer]
        if analyst_done:
            choice = ruled(state, f"the revision of draft {t.number} by ticket analyst "
                                  f"{analyst_done[-1].agent_id} is unfinished",
                           {Ruling.AGAIN: "launch another ticket analyst to revise it"})
            if isinstance(choice, Send):
                return choice
        waiting.append(t)
        return None
    if log_ready(t) and t.log[last_i].note.startswith(REVISED) and at_cap(t):
        return open_last(t)
    by_log = log_ready(t)
    if not by_log and not given_after(state, t):
        return None
    given = since if by_log else t.log[-1].time
    reviewed = [a for a in agents if a.role is Role.TICKET_REVIEWER and a.launched > since
                and a.launched >= given]
    if reviewed:
        what = (f"ticket reviewer {reviewed[-1].agent_id} left draft {t.number} under "
                f"`tickets/draft/` with no finding")
        choice = ruled(state, what, {Ruling.AGAIN: "launch another ticket reviewer on it",
                                     Ruling.OPEN: "move it to `tickets/open/`"})
        if isinstance(choice, Send):
            return choice
        if choice is Ruling.OPEN:
            return Bash(log(t.number, Status.OPEN, Status.DRAFT,
                            f"opened by the coordinator's ruling {ruling_key(what)}", None))
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
                    f"{LAST}: opens with no further ticket review", None))


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

