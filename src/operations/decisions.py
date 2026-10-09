"""The ticket analysts the operator launches on the steps the command
cannot decide (`steps.Undecided`), and the reads of their replies.

Such a step goes to one ticket analyst, launched with the step and the
agent id of the operator that holds it (`briefs.held_step`), whose subject
gives the step's decision key, so no operator of the session launches a
second analyst on it, and its procedure waits on that analyst while it
runs and once it returned (`steps.repeated`). A step an operator already
gave the coordinator goes to no analyst, and its procedure waits on the
coordinator's decision (`steps.repeated`). The analyst's reply rules
the step by a ruling in a fixed form, which the command applies as it
applies the coordinator's, for every operator of the session
(`directives.rulings`). Where the analyst brings that decision to the user,
its `decision:` item goes to the coordinator (`triage`), and the
coordinator gives the user's decision in a `Decision:` line.

The operator that answers an analyst's reply (`applier`) is the one that
launched it, while that operator has printed no final reply since the
launch, and otherwise the operator `me`. Since one operator carries the
session's work at a time (`plan`), one operator answers each reply.

A step the command cannot place (`steps.rulable`) has no decision key: its
analyst makes the act the step needs and gives no ruling, the command
does not send its reply back to it for a form, and where the step still holds once it returned,
the final reply of its applier gives it (`undecided`).

On a step `steps.held` made, a reply that gives neither a ruling in a fixed form nor a `decision:` item goes back
to the analyst once, from its applier, with a request to send it again in
that form (`briefs.DECISION_FORM`). Where the answer is still in neither
form, the step stays held, and the final reply of its applier gives it
(`undecided`). A launch of an analyst on a held step that failed is not
itself given to another analyst: its step stays held, and the final reply
of the operator that made that call gives the step, with the call and the
text of its failure (`failed`)."""

from controlled_markdown import mctx
from operations import briefs
from operations.directives import reply_decisions
from operations.reports import Label, items_of
from operations.roles import Purpose, Role, analyst_of, analyst_subject, described
from operations.state import Agent, State
from operations.steps import (Launch, Send, Step, Undecided, ask_again, decided_by,
                             decision_key, failure, final_replies, nested, rulable)


def launch(state: State, step: Undecided) -> Launch:
    return Launch(Role.TICKET_ANALYST, analyst_subject(Purpose.STEP, decision_key(step.what)),
                  briefs.held_step(step.what, state.me, rulable(step.what)))


def applier(state: State, a: Agent) -> str:
    """The operator that answers the reply of `a`, an analyst on a held
    step."""
    return state.me if launcher_ended(state, a) else a.operator


def launcher_ended(state: State, a: Agent) -> bool:
    """Whether the operator that launched `a` printed its final reply since
    that launch."""
    return any(t > a.launched for t in final_replies(state, a.operator))


def decides(a: Agent) -> bool:
    """Whether the latest reply of `a`, an analyst on a held step, gives a
    ruling in a fixed form or a `decision:` item."""
    r = a.last_report
    return r is not None and (bool(reply_decisions(a, r))
                              or items_of(a, [Label.DECISION]) is not None)


def returned(state: State) -> list[Agent]:
    """The ticket analysts on held steps that returned, whose replies the
    operator `me` answers."""
    return [a for a, purpose, _ in state.analysts()
            if purpose is Purpose.STEP and not a.pending and a.agent_id is not None
            and a.reports and applier(state, a) == state.me]


def asks(state: State) -> Step | None:
    """The message that asks a ticket analyst on a held step whose reply
    the operator `me` applies to send its latest reply again in the form
    the command reads, where that reply gives no decision."""
    for a in returned(state):
        if a.agent_id is None or not rulable(a.brief) or decides(a):
            continue
        asked = ask_again(state, a.agent_id, [r.time for r in a.reports], briefs.DECISION_FORM)
        if isinstance(asked, Send):
            return asked
    return None


def undecided(state: State, holding: set[str]) -> list[str]:
    """The lines of the final reply of the operator `me` on each held step
    whose ticket analyst returned with no decision after it was asked
    again, and on each step the command cannot place whose decision key
    `holding` gives, once the latest analyst on it returned."""
    out: list[str] = []
    latest = {keys[0]: a for a, purpose, keys in state.analysts()
              if purpose is Purpose.STEP and len(keys) == 1}
    for a in returned(state):
        if rulable(a.brief) and not decides(a):
            out.append(mctx("- Ticket analyst {agent} returned with no decision of the held step "
                            "its brief gives:").format(agent=a.agent_id))
            out += nested(a.brief)
        elif not rulable(a.brief) and any(latest.get(k) is a for k in holding):
            out.append(mctx("- Ticket analyst {agent} returned, and the step its brief gives "
                            "still holds:").format(agent=a.agent_id))
            out += nested(a.brief)
    return out


def failed(state: State) -> list[str]:
    """The lines of the final reply of the operator `me` on each held step
    whose analyst's launch, the last call `me` made of it, failed, with no
    analyst on that step launched since."""
    last: dict[str, tuple[float, str, str, str]] = {}
    for c in sorted(state.calls, key=lambda c: c.time):
        what = str(c.input.get("description", ""))
        d = described(what) if c.operator == state.me and c.tool == "Agent" else None
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
