"""The step that ends the operator (`ending`), and the lines of what
stands at its end (`reply_lines`, `final`). `held` is the
set of the analyst keys (`steps.analyst_key`) of the undecided steps the
procedures wait on, which `holding` gives."""

from collections.abc import Callable, Iterable

from controlled_markdown import mctx
from operations import changes, decisions, drafts, passes, runs, taking, triage
from operations.directives import NUMBER, TASK, Directive, Line, Pipeline, lines
from operations.final_reply import ending_step, final_sends, final_text, first_line, nested
from operations.handled import repeated, sends_to
from operations.journal import BOUND
from operations.roles import Role
from operations.state import State, Ticket
from operations.order import PROCEDURES, placed
from operations.steps import Step, Undecided, analyst_key
from ticketing.vocabulary import Status


def ending(state: State, text: str) -> Step:
    """The operator's final reply, whose text is `text`: the message that
    sends its parent (`State.parents`) `text`, where the journal gives no
    message of the operator's done that sends a final reply with the first
    line of `text`, whose step was given after the last message that
    reached it and after the last final send of each operator of
    `State.taken_up`, then the reply."""
    parent = state.parents[state.me]
    since = max([*(m.time for m in state.received),
                 *(sends[-1].time for o in state.taken_up if (sends := final_sends(state, o)))],
                default=0.0)
    return ending_step(parent, text, since, any(
        e.operator == state.me and e.close is not None and e.given > since
        and (sent := final_text(e.text)) is not None and first_line(sent) == first_line(text)
        for e in sends_to(state, parent)))


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


type Outcomes = list[tuple[Pipeline, passes.Outcome]]


def line_state(state: State, ln: Line, outcomes: Outcomes) -> str:
    """A line of the coordinator's to the operator, as done or as
    unfinished with its reasons."""
    reasons = REASONS[ln.kind](state, ln, outcomes)
    if not reasons:
        return mctx("- `{line}`: done").format(line=ln.text)
    return mctx("- `{line}`: unfinished: {reasons}").format(line=ln.text,
                                                             reasons="; ".join(reasons))


def outside_closed(state: State, numbers: Iterable[str], word: str) -> list[str]:
    return [mctx("{word} {n} {stands}").format(word=word, n=n, stands=stands_under(t))
            for n in numbers
            if (t := state.tracker.tickets.get(n)) is not None and t.status is not Status.CLOSED]


def solve_state(state: State, ln: Line, outcomes: Outcomes) -> list[str]:
    by_task = {p.task: o for p, o in outcomes}
    return [REASON.format(of=m["task"], reason=r) for m in TASK.finditer(ln.rest)
            if (r := pipeline_state(by_task.get(m["task"]))) is not None]


def drafts_state(state: State, ln: Line, outcomes: Outcomes) -> list[str]:
    under = {t.number for t in drafts.unended(state)}
    return [draft_stands(n) for n in NUMBER.findall(ln.rest) if n in under]


def expedite_state(state: State, ln: Line, outcomes: Outcomes) -> list[str]:
    return outside_closed(state, sorted(taking.served(state, set(NUMBER.findall(ln.rest)))),
                          mctx("ticket"))


def merged_state(state: State, ln: Line, outcomes: Outcomes) -> list[str]:
    if any(a.launched > ln.message.time for a in state.agents_of(Role.BATCH_PROFILE)):
        return []
    return [mctx("no batch profile has launched since the line was given")]


def merge_state(state: State, ln: Line, outcomes: Outcomes) -> list[str]:
    return outside_closed(state, NUMBER.findall(ln.rest), mctx("change"))


def open_state(state: State, ln: Line, outcomes: Outcomes) -> list[str]:
    return [settled_open(n) for n in triage.unsettled(state)]


def unread_state(state: State, ln: Line, outcomes: Outcomes) -> list[str]:
    return [mctx("it is in no form the command reads, and went to the coordinator")]


def no_state(state: State, ln: Line, outcomes: Outcomes) -> list[str]:
    return []


def run_state(state: State, ln: Line, outcomes: Outcomes) -> list[str]:
    """The reasons the `Op run:` line `ln` stands unfinished: each pipeline of
    its run that runs, the start its script gives, and a standing fault,
    with, where any of these stands, the reason each stopped pipeline
    stopped."""
    by_pipeline = dict(outcomes)
    own = runs.started(state, ln)
    fault = runs.given(state, ln)
    going = [REASON.format(of=s.pipeline.task, reason=r) for s in own
             if s.failed is None and not (o := by_pipeline[s.pipeline]).ended
             and (r := pipeline_state(o)) is not None]
    if runs.next_start(state, ln, {p.task for p in passes.running(state)}) is not None:
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


REASONS: dict[Directive | None, Callable[[State, Line, Outcomes], list[str]]] = {
    Directive.SOLVE: solve_state, Directive.RUN: run_state, Directive.DRAFTS: drafts_state,
    Directive.EXPEDITE: expedite_state, Directive.ALLOW: no_state,
    Directive.MERGED: merged_state, Directive.MERGE: merge_state, Directive.OPEN: open_state,
    Directive.SCOPE: no_state, Directive.PAUSE: no_state, Directive.RESUME: no_state,
    Directive.PACE: no_state,
    Directive.OVERRIDE: no_state, Directive.DECISION: no_state, None: unread_state}
"""The reasons a line of each directive stands unfinished, by its
directive, None for a line in no form the command reads."""


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


def reply_lines(state: State, held: set[str]) -> list[str]:
    """The lines each reply of the operator that ends it gives: its lines
    (`line_states`), the items for the coordinator it carries
    (`triage.told`), the held steps no decision reached
    (`decisions.undecided`, `decisions.failed`), and the steps it set
    retired (`retired_lines`)."""
    return [*line_states(state), *triage.told(state),
            *decisions.undecided(state, held), *decisions.failed(state), *retired_lines(state)]


RETIRED_LINE = mctx("- Step {key}, which `{origin}` gives, is retired: `next` gave it {bound} "
                  "times in a row, and filed a `bug` on it.")


def retired_lines(state: State) -> list[str]:
    """A line on each step the operator `me` retired (`order.retire`)."""
    return [RETIRED_LINE.format(key=e.retires, origin=of[-1].origin, bound=BOUND)
            for e in state.journal.retiring(state.me)
            if e.retires is not None and (of := state.journal.of(e.retires))]


def stands(state: State, head: str, step: Step | None) -> tuple[str, bool]:
    """The line of the final reply on a draft or a change that stands, by
    `head`, with its step: where that step is undecided and went to a
    ticket analyst, the line gives that step, which its procedure waits
    on, and the second value holds."""
    if isinstance(step, Undecided) and repeated(step, state):
        return head + mctx(": it waits on a decision of the step: {what}").format(
            what=step.text), True
    return head, False


def final(state: State, held: set[str]) -> str:
    """The operator's final reply: what stands at its end."""
    out = reply_lines(state, held)
    for n, deps in taking.waiting(state):
        waited = ", ".join(deps)
        out.append("- " + mctx("Change {n} not taken: it waits for {waited}").format(
            n=n, waited=waited))
    standing = [stands(state, f"- {sentence(draft_stands(t.number))}",
                       drafts.alone(state, t)) for t in drafts.unended(state)]
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


def holding(state: State) -> set[str]:
    """The analyst keys of the undecided steps the procedures wait on, as
    `placed` gives them."""
    return {analyst_key(u) for procedure in PROCEDURES
            if (u := placed(state, procedure)[1]) is not None} | {
        analyst_key(u) for u in decisions.unread_steps(state)} | {
        analyst_key(u) for t in changes.held(state)
        if isinstance(u := changes.next_step(state, t), Undecided) and repeated(u, state)}
