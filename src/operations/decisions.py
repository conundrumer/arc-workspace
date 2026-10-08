"""The ticket analysts the loop launches on the steps the command cannot
decide (`steps.Undecided`), and the reads of their replies.

Such a step goes to one ticket analyst, launched with the step
(`briefs.held_step`), whose subject gives the step's decision key, so the
loop launches no second analyst on it, and its procedure waits on that
analyst while it runs and once it returned (`steps.repeated`). A step the
loop already gave the coordinator goes to no analyst, and its procedure
waits on the coordinator's decision (`steps.repeated`). The analyst's
reply rules the step by a ruling in a fixed form, as a ruling of the
coordinator's rules it (`directives`). Where the analyst brings that
decision to the user, its `decision:` item goes to the coordinator
(`triage`), and the coordinator gives the user's decision in a
`Decision:` line.

A reply that gives neither a decision line nor a `decision:` item goes back
to the analyst once, with a request to send it again in that form
(`briefs.DECISION_FORM`). Where the answer is still in neither form, the
step stays held, and the loop's final reply gives it (`undecided`). A
launch of an analyst on a held step that failed is not itself given to
another analyst: its step stays held, and the loop's final reply gives the
step, with the call and the text of its failure (`failed`)."""

from controlled_markdown import mctx
from operations import briefs
from operations.directives import reply_decisions
from operations.reports import Label, items_of
from operations.roles import Purpose, Role, analyst_of, analyst_subject, described
from operations.state import Agent, State
from operations.steps import (
    Launch,
    Send,
    Step,
    Undecided,
    ask_again,
    decision_key,
    failure,
    nested,
)


def launch(state: State, step: Undecided) -> Launch:
    return Launch(Role.TICKET_ANALYST, analyst_subject(Purpose.STEP, decision_key(step.what)),
                  briefs.held_step(step.what))


def decides(a: Agent) -> bool:
    """Whether the latest reply of `a`, an analyst on a held step, gives a
    decision line or a `decision:` item."""
    r = a.last_report
    return r is not None and (bool(reply_decisions(a, r))
                              or items_of(a, [Label.DECISION]) is not None)


def returned(state: State) -> list[Agent]:
    """The ticket analysts on held steps that returned."""
    return [a for a, purpose, _ in state.analysts()
            if purpose is Purpose.STEP and not a.pending and a.agent_id is not None
            and a.reports]


def asks(state: State) -> Step | None:
    """The message that asks a ticket analyst on a held step to send its
    latest reply again in the form the command reads, where that reply
    gives no decision."""
    for a in returned(state):
        if a.agent_id is None or decides(a):
            continue
        asked = ask_again(state, a.agent_id, [r.time for r in a.reports], briefs.DECISION_FORM)
        if isinstance(asked, Send):
            return asked
    return None


def undecided(state: State) -> list[str]:
    """The lines of the loop's final reply on each held step whose ticket
    analyst returned with no decision after it was asked
    again."""
    out: list[str] = []
    for a in returned(state):
        if not decides(a):
            out.append(mctx("- Ticket analyst {agent} returned with no decision of the held step "
                            "its brief gives:").format(agent=a.agent_id))
            out += nested(a.brief)
    return out


def failed(state: State) -> list[str]:
    """The lines of the loop's final reply on each held step whose
    analyst's launch, the last call the loop made of it, failed, with no
    analyst on that step launched since."""
    last: dict[str, tuple[float, str, str, str]] = {}
    for c in sorted(state.calls, key=lambda c: c.time):
        what = str(c.input.get("description", ""))
        d = described(what) if c.tool == "Agent" else None
        if d is None or d.role is not Role.TICKET_ANALYST:
            continue
        parsed = analyst_of(d.subject)
        if parsed is not None and parsed[0] is Purpose.STEP:
            last[d.subject] = (c.time, what, failure(c) if c.error else "",
                               str(c.input.get("prompt", "")))
    out: list[str] = []
    for subject, (time, what, why, prompt) in last.items():
        if not why or any(a.launched > time for a in state.agents_of(Role.TICKET_ANALYST, subject)):
            continue
        out.append(mctx("- The launch `{what}` of a ticket analyst on the held step its brief "
                        "gives failed: {why}").format(what=what, why=why))
        out += nested(prompt)
    return out
