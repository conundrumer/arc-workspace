"""Which attempts occupy their work, and the identity of a replacement, or the
message that gives none."""

import json
import re
from collections.abc import Iterable
from dataclasses import replace

from controlled_markdown import mctx
from operations import briefs
from operations.constants import COORDINATOR
from operations.directives import give_again_line, given_again, reply_decisions
from operations.reports import FOR_COORDINATOR, Label, heading_part, labeled_items
from operations.roles import Purpose, Role, analyst_of
from operations.state import Agent, Call, State, Tool
from operations.steps import Launch, Send, Step, key, rulable


def decided(a: Agent) -> bool:
    """Whether the latest turn returned a decision in one of the fixed forms."""
    r = a.last_report
    if r is None or r.time <= a.since:
        return False
    return bool(reply_decisions(a, r)) or Label.DECISION in top_labels(r.text)


def top_labels(text: str) -> set[Label]:
    """The labels of the top-level items of the part of `text` for the
    coordinator."""
    return {label for label, _ in labeled_items(heading_part(text, FOR_COORDINATOR) or "")[0]}


def finished(a: Agent) -> bool:
    """A fresh report completes an attempt unless it reports an interruption.

    A decision is a result even when it leaves work for the user. Reports
    from before the latest resume cannot finish that resume's work. A
    checker's findings and an editor's Blocked reply are results;
    unfinished work in a coordinator handoff, or a report opening with
    an incomplete disposition, is not.
    """
    r = a.last_report
    if r is None or r.time <= a.since or not r.text.strip():
        return False
    labels = top_labels(r.text)
    if decided(a):
        return True
    purpose = analyst_of(a.subject) if a.role is Role.TICKET_ANALYST else None
    if purpose is not None and purpose[0] is Purpose.STEP and rulable(a.brief):
        return False
    return Label.UNFINISHED not in labels and re.match(
        r"\s*(?:stopped|unfinished)\b", r.text, re.IGNORECASE) is None


def occupies(a: Agent) -> bool:
    """Whether this attempt still runs or has delivered its result, and the
    harness has not refused a message to it (`Agent.refused`): a refused
    agent ended with no result."""
    return a.pending or (finished(a) and a.refused is None)


def refused_message(c: Call) -> bool:
    """Whether the harness gave the result of the SendMessage call `c` as a
    refusal: a JSON object whose `success` is false."""
    try:
        given = json.loads(c.result or "")
    except ValueError:
        return False
    return c.tool == Tool.SEND_MESSAGE and isinstance(given, dict) and given.get("success") is False


def with_refusals(agents: Iterable[Agent], calls: Iterable[Call]) -> tuple[Agent, ...]:
    """`agents`, each with `Agent.refused` set from the SendMessage `calls`
    of the session."""
    latest: dict[str, Call] = {}
    for c in sorted(calls, key=lambda c: c.time):
        if c.tool == Tool.SEND_MESSAGE and not c.error and c.result is not None:
            latest[str(c.input.get("to"))] = c
    out = []
    for a in agents:
        c = latest.get(a.agent_id) if a.agent_id is not None else None
        if (c is not None and not a.pending and refused_message(c) and c.time > a.since
                and not any(r.time > c.time for r in a.reports)):
            a = replace(a, refused=c.time)
        out.append(a)
    return tuple(out)


STOPS_BOUND = 2
"""How many attempts of one role and subject in a row may stop with no
result before `replacement` gives no further launch."""

STOPPED = mctx("Role {role} on {subject} has stopped with no result in each of its last "
               "{count} attempts, {agents}, so the operator launches no further attempt. "
               "Its last report: {head}. The line `{line}` lets the launches go on once "
               "the fault is fixed.")
"""The message to the coordinator that `replacement` gives in place of a
launch."""


def since_ruling(state: State, step: Launch) -> list[Agent]:
    """The attempts of the role and subject of `step` launched after the
    last `Op override: give again` ruling on its `key`."""
    again = given_again(state).get(key(step), 0.0)
    return [a for a in attempts(state, step) if a.launched > again]


def attempts(state: State, step: Launch) -> list[Agent]:
    """The agents of the role and subject of `step` that took the editor
    part of its brief: the fragments alone, or the documents."""
    wanted = briefs.gives_fragments_alone(step.brief)
    return [a for a in state.agents_of(step.role, step.subject)
            if briefs.gives_fragments_alone(a.brief) == wanted]


def stopped_attempts(state: State, step: Launch) -> list[Agent]:
    """The attempts of the role and subject of `step`, after the last
    `Op override: give again` ruling on its key, of which the last
    `STOPS_BOUND` all stopped with no result, or an empty list where they
    did not. An attempt the usage limit stopped
    (`TranscriptsRead.limited`) does not count, as `limit_resume` resumes it."""
    last = since_ruling(state, step)[-STOPS_BOUND:]
    if len(last) < STOPS_BOUND or any(
            occupies(a) or a.agent_id in state.transcripts.limited for a in last):
        return []
    return last


def replacement(state: State, step: Step) -> Step:
    """Give a retry its own journal entry (`steps.entry_key`), past the
    interrupted launch's.

    Keep the procedure's brief and admission rules. The `attempt` is the
    count of the attempts of the step's role and subject launched after the
    last `Op override: give again` ruling on its `key` that stopped with no
    result: stable across reads, and one more if the replacement also
    stops. Where the last `STOPS_BOUND` attempts of the step's role and
    subject all stopped with no result, give in its place one message to
    the coordinator (`STOPPED`), which `give_again_line` makes the launches
    go on from.
    """
    if not isinstance(step, Launch):
        return step
    past = attempts(state, step)
    if not past or occupies(past[-1]):
        return step
    if stopped := stopped_attempts(state, step):
        last = stopped[-1].last_report
        head = "no report" if last is None or not last.text.strip() else \
            last.text.strip().split("\n", 1)[0]
        return Send(COORDINATOR, STOPPED.format(
            role=step.role, subject=step.subject, count=len(stopped),
            agents=", ".join(str(a.agent_id) for a in stopped), head=head,
            line=give_again_line(key(step))),
            f"stopped {step.role} {step.subject} {key(step)}", since=stopped[-1].launched,
            change=step.change)
    return replace(step, attempt=sum(not occupies(a) for a in since_ruling(state, step)))
