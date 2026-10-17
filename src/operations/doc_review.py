"""The review of a change's documents by its doc reviewer, from that
reviewer's launch to the pass of its review. The change's doc reviewer is
the latest one launched on its current worktree.

A change with a doc editor passes its review once the latest reply of its
doc reviewer opens with `no finding stands` and follows each editor's last
report, or precedes the last report only of editors that reviewer sent a
message, since such an editor sends that reviewer its fixes before each
reply, or of the editor that launched it, since its reply reaches that
editor. A doc editor launches its doc reviewer from the launch
`scripts/operate.py` prints to it (`editor_review`), once no other
editor of the change is pending, and stays in its run until that
reviewer has replied; otherwise the command launches the reviewer. A
reply that precedes the last report of any other editor is read for no
finding, and that reviewer is asked once to review the change again, and
the review is held where it has not replied since, unless that reply
opens with `no finding stands` and its `reports.WORKTREE` line gives the
`worktrees.fingerprint` the worktree has now, as then the worktree is in
the state that reply read. `steps.Undecided.reread` gives why the
command reads the state again before it launches an analyst on that hold.
A reply that opens with `reports.AT_CAP` holds the review until a ticket
analyst launched on it since it has replied, which `changes.leftover`
launches, and then the review passes, whatever editors report after it, and
that reviewer is asked to review the change no more. A reply in any other form holds the review. The command launches no editor for a reviewer's findings: that
reviewer sends them to the editors of its brief.

A doc editor that `change_fragments` launches on a change's `mctx` fragments after
the reviewer replied neither launched that reviewer nor got a message from
it, so its report after that reply is among those the review must
follow."""

from dataclasses import replace
from pathlib import Path
from typing import Literal

from controlled_markdown import mctx
from operations import briefs, messages
from operations.change_agents import change_editors, editors_in, of_change, settled, unstaffed
from operations.change_holds import Hold, findings_hold, unreplied_hold
from operations.directives import Decision, decided, ruled
from operations.handled import sent
from operations.reports import at_cap, no_finding, shows_current
from operations.roles import Role
from operations.state import Agent, State, Ticket, last_reported
from operations.steps import Launch, Send, Step, Undecided, agent_ids
from operations.worktrees import worktree


def latest_reviewer(agents: list[Agent], w: Path) -> Agent | None:
    """The latest doc reviewer among a change's `agents` whose brief gives
    the change's worktree `w`, which is the change's doc reviewer, or None
    where it has none. A reviewer of an earlier run of the change reviewed
    that run's worktree, so it is none of the change's now."""
    line = briefs.fingerprint_line(w)
    reviewers = [a for a in agents if a.role is Role.DOC_REVIEWER and line in a.brief]
    return reviewers[-1] if reviewers else None


def doc_review(state: State, t: Ticket, w: Path, here: list[Agent],
               agents: list[Agent]) -> Step | None | Literal[False]:
    """The step of the review of the change's documents, or False where it
    has passed."""
    r = latest_reviewer(agents, w)
    if r is None:
        return review_launch(state, t, w, here, state.me, 0.0)
    if r.pending:
        return None
    reply = r.last_report
    if reply is not None and at_cap(r):
        judged = any(a.role is Role.TICKET_ANALYST and a.launched > reply.time
                     and briefs.on_cap_reply(a) and a.last_report is not None for a in agents)
        return False if judged else None
    if reply is not None and (late := [a for a in here if (rep := a.last_report) is not None
                                       and rep.time > reply.time]):
        return review_stale(state, t, w, here, r, reply.time, late)
    if reply is not None and no_finding(r):
        return False
    if reply is None:
        return unreplied(state, t, w, here, r)
    return review_decided(state, t, w, here, findings_hold(r, t.number))


def unreplied(state: State, t: Ticket, w: Path, here: list[Agent],
              r: Agent) -> Step | Literal[False]:
    """The step on a review whose doc reviewer `r` has not replied since
    its editors ended. `steps.Undecided.reread` gives why its held step is
    marked."""
    step = review_decided(state, t, w, here, unreplied_hold(r, t.number))
    return replace(step, reread=True) if isinstance(step, Undecided) else step


def review_stale(state: State, t: Ticket, w: Path, here: list[Agent], r: Agent, since: float,
                 late: list[Agent]) -> Step | Literal[False]:
    """The step on the reply at `since` of the doc reviewer `r`, which
    precedes the last report of the editors `late`: False where it opens
    with `no finding stands` and `r` sent each of them a message or is a
    launch of theirs, since its reply reaches its launcher, or where it
    opens so and gives the change's worktree `w` in the state it is in,
    and otherwise the message that asks `r` to review the change again,
    or, where `r` is of `TranscriptsRead.elsewhere`, the step `unreplied`
    gives."""
    if no_finding(r):
        if shows_current(r, w):
            return False
        messaged = state.transcripts.sent_by(r)
        if messaged is None:
            return Undecided(mctx("the transcript of doc reviewer {agent} of change {number} "
                                  "is unknown").format(agent=r.agent_id, number=t.number))
        ids = agent_ids(late)
        if isinstance(ids, Undecided):
            return ids
        if all(i in messaged or i == r.operator for i in ids):
            return False
    message = messages.review_again(since)
    if r.agent_id is not None and r not in state.transcripts.elsewhere \
            and not sent(state, r.agent_id, message):
        return Send(r.agent_id, message, f"review again {t.number} {since}")
    return unreplied(state, t, w, here, r)


def review_decided(state: State, t: Ticket, w: Path, here: list[Agent],
                 hold: Hold) -> Step | Literal[False]:
    """The step on a review held on `hold`, by its decision:
    False where the review passes."""
    choice = decided(state, hold.text, hold.choices)
    if isinstance(choice, Undecided):
        return choice
    if choice is Decision.PASSES:
        return False
    return review_launch(state, t, w, here, state.me, ruled(state, hold.text))


def with_ids(agents: list[Agent]) -> list[tuple[Agent, str]] | Undecided:
    """Each of `agents` beside its agent id, as `agent_ids` gives it, for
    the briefs that give each editor of a change with its part
    (`briefs.editor_lines`)."""
    ids = agent_ids(agents)
    if isinstance(ids, Undecided):
        return ids
    return list(zip(agents, ids, strict=True))


def review_launch(state: State, t: Ticket, w: Path, here: list[Agent], launcher: str,
                  ruled: float) -> Step:
    """The launch of a doc reviewer on the change, with its editors, what
    the agents before it settled (`change_agents.settled`), and its rounds
    (`briefs.review_rounds`), by
    `launcher`, on the ruling at `ruled` (`directives.ruled`), or 0.0 on
    none."""
    editors = with_ids(here)
    if isinstance(editors, Undecided):
        return editors
    known = settled(state, t, Role.DOC_REVIEWER, None)
    return Launch(Role.DOC_REVIEWER, t.number, briefs.doc_review(
        t.number, w, editors, launcher, known, briefs.review_rounds(known.launched_before)),
        occasion=str(max(last_reported(here), ruled)))


NO_OPERATOR = mctx("{agent} is no doc editor that an operator of the session launched: give "
                   "your final reply.")
"""The line `editor_review` gives an agent that is no doc editor an operator
launched."""


def editor_review(state: State, editor: str) -> Step | str:
    """The launch of the doc reviewer of the change of the doc editor
    `editor`, launched by it. In its place it gives a line: where
    `editor` is no doc editor an operator launched, `NO_OPERATOR`; where the change has a doc
    reviewer on its current worktree, whoever launched it, the line that names the latest one, so
    the editor launches no other; and where an editor role of the change
    has no agent in its worktree or another editor there is pending, the
    line that says the operator launches the review."""
    mine = [a for a in state.transcripts.agents if a.agent_id == editor and a.role is Role.DOC_EDITOR]
    if not mine:
        return NO_OPERATOR.format(agent=editor)
    t = state.tracker.tickets.get(mine[-1].subject)
    if t is None:
        return Undecided(mctx("the ticket of change {number} of doc editor {agent} is not "
                              "read").format(number=mine[-1].subject, agent=editor))
    editors = change_editors(t)
    if not isinstance(editors, tuple):
        return editors
    w = worktree(t, state)
    if w is None:
        return Undecided(mctx("change {number} gives no worktree").format(number=t.number))
    agents = of_change(state, t)
    if (reviewer := latest_reviewer(agents, w)) is not None:
        ids = agent_ids([reviewer])
        if isinstance(ids, Undecided):
            return ids
        return mctx("Change {number} already has doc reviewer {agent}, so launch no other "
                    "doc reviewer.").format(number=t.number, agent=ids[0])
    here = editors_in(agents, w)
    if (unstaffed(editors, here)
            or any(a.pending for a in here if a.agent_id != editor)):
        return mctx("Another editor of change {number} has not reported, so the operator "
                    "launches the review: give your final reply.").format(number=t.number)
    return review_launch(state, t, w, here, editor, 0.0)
