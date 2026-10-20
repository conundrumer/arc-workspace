"""The order in which the operator's command takes the procedures' steps,
and the batch of launches of one output.

The steps come in this order: the resume of each agent the usage limit
stopped (`limit_resume`); the load check of the machine watcher's
newest alert (`load_check`); the coordinator's lines in no form the
command reads, each given back to the coordinator once, and then the
fault of each run script, once for each text it has (`runs`); the ticket
files the read of the tracker left out (`decisions.unread_files`); the
alerts; the tickets on stalled agents; the messages on the concept
faults of the solver passes that ended (`concept_faults`); the request to a ticket analyst on a held step to give its decision
again; the decisions for the user, the changes handed to the coordinator
(`merging.handoffs`), and the items of each ticket analyst's
reply for the coordinator; the monitor's steps (`monitor`); the release
of tickets; the move to `tickets/reopened/` of the tickets the coordinator wrote on
under `tickets/blocked/`, `tickets/waiting/` or `tickets/closed/`; the coordinator's later
lines to the ticket analysts that run on their tickets; the ticket
analysts on open tickets; the review of drafts; the changes, and for a
held change with no step, the step `idle_changes` gives where it is
idle; the move to `tickets/draft/` of the changes that a ticket holds up
(`ticket_stall.stall`), so that the take of a change comes before the
move of the changes that wait on it; the solver pipelines; the cost
audit (`cost_audit`); the code review and the lib review (`reviews`);
the standing doc review and the review on an overdue reader
(`standing_reviews`); the gate (`gate_launch`); the process assessment
(`assessment`); the sweep and the script check (`after_profile`); After
a batch (`batches`); the
messages and the tickets on the stalled tickets of the operators
(`alerts.ticket_stalls`), so that a step that would end a stall comes
before the message on it; the message and the tickets on the tickets
that wait on nothing that moves them (`unwaited`), after each step that
would give such a ticket a party; and, last, the message to the coordinator on
a held change whose wait is stuck (`alerts.stuck_waits`). A step that
is a message an operator already sent is passed over, and so are an
undecided step an operator already handled (`handled.repeated`) and a step
an `Op override: pass over` ruling passed over (`directives.passed`), other
than a solver pass, whose pipeline stops on it (`passes.run`), and a step
the step journal gives as in flight or retired (`journal.due`). A
launch a procedure gives, other than that of a ticket analyst on a held
step, is held where its chain of causes runs `lineage.DEPTH` launches of
its kind deep (`lineage`), and so is a launch of an agent type the
operator's agent listing lacks (`unlisted`). Each step that the usage
pace holds, as `--help pace` of `operate.py` gives it
(`start_holds.pace_holds`), is held, and its procedure gives its next
step in its place, with the held step set aside
(`State.aside`). A launch comes with each
launch the procedures
give after it, with the launches before it made, up to the harness's
limit of concurrent subagents or the pace's cap (`start_holds.limit`); each step of the procedures from the
release of tickets on that is no launch, or that launches a ticket
analyst on a held step, is set aside, and comes at a later call, in this
order (`batch`)."""


from collections.abc import Callable
from dataclasses import replace

from controlled_markdown import mctx
from operations import (after_profile, alerts, assessment, batches, changes, concept_faults, cost_audit, decisions, drafts,
                        gate_launch, idle_changes, limit_resume, lineage, load_check, merging, monitor, passes, reviews, runs,
                        standing_reviews, start_holds, ticket_stall, triage, taking, unbatched, unwaited)
from operations.directives import (
    lines,
    passed,
    unread,
)
from operations import briefs
from operations.pacing import Capped, Pace
from operations.roles import PASSES, Purpose, Role, launch_parameters, launched_type
from operations.state import Agent, Call, NotComputed, State, Tool, Waits, memoized
from operations.handled import held_aside, repeated
from operations.constants import COORDINATOR
from operations.journal import BOUND, Due, due, failures
from operations.log_commands import file_ticket
from operations.steps import (Bash, Journaled, Launch, Send, Step, Undecided, key,
                              retirement_key, unread_line)
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
    a ruling passed over waits until the state changes. A step a ruling passed
    over goes as `scripts/operate.py --help rulings` gives it; where the
    line that passed it over answered that step, the step stays held. A
    procedure whose step, as it gives it, `State.aside` holds gives no
    step. Which step the journal holds back or retires is as
    `scripts/operate.py --help journal` gives it (`journal.due`, `retire`).
    A procedure that gives the step of one of several subjects passes over
    a subject whose step `State.aside` holds (`held_aside`).
    A launch the operator's agent listing lacks (`unlisted`) gives no step
    where it is due. A step the usage pace holds (`start_holds.pace_holds`),
    and a step whose placed step the journal retired (`Due.RETIRED`), is
    set aside, and the procedure read again."""
    waited: Undecided | None = None
    while True:
        given, s, on, retired = placed_given(state, procedure)
        if given is None:
            return None, waited
        if s is None:
            if not retired:
                return s, on or waited
        else:
            step = s
            if not start_holds.pace_holds(state, lambda: start_holds.starts_run(state, step)):
                return s, on or waited
        waited = waited or on
        state = replace(state, aside=state.aside | {key(given)})


@memoized
def placed_given(state: State, procedure: Callable[[State], Step | None]
                 ) -> tuple[Step | None, Step | None, Undecided | None, bool]:
    """The step `procedure` gives on `state`, None where it gives none or
    `held_aside` holds it, with what `place` gives for it, the usage pace
    aside."""
    given = procedure(state)
    if given is None or held_aside(state, given):
        return None, None, None, False
    return given, *place(state, given)


def place(state: State, s: Step | None) -> tuple[Step | None, Undecided | None, bool]:
    """The step of `placed` for the step `s` its procedure gives, the
    usage pace aside, the undecided step it waits on, and whether the step
    it placed is one the journal retired (`Due.RETIRED`), of which it gives
    no step."""
    while s is not None:
        if isinstance(s, Launch):
            s = lineage.held(state, s)
        if isinstance(s, Launch | Send | Bash) and due(state.journal, s, state.now) is Due.RETIRED:
            return None, None, True
        if repeated(s, state):
            return None, s if isinstance(s, Undecided) else None, False
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
            return s, None, False
        match due(state.journal, s, state.now):
            case Due.GIVE:
                return (None, None, False) if unlisted(state, s) else (s, None, False)
            case Due.WAIT:
                return None, on, False
            case Due.RETIRED:
                return None, on, True
            case Due.RETIRE:
                return retire(state, s), None, False
    return None, None, False


def retire(state: State, step: Journaled) -> Bash:
    """The command that files the one `bug` on `step`, which the journal
    gives as given `journal.BOUND` times in a row, and that retires it
    for the session."""
    k = key(step)
    given = failures(state.journal.of(k))[-BOUND:]
    title = mctx("`scripts/operate.py next`: gives step {key} of `{origin}` {bound} times in "
                 "a row").format(key=k, origin=step.origin, bound=BOUND)
    impact = mctx("`next` retired step {key}, which `{origin}` gives, for the session.").format(
        key=k, origin=step.origin)
    evidence = "\n".join([mctx("The step as `next` gives it last:"), "```", repr(step), "```",
                          mctx("The times `next` gave it, as the journal gives them:"),
                          *(GIVE_LINE.format(time=utc_stamp(e.given), operator=e.operator,
                                             outcome=e.close.outcome if e.close else "",
                                             why=e.close.why if e.close else "")
                            for e in given)])
    impact_section, evidence_section = DEFECT_SECTIONS
    text = ticket_text(Kind.BUG, title, {impact_section: impact, evidence_section: evidence})
    retiring = retirement_key(step)
    return file_ticket(Domain.AGENT, state.me, text, retiring, retires=retiring, occasion=retiring)


GIVE_LINE = mctx("- {time}, to {operator}: {outcome} {why}")


def unlisted(state: State, step: Step) -> bool:
    """Whether `step` is a launch that `operate.py --help next` gives as
    one of an agent type the operator's agent listing lacks."""
    if not isinstance(step, Launch) or state.listing is None:
        return False
    agent_type = launched_type(step.role, step.subject, step.model)
    return agent_type not in state.listing and agent_type in state.git.definitions


def pace_held_step(state: State) -> Pace | Capped | None:
    """What holds agent starts (`start_holds.hold`), where it holds the
    step that `place` gives for a procedure of `PROCEDURES` on `state`, or
    None."""
    held = start_holds.hold(state)
    if held is None:
        return None
    for procedure in PROCEDURES:
        _, s, _, _ = placed_given(state, procedure)
        if start_holds.pace_holds(state, lambda: s is not None and start_holds.starts_run(state, s)):
            return held
    return None


def lacked(state: State) -> Launch | None:
    """The launch of the first procedure of `PROCEDURES` that `placed`
    holds for the agent listing (`unlisted`), as `placed` gives it on
    `state` with no listing read, or None."""
    if state.listing is None or state.git.definitions.keys() <= state.listing:
        return None
    unread = replace(state, listing=None)
    for procedure in PROCEDURES:
        s, _ = placed(unread, procedure)
        if isinstance(s, Launch) and unlisted(state, s):
            return s
    return None


def listing_wait(state: State, held: Launch) -> Launch | None:
    """The launch of the agent whose end resumes the operator, held on
    `held`, or None where such an agent of `state.me` is pending."""
    subject = key(held)
    if any(a.pending and a.operator == state.me
           for a in state.agents_of(Role.LISTING_WAIT, subject)):
        return None
    return Launch(Role.LISTING_WAIT, subject, briefs.LISTING_WAIT, occasion=subject)


def made(state: State, step: Launch) -> State:
    """`state` with `step` made, as the next read would give it with no
    report yet: an Agent call of `state.me` at `state.now` that gives the
    step, with no result, and a pending agent of `state.me` with no agent
    id."""
    call = Call(operator=state.me, time=state.now, tool=Tool.AGENT, result=None, error=False,
                input=launch_parameters(step.role, step.subject, step.model, step.brief))
    agent = Agent(agent_id=None, operator=state.me, role=step.role, subject=step.subject,
                  brief=call.input["prompt"], launched=state.now, since=state.now, waits=Waits.AT_WORK, reports=(),
                  notifies=True)
    t = state.transcripts
    return replace(state, transcripts=replace(t, calls=(*t.calls, call),
                                              agents=(*t.agents, agent)))


def joins(state: State, step: Step) -> bool:
    """Whether `step` goes out in a batch. A held step given on the state
    with the batch's launches made can rest on what `made` leaves out, such
    as an agent id, so a later call reads it on the state the transcripts
    give."""
    if not isinstance(step, Launch):
        return False
    analysis = unbatched.analysis(step.role, step.subject)
    return analysis is None or analysis[0] is not Purpose.STEP


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
    where the running agents of the session's operators number
    `start_holds.limit`, since the agents of the session share it, or
    where no procedure of `LATE` gives a step."""
    out = [first_launch]
    state = made(state, first_launch)
    while not state.past_bound and start_holds.running(state) < start_holds.limit(state):
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
    if isinstance(pace := state.computed.pace, NotComputed):
        found.append(Send(COORDINATOR, mctx("The usage pace counts as past: {why}").format(
            why=pace.why), f"pace {pace.why}"))
    return next((s for s in found if not repeated(s, state)), None)


def held_changes(state: State) -> Step | None:
    """`changes.step`, with the step on an idle held change
    (`idle_changes.step`)."""
    return changes.step(state, idle_changes.step)


def pipelines(state: State) -> Step | None:
    return passes.step(state)[0]


EARLY: tuple[Callable[[State], Step | None], ...] = (
    limit_resume.step, load_check.load_check, unread_lines, decisions.unread_files, alerts.step, alerts.stalls, alerts.stuck, alerts.late_resumes, concept_faults.step, decisions.asks, triage.decisions, merging.handoffs, triage.main_wanted, triage.for_coordinator,
    triage.unfinished)
LATE: tuple[Callable[[State], Step | None], ...] = (
    taking.release, triage.reopen, triage.later_lines, triage.settle, drafts.step,
    held_changes, ticket_stall.stall,
    pipelines, cost_audit.audit, *reviews.PROCEDURES, standing_reviews.standing_review,
    standing_reviews.overdue_review, gate_launch.gate,
    assessment.assessment, after_profile.validation, after_profile.script_check, batches.step,
    alerts.ticket_stalls, unwaited.step, alerts.stuck_waits)
PROCEDURES = EARLY + LATE


def monitor_step(state: State, watch: monitor.MonitorState) -> Step | None:
    return monitor.step(watch, lambda s: repeated(s, state))
