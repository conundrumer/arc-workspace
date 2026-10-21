"""The ticket analysts the operator launches on the steps the command
cannot decide (`steps.Undecided`), and the reads of their replies.

Such a step goes to one ticket analyst, launched with the step and the
agent id of the operator that holds it (`briefs.held_step`), whose subject
gives the step's analyst key (`steps.analyst_key`), so no operator of the session launches a
second analyst on it, and its procedure waits on that analyst while it
runs and once it returned (`handled.repeated`). A step an operator already
gave the coordinator goes to no analyst, and its procedure waits on the
coordinator's decision (`handled.repeated`). The rulings an analyst's
reply gives, and which replies go back to their analyst, are as
`scripts/operate.py --help rulings` gives them (`directives.rulings`).
Where the analyst brings that decision to the user,
its `decision:` item goes to the coordinator (`triage`), and the
coordinator gives the user's decision in an `Op decision:` line.

The operator that answers an analyst's reply (`applier`) is the one that
launched it, while that operator has printed no final reply since the
launch, and otherwise the operator `me`. Since one operator does the
session's work at a time (`plan`), one operator answers each reply.

A step the command cannot place is `steps.rulable`. A reply that goes
back goes from its applier, with a request to send it again in the form
the command reads (`messages.DECISION_FORM`); a `decision:` item counts as
that form. Where the step still holds once its analyst returned, the final
reply of its applier gives it (`undecided`), other than where its tickets
closed (`briefs.step_tickets`), since nothing reads the reply once they
closed. A launch of an analyst on a held step that failed is not
itself given to another analyst: its step stays held, and the final reply
of the operator that made that call gives the step, with the call and the
text of its failure (`failed`).

A ticket file the read of the tracker left out (`TrackerRead.unread`) is a step
the command cannot place, one for each content the file has
(`unread_steps`), once its last write is `WRITE_SECONDS` old, so that a
file read while an agent writes it goes to no analyst. A step on a content
of the file goes to no analyst either while an analyst launched on a step
on an earlier content of that file runs. The step goes
to the operators that act on the session of the ticket number the
file's name gives (`Unread.session`, `State.acts_on`), and where that
name gives no session, to the operators of every session."""

from pathlib import Path

from controlled_markdown import mctx
from operations import briefs, messages
from operations.change_agents import settled
from operations.directives import reply_decisions
from operations.completion import finished, occupies
from operations.reports import Label, items_of
from operations.roles import Purpose, Role, analyst_of, analyst_subject, described
from operations.state import Agent, State, Tool, Unread, own
from operations.final_reply import failure, final_replies, session_operator
from operations.nesting import nested
from operations.handled import ask_again, decided_by, held_aside, repeated
from operations.steps import Launch, Send, Step, Undecided, analyst_key, rulable
from operations.tracker import closed


WRITE_SECONDS = 30.0


def writing(state: State, u: Unread) -> bool:
    """Whether `u` was written less than `WRITE_SECONDS` ago."""
    return state.now - u.modified < WRITE_SECONDS


def unread_steps(state: State) -> list[Undecided]:
    """The step on each ticket file the read of the tracker left out, other
    than one an agent may still write, and other than one whose file name
    gives a session the operators do not act on (`State.acts_on`)."""
    return [Undecided(mctx("{subject} does not read as the operator reads a ticket, so every "
                           "procedure passes over its ticket: {why} (its content's digest: "
                           "{digest})").format(subject=unread_subject(u.path), why=u.why,
                                               digest=u.digest),
                      subject=unread_subject(u.path))
            for u in sorted(state.tracker.unread, key=lambda u: u.path)
            if not writing(state, u) and (u.session is None or state.acts_on(u.session))]


def unread_subject(path: Path) -> str:
    """The subject of the step of `unread_steps` on the file `path`, the
    same at each content of the file (`steps.Undecided`)."""
    return mctx("the ticket file {path}").format(path=path)


def unread_files(state: State) -> Step | None:
    """The first step of `unread_steps` no operator handled, or where each
    was handled, the first, which its procedure then waits on."""
    steps = unread_steps(state)
    return next((s for s in steps if not repeated(s, state)), steps[0] if steps else None)


def launch(state: State, step: Undecided) -> Launch:
    """The launch of a ticket analyst on the held step `step`, whose brief
    gives, where the step is of a change, what the agents launched on it
    settled (`change_agents.settled`)."""
    known = None if step.change is None else settled(
        state, state.tracker.tickets[step.change], Role.TICKET_ANALYST, None)
    return Launch(Role.TICKET_ANALYST, analyst_subject(Purpose.STEP, analyst_key(step)),
                  briefs.held_step(step.text, state.me, rulable(step.text), known),
                  reread=step.reread, change=step.change, occasion=analyst_key(step))


def applier(state: State, a: Agent) -> str:
    """The operator that answers the reply of `a`, an analyst on a held
    step."""
    return state.me if launcher_ended(state, a) else a.operator


def launcher_ended(state: State, a: Agent) -> bool:
    """Whether the operator whose launch `a` is or stands in
    (`final_reply.session_operator`) sent the coordinator the text of its
    final reply since that launch; False where it gives None."""
    op = session_operator(state, a)
    return op is not None and any(t > a.launched for t in final_replies(state, op))


def decides(a: Agent) -> bool:
    """Whether the latest reply of `a`, an analyst on a held step, gives a
    ruling in a fixed form or a `decision:` item."""
    r = a.last_report
    return r is not None and (bool(reply_decisions(a, r))
                              or items_of(a, [Label.DECISION]) is not None)


def returned(state: State) -> list[Agent]:
    """The ticket analysts on held steps that returned, whose replies the
    operator `me` answers, other than those `tickets_closed` gives, whose
    replies do not go back, as `scripts/operate.py --help rulings` gives."""
    return [a for a, purpose, _ in state.analysts()
            if purpose is Purpose.STEP and not a.pending and a.agent_id is not None
            and finished(a) and not tickets_closed(state, a) and applier(state, a) == state.me]


def tickets_closed(state: State, a: Agent) -> bool:
    """Whether the step of `a`, an analyst on a held step, gives one ticket
    or more, each under `tickets/closed/`."""
    return all_closed(state, briefs.step_tickets(a.brief))


def all_closed(state: State, numbers: list[str]) -> bool:
    """Whether `numbers` gives one ticket or more, each under
    `tickets/closed/`."""
    return bool(numbers) and all(closed(state, n) for n in numbers)


def asks(state: State) -> Step | None:
    """The message that asks a ticket analyst on a held step whose reply
    the operator `me` applies to send its latest reply again in the form
    the command reads, where that reply gives no decision."""
    for a in returned(state):
        if a.agent_id is None or not rulable(a.brief) or decides(a):
            continue
        asked = ask_again(state, a.agent_id, [r.time for r in a.reports], messages.DECISION_FORM)
        if isinstance(asked, Send) and not held_aside(state, asked):
            return asked
    return None


def undecided(state: State, holding: set[str]) -> list[str]:
    """The lines of the final reply of the operator `me` on each held step
    whose ticket analyst returned with no decision after it was asked
    again, and on each step the command cannot place whose analyst key
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
    for c in sorted(state.transcripts.calls, key=lambda c: c.time):
        what = str(c.input.get("description", ""))
        d = described(what) if c.operator == state.me and c.tool == Tool.AGENT else None
        if d is None or d.role is not Role.TICKET_ANALYST:
            continue
        parsed = analyst_of(d.subject)
        if parsed is not None and parsed[0] is Purpose.STEP:
            last[d.subject] = (c.time, what, failure(c) if c.error else "",
                               own(str(c.input.get("prompt", ""))))
    out: list[str] = []
    for subject, (time, what, why, prompt) in last.items():
        if not why or any(a.launched > time and occupies(a)
                          for a in state.agents_of(Role.TICKET_ANALYST, subject)):
            continue
        out.append(mctx("- The launch `{what}` of a ticket analyst on the held step its brief "
                        "gives failed: {why}").format(what=what, why=why))
        out += nested(prompt)
    return out
