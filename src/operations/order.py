"""The order in which the operator's command takes the procedures' steps,
and the batch of launches of one output.

The steps come in this order: the resume of each agent the usage limit
stopped (`limit_resume`); the coordinator's lines in no form the
command reads, each given back to the coordinator once, and then the
fault of each run script, once for each text it has (`runs`); the ticket
files the read of the tracker left out (`decisions.unread_files`); the
alerts; the tickets on stalled agents; the messages on the concept
faults of the solver passes that ended (`concept_faults`); the request to a ticket analyst on a held step to give its decision
again; the decisions for the user, the changes handed to the coordinator
(`merging.handoffs`), and the items of each ticket analyst's
reply for the coordinator; the monitor's steps (`monitor`); at launch,
the release of tickets; the move back to `tickets/open/` of the tickets the coordinator wrote on
under `tickets/blocked/`, `tickets/waiting/` or `tickets/closed/`; the coordinator's later
lines to the ticket analysts that run on their tickets; the ticket
analysts on open tickets; the move to `tickets/draft/` of the changes
that a ticket holds up (`ticket_stall.stall`); the review
of drafts; the changes; the solver pipelines; the cost audit, the code
review, the standing doc review, the gate and the process assessment
(`batches`); After a batch; the
messages and the tickets on the stalled tickets of the operators
(`alerts.ticket_stalls`), last, so that a step that would end a stall
comes before the message on it. A step that
is a message an operator already sent is passed over, and so are an
undecided step an operator already handled (`handled.repeated`) and a step
an `Override: pass over` ruling passed over (`directives.passed`), other
than a solver pass, whose pipeline stops on it (`passes.run`), and a step
the step journal gives as in flight or retired (`journal.due`). A
launch a procedure gives, other than that of a ticket analyst on a held
step, is held where its chain of causes runs `lineage.DEPTH` launches of
its kind deep (`lineage`). A launch comes with each launch the procedures
give after it, with the launches before it made, up to the harness's
limit of concurrent subagents; each step of the procedures from the
release of tickets on that is no launch, or that launches a ticket
analyst on a held step, is set aside, and comes at a later call, in this
order (`batch`)."""


import shlex
from collections.abc import Callable
from dataclasses import replace

from controlled_markdown import mctx
from operations import (alerts, batches, changes, concept_faults, decisions, drafts, limit_resume, lineage, merging,
                        monitor, passes, runs, ticket_stall, triage, taking)
from operations.directives import (
    lines,
    passed,
    unread,
)
from operations.roles import PASSES, Purpose, description, launch_parameters, launched_type
from operations.state import Agent, Call, State, Tool, Waits
from operations.final_reply import failure
from operations.handled import held_aside, repeated
from operations.constants import COORDINATOR, SUBAGENT_LIMIT
from operations.journal import BOUND, Due, due
from operations.log_commands import AGENT, FILE_TICKET
from operations.pacing import Unknown
from operations.steps import (Bash, Journaled, Launch, Send, Step, Undecided, key,
                              unread_line)
from ticketing.text import ticket_text
from ticketing.times import utc_stamp
from ticketing.vocabulary import DEFECT_SECTIONS, Domain, Kind


def first(state: State, *procedures: Callable[[State], Step | None]) -> Step | None:
    """The first step of `procedures` that is ready (`placed`)."""
    for procedure in procedures:
        s, _ = placed(state, procedure)
        if s is not None:
            return s
    return None


def placed(state: State, procedure: Callable[[State], Step | None]
           ) -> tuple[Step | None, Undecided | None]:
    """The step of `procedure` that is ready, where an undecided step is the
    launch of a ticket analyst on it (`decisions`) and a launch whose chain
    of causes holds it is the step held on it (`lineage.held`), and the undecided step
    the procedure waits on, where it waits on one. A procedure whose step
    a ruling passed over waits until the state changes. A step passed
    over is undecided, once, as one its procedure waits on, other than the
    launch of an analyst on an undecided step: where the line that passed
    it over answered that step, the step stays held. A procedure whose
    step, as it gives it, `State.aside` holds gives no step. A step the
    journal gives as in flight or retired gives no step either, and
    one it gives as reaching `journal.BOUND` gives the step that retires
    it (`retire`)."""
    s = procedure(state)
    if s is not None and held_aside(state, s):
        return None, None
    while s is not None:
        if isinstance(s, Launch):
            s = lineage.held(state, s)
        if repeated(s, state):
            return None, s if isinstance(s, Undecided) else None
        on = s if isinstance(s, Undecided) else None
        if on is not None:
            s = decisions.launch(state, on)
        if not (isinstance(s, Launch) and s.role in PASSES) and (
                ruling := passed(s, state)) is not None:
            s = None if on is not None else Undecided(mctx(
                "step {key}, which the line `{line}` passed over, holds up its "
                "procedure").format(key=key(s), line=ruling.text))
            continue
        if not isinstance(s, Launch | Send | Bash):
            return s, None
        match due(state.journal, key(s)):
            case Due.GIVE:
                return s, None
            case Due.WAIT:
                return None, on
            case Due.RETIRE:
                return retire(state, s), None
    return None, None


def retire(state: State, step: Journaled) -> Bash:
    """The command that files the one `bug` on `step`, which the journal
    gives as given `journal.BOUND` times in a row, and that retires it
    for the session."""
    k = key(step)
    given = state.journal.of(k)[-BOUND:]
    title = mctx("`scripts/operate.py next`: gives step {key} of `{origin}` {bound} times in "
                 "a row").format(key=k, origin=step.origin, bound=BOUND)
    impact = mctx("`next` retired step {key}, which `{origin}` gives, for the session, and "
                  "its procedure gives nothing in its place.").format(
        key=k, origin=step.origin)
    evidence = "\n".join([mctx("The step as `next` gives it last:"), "```", repr(step), "```",
                          mctx("The times `next` gave it, as the journal gives them:"),
                          *(GIVE_LINE.format(time=utc_stamp(e.given), operator=e.operator,
                                             outcome=e.close.outcome if e.close else "",
                                             why=e.close.why if e.close else "")
                            for e in given)])
    impact_section, evidence_section = DEFECT_SECTIONS
    text = ticket_text(Kind.BUG, title, {impact_section: impact, evidence_section: evidence})
    return Bash(shlex.join([*FILE_TICKET, Domain.AGENT.value, state.me, AGENT])
                + " <<'TICKET'\n" + text + "TICKET", k, retires=k, occasion=k)


GIVE_LINE = mctx("- {time}, to {operator}: {outcome} {why}")


LOAD_SECONDS = 900
"""How long after the last write of an agent type's rendered definition a
launch of that type that fails with the type not found is taken as made
before the harness loaded the type, and is made again (`unloaded`), as the
section `An agent type not found` of `prompts/agents/notes/launching.md`
gives."""

RETRY_SECONDS = 60
"""How long after a launch that `unloaded` gives the launch is made again,
as the section `An agent type not found` of
`prompts/agents/notes/launching.md` gives."""


def launch_calls(state: State, step: Launch) -> list[Call]:
    """The Agent calls of `step` by `state.me`."""
    what = description(step.role, step.subject)
    return [c for c in state.transcripts.calls if c.operator == state.me
            and c.tool == Tool.AGENT and c.input.get("description") == what]


def failed_last(calls: list[Call]) -> Call | None:
    return calls[-1] if calls and calls[-1].error else None


def unloaded(state: State, step: Launch) -> Call | None:
    """The last Agent call of `step` by `state.me`, where it failed, the
    first line of its result is `Agent type '<agent type>' not found` or
    starts with that text followed by `.`, and it came less than
    `LOAD_SECONDS` after the last write of that type's rendered definition
    (`GitRead.definitions`)."""
    if (last := failed_last(launch_calls(state, step))) is None:
        return None
    agent_type = launched_type(step.role, step.subject)
    written = state.git.definitions.get(agent_type)
    if written is None or last.time - written >= LOAD_SECONDS:
        return None
    why = failure(last)
    bare = mctx("Agent type '{agent_type}' not found").format(agent_type=agent_type)
    if why != bare and not why.startswith(bare + "."):
        return None
    return last


def made(state: State, step: Launch) -> State:
    """`state` with `step` made, as the next read would give it with no
    report yet: an Agent call of `state.me` at `state.now` that gives the
    step, with no result, and a pending agent of `state.me` with no agent
    id."""
    call = Call(operator=state.me, time=state.now, tool=Tool.AGENT, result=None, error=False,
                input=launch_parameters(step.role, step.subject, step.model) | {"prompt": step.brief})
    agent = Agent(agent_id=None, operator=state.me, role=step.role, subject=step.subject,
                  brief=step.brief, launched=state.now, waits=Waits.AT_WORK, reports=(),
                  notifies=True)
    t = state.transcripts
    return replace(state, transcripts=replace(t, calls=(*t.calls, call),
                                              agents=(*t.agents, agent)))


def joins(state: State, step: Step) -> bool:
    """Whether `step` goes out in a batch. `operator_step` holds a launch
    made again after an `unloaded` call back from the state already read.
    A held step given on the state with the batch's launches made can rest
    on what `made` leaves out, such as an agent id, so a later call reads
    it on the state the transcripts give."""
    if not isinstance(step, Launch):
        return False
    analysis = batches.analysis(step.role, step.subject)
    held = analysis is not None and analysis[0] is Purpose.STEP
    return not held and unloaded(state, step) is None


def batch(state: State, watch: monitor.MonitorState, first_launch: Launch) -> tuple[Launch, ...]:
    """`first_launch`, then each launch the procedures give on the state
    with each launch before it made (`made`), in the plan's order, past
    the steps of `LATE` that are no launch or that launch a ticket analyst
    on a held step, which a later call gives. A
    step of a procedure of `LATE` that does not join the batch (`joins`)
    is set aside (`State.aside`), as its procedure gave it, and the
    procedures read again. The batch ends where a procedure of `EARLY` or
    the monitor gives a step that does not join it, where the operator is
    past its context bound, as `next_step` then gives its final reply,
    where the pending agents of the session's operators number
    `SUBAGENT_LIMIT`, since the agents of the session share the limit, or
    where no procedure of `LATE` gives a step."""
    out = [first_launch]
    state = made(state, first_launch)
    while (not state.past_bound
           and sum(a.pending for a in state.transcripts.agents) < SUBAGENT_LIMIT):
        early = first(state, *EARLY, lambda st: monitor_step(st, watch))
        if early is not None:
            if not isinstance(early, Launch) or not joins(state, early):
                break
            out.append(early)
            state = made(state, early)
            continue
        for procedure in LATE:
            given = procedure(state)
            s, _ = placed(state, lambda _st: given)
            if s is None or given is None:
                continue
            if isinstance(s, Launch) and joins(state, s):
                out.append(s)
                state = made(state, s)
            else:
                state = replace(state, aside=state.aside | {key(given)})
            break
        else:
            break
    return tuple(out)


def unread_lines(state: State) -> Step | None:
    found = [unread_line(ln.text) for ln in unread(state)]
    for ln in runs.run_lines(lines(state)):
        if isinstance(fault := runs.given(state, ln), str):
            found.append(runs.fault_message(ln, runs.STARTS_NOTHING, fault))
        if isinstance(fault := runs.takes_given(state, ln), str):
            found.append(runs.fault_message(ln, runs.TAKES_NOTHING, fault))
    if isinstance(pace := state.computed.pace, Unknown):
        found.append(Send(COORDINATOR, mctx("The usage pace counts as past: {why}").format(
            why=pace.why), f"pace {pace.why}"))
    return next((s for s in found if not repeated(s, state)), None)


def launching(state: State) -> Step | None:
    """The release of tickets, before the operator's first launch."""
    if any(c.operator == state.me and c.tool == Tool.AGENT for c in state.transcripts.calls):
        return None
    return taking.release(state)


def pipelines(state: State) -> Step | None:
    return passes.step(state)[0]


EARLY: tuple[Callable[[State], Step | None], ...] = (
    limit_resume.step, unread_lines, decisions.unread_files, alerts.step, alerts.stalls, alerts.stuck, alerts.late_resumes, concept_faults.step, decisions.asks, triage.decisions, merging.handoffs, triage.main_wanted, triage.for_coordinator,
    triage.unfinished)
LATE: tuple[Callable[[State], Step | None], ...] = (
    launching, triage.reopen, triage.later_lines, triage.settle, ticket_stall.stall, drafts.step,
    changes.step,
    pipelines, batches.audit, batches.code_review, batches.lib_review, batches.standing_review,
    batches.overdue_review, batches.gate,
    batches.assessment, batches.step, alerts.ticket_stalls)
PROCEDURES = EARLY + LATE


def monitor_step(state: State, watch: monitor.MonitorState) -> Step | None:
    return monitor.step(watch, lambda s: repeated(s, state))
