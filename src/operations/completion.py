"""Which attempts occupy their work, and the identity of a replacement, or the
message that gives none."""

import re
from dataclasses import replace

from controlled_markdown import mctx
from operations.constants import COORDINATOR
from operations.directives import give_again_line, given_again, reply_decisions
from operations.reports import FOR_COORDINATOR, LABELED, Label, heading_part
from operations.roles import Purpose, Role, analyst_of
from operations.state import Agent, State
from operations.steps import Launch, Send, Step, key, rulable


def decided(a: Agent) -> bool:
    """Whether the latest turn returned a decision in one of the fixed forms."""
    r = a.last_report
    if r is None or r.time <= a.since:
        return False
    return bool(reply_decisions(a, r)) or any(
        (m := LABELED.match(ln)) is not None and m["label"].lower() == Label.DECISION
        for ln in (heading_part(r.text, FOR_COORDINATOR) or "").splitlines())


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
    labels = {m["label"].lower() for ln in
              (heading_part(r.text, FOR_COORDINATOR) or "").splitlines()
              if (m := LABELED.match(ln)) is not None}
    if decided(a):
        return True
    purpose = analyst_of(a.subject) if a.role is Role.TICKET_ANALYST else None
    if purpose is not None and purpose[0] is Purpose.STEP and rulable(a.brief):
        return False
    return Label.UNFINISHED not in labels and re.match(
        r"\s*(?:stopped|unfinished)\b", r.text, re.IGNORECASE) is None


def occupies(a: Agent) -> bool:
    """Whether this attempt still runs or has delivered its result."""
    return a.pending or finished(a)


STOPS_BOUND = 2
"""How many attempts of one role and subject in a row may stop with no
result before `replacement` gives no further launch."""

STOPPED = mctx("Role {role} on {subject} has stopped with no result in each of its last "
               "{count} attempts, {agents}, so the operator launches no further attempt. "
               "Its last report: {head}. The line `{line}` lets the launches go on once "
               "the fault is fixed.")
"""The message to the coordinator that `replacement` gives in place of a
launch."""


def stopped_attempts(state: State, step: Launch) -> list[Agent]:
    """The attempts of the role and subject of `step`, after the last
    `Op override: give again` ruling on its key, of which the last
    `STOPS_BOUND` all stopped with no result, or an empty list where they
    did not. An attempt the usage limit stopped
    (`TranscriptsRead.limited`) does not count, as `limit_resume` resumes it."""
    again = given_again(state).get(key(step), 0.0)
    past = [a for a in state.agents_of(step.role, step.subject) if a.launched > again]
    last = past[-STOPS_BOUND:]
    if len(last) < STOPS_BOUND or any(
            occupies(a) or a.agent_id in state.transcripts.limited for a in last):
        return []
    return last


def replacement(state: State, step: Step) -> Step:
    """Give a retry its own occasion, past the interrupted launch's journal.

    Keep the procedure's brief and admission rules. The suffix is stable
    across reads, and changes again if the replacement also stops. Where
    the last `STOPS_BOUND` attempts of the step's role and subject all
    stopped with no result, give in its place one message to the
    coordinator (`STOPPED`), which `give_again_line` makes the launches go
    on from.
    """
    if not isinstance(step, Launch):
        return step
    past = state.agents_of(step.role, step.subject)
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
            f"stopped {step.role} {step.subject}", since=stopped[-1].launched,
            change=step.change)
    a = past[-1]
    suffix = f" replacement {a.agent_id} {a.launched} {a.since}"
    return step if step.occasion.endswith(suffix) else replace(
        step, occasion=step.occasion + suffix)
