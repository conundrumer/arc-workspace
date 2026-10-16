"""The operator's next step, in the order `order` gives, its waits, and
its final reply.

One operator carries the session's work at a time: an operator for which a
later one of the session runs ends at once, and the later one carries on
from the state, so two operators never act on one ticket. The coordinator's
lines, and the other agents' messages other than the alerts `alerts` acts
on for the operator that carries the work on, give steps only to the
operator they reached, so the work a line to an earlier operator left
unfinished reaches a later one only where the coordinator gives it again
(`passes.every`);
a `Decision:` line that rules a held step holds for every operator
(`directives`), and the items for the coordinator of a ticket analyst's
reply go to the final reply of the operator that carries that reply
(`final_reply.carrier`). An operator past its context bound ends at once
too, and asks its parent, the coordinator or an operator launcher, for a
fresh operator with no lines; the operator launched next takes up from the state each line
that the operators before it in a row that ended so received
(`taken_up`), and, once their work is no longer open, through
`taking.release`, the changes of the session and of the tickets the
coordinator gives it in a line, and of each ticket a chain of links
reaches from one of those.

Where no step is ready, and an agent of an operator runs that is not
stuck, a ticket of the operators' waits on another holder whose work is
open and that is not stuck (`TranscriptsRead.stuck`), a ticket
file the read of the tracker left out may still be written
(`decisions.writing`), or the usage pace alone holds back an open
ticket (`taking.pace_held`), the agent runs
the command again, which blocks in the foreground first. Otherwise the
agent gives its final reply, after the message that sends its parent
its text (`ending`), with each stuck agent or holder it waited on."""

from collections.abc import Mapping, Sequence

from controlled_markdown import mctx
from operations import (changes, decisions, drafts, monitor, passes, runs, triage, taking)
from operations.directives import (
    NUMBER,
    TASK,
    Directive,
    Line,
    Pipeline,
    lines,
)
from operations.roles import Role
from operations.state import Call, State, Ticket
from ticketing.times import utc_stamp
from ticketing.vocabulary import Status
from operations.final_reply import (FOR_CONTEXT, ending_step, final_sends, final_sends_in,
                                   for_context, live_holder, nested, sent_final_text)
from operations.handled import repeated
from operations.order import EARLY, LATE, PROCEDURES, first, monitor_step, placed
from operations.steps import (Poll, Step, Undecided, decision_key)

GIVEN_AGAIN = mctx("a line below that stands unfinished reaches it only where it is given to it "
                   "again")


def elsewhere(state: State) -> list[str]:
    """The tickets of the operators' scope that another live holder
    (`live_holder`) of the session (`State.session_holders`) holds."""
    return [n for n in sorted(taking.scope(state))
            if (t := state.tracker.tickets.get(n)) is not None and t.status is Status.ASSIGNED
            and t.holder not in (None, state.me) and t.holder in state.session_holders
            and live_holder(state, t.holder)]


def unknown_line(line: str) -> str:
    """The line of a final reply that gives the `monitor.undecided` line
    `line`."""
    return f"- {line}"


def next_step(state: State, watch: monitor.MonitorState) -> Step:
    """The operator's next step, where `watch` is the state the monitor's
    steps read. Each reply gives, after its lines, each line
    `monitor.undecided` gives."""
    unknown = [unknown_line(line) for line in dict.fromkeys(monitor.undecided(watch))]
    mine = state.operators.index(state.me) if state.me in state.operators else -1
    later = [o for o in state.operators[mine + 1:] if o in state.open_operators]
    if later:
        return ending(state,
                      mctx("Operator {operator} carries the work on, from the state; {given}.").format(
                          operator=later[-1], given=GIVEN_AGAIN)
                      + "\n" + "\n".join([*reply_lines(state), *unknown]))
    s = first(state, *EARLY)
    if s is not None:
        return s
    if state.past_bound:
        return ending(state,
                      FOR_CONTEXT + "\n" + "\n".join([*reply_lines(state), *unknown]))
    s = first(state, lambda st: monitor_step(st, watch), *LATE)
    if s is not None:
        return s
    pace = taking.pace_held(state, [*triage.unsettled_open(state),
                                    *(t.number for t in taking.ready(state)
                                      if not taking.taken_before(t))])
    stuck = state.transcripts.stuck
    waits = [a.agent_id for a in state.transcripts.agents if a.pending or a.agent_id in state.transcripts.quiet]
    waits += [h for n in elsewhere(state) if (h := state.tracker.tickets[n].holder) is not None]
    if (pace is not None or any(w is None or w not in stuck for w in waits)
            or any(decisions.writing(state, u) for u in state.tracker.unread)):
        return Poll(pace)
    quiet = [mctx("- Stopped waiting on {agent}: no progress since {time}.").format(
        agent=w, time=utc_stamp(stuck[w].since)) for w in dict.fromkeys(waits) if w is not None]
    return ending(state, "\n".join([final(state), *quiet, *unknown]))


def ending(state: State, text: str) -> Step:
    """The operator's final reply, whose text is `text`: the message that
    sends its parent (`State.parents`) `text`, where the operator sent none
    since the last message that reached it, then the reply."""
    parent = state.parents[state.me]
    since = max((m.time for m in state.received), default=0.0)
    return ending_step(parent, text,
                       any(c.time > since for c in final_sends(state, state.me)))


def taken_up(me: str, operators: Sequence[str], calls: Sequence[Call],
             parents: Mapping[str, str]) -> frozenset[str]:
    """The operators of `operators` launched right before `me`, in a row,
    each of which `next` printed the final reply `FOR_CONTEXT`, as their
    `calls` to their `parents` give it."""
    mine = operators.index(me) if me in operators else 0
    out: set[str] = set()
    for o in reversed(operators[:mine]):
        if not any(for_context(sent_final_text(c) or "")
                   for c in final_sends_in(calls, o, parents[o])):
            break
        out.add(o)
    return frozenset(out)


def pipeline_state(o: passes.Outcome | None) -> str | None:
    """Why a pipeline is unfinished, or None where it ran to its end."""
    if o is None:
        return mctx("its pipeline has not started")
    if not o.ended:
        return mctx("its pipeline runs")
    return STOPPED.format(why=o.standing.stopped) if o.standing.stopped else None


STOPPED = mctx("its pipeline stopped: {why}")


def stands_under(t: Ticket) -> str:
    return mctx("stands under `tickets/{status}/`").format(status=t.status.value)


REASON = mctx("{of}: {reason}")


def line_state(state: State, ln: Line, outcomes: list[tuple[Pipeline, passes.Outcome]]) -> str:
    """A line of the coordinator's to the operator, as done or as
    unfinished with its reasons."""
    numbers = NUMBER.findall(ln.rest)
    reasons: list[str] = []
    match ln.kind:
        case Directive.SOLVE:
            by_task = {p.task: o for p, o in outcomes}
            reasons = [REASON.format(of=m["task"], reason=r) for m in TASK.finditer(ln.rest)
                       if (r := pipeline_state(by_task.get(m["task"]))) is not None]
        case Directive.RUN:
            reasons = run_state(state, ln, outcomes)
        case Directive.DRAFTS:
            under = {t.number for t in drafts.unended(state)}
            reasons = [draft_stands(n) for n in numbers if n in under]
        case Directive.EXPEDITE:
            reasons = [mctx("ticket {n} {stands}").format(n=n, stands=stands_under(t))
                       for n in sorted(taking.reached(state, set(numbers)))
                       if (t := state.tracker.tickets.get(n)) is not None and t.status is not Status.CLOSED]
        case Directive.MERGED:
            if not any(a.launched > ln.message.time for a in state.agents_of(Role.BATCH_PROFILE)):
                reasons = [mctx("After a batch has not run since it was given")]
        case Directive.MERGE:
            reasons = [mctx("change {n} {stands}").format(n=n, stands=stands_under(t))
                       for n in numbers
                       if (t := state.tracker.tickets.get(n)) is not None and t.status is not Status.CLOSED]
        case Directive.OPEN:
            reasons = [settled_open(n) for n in triage.unsettled(state)]
        case None:
            reasons = [mctx("it is in no form the command reads, and went to the coordinator")]
        case _:
            pass
    if not reasons:
        return mctx("- `{line}`: done").format(line=ln.text)
    return mctx("- `{line}`: unfinished: {reasons}").format(line=ln.text,
                                                             reasons="; ".join(reasons))


def run_state(state: State, ln: Line, outcomes: list[tuple[Pipeline, passes.Outcome]]) -> list[str]:
    """The reasons the `Run:` line `ln` stands unfinished: each pipeline of
    its run that runs, the start its script gives, and a standing fault,
    with, where any of these stands, the reason each stopped pipeline
    stopped."""
    by_pipeline = dict(outcomes)
    own = runs.started(state, ln)
    fault = runs.given(state, ln)
    going = [REASON.format(of=s.pipeline.task, reason=r) for s in own
             if s.failed is None and not (o := by_pipeline[s.pipeline]).ended
             and (r := pipeline_state(o)) is not None]
    if runs.next_start(state, ln, passes.running(state)) is not None:
        going.append(mctx("its script gives a pipeline to start"))
    if isinstance(fault, str):
        going.append(mctx("a fault stops it: {fault}").format(fault=fault))
    if not going:
        return []
    stopped = [REASON.format(of=s.pipeline.task, reason=r) for s in own
               if (r := s.failed if s.failed is not None
                   else None if (why := by_pipeline[s.pipeline].standing.stopped) is None
                   else STOPPED.format(why=why)) is not None]
    return [*going, *stopped]


def draft_stands(number: str) -> str:
    return mctx("draft {number} stands under `tickets/draft/`").format(number=number)


def settled_open(number: str) -> str:
    return mctx("ticket {number} stands open after its ticket analyst returned").format(
        number=number)


def sentence(clause: str) -> str:
    return clause[:1].upper() + clause[1:]


def line_states(state: State) -> list[str]:
    """Each line of the operator's brief and of the coordinator's later
    messages to it, as done or as unfinished with its reasons, each distinct item once, in
    the order of its first line."""
    _, outcomes = passes.step(state)
    return list(dict.fromkeys(line_state(state, ln, outcomes) for ln in lines(state)))


def reply_lines(state: State) -> list[str]:
    """The lines each reply of the operator that ends it gives: its lines
    (`line_states`), the items for the coordinator it carries
    (`triage.told`), and the held steps no decision reached
    (`decisions.undecided`, `decisions.failed`)."""
    return [*line_states(state), *triage.told(state),
            *decisions.undecided(state, holding(state)), *decisions.failed(state)]


def holding(state: State) -> set[str]:
    """The decision keys of the undecided steps the procedures wait on, as
    `placed` gives them."""
    return {decision_key(u.what) for procedure in PROCEDURES
            if (u := placed(state, procedure)[1]) is not None} | {
        decision_key(u.what) for u in decisions.unread_steps(state)} | {
        decision_key(u.what) for t in changes.held(state)
        if isinstance(u := changes.next_step(state, t), Undecided) and repeated(u, state)}


def stands(state: State, head: str, step: Step | None) -> tuple[str, bool]:
    """The line of the final reply on a draft or a change that stands, by
    `head`, with its step: where that step is undecided and went to a
    ticket analyst, the line gives that step, which its procedure waits
    on, and the second value holds."""
    if isinstance(step, Undecided) and repeated(step, state):
        return head + mctx(": it waits on a decision of the step: {what}").format(
            what=step.what), True
    return head, False


def final(state: State) -> str:
    """The operator's final reply: what stands at its end."""
    out = reply_lines(state)
    for n, deps in taking.waiting(state):
        waited = ", ".join(deps)
        out.append("- " + mctx("Change {n} not taken: it waits for {waited}").format(
            n=n, waited=waited))
    standing = [stands(state, f"- {sentence(draft_stands(t.number))}",
                       drafts.draft_step(state, t, [], [])) for t in drafts.unended(state)]
    standing += [(f"- {sentence(settled_open(n))}", False)
                 for n in triage.unsettled(state)]
    standing += [stands(state, "- " + mctx("Change {n} stays under `tickets/assigned/`").format(
                            n=t.number),
                        changes.next_step(state, t)) for t in changes.held(state)]
    out += [line for line, _ in standing]
    head = (mctx("Done: no procedure has a step left other than those that wait on a "
                 "decision, as the lines below give.")
            if any(asked for _, asked in standing)
            else mctx("Done: no procedure has a step left."))
    out.insert(0, head)
    for a in state.agents_of(Role.AFTER_MERGE):
        if a.operator == state.me and (r := a.last_report) is not None:
            out.append("- " + mctx("The report after the merge of change {number}, by "
                                   "{agent}:").format(number=a.subject, agent=a.agent_id))
            out += nested(r.text)
    return "\n".join(out)
