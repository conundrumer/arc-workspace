"""Which attempts occupy their work, and the identity of a replacement."""

import re
from dataclasses import replace

from operations.directives import reply_decisions
from operations.reports import FOR_COORDINATOR, LABELED, Label, heading_part
from operations.roles import EDITORS, Purpose, Role, analyst_of
from operations.state import Agent, State
from operations.steps import Launch, Step, rulable


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
    checker's findings are its result; unfinished work in a coordinator
    handoff, or a report opening with an incomplete disposition, is not.
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
    if a.role in EDITORS and re.search(
            r"^\s*(?:[-*+]\s+)?(?:unfinished\s*:|[^:\n]+:\s*unfinished\b)",
            r.text, re.IGNORECASE | re.MULTILINE):
        return False
    return Label.UNFINISHED not in labels and re.match(
        r"\s*(?:blocked|stopped|unfinished)\b", r.text, re.IGNORECASE) is None


def occupies(a: Agent) -> bool:
    """Whether this attempt still runs or has delivered its result."""
    return a.pending or finished(a)


def replacement(state: State, step: Step) -> Step:
    """Give a retry its own occasion, past the interrupted launch's journal.

    Keep the procedure's brief and admission rules. The suffix is stable
    across reads, and changes again if the replacement also stops.
    """
    if not isinstance(step, Launch):
        return step
    past = state.agents_of(step.role, step.subject)
    if not past or occupies(past[-1]):
        return step
    a = past[-1]
    suffix = f" replacement {a.agent_id} {a.launched} {a.since}"
    return step if step.occasion.endswith(suffix) else replace(
        step, occasion=step.occasion + suffix)
