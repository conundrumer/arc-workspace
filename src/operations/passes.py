"""The solver pipelines: Analyze, then Create, then Refine on one task, from
the pass the coordinator gives, as
[Passes on a task](prompts/agents/notes/launching.md#passes-on-a-task)
gives the claim and the work set aside around them. Whether a task is
claimed is read from its claim file: a pipeline on a task another session
claims stops, and a pipeline from the queue takes no such task.

After each pass, a transcript review of it, then one ticket analyst with
the tickets the pass's report lists under `## Tickets filed` and those the
review filed, and the review. The next pass runs once each `interference`
ticket on the task filed since the pipeline started stands under
`tickets/closed/`; the changes that settle them are taken first, as
`changes.boosted` gives. A pass's reply that is no report's path, or a
report with no `## Tickets filed` section, goes back to the pass once,
with a request to send it again in that form. The pipeline stops where
the pass's answer is still in no such form, once a ticket analyst on
that answer, quoted, as an undecided step was launched; where an `interference`
ticket waits on the user; where one stands open once the ticket analyst
returned; or where a ruling passed over the launch of its next pass.
Once it ends or stops, the work set aside goes back, as
`scripts/operate.py restore` does."""

import re
import shlex
from dataclasses import dataclass

from arc.task import TASK_ID
from controlled_markdown import mctx
from operations import briefs
from operations.directives import (Line, Pipeline, lines, overrides, passed, pipelines,
                                   queue_counts, session_lines)
from operations.reports import TICKETS_FILED
from operations.roles import PASSES, Purpose, Role, analyst_subject, joined
from operations.state import Agent, State
from ticketing.vocabulary import Domain, Kind, Status
from operations.command_words import RUN_COMMAND
from operations.handled import ask_again, bash_calls, repeated
from operations.steps import Bash, Launch, Send, Step, Undecided, agent_ids
from operations.task_work import CLAIM, tasks_work
from operations.tracker import blocked_on_user

TASK = re.compile(rf"\b{TASK_ID}\b")
SETS_ASIDE = (Role.ANALYZE, Role.CREATE)
QUEUE_SPARE = 3
"""How many tasks the queue lists per task the coordinator asks for, so
that a failed claim leaves one to take."""


def queue_command(count: int) -> str:
    return f"bash scripts/queue.sh --order name -n {count * QUEUE_SPARE}"


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
    return [t.number for t in state.tickets.values() if t.domain is Domain.TASK
            and t.subject == task and t.filer == Role.TRANSCRIPT_REVIEW.value
            and t.filed >= review.launched]


def run(state: State, p: Pipeline) -> Outcome:
    since = p.since
    restore = restore_command(p.task)
    order = PASSES[PASSES.index(p.start):]
    for role in order:
        a = latest(state, role, p.task, since)
        if a is None:
            holder = state.claims.get(p.task)
            if holder is not None and holder != state.session:
                return Outcome(None, True, f"the claim on task {p.task} fails: session "
                                           f"{holder} holds it")
            if holder is None:
                claim = claim_command(state, p.task)
                tries = ran(state, claim, since)
                if any(tries):
                    return Outcome(None, True, f"the claim on task {p.task} fails")
                return Outcome(None if tries else Bash(claim))
            aside = aside_command(p.task, role)
            if role in SETS_ASIDE and not ran(state, aside, since):
                return Outcome(Bash(aside))
            launch = Launch(role, p.task, briefs.solver_pass(p.task, overrides(state, p.task, role, since)))
            if (line := passed(launch, state)) is not None:
                return end(state, p, restore, f"the line `{line}` passed over its {role} pass")
            return Outcome(launch)
        since = a.launched
        if a.pending:
            return Outcome(None)
        if a.agent_id is None:
            return end(state, p, restore, f"the {role} pass on {p.task} has no agent id")
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
            return end(state, p, restore, f"the {role} pass {a.agent_id} replied with no "
                                          f"path of a report with a `{TICKETS_FILED}` "
                                          f"section")
        review = latest(state, Role.TRANSCRIPT_REVIEW, a.agent_id, a.launched)
        if review is None:
            return Outcome(Launch(Role.TRANSCRIPT_REVIEW, a.agent_id, briefs.transcript_review(
                a.agent_id, Domain.TASK.value, p.task, True)))
        if review.pending:
            return Outcome(None)
        numbers = [*filed, *review_tickets(state, p.task, review)]
        analyst = [x for x, purpose, nums in state.analysts()
                   if purpose is Purpose.PASS and p.task in nums and x.launched > review.launched]
        if numbers and not analyst:
            subject = analyst_subject(Purpose.PASS, joined([p.task, *numbers]))
            reviewer = agent_ids([review])
            if isinstance(reviewer, Undecided):
                return Outcome(reviewer)
            return Outcome(Launch(Role.TICKET_ANALYST, subject, briefs.pass_settle(
                numbers, p.task, reviewer[0], state.me), items=len(numbers)))
        if any(x.pending for x in analyst):
            return Outcome(None)
        interference = [t for t in state.tickets.values() if t.kind is Kind.INTERFERENCE
                        and t.domain is Domain.TASK and t.subject == p.task
                        and t.filed >= p.since and t.status is not Status.CLOSED]
        for t in interference:
            if blocked_on_user(t) is not None:
                return end(state, p, restore, f"interference ticket {t.number} waits on the user")
            if t.status in (Status.OPEN, Status.ASSIGNED):
                return end(state, p, restore, f"the ticket analyst left interference ticket "
                                              f"{t.number} open")
        if interference:
            return Outcome(None)
    return end(state, p, restore, None)


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
    return p.since <= time and not any(
        p.since <= c.time < time and not c.error
        for c in bash_calls(state, restore_command(p.task)))


def queued(state: State, given: list[Line]) -> list[Pipeline]:
    """The pipelines on tasks taken from the queue: for each line of
    `given` that asks for tasks from it, the tasks of the queue's listing
    whose claim the session took, up to the count the line gives, from
    Analyze. A line given while the pipelines of an earlier one run, as a
    line given again, takes no tasks."""
    out: list[Pipeline] = []
    for count, m in queue_counts(given):
        since = m.time
        if any(not q.task or runs_at(state, q, since) for q in out):
            continue
        command = queue_command(count)
        calls = [c for c in bash_calls(state, command) if c.time >= since and c.result]
        if not calls:
            out.append(Pipeline("", Role.ANALYZE, since, m.operator, True))
            continue
        tasks = list(dict.fromkeys(TASK.findall(calls[-1].result or "")))
        taken = [t for t in tasks if state.claims.get(t) == state.session
                 or any(a.launched >= since for a in state.agents_of(Role.ANALYZE, t))]
        out += [Pipeline(t, Role.ANALYZE, since, m.operator, True) for t in taken[:count]]
        if len(taken) < count:
            for t in tasks:
                if t not in taken and t not in state.claims:
                    out.append(Pipeline(t, Role.ANALYZE, since, m.operator, True))
                    break
    return out


def session(state: State) -> list[Pipeline]:
    """The pipelines the coordinator's lines to the session's operators
    give, in the order their lines arrived. A line on a task whose pipeline
    from an earlier line, or from the same line, runs when it is given, as
    a line given again, starts none."""
    given = session_lines(state)
    out: list[Pipeline] = []
    for p in sorted([*pipelines(given), *queued(state, given)], key=lambda x: x.since):
        if p.task and any(q.task == p.task and runs_at(state, q, p.since) for q in out):
            continue
        out.append(p)
    return out


def every(state: State) -> list[Pipeline]:
    """The pipelines of `session` that the coordinator's lines to the
    operator `me` give: those a line to it starts, and those a line to it
    gives again before they end, a `Solve` line by their task and a
    `Solve from the queue` line each pipeline a line of that form gives."""
    given = lines(state)
    again = [(m.time, None) for _, m in queue_counts(given)]
    again += [(p.since, p.task) for p in pipelines(given)]
    return [p for p in session(state) if p.operator == state.me
            or any((p.queued if task is None else p.task == task) and runs_at(state, p, time)
                   for time, task in again)]


def step(state: State) -> tuple[Step | None, list[tuple[Pipeline, Outcome]]]:
    """The next step of the pipelines, and where each stands."""
    outcomes: list[tuple[Pipeline, Outcome]] = []
    first: Step | None = None
    for p in every(state):
        if not p.task:
            count = next(c for c, m in queue_counts(session_lines(state)) if m.time == p.since)
            o = Outcome(Bash(queue_command(count)))
        else:
            o = run(state, p)
        outcomes.append((p, o))
        if first is None and o.step is not None:
            first = o.step
    return first, outcomes


def awaits_analyst(state: State, task: str) -> bool:
    """Whether a pipeline on `task` has yet to launch the ticket analyst of
    its latest pass."""
    for p in every(state):
        if p.task != task:
            continue
        o = run(state, p)
        if o.ended:
            continue
        passes = [a for r in PASSES for a in state.agents_of(r, task) if a.launched >= p.since]
        if not passes:
            continue
        last = max(passes, key=lambda a: a.launched)
        if not any(x.launched > last.launched for x, purpose, nums in state.analysts()
                   if purpose is Purpose.PASS and task in nums):
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
