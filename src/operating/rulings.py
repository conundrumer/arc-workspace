"""The ticket analysts the operator launches on the steps the command
cannot decide (`steps.Undecided`), and the reads of their replies.

Such a step goes to one ticket analyst, launched with the step and the
agent id of the operator that holds it (`briefs.held_step`), whose subject
gives the step's ruling key, so no operator of the session launches a
second analyst on it, and its procedure waits on that analyst while it
runs and once it returned (`steps.repeated`). A step an operator already
gave the coordinator goes to no analyst, and its procedure waits on the
coordinator's ruling (`steps.repeated`). The analyst's reply rules
the step by an `Override:` or `Decision:` line, as a line of the
coordinator's rules it, and a `Decision:` line that gives the ruling key
of a held step rules it for every operator of the session
(`directives.ruled`). Where the analyst brings that decision to the user,
its `decision:` item goes to the coordinator (`settling`), and the
coordinator gives the user's ruling in a `Decision:` line.

The operator that applies an analyst's reply (`applier`) is the one that
launched it, while that operator has printed no final reply since the
launch, and otherwise the operator whose procedure meets the step: the
command prints that operator the analyst's ruling lines with the step,
once in the session (`relay`), and that operator applies them as lines of
an analyst it launched. Since one operator carries the session's work at
a time (`plan`), one operator applies each ruling.

A reply that gives neither a ruling line nor a `decision:` item goes back
to the analyst once, from its applier, with a request to send it again in
that form (`briefs.RULING_FORM`). Where the answer is still in neither
form, the step stays held, and the final reply of its applier gives it
(`unruled`). A launch of an analyst on a held step that failed is not
itself given to another analyst: its step stays held, and the final reply
of the operator that made that call gives the step, with the call and the
text of its failure (`failed`)."""

from controlled_markdown import mctx
from operating import briefs
from operating.directives import reply_rulings
from operating.reports import Label, items_of
from operating.roles import Purpose, Role, analyst_of, analyst_subject, described
from operating.state import Agent, State
from operating.steps import (Launch, Relay, Send, Step, Undecided, ask_again, failure,
                             final_replies, nested, ruled_by, ruling_key)


def launch(state: State, step: Undecided) -> Launch:
    return Launch(Role.TICKET_ANALYST, analyst_subject(Purpose.STEP, ruling_key(step.what)),
                  briefs.held_step(step.what, state.me))


def applier(state: State, a: Agent) -> str:
    """The operator that applies the reply of `a`, an analyst on a held
    step."""
    return state.me if launcher_ended(state, a) else a.operator


def launcher_ended(state: State, a: Agent) -> bool:
    """Whether the operator that launched `a` printed its final reply since
    that launch."""
    return any(t > a.launched for t in final_replies(state, a.operator))


def rules(a: Agent) -> bool:
    """Whether the latest reply of `a`, an analyst on a held step, gives a
    ruling line or a `decision:` item."""
    r = a.last_report
    return r is not None and (bool(reply_rulings(a, r))
                              or items_of(a, [Label.DECISION]) is not None)


def returned(state: State) -> list[Agent]:
    """The ticket analysts on held steps that returned, whose replies the
    operator `me` applies."""
    return [a for a, purpose, _ in state.analysts()
            if purpose is Purpose.STEP and not a.pending and a.agent_id is not None
            and a.reports and applier(state, a) == state.me]


def relay(state: State, step: Undecided) -> Relay | None:
    """The ruling lines of the latest analyst on `step`, where its launcher
    printed its final reply since that analyst's launch."""
    analysts = ruled_by(state, step)
    if not analysts:
        return None
    a = analysts[-1]
    r = a.last_report
    if a.agent_id is None or r is None or a.pending or not launcher_ended(state, a):
        return None
    lines = tuple(ln.text for ln in reply_rulings(a, r))
    return Relay(a.agent_id, step.what, lines) if lines else None


def asks(state: State) -> Step | None:
    """The message that asks a ticket analyst on a held step whose reply
    the operator `me` applies to send its latest reply again in the form
    the command reads, where that reply gives no ruling."""
    for a in returned(state):
        if a.agent_id is None or rules(a):
            continue
        asked = ask_again(state, a.agent_id, [r.time for r in a.reports], briefs.RULING_FORM)
        if isinstance(asked, Send):
            return asked
    return None


def unruled(state: State) -> list[str]:
    """The lines of the final reply of the operator `me` on each held step
    whose ticket analyst returned with no ruling after it was asked
    again."""
    out: list[str] = []
    for a in returned(state):
        if not rules(a):
            out.append(mctx("- Ticket analyst {agent} returned with no ruling of the held step "
                            "its brief gives:").format(agent=a.agent_id))
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
