"""The solver pipelines: Analyze, then Create, then Refine on one task, from
the pass the coordinator gives, as
[Passes on a task](prompts/agents/notes/launching.md#passes-on-a-task)
gives the claim and the work set aside around them.

After each pass, a transcript review of it, then one ticket analyst with
the tickets the pass's report lists under `## Tickets filed` and those the
review filed, and the review. The next pass runs once each `interference`
ticket on the task filed since the pipeline started stands under
`tickets/closed/`; the changes that settle them are taken first, as
`changes.boosted` gives. The pipeline stops where the pass's reply is no
report's path, or a report with no `## Tickets filed` section, once the
coordinator has that reply, quoted, as undecided; where an `interference`
ticket waits on the user; where one stands open once the ticket analyst
returned; or where an operator passed over the launch of its next pass.
Once it ends or stops, the work set aside goes back, as
`scripts/operate.py restore` does."""

import re
import shlex
from dataclasses import dataclass

from operating import briefs
from operating.directives import Pipeline, pipelines, queue_counts
from operating.roles import PASSES, Purpose, Role, analyst_subject, joined
from operating.state import Agent, State
from ticketing.vocabulary import Domain, Kind, Status
from operating.steps import COORDINATOR, RUN_COMMAND, Bash, Launch, Send, Step, passed, undecided
from operating.tracker import blocked_on_user

TASK = re.compile(r"\b[0-9a-f]{8}\b")
SETS_ASIDE = (Role.ANALYZE, Role.CREATE)
QUEUE_SPARE = 3
"""How many tasks the queue lists per task the coordinator asks for, so
that a failed claim leaves one to take."""


@dataclass(frozen=True)
class Outcome:
    """Where a pipeline stands: its next step, None where it waits, and
    where it has ended, the reason it stopped, or None where it ran to its
    end."""
    step: Step | None
    ended: bool = False
    stopped: str | None = None


def claim_command(state: State, task: str) -> str:
    d = state.main_tree / "work" / "task" / task
    return (f"mkdir -p {shlex.quote(str(d))} && (set -C; echo \"$CLAUDE_CODE_SESSION_ID\" > "
            f"{shlex.quote(str(d / 'claim'))})")


def aside_command(task: str, role: Role) -> str:
    return f"{RUN_COMMAND} set-aside {task} {role}"


def restore_command(task: str) -> str:
    return f"{RUN_COMMAND} restore {task}"


def ran(state: State, command: str, since: float) -> list[bool]:
    """Whether each call of `command` since `since` failed."""
    return [c.error for c in state.bash_calls(command) if c.time >= since and c.result is not None]


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
            if state.claims.get(p.task) != state.session:
                claim = claim_command(state, p.task)
                tries = ran(state, claim, since)
                if any(tries):
                    return Outcome(None, True, f"the claim on task {p.task} fails")
                return Outcome(Bash(claim))
            aside = aside_command(p.task, role)
            if role in SETS_ASIDE and not ran(state, aside, since):
                return Outcome(Bash(aside))
            launch = Launch(role, p.task, briefs.solver_pass(p.task))
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
            told = no_report(role, a)
            if not state.sent(COORDINATOR, told.message):
                return Outcome(told)
            return end(state, p, restore, f"the {role} pass {a.agent_id} replied with no "
                                          f"path of a report with a `## Tickets filed` "
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
            return Outcome(Launch(Role.TICKET_ANALYST, subject, briefs.pass_settle(
                numbers, p.task, review.agent_id or "", state.me)))
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


def no_report(role: Role, a: Agent) -> Send:
    """The step that gives the coordinator, quoted, a pass's reply that
    names no report file with a `## Tickets filed` section."""
    r = a.last_report
    quoted = "\n".join(f"> {line}" for line in (r.text if r else "").strip().splitlines())
    return undecided(f"the {role} pass {a.agent_id} replied with no path of a report that "
                     f"has a `## Tickets filed` section, so its pipeline on {a.subject} "
                     f"stops. Its reply:\n{quoted}")


def end(state: State, p: Pipeline, restore: str, reason: str | None) -> Outcome:
    if not ran(state, restore, p.since):
        return Outcome(Bash(restore))
    return Outcome(None, True, reason)


def ended_before(state: State, p: Pipeline, time: float) -> bool:
    """Whether the pipeline `p` ended before `time`: its work set aside went
    back by then."""
    return any(p.since <= c.time < time and c.result is not None and not c.error
               for c in state.bash_calls(restore_command(p.task)))


def queued(state: State) -> list[Pipeline]:
    """The pipelines on tasks taken from the queue: for each line that asks
    for tasks from it, the tasks of the queue's listing whose claim the
    session took, up to the count the line gives, from Analyze. A line
    given while the pipelines of an earlier one run, as a line given again,
    takes no tasks."""
    out: list[Pipeline] = []
    for count, since in queue_counts(state):
        if any(not q.task or not ended_before(state, q, since) for q in out):
            continue
        command = f"bash scripts/queue.sh --order name -n {count * QUEUE_SPARE}"
        calls = [c for c in state.bash_calls(command) if c.time >= since and c.result]
        if not calls:
            out.append(Pipeline("", Role.ANALYZE, since))
            continue
        tasks = list(dict.fromkeys(TASK.findall(calls[-1].result or "")))
        taken = [t for t in tasks if state.claims.get(t) == state.session
                 or any(a.launched >= since for a in state.agents_of(Role.ANALYZE, t))]
        out += [Pipeline(t, Role.ANALYZE, since) for t in taken[:count]]
        if len(taken) < count:
            for t in tasks:
                if t not in taken and not any(ran(state, claim_command(state, t), since)):
                    out.append(Pipeline(t, Role.ANALYZE, since))
                    break
    return out


def every(state: State) -> list[Pipeline]:
    """The pipelines the coordinator's lines give. A line on a task whose
    pipeline from an earlier line had not ended when it was given, as a
    line given again, starts none."""
    out: list[Pipeline] = []
    for p in [*pipelines(state), *queued(state)]:
        if p.task and any(q.task == p.task and not ended_before(state, q, p.since) for q in out):
            continue
        out.append(p)
    return out


def step(state: State) -> tuple[Step | None, list[tuple[Pipeline, Outcome]]]:
    """The next step of the pipelines, and where each stands."""
    outcomes: list[tuple[Pipeline, Outcome]] = []
    first: Step | None = None
    for p in every(state):
        if not p.task:
            count = next(c for c, s in queue_counts(state) if s == p.since)
            o = Outcome(Bash(f"bash scripts/queue.sh --order name -n {count * QUEUE_SPARE}"))
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
