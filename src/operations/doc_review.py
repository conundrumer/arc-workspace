"""The review of a change's documents by its doc reviewer, from that
reviewer's launch to the pass of its review.

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
`tracker.fingerprint` the worktree has now, as then the worktree is in
the state that reply read. A reply in any other form holds the
review. The command launches no editor for a reviewer's findings: that
reviewer sends them to the editors of its brief.

A doc editor that `changes` launches on a change's `mctx` fragments after
the reviewer replied neither launched that reviewer nor got a message from
it, so its report after that reply is among those the review must
follow."""

from pathlib import Path
from typing import Literal

from controlled_markdown import mctx
from operations import briefs, messages
from operations.directives import Decision, decided
from operations.handled import sent
from operations.reports import NO_FINDING, no_finding, reviewed_state
from operations.roles import Role
from operations.state import Agent, State, Ticket
from operations.steps import Launch, Send, Step, Undecided, agent_ids
from operations.tracker import fingerprint


def latest_reviewer(agents: list[Agent]) -> Agent | None:
    """The latest doc reviewer among a change's `agents`, which is the
    change's doc reviewer, or None where it has none."""
    reviewers = [a for a in agents if a.role is Role.DOC_REVIEWER]
    return reviewers[-1] if reviewers else None


def doc_review(state: State, t: Ticket, w: Path, here: list[Agent],
               agents: list[Agent]) -> Step | None | Literal[False]:
    """The step of the review of the change's documents, or False where it
    has passed."""
    r = latest_reviewer(agents)
    if r is None:
        return review_launch(t, w, here, state.me)
    if r.pending:
        return None
    reply = r.last_report
    if reply is not None and (late := [a for a in here if (rep := a.last_report) is not None
                                       and rep.time > reply.time]):
        return review_stale(state, t, w, here, r, reply.time, late)
    if reply is not None and no_finding(r):
        return False
    if reply is None:
        return review_decided(state, t, w, here, unreplied(r, t))
    return review_decided(state, t, w, here, mctx(
        "the reply of doc reviewer {agent} on change {number} does not open with "
        "`{no_finding}`").format(agent=r.agent_id, number=t.number, no_finding=NO_FINDING))


def unreplied(r: Agent, t: Ticket) -> str:
    return mctx("doc reviewer {agent} of change {number} has not replied since its editors "
                "ended").format(agent=r.agent_id, number=t.number)


def review_stale(state: State, t: Ticket, w: Path, here: list[Agent], r: Agent, since: float,
                 late: list[Agent]) -> Step | Literal[False]:
    """The step on the reply at `since` of the doc reviewer `r`, which
    precedes the last report of the editors `late`: False where it opens
    with `no finding stands` and `r` sent each of them a message or is a
    launch of theirs, since its reply reaches its launcher, or where it
    opens so and gives the change's worktree `w` in the state it is in,
    and otherwise the message that asks `r` to review the change again."""
    if no_finding(r):
        if (seen := reviewed_state(r)) is not None and seen == fingerprint(w):
            return False
        if r.messaged is None:
            return Undecided(mctx("the transcript of doc reviewer {agent} of change {number} "
                                  "is unknown, so the command cannot read whom it sent a "
                                  "message").format(agent=r.agent_id, number=t.number))
        ids = agent_ids(late)
        if isinstance(ids, Undecided):
            return ids
        if all(i in r.messaged or i == r.operator for i in ids):
            return False
    message = messages.review_again(since)
    if r.agent_id is not None and not sent(state, r.agent_id, message):
        return Send(r.agent_id, message)
    return review_decided(state, t, w, here, unreplied(r, t))


def review_decided(state: State, t: Ticket, w: Path, here: list[Agent],
                 what: str) -> Step | Literal[False]:
    """The step on a review held for `what`, by its decision:
    False where the review passes."""
    choice = decided(state, what, {Decision.PASSES: mctx("the review passes"),
                                 Decision.AGAIN: mctx("launch another doc reviewer")})
    if isinstance(choice, Undecided):
        return choice
    if choice is Decision.PASSES:
        return False
    return review_launch(t, w, here, state.me)


def review_launch(t: Ticket, w: Path, here: list[Agent], launcher: str) -> Step:
    """The launch of a doc reviewer on the change, with its editors, by
    `launcher`."""
    ids = agent_ids(here)
    if isinstance(ids, Undecided):
        return ids
    return Launch(Role.DOC_REVIEWER, t.number, briefs.doc_review(
        t.number, w, [(a.role, i) for a, i in zip(here, ids, strict=True)], launcher))
