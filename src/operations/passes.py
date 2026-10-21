"""The solver pipelines: Analyze, then Create, then Refine on one task, from
the pass the coordinator gives. `task_work` claims the task and sets
aside its earlier work around those passes. Whether a task is
claimed is read from its claim file: a pipeline on a task another session
claims stops.

The pipeline keeps two chains on the task. On the pass chain, the next
pass runs once the pass before it ended with its report and no
`interference` ticket on the task filed since the pipeline started stands
outside `tickets/closed/`; it waits on no review and no analyst. On the
review chain, each ended pass gets a transcript review once the review of
the pass before it returned, then, where any ticket below is, one ticket
analyst with the tickets the pass's report lists under `## Tickets filed`
that stand outside `tickets/closed/` once the review returned, those its
review filed, and the review; a pass's analyst is the one whose brief
gives that pass's review. The pipeline ends once each review and analyst has returned. For
the `interference` tickets, the changes that settle them are taken first, as
`change_take.boosted` gives. A pass's tickets are read from the report file
it wrote under the task's work directory since its launch, whatever its
reply. Where it wrote no such file with a `## Tickets filed` section, the
pass gets `messages.PASS_RESEND` on its reply once. The pipeline stops
where the pass still wrote no such file, once a ticket analyst on its last reply, quoted, as an
undecided step was launched; where an `interference`
ticket waits on the user; where one stands untaken or assigned once the ticket analyst
returned; or where a ruling passes over its next pass. A ruling on a pass
holds for each pipeline on its task unless the work set aside for an
earlier pipeline on that task went back after the ruling and before the
pipeline started.
Once an `interference` ticket on a task closes, while the task's solver
stands, a fresh agent fixes in place what the closure leaves wrong in it
(`fixes`); a pipeline of the session on that task holds its next pass and
its end until that fix returned. The fix launches only once the session
holds the task's claim, which it takes where none stands, and it releases
that claim once it returned where no pipeline of the session runs on the
task.
Once it ends or stops, the work set aside goes back, as
`scripts/operate.py restore` does, with the reason it stopped, or an empty
argument where it ran to its end. Once the first `restore` call on its
task that did not fail at or after its start, by any agent, gives that
argument, the pipeline has ended with that reason, and no later work on its task
changes that. Where the first such call gives the task id
alone, the pipeline's outcome is read from its passes, reviews and
tickets, as for a pipeline whose work has not gone back."""

import math
import shlex
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from controlled_markdown import mctx
from operations import briefs, messages, runs
from operations.directives import Line, Pipeline, lines, overrides, passed, pipelines, session_lines
from operations.completion import decided, occupies
from operations.reports import TICKETS_FILED
from operations.roles import PASSES, Purpose, Role, analyst_subject, joined
from operations.state import Agent, Call, Restore, State, Ticket, last_reported, memoized
from ticketing.vocabulary import UNTAKEN, Domain, Kind, Resolution, Status
from operations.command_words import RUN_COMMAND, simple_commands
from operations.handled import bash_calls, bash_calls_within, done, repeated, send_again
from operations.steps import Bash, Launch, Send, Step, Undecided, agent_ids
from operations.task_work import CLAIM_HELD
from operations.tracker import blocked_on_user

SETS_ASIDE = (Role.ANALYZE, Role.CREATE)

NO_REPORT = mctx("the {role} pass {agent} wrote, since its launch, no report file under its "
                 "task's work directory with a `{section}` section")


@dataclass(frozen=True)
class Outcome:
    """A pipeline's next step, None where it waits, whether it has ended,
    and where it stands."""
    step: Step | None
    ended: bool = False
    standing: runs.Standing = runs.Standing()


def claim_command(task: str) -> str:
    return f"{RUN_COMMAND} claim {task}"


def aside_command(task: str, role: Role) -> str:
    return f"{RUN_COMMAND} set-aside {task} {role}"


def restore_command(task: str) -> str:
    return f"{RUN_COMMAND} restore {task}"


def release_command(task: str) -> str:
    return f"{RUN_COMMAND} release {task}"


def restore_step(task: str, reason: str | None) -> str:
    return f"{restore_command(task)} {shlex.quote(reason or '')}"


def restore_argument(c: Call, task: str) -> str | None:
    """The argument the `restore` call `c` on `task` gives after the task
    id, None where it gives the task id alone."""
    lead = restore_command(task).split()
    for words in simple_commands(c.command):
        if words[:len(lead)] == lead and len(words) == len(lead) + 1:
            return words[-1]
    return None


def ran(state: State, command: str, since: float) -> list[bool]:
    """Whether each call that made the step `command` since `since`
    failed: a pending call has not."""
    return [c.result is not None and c.error for c in bash_calls(state, command)
            if c.time >= since]


def latest(state: State, role: Role, subject: str, since: float) -> Agent | None:
    found = [a for a in state.agents_of(role, subject) if a.launched >= since]
    if not found:
        return None
    a = found[-1]
    complete = (tickets_listed(state, a.agent_id) is not None if role in PASSES
                else occupies(a))
    return a if a.pending or complete else None


def review_tickets(state: State, task: str, review: Agent) -> list[str]:
    """The tickets `review` filed on `task`: those of the transcript review
    filed from its launch up to the launch of the first transcript review
    launched after it on any pass of `task`. The review of a pass launches
    only once the review before it returned, so that bound holds each
    review's tickets apart whatever passes have ended."""
    passes = {a.agent_id for role in PASSES for a in state.agents_of(role, task)
              if a.agent_id is not None}
    nexts = [r.launched for r in state.agents_of(Role.TRANSCRIPT_REVIEW)
             if r.subject in passes and r.launched > review.launched]
    bound = min(nexts, default=None)
    return [t.number for t in state.tracker.tickets.values() if t.domain is Domain.TASK
            and t.subject == task and t.filer == Role.TRANSCRIPT_REVIEW.value
            and t.filed >= review.launched and (bound is None or t.filed < bound)
            and t.status is not Status.DEFERRED]


def held(state: State, numbers: tuple[str, ...]) -> tuple[Ticket, ...]:
    tickets = state.tracker.tickets
    return tuple(tickets[n] for n in numbers if n in tickets)


def standing(state: State, numbers: tuple[str, ...]) -> list[str]:
    tickets = state.tracker.tickets
    return [n for n in numbers if n not in tickets or tickets[n].status is not Status.CLOSED]


def settles(analyst: Agent, review: str) -> bool:
    """Whether the pass analyst `analyst` is the one of the pass whose
    transcript review is the agent `review`. A pass analyst's brief gives
    one review's agent id, its own, whatever the wording of the brief."""
    return review in analyst.brief


type Ended = tuple[str, Agent, tuple[str, ...]]
"""A pass that ended with its report: its agent id, the pass, and the
tickets its report lists."""


def reviews(state: State, task: str, ended: list[Ended]) -> tuple[Step | None] | None:
    """The review chain over the passes of `ended`: its next step, (None,)
    where it waits, or None where each review and analyst has returned."""
    found = [latest(state, Role.TRANSCRIPT_REVIEW, i, a.launched) for i, a, _ in ended]
    waits = False
    for (i, ran_pass, filed), review in zip(ended, found, strict=True):
        if review is None:
            return (Launch(Role.TRANSCRIPT_REVIEW, i, briefs.transcript_review(
                i, Domain.TASK.value, task, True, held(state, filed)),
                occasion=str(last_reported([ran_pass]))),)
        if review.pending:
            return (None,)
        reviewer = agent_ids([review])
        if isinstance(reviewer, Undecided):
            return (reviewer,)
        numbers = [*standing(state, filed), *review_tickets(state, task, review)]
        analyst = [x for x, purpose, nums in state.analysts()
                   if purpose is Purpose.PASS and nums[0] == task and settles(x, reviewer[0]) and occupies(x)]
        if numbers and not analyst:
            subject = analyst_subject(Purpose.PASS, joined([task, *numbers]))
            return (Launch(Role.TICKET_ANALYST, subject, briefs.pass_settle(
                numbers, task, reviewer[0], state.me), items=len(numbers),
                occasion=str(last_reported([review]))),)
        waits = waits or any(x.pending for x in analyst)
    return (None,) if waits else None


def interference(state: State, p: Pipeline) -> str | bool:
    """The `interference` check before a pass: the reason the pipeline
    stops, or whether a ticket holds the next pass."""
    found = [t for t in state.tracker.tickets.values() if t.kind is Kind.INTERFERENCE
             and t.domain is Domain.TASK and t.subject == p.task
             and t.filed >= p.since and t.status is not Status.CLOSED]
    for t in found:
        if blocked_on_user(t) is not None:
            return mctx("interference ticket {number} waits on the user").format(number=t.number)
        given = [x for x, _, nums in state.analysts()
                 if t.number in nums and x.launched > t.filed and occupies(x)]
        if (t.status in UNTAKEN or t.status is Status.ASSIGNED) and given and not any(
                x.pending for x in given):
            return mctx("the ticket analyst left interference ticket {number} open").format(
                number=t.number)
    return bool(found)


type Stopped = tuple[str | None]
"""The end of a pass chain: the reason its pipeline stops, or None where
each pass ended with its report."""


def run(state: State, p: Pipeline) -> Outcome:
    """The next step of the pipeline `p`, the step of its review chain
    first, then that of its pass chain, or, where the first `restore`
    call on its task that did not fail since its start gives the argument
    after the task id, its end with that argument as the reason, or None
    where it is empty."""
    first = next(iter(restores(state, p.task, p.since, math.inf)), None)
    if first is not None and first.argument is not None:
        return Outcome(None, True, runs.Standing(stopped=first.argument or None))
    ended: list[Ended] = []
    hold = interference(state, p)
    held = hold is True
    fixing = p.task in fixed_tasks(state)
    own = pass_chain(state, p, ended, hold, fixing)
    chain = reviews(state, p.task, ended)
    passing = False
    if len(own) == 2:
        step, passing = own
        if chain is not None and chain[0] is not None:
            step = chain[0]
    elif chain is not None:
        step = chain[0]
    elif own[0] is None and held or fixing:
        step = None
    else:
        reason = own[0]
        return end(state, p, hold if reason is None and isinstance(hold, str) else reason)
    return Outcome(step, standing=runs.Standing(passing=passing, held=held))


type Next = tuple[Step | None, bool]
"""The next step of a pass chain, None where it waits, and its `passing`,
as `scripts/operate.py --help run` gives it."""


def pass_chain(state: State, p: Pipeline, ended: list[Ended], hold: str | bool,
               fixing: bool) -> Next | Stopped:
    """The next step of the pass chain of `p`, or its end, with each pass
    that ended with its report appended to `ended`, where `hold` is what
    `interference` gives on `p` and `fixing` whether a solver fix on its
    task is due or pending, which holds its next pass and counts as no
    pass to launch, so that the lane of a run's pipeline frees at the
    closure."""
    since = p.since
    for role in p.passes:
        a = latest(state, role, p.task, since)
        if a is None:
            if isinstance(hold, str):
                return (hold,)
            if hold:
                return (None, False)
            if fixing:
                return (None, False)
            holder = state.git.claims.get(p.task)
            if holder is not None and holder != state.session:
                return (CLAIM_HELD.format(task=p.task, holder=holder),)
            if holder is None:
                claim = claim_command(p.task)
                tries = ran(state, claim, since)
                if any(tries):
                    return (mctx("the claim on task {task} fails").format(task=p.task),)
                return (None if tries else Bash(claim, f"{p.task} claim",
                                                     occasion=work_occasion(state, p, since)), True)
            aside = aside_command(p.task, role)
            setting = Bash(aside, f"{p.task} aside {role}",
                           occasion=work_occasion(state, p, since))
            if role in SETS_ASIDE and not done(state, setting):
                return (setting, True)
            launch = Launch(role, p.task, briefs.solver_pass(p.task, overrides(state, p.task, role, since)),
                            occasion=str(since))
            ruling = passed(launch, state)
            if ruling is not None and not restored(state, p.task, ruling.message.time, p.since):
                return (mctx("the line `{line}` passed over its {role} pass").format(
                    line=ruling.text, role=role),)
            return (launch, True)
        since = a.launched
        if a.pending:
            return (None, True)
        if a.agent_id is None:
            return (mctx("the {role} pass on {task} has no agent id").format(role=role, task=p.task),)
        filed = tickets_listed(state, a.agent_id)
        if filed is None:
            if a.reports:
                asked = send_again(state, a.agent_id, [r.time for r in a.reports],
                                   messages.pass_resend, TICKETS_FILED)
                if isinstance(asked, Send):
                    return (asked, True)
            told = no_report(role, a)
            if not repeated(told, state):
                return (told, True)
            return (NO_REPORT.format(role=role, agent=a.agent_id, section=TICKETS_FILED),)
        ended.append((a.agent_id, a, filed))
    return (None,)


def tickets_listed(state: State, agent_id: str | None) -> tuple[str, ...] | None:
    """The tickets the report of the pass `agent_id` lists
    (`state.PassReport.tickets`)."""
    r = state.transcripts.pass_reports.get(agent_id or "")
    return None if r is None else r.tickets


def no_report(role: Role, a: Agent) -> Undecided:
    """The undecided step on a pass that wrote no report file with a
    `## Tickets filed` section since its launch, with its last reply
    quoted."""
    r = a.last_report
    quoted = "\n".join(f"> {line}" for line in (r.text if r else "").strip().splitlines())
    return Undecided("\n".join([
        mctx("{stop}, so its pipeline on {task} stops.").format(
            stop=NO_REPORT.format(role=role, agent=a.agent_id, section=TICKETS_FILED),
            task=a.subject),
        mctx("Its last reply:"), quoted]))


def end(state: State, p: Pipeline, reason: str | None) -> Outcome:
    """The end of the pipeline `p` with `reason`, the reason it stopped,
    or None where it ran to its end: the `restore` step that gives
    `reason`, until a `restore` call on its task, with or without that
    argument, came at or after the latest claim or set-aside of its task
    the operators' steps made since the pipeline's start, or that start
    where they made none: one the operator made, pending or failed
    included, or one `restores` gives. A second call would move back the
    files of a later set-aside and remove a later claim; a call before
    that claim or set-aside leaves the work they took for the pipeline."""
    restore = restore_step(p.task, reason)
    bound = taken_at(state, p.task, p.since)
    if not (ran(state, restore_command(p.task), bound) or ran(state, restore, bound)
            or restored(state, p.task, bound, math.inf)):
        return Outcome(Bash(restore, f"{p.task} restore",
                            occasion=str(set_aside_at(state, p.task, p.since))))
    return Outcome(None, True, runs.Standing(stopped=reason))


def work_occasion(state: State, p: Pipeline, since: float) -> str:
    """The occasion (`steps.key`) of the claim and the set-aside before a
    pass of `p` whose chain stands at `since`, the launch of the pass
    before it or the pipeline's start: that time, with the latest restore
    of its task since the pipeline's start, after which the work is
    claimed and set aside again."""
    return f"{since} {max((c.time for c in restores(state, p.task, p.since, state.now)), default=0.0)}"


def set_aside_at(state: State, task: str, since: float) -> float:
    """The time of the latest set-aside of `task`'s work since `since`, by
    any pass, the occasion of the restore that puts it back (`steps.key`),
    or `since` where none came."""
    return latest_call(state, [aside_command(task, role) for role in SETS_ASIDE], since)


def taken_at(state: State, task: str, since: float) -> float:
    """The time of the latest claim or set-aside of `task` since `since`,
    or `since` where none came."""
    return latest_call(state, [claim_command(task), *(aside_command(task, role) for role in SETS_ASIDE)],
                       since)


def latest_call(state: State, commands: list[str], since: float) -> float:
    """The time of the latest Bash call of the operators that ran one of
    `commands` since `since`, or `since` where none came."""
    return max((c.time for command in commands for c in bash_calls(state, command)
                if c.time >= since), default=since)


def runs_at(state: State, p: Pipeline, time: float) -> bool:
    """Whether the pipeline `p` runs at `time`, so that a line given then
    gives it again: its line came before or with that time, and its work
    set aside had not gone back by then."""
    return p.since <= time and not restored(state, p.task, p.since, time)


def restored(state: State, task: str, start: float, stop: float) -> bool:
    """Whether a `restore` call on `task` that did not fail came at or
    after `start` and before `stop`."""
    return bool(restores(state, task, start, stop))


def restores(state: State, task: str, start: float, stop: float) -> list[Restore]:
    """The `restore` calls on `task` that did not fail, at or after `start`
    and before `stop`, in time order: those `GitRead.restores` records, by
    any agent, and the operators' own, which a record may not yet hold. An
    operator's own call stands in both with one argument."""
    own = [Restore(c.time, restore_argument(c, task)) for c in bash_calls_within(
               state, restore_command(""), restore_command(task))
           if not c.error]
    return sorted((r for r in [*state.git.restores.get(task, ()), *own] if start <= r.time < stop),
                  key=lambda r: r.time)


def started(state: State, given: Iterable[Line]) -> list[Pipeline]:
    """The pipelines whose start calls the `Op run:` lines of `given` give,
    other than those whose call failed."""
    return [s.pipeline for ln in runs.run_lines(given) for s in runs.started(state, ln)
            if s.failed is None]


@memoized
def session(state: State) -> list[Pipeline]:
    """The pipelines the coordinator's lines to the session's operators
    give, and those their runs started, in the order of their lines and
    calls. A line on a task whose pipeline from an earlier line, or from
    the same line, runs when it is given, as a line given again, starts
    none."""
    given = session_lines(state)
    out: list[Pipeline] = []
    for p in sorted(dict.fromkeys([*pipelines(given), *started(state, given)]),
                    key=lambda x: x.since):
        if any(q.task == p.task and runs_at(state, q, p.since) for q in out):
            continue
        out.append(p)
    return out


@memoized
def every(state: State) -> list[Pipeline]:
    """The pipelines of `session` that the coordinator's lines to the
    operator `me` give: those a line to it starts, those an `Op run:` line to
    it starts, and those an `Op solve` line to it gives again by their task
    before they end."""
    given = lines(state)
    own = set(started(state, given))
    again = [(p.since, p.task) for p in pipelines(given)]
    return [p for p in session(state) if p.operator == state.me or p in own
            or any(p.task == task and runs_at(state, p, time) for time, task in again)]


DROPPED = mctx("a pipeline of an earlier line runs on its task")
"""The reason a run's pipeline that `session` drops ended."""


@memoized
def running(state: State) -> list[Pipeline]:
    """The pipelines of `session` that run now."""
    return [p for p in session(state) if runs_at(state, p, state.now)]


def outcomes(state: State) -> list[tuple[Pipeline, Outcome]]:
    """Where each pipeline stands, as `run` gives it, ended pipelines
    included, and each run's pipeline that `session` drops as ended."""
    pipelines_now = every(state)
    out = [(p, Outcome(None, True, runs.Standing(stopped=DROPPED.format(task=p.task))))
           for p in started(state, lines(state)) if p not in pipelines_now]
    return out + [(p, run(state, p)) for p in pipelines_now]


def step(state: State) -> tuple[Step | None, list[tuple[Pipeline, Outcome]]]:
    """The next step of the pipelines, and where each stands (`outcomes`),
    then the step of a solver fix (`fix_step`), then the start that a run
    gives next."""
    found = outcomes(state)
    first = next((o.step for _, o in found if o.step is not None), None)
    if first is None:
        first = fix_step(state)
    if first is None:
        first = next((s for ln in runs.run_lines(lines(state))
                      if (s := runs.next_start(state, ln, busy(state))) is not None), None)
    return first, found


FIXES_FROM = datetime(2026, 10, 17, 15, 3, 55, tzinfo=UTC).timestamp()
"""The time from which a closure gets a solver fix: the solvers that the
closures before it left wrong were fixed by hand."""


@dataclass(frozen=True)
class Fix:
    """A closed `interference` ticket whose solver fix is due, and the time
    its closure counts from (`resolved`)."""
    ticket: Ticket
    closed: float

    @property
    def task(self) -> str:
        return self.ticket.subject


def closing(t: Ticket) -> int | None:
    """The index in `t`'s log of the line that closed it, as `closing_line`
    in `scripts/file_ticket.py` reads it, or None where none did."""
    found = [i for i, ln in enumerate(t.log)
             if ln.status is Status.CLOSED and ln.resolution is not None]
    return found[-1] if found else None


def on_task(t: Ticket, task: str) -> bool:
    return t.kind is Kind.INTERFERENCE and t.domain is Domain.TASK and t.subject == task


def resolved(state: State, t: Ticket) -> float | None:
    """The time from which the closure of the `interference` ticket `t`
    counts: the time of its closing line, or, where it closed `duplicate`,
    the latest of that and the closing lines of the tickets it duplicates,
    followed through each ticket closed `duplicate` in turn. None where one
    of them is not closed or is not read, where that chain comes back to a
    ticket of it, or where it reaches another `interference` ticket on the
    task of `t`, which gets the fix itself."""
    seen: set[str] = set()
    at = 0.0
    u = t
    while u.number not in seen and u.status is Status.CLOSED and (i := closing(u)) is not None:
        seen.add(u.number)
        line = u.log[i]
        at = max(at, line.time)
        if line.resolution is not Resolution.DUPLICATE:
            return at
        target = state.ticket(line.duplicate_of) if line.duplicate_of is not None else None
        if target is None or on_task(target, t.subject):
            return None
        u = target
    return None


def fixers(state: State, t: Ticket, since: float) -> list[Agent]:
    """The fix agents of the session launched on `t` since `since`."""
    return [a for a in state.agents_of(Role.SOLVER_FIX, t.number) if a.launched >= since]


@memoized
def fixes(state: State) -> list[Fix]:
    """The `interference` tickets whose solver fix is due, in the tracker's
    order. The record that a fix is done is the line its agent writes on
    the ticket, which the tracker shares across sessions; a ticket closed
    again after that line gets a fix of its new closure. An interrupted
    fix with no completion line leaves that closure due. A
    solver pass on the task launched since the closure wrote the solver
    with the closure in place, so it leaves no fix due."""
    out: list[Fix] = []
    for t in sorted(state.tracker.tickets.values(), key=lambda t: t.order):
        if not on_task(t, t.subject) or t.subject not in state.git.solvers or not (
                state.mine(t) or t.session in state.sessions.fixed_for):
            continue
        at = resolved(state, t)
        i = closing(t)
        if at is None or i is None or at < FIXES_FROM or any(
                a.pending or decided(a) for a in fixers(state, t, at)) or any(
                a.launched >= at and (a.pending or tickets_listed(state, a.agent_id) is not None)
                for role in PASSES for a in state.agents_of(role, t.subject)):
            continue
        if any(ln.note.startswith(f"{briefs.FIX_MARK}:") for ln in t.log[i + 1:]):
            continue
        out.append(Fix(t, at))
    return out


def fix_agents(state: State) -> list[tuple[str, Agent]]:
    """Each fix agent of the session, with its task, where its ticket is
    read."""
    return [(t.subject, a) for a in state.agents_of(Role.SOLVER_FIX)
            if (t := state.ticket(a.subject)) is not None]


def fixed_tasks(state: State) -> set[str]:
    """The tasks whose solver fix is due or pending."""
    return {f.task for f in fixes(state)} | {task for task, a in fix_agents(state) if a.pending}


@memoized
def releases(state: State) -> list[tuple[str, Agent]]:
    """Each task whose claim is to be released, with the fix agent that
    returned on it: the latest on its task, with no fix pending there, no
    `release` call on it since its launch, and the claim held by the
    session while no pipeline of the session runs on the task, so that the
    claim is the fix's."""
    on = {p.task for p in running(state)}
    latest_fix = {task: a for task, a in fix_agents(state)}
    due = {f.task for f in fixes(state)}
    return [(task, a) for task, a in latest_fix.items()
            if not a.pending and task not in on and task not in due
            and state.git.claims.get(task) == state.session
            and not ran(state, release_command(task), a.launched)]


@memoized
def busy(state: State) -> set[str]:
    """The tasks a run's start waits on: each a pipeline of the session
    runs on, each whose solver fix is due or pending, and each whose fix's
    claim is still to be released."""
    return ({p.task for p in running(state)} | fixed_tasks(state)
            | {task for task, _ in releases(state)})


def waited_on(t: Ticket) -> str | None:
    """The change `t` last waited on, as its log gives it."""
    return next((ln.on_change for ln in reversed(t.log) if ln.on_change is not None), None)


def fix_step(state: State) -> Step | None:
    """The next step of the solver fixes: the `release` of a fix's claim,
    or, for a fix due on a task where no other fix is pending and no pass
    of a pipeline of the session on the task is pending, its launch once
    the session holds the task's claim, which the step takes first where
    none stands. Where another session holds it, the fix waits. A pipeline
    from an `Op solve` line claims its task only at its first pass, so a
    pipeline of the session on the task does not show that the session
    holds the claim. A pending fix whose task no claim holds, as after a
    `restore` that ran outside the steps, claims it again, so that no
    other pipeline sets aside the solver it edits."""
    for task, a in releases(state):
        return Bash(release_command(task), f"{task} release", occasion=str(a.launched))
    pending = {task for task, a in fix_agents(state) if a.pending}
    on = running(state)
    for task, a in fix_agents(state):
        if (a.pending and task not in state.git.claims
                and (step := claim_step(state, task, a.launched)) is not None):
            return step
    for f in fixes(state):
        if f.task in pending:
            continue
        past = fixers(state, f.ticket, f.closed)
        occasion = f"{f.closed} {past[-1].since}" if past else str(f.closed)
        launch = Launch(Role.SOLVER_FIX, f.ticket.number,
                        briefs.solver_fix(f.task, f.ticket.number, waited_on(f.ticket), state.me),
                        occasion=occasion)
        if any(a.pending for p in on if p.task == f.task for a in passes_of(state, p)):
            continue
        holder = state.git.claims.get(f.task)
        if holder == state.session:
            return launch
        if holder is not None:
            continue
        if (step := claim_step(state, f.task, f.closed)) is not None:
            return step
    return None


def claim_step(state: State, task: str, since: float) -> Bash | None:
    """The claim of `task` for a solver fix, None while the latest such
    call since `since` is pending or has not yet shown in the claim file;
    it is given again after a call that failed."""
    claim = claim_command(task)
    tries = ran(state, claim, since)
    if tries and not tries[-1]:
        return None
    return Bash(claim, f"{task} fix claim", occasion=f"{since} {len(tries)}")


def passes_of(state: State, p: Pipeline) -> list[Agent]:
    """The passes launched on the task of `p` since its start."""
    return [a for r in PASSES for a in state.agents_of(r, p.task) if a.launched >= p.since]


def awaits_analyst(state: State, number: str) -> bool:
    """Whether a pipeline on the task of the ticket `number` has not ended,
    no pass analyst was launched with the ticket among its tickets, and the
    pipeline will give it one: a transcript review filed it since the
    pipeline started, or a solver pass did, while a pass of the pipeline is
    pending or the report of one that ended lists it."""
    t = state.tracker.tickets[number]
    if t.domain is not Domain.TASK or any(
            purpose is Purpose.PASS and number in nums for _, purpose, nums in state.analysts()):
        return False
    for p in every(state):
        if p.task != t.subject or t.filed < p.since or run(state, p).ended:
            continue
        if t.filer == Role.TRANSCRIPT_REVIEW.value:
            return True
        if t.filer not in {r.value for r in PASSES}:
            continue
        passes = passes_of(state, p)
        if any(a.pending or a.agent_id is not None
               and number in (tickets_listed(state, a.agent_id) or ()) for a in passes):
            return True
    return False


def reviewed(state: State) -> frozenset[str]:
    """The agents that get a transcript review: each that one was launched
    on after its own launch, and each whose review launch a pipeline's next
    step gives on this read. The monitor reads this before the pipelines
    take their step, so a review about to launch counts too."""
    out = {a.agent_id for a in state.transcripts.agents if a.agent_id is not None
           and latest(state, Role.TRANSCRIPT_REVIEW, a.agent_id, a.launched) is not None}
    _, outcomes = step(state)
    out |= {o.step.subject for _, o in outcomes
            if isinstance(o.step, Launch) and o.step.role is Role.TRANSCRIPT_REVIEW}
    return frozenset(out)
