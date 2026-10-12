"""The solver pipelines: Analyze, then Create, then Refine on one task, from
the pass the coordinator gives, as
[Passes on a task](prompts/agents/notes/launching.md#passes-on-a-task)
gives the claim and the work set aside around them. Whether a task is
claimed is read from its claim file: a pipeline on a task another session
claims stops.

The pipeline keeps two chains on the task. On the pass chain, the next
pass runs once the pass before it ended with its report and no
`interference` ticket on the task filed since the pipeline started stands
outside `tickets/closed/`; it waits on no review and no analyst. On the
review chain, each ended pass gets a transcript review once the review of
the pass before it returned, then one ticket analyst with the tickets the
pass's report lists under `## Tickets filed` and those its review filed,
and the review; a pass's analyst is the one whose brief gives that pass's
review. The pipeline ends once each review and analyst has returned. For
the `interference` tickets, the changes that settle them are taken first, as
`changes.boosted` gives. A pass's reply that is no report's path, or a
report with no `## Tickets filed` section, goes back to the pass once,
with a request to send it again in that form. The pipeline stops where
the pass's answer is still in no such form, once a ticket analyst on
that answer, quoted, as an undecided step was launched; where an `interference`
ticket waits on the user; where one stands open once the ticket analyst
returned; or where a ruling passes over its next pass. A ruling on a pass
holds for each pipeline on its task unless the work set aside for an
earlier pipeline on that task went back after the ruling and before the
pipeline started.
Once it ends or stops, the work set aside goes back, as
`scripts/operate.py restore` does."""

import shlex
from dataclasses import dataclass

from controlled_markdown import mctx
from operations import briefs, runs
from operations.directives import Line, Pipeline, lines, overrides, passed, pipelines, session_lines
from operations.reports import TICKETS_FILED
from operations.roles import PASSES, Purpose, Role, analyst_subject, joined
from operations.state import Agent, State
from ticketing.vocabulary import Domain, Kind, Status
from operations.command_words import RUN_COMMAND
from operations.handled import ask_again, bash_calls, repeated
from operations.steps import Bash, Launch, Send, Step, Undecided, agent_ids
from operations.task_work import CLAIM, CLAIM_HELD, tasks_work
from operations.tracker import blocked_on_user

SETS_ASIDE = (Role.ANALYZE, Role.CREATE)


@dataclass(frozen=True)
class Outcome:
    """Where a pipeline stands: its next step, None where it waits, and
    where it has ended, the reason it stopped, or None where it ran to its
    end."""
    step: Step | None
    ended: bool = False
    stopped: str | None = None


def claim_command(state: State, task: str) -> str:
    d = tasks_work(state.main_tree) / task
    return (f"mkdir -p {shlex.quote(str(d))} && (set -C; echo \"$CLAUDE_CODE_SESSION_ID\" > "
            f"{shlex.quote(str(d / CLAIM))})")


def aside_command(task: str, role: Role) -> str:
    return f"{RUN_COMMAND} set-aside {task} {role}"


def restore_command(task: str) -> str:
    return f"{RUN_COMMAND} restore {task}"


def ran(state: State, command: str, since: float) -> list[bool]:
    """Whether each call that made the step `command` since `since`
    failed: a pending call has not."""
    return [c.result is not None and c.error for c in bash_calls(state, command)
            if c.time >= since]


def latest(state: State, role: Role, subject: str, since: float) -> Agent | None:
    found = [a for a in state.agents_of(role, subject) if a.launched >= since]
    return found[-1] if found else None


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
    return [t.number for t in state.tickets.values() if t.domain is Domain.TASK
            and t.subject == task and t.filer == Role.TRANSCRIPT_REVIEW.value
            and t.filed >= review.launched and (bound is None or t.filed < bound)
            and t.status is not Status.WATCHING]


def settles(analyst: Agent, nums: list[str], review: str) -> bool:
    """Whether the pass analyst `analyst`, whose subject gives `nums`, is
    the one of the pass whose transcript review is the agent `review`."""
    task, *numbers = nums
    first = briefs.PASS_SETTLE.format(numbers=briefs.item_list(numbers), task=task, review=review)
    return analyst.brief.startswith(first)


type Ended = tuple[str, Agent, tuple[str, ...]]
"""A pass that ended with its report: its agent id, the pass, and the
tickets its report lists."""


def reviews(state: State, task: str, ended: list[Ended]) -> Outcome | None:
    """The review chain over the passes of `ended`: its next step,
    Outcome(None) where it waits, or None where each review and analyst
    has returned."""
    found = [latest(state, Role.TRANSCRIPT_REVIEW, i, a.launched) for i, a, _ in ended]
    waits = False
    for (i, _, filed), review in zip(ended, found, strict=True):
        if review is None:
            return Outcome(Launch(Role.TRANSCRIPT_REVIEW, i, briefs.transcript_review(
                i, Domain.TASK.value, task, True)))
        if review.pending:
            return Outcome(None)
        reviewer = agent_ids([review])
        if isinstance(reviewer, Undecided):
            return Outcome(reviewer)
        numbers = [*filed, *review_tickets(state, task, review)]
        analyst = [x for x, purpose, nums in state.analysts()
                   if purpose is Purpose.PASS and nums[0] == task and settles(x, nums, reviewer[0])]
        if numbers and not analyst:
            subject = analyst_subject(Purpose.PASS, joined([task, *numbers]))
            return Outcome(Launch(Role.TICKET_ANALYST, subject, briefs.pass_settle(
                numbers, task, reviewer[0], state.me), items=len(numbers)))
        waits = waits or any(x.pending for x in analyst)
    return Outcome(None) if waits else None


def interference(state: State, p: Pipeline) -> Outcome | str | None:
    """The `interference` check before a pass: the reason the pipeline
    stops, Outcome(None) where a ticket holds the next pass, or None where
    none does."""
    found = [t for t in state.tickets.values() if t.kind is Kind.INTERFERENCE
             and t.domain is Domain.TASK and t.subject == p.task
             and t.filed >= p.since and t.status is not Status.CLOSED]
    for t in found:
        if blocked_on_user(t) is not None:
            return f"interference ticket {t.number} waits on the user"
        given = [x for x, _, nums in state.analysts()
                 if t.number in nums and x.launched > t.filed]
        if t.status in (Status.OPEN, Status.ASSIGNED) and given and not any(
                x.pending for x in given):
            return f"the ticket analyst left interference ticket {t.number} open"
    return Outcome(None) if found else None


def run(state: State, p: Pipeline) -> Outcome:
    """The next step of the pipeline `p`, the step of its review chain
    first, then that of its pass chain."""
    since = p.since
    restore = restore_command(p.task)
    ended: list[Ended] = []

    def stop(reason: str | None) -> Outcome:
        chain = reviews(state, p.task, ended)
        return chain if chain is not None else end(state, p, restore, reason)

    for role in p.passes:
        chain = reviews(state, p.task, ended)
        if chain is not None and chain.step is not None:
            return chain
        a = latest(state, role, p.task, since)
        if a is None:
            held = interference(state, p)
            if isinstance(held, str):
                return stop(held)
            if held is not None:
                return held
            holder = state.claims.get(p.task)
            if holder is not None and holder != state.session:
                return stop(CLAIM_HELD.format(task=p.task, holder=holder))
            if holder is None:
                claim = claim_command(state, p.task)
                tries = ran(state, claim, since)
                if any(tries):
                    return stop(f"the claim on task {p.task} fails")
                return Outcome(None if tries else Bash(claim))
            aside = aside_command(p.task, role)
            if role in SETS_ASIDE and not ran(state, aside, since):
                return Outcome(Bash(aside))
            launch = Launch(role, p.task, briefs.solver_pass(p.task, overrides(state, p.task, role, since)))
            ruling = passed(launch, state)
            if ruling is not None and not restored(state, p.task, ruling.message.time, p.since):
                return stop(f"the line `{ruling.text}` passed over its {role} pass")
            return Outcome(launch)
        since = a.launched
        if a.pending:
            return Outcome(None)
        if a.agent_id is None:
            return stop(f"the {role} pass on {p.task} has no agent id")
        filed = state.pass_tickets.get(a.agent_id)
        if filed is None:
            if a.reports:
                asked = ask_again(state, a.agent_id, [r.time for r in a.reports],
                                  briefs.PASS_FORM)
                if isinstance(asked, Send):
                    return Outcome(asked)
            told = no_report(role, a)
            if not repeated(told, state):
                return Outcome(told)
            return stop(f"the {role} pass {a.agent_id} replied with no path of a report with "
                        f"a `{TICKETS_FILED}` section")
        ended.append((a.agent_id, a, filed))
    chain = reviews(state, p.task, ended)
    if chain is not None:
        return chain
    held = interference(state, p)
    if isinstance(held, Outcome):
        return held
    return end(state, p, restore, held)


def no_report(role: Role, a: Agent) -> Undecided:
    """The undecided step on a pass's reply, quoted, that names no report
    file with a `## Tickets filed` section."""
    r = a.last_report
    quoted = "\n".join(f"> {line}" for line in (r.text if r else "").strip().splitlines())
    return Undecided(mctx("the {role} pass {agent} replied with no path of a report that has "
                          "a `{section}` section, so its pipeline on {task} stops. Its "
                          "reply:").format(role=role, agent=a.agent_id, section=TICKETS_FILED,
                                           task=a.subject) + "\n" + quoted)


def end(state: State, p: Pipeline, restore: str, reason: str | None) -> Outcome:
    if not ran(state, restore, p.since):
        return Outcome(Bash(restore))
    return Outcome(None, True, reason)


def runs_at(state: State, p: Pipeline, time: float) -> bool:
    """Whether the pipeline `p` runs at `time`, so that a line given then
    gives it again: its line came before or with that time, and its work
    set aside had not gone back by then."""
    return p.since <= time and not restored(state, p.task, p.since, time)


def restored(state: State, task: str, start: float, stop: float) -> bool:
    """Whether a `restore` call on `task` that did not fail came at or
    after `start` and before `stop`."""
    return any(start <= c.time < stop and not c.error
               for c in bash_calls(state, restore_command(task)))


def started(state: State, given: list[Line]) -> list[Pipeline]:
    """The pipelines whose start calls the `Run:` lines of `given` give,
    other than those whose call failed."""
    return [s.pipeline for ln in runs.run_lines(given) for s in runs.started(state, ln)
            if s.failed is None]


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


def every(state: State) -> list[Pipeline]:
    """The pipelines of `session` that the coordinator's lines to the
    operator `me` give: those a line to it starts, those a `Run:` line to
    it starts, and those a `Solve` line to it gives again by their task
    before they end."""
    given = lines(state)
    own = set(started(state, given))
    again = [(p.since, p.task) for p in pipelines(given)]
    return [p for p in session(state) if p.operator == state.me or p in own
            or any(p.task == task and runs_at(state, p, time) for time, task in again)]


DROPPED = mctx("a pipeline of an earlier line runs on its task")
"""The reason a run's pipeline that `session` drops ended."""


def running(state: State) -> list[Pipeline]:
    """The pipelines of `session` that run now."""
    return [p for p in session(state) if runs_at(state, p, state.now)]


def outcomes(state: State) -> list[tuple[Pipeline, Outcome]]:
    """Where each pipeline stands, and each run's pipeline that `session`
    drops as ended."""
    pipelines_now = every(state)
    out = [(p, Outcome(None, True, DROPPED.format(task=p.task)))
           for p in started(state, lines(state)) if p not in pipelines_now]
    return out + [(p, run(state, p)) for p in pipelines_now]


def step(state: State) -> tuple[Step | None, list[tuple[Pipeline, Outcome]]]:
    """The next step of the pipelines, and where each stands (`outcomes`),
    then the start that a run gives next."""
    found = outcomes(state)
    first = next((o.step for _, o in found if o.step is not None), None)
    if first is None:
        first = next((s for ln in runs.run_lines(lines(state))
                      if (s := runs.next_start(state, ln, running(state))) is not None), None)
    return first, found


def awaits_analyst(state: State, number: str) -> bool:
    """Whether a pipeline on the task of the ticket `number` has not ended,
    no pass analyst was launched with the ticket among its tickets, and the
    pipeline will give it one: a transcript review filed it since the
    pipeline started, or a solver pass did, while a pass of the pipeline is
    pending or the report of one that ended lists it."""
    t = state.tickets[number]
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
        passes = [a for r in PASSES for a in state.agents_of(r, t.subject) if a.launched >= p.since]
        if any(a.pending or a.agent_id is not None
               and number in (state.pass_tickets.get(a.agent_id) or ()) for a in passes):
            return True
    return False


def reviewed(state: State) -> frozenset[str]:
    """The agents that get a transcript review: each that one was launched
    on after its own launch, and each whose review launch a pipeline's next
    step gives on this read. The monitor reads this before the pipelines
    take their step, so a review about to launch counts too."""
    out = {a.agent_id for a in state.agents if a.agent_id is not None
           and latest(state, Role.TRANSCRIPT_REVIEW, a.agent_id, a.launched) is not None}
    _, outcomes = step(state)
    out |= {o.step.subject for _, o in outcomes
            if isinstance(o.step, Launch) and o.step.role is Role.TRANSCRIPT_REVIEW}
    return frozenset(out)
