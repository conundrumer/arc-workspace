"""The review of a change's documents by its doc reviewer, from that
reviewer's launch to the pass of its review. The change's doc reviewer is
the latest one launched on its current worktree.

A change with a doc editor passes its review once the latest reply of its
doc reviewer opens with `no finding stands` and follows each editor's last
report, or precedes the last report only of editors that reviewer sent a
message, since such an editor sends that reviewer its fixes before each
reply, or of the editor that launched it, since its reply reaches that
editor. An editor of the change may launch its doc reviewer, as
`changes.editor_step` gives; otherwise the command launches it. A
reply that precedes the last report of any other editor is read for no
finding, and that reviewer is asked once to review the change again, and
the review is held where it has not replied since, or, where that
reviewer is of another session (`TranscriptsRead.elsewhere`), which no
message reaches, a new doc reviewer is launched on the worktree, unless
that reply opens with `no finding stands` and its `reports.WORKTREE` line gives the
`worktrees.fingerprint` the worktree has now, as then the worktree is in
the state that reply read. `steps.Undecided.reread` gives why the
command reads the state again before it launches an analyst on that hold.
A reply that opens with `reports.AT_CAP` holds the review until a ticket
analyst launched on it since it has replied, which `changes.leftover`
launches, and then the review passes, whatever editors report after it, and
that reviewer is asked to review the change no more. A reply in any other form holds the review.
A doc reviewer that ended with no report (`state.Agent.unreported`) is
no review. Its replacement gets the current editors' reports, even if
more than one earlier attempt ended without a result. The command launches no editor for a reviewer's findings: that
reviewer sends them to the editors of its brief.

A doc editor that `change_fragments` launches on a change's `mctx` fragments after
the reviewer replied neither launched that reviewer nor got a message from
it, so its report after that reply is among those the review must
follow."""

from dataclasses import replace
from pathlib import Path

from controlled_markdown import mctx
from operations import briefs, messages
from operations.completion import occupies
from operations.change_agents import settled
from operations.change_holds import Hold, findings_hold, unreplied_hold
from operations.directives import Decision, ruling
from operations.handled import sent
from operations.reports import at_cap, no_finding, shows_current
from operations.roles import Role
from operations.state import Agent, State, Ticket, last_reported
from operations.steps import Launch, Pause, Send, Step, Undecided, agent_ids


def reviewers_of(agents: list[Agent], w: Path) -> list[Agent]:
    """The doc reviewers among a change's `agents` whose brief gives the
    change's worktree `w`. A reviewer of an earlier run of the change
    reviewed that run's worktree, so it is none of the change's now."""
    line = briefs.fingerprint_command(w)
    return [a for a in agents if a.role is Role.DOC_REVIEWER and line in a.brief]


def latest_reviewer(agents: list[Agent], w: Path) -> Agent | None:
    """The latest of `reviewers_of`, which is the change's doc reviewer,
    or None where it has none."""
    reviewers = reviewers_of(agents, w)
    return reviewers[-1] if reviewers else None


def doc_review(state: State, t: Ticket, w: Path, here: list[Agent],
               agents: list[Agent], launcher: str) -> Step | Pause:
    """The step of the review of the change's documents, with `launcher`
    as the launcher of each doc reviewer it launches, `Pause.WAIT` where it
    waits on an agent, or `Pause.CLEAR` where it has passed."""
    r = latest_reviewer(agents, w)
    if r is None or not occupies(r):
        return review_launch(state, t, w, here, launcher, 0.0)
    if r.pending:
        return Pause.WAIT
    reply = r.last_report
    if reply is not None and at_cap(r):
        judged = any(a.role is Role.TICKET_ANALYST and a.launched > reply.time
                     and briefs.on_cap_reply(a) and occupies(a) and not a.pending for a in agents)
        return Pause.CLEAR if judged else Pause.WAIT
    if reply is not None and (late := [a for a in here if (rep := a.last_report) is not None
                                       and rep.time > reply.time]):
        return review_stale(state, t, w, here, r, reply.time, late, launcher)
    if reply is not None and no_finding(r):
        return Pause.CLEAR
    if reply is None:
        return unreplied(state, t, w, here, r, launcher)
    return review_decided(state, t, w, here, findings_hold(r, t.number), launcher)


def unreplied(state: State, t: Ticket, w: Path, here: list[Agent],
              r: Agent, launcher: str) -> Step | Pause:
    """The step on a review whose doc reviewer `r` has not replied since
    its editors ended. `steps.Undecided.reread` gives why its held step is
    marked."""
    step = review_decided(state, t, w, here, unreplied_hold(r, t.number), launcher)
    return replace(step, reread=True) if isinstance(step, Undecided) else step


def review_stale(state: State, t: Ticket, w: Path, here: list[Agent], r: Agent, since: float,
                 late: list[Agent], launcher: str) -> Step | Pause:
    """The step on the reply at `since` of the doc reviewer `r`, which
    precedes the last report of the editors `late`: `Pause.CLEAR` where it opens
    with `no finding stands` and `r` sent each of them a message or is a
    launch of theirs, since its reply reaches its launcher, or where it
    opens so and gives the change's worktree `w` in the state it is in,
    and otherwise, where `r` is of `TranscriptsRead.elsewhere`, which no
    message reaches, or the harness refused a message to it
    (`Agent.refused`), the launch of a new doc reviewer on `w`
    (`review_launch`), and where it is not, the message that asks `r` to
    review the change again, or, where `r` has no agent id or was sent
    that message, the step `unreplied` gives."""
    if no_finding(r):
        if shows_current(r, w):
            return Pause.CLEAR
        messaged = state.transcripts.sent_by(r)
        if messaged is None:
            return Undecided(mctx("the transcript of doc reviewer {agent} of change {number} "
                                  "is unknown").format(agent=r.agent_id, number=t.number))
        ids = agent_ids(late)
        if isinstance(ids, Undecided):
            return ids
        if all(i in messaged or i == r.operator for i in ids):
            return Pause.CLEAR
    if r in state.transcripts.elsewhere or r.refused is not None:
        return review_launch(state, t, w, here, launcher, since)
    message = messages.review_again(since)
    if r.agent_id is not None and not sent(state, r.agent_id, message):
        return Send(r.agent_id, message, f"review again {t.number} {since}")
    return unreplied(state, t, w, here, r, launcher)


def review_decided(state: State, t: Ticket, w: Path, here: list[Agent],
                   hold: Hold, launcher: str) -> Step | Pause:
    """The step on a review held on `hold`, by its decision:
    `Pause.CLEAR` where the review passes."""
    r = ruling(state, hold.text, hold.choices)
    if isinstance(r, Undecided):
        return r
    if r.choice is Decision.PASSES:
        return Pause.CLEAR
    return review_launch(state, t, w, here, launcher, r.time)


def with_ids(agents: list[Agent]) -> list[tuple[Agent, str]] | Undecided:
    """Each of `agents` beside its agent id, as `agent_ids` gives it, for
    the briefs that give each editor of a change with its part
    (`briefs.editor_lines`)."""
    ids = agent_ids(agents)
    if isinstance(ids, Undecided):
        return ids
    return list(zip(agents, ids, strict=True))


def review_launch(state: State, t: Ticket, w: Path, here: list[Agent], launcher: str,
                  after: float) -> Step:
    """The launch of a doc reviewer on the change, with its editors, what
    the agents before it settled (`change_agents.settled`), and its rounds
    (`briefs.review_rounds`), by
    `launcher`, after the time `after` of the ruling it is launched on
    (`directives.Ruling`), of the launch or last resume of the reviewer
    that ended with no report it replaces, or of the reply of the reviewer
    of `TranscriptsRead.elsewhere` it replaces (`review_stale`), or 0.0
    after none of those."""
    editors = with_ids(here)
    if isinstance(editors, Undecided):
        return editors
    known = settled(state, t, Role.DOC_REVIEWER, None)
    return Launch(Role.DOC_REVIEWER, t.number, briefs.doc_review(
        t.number, w, editors, launcher, known, briefs.review_rounds(known.launched_before)),
        occasion=str(max(last_reported(here), after)))
