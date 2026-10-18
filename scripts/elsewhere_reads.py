"""The agents of other runs on the changes an operator holds: the agents
that operators of other sessions launched on them, and the checks that
their editors launched."""

from collections.abc import Mapping, Sequence
from pathlib import Path

from operator_reads import AgentsRead, ended_by, ended_elsewhere, kept
from operator_transcript import read_operator
from transcripts import find
from transcript_snapshots import Refused

from controlled_markdown import mctx
from operations.change_agents import on_change
from operations.change_budget import left_draft
from operations.changes import holds
from operations.log_commands import AGENT
from operations.roles import CHECKS, LAUNCHING_EDITORS
from operations.state import Agent, Ticket


def editor_checks(agents: Sequence[Agent], main: Path, undecided: list[str]) -> AgentsRead:
    """The checks, of `roles.CHECKS`, that the editors among `agents` of
    `roles.LAUNCHING_EDITORS` launched, read from those editors'
    transcripts as an operator's launches are read, with the editor as
    their `operator`."""
    out: list[Agent] = []
    reads: list[AgentsRead] = []
    for a in agents:
        if a.role not in LAUNCHING_EDITORS or a.agent_id is None:
            continue
        theirs = read_operator(a.agent_id, find(a.agent_id), main, undecided, {}, False)
        out += [r for r in theirs.agents if r.role in CHECKS]
        reads.append(theirs.launched)
    return kept(out, reads)


def elsewhere_agents(tickets: Mapping[str, Ticket], me: str, operators: frozenset[str],
                     main: Path, undecided: list[str]) -> AgentsRead:
    """`TranscriptsRead.elsewhere` over the changes of `tickets` `me` holds, where
    `operators` gives the operators of the session. Each agent kept whose
    work is no longer open ends with its final reply, as `ended_elsewhere`
    gives it. Where the transcript of such an operator is not found, an
    `undecided` line names it."""
    out: list[Agent] = []
    reads: list[AgentsRead] = []
    for t in (t for t in tickets.values() if holds(t, me)):
        since = left_draft(t)
        others = dict.fromkeys(ln.agent_id for ln in t.log
                               if ln.time > since and ln.agent == AGENT and ln.agent_id
                               and ln.agent_id not in operators)
        for oid in others:
            try:
                path = find(oid)
            except Refused:
                undecided.append(mctx("{run}: no transcript of operator {agent} of another "
                                      "session is found, so its agents on change {number} are "
                                      "not read").format(run=me, agent=oid, number=t.number))
                continue
            one = read_operator(oid, path, main, undecided, {}, False)
            theirs = [a for a in one.agents if a.launched > since and on_change(a, t.number)]
            reviewers = editor_checks(theirs, main, undecided)
            reads += [one.launched, reviewers]
            theirs += [r for r in reviewers.agents
                       if r.launched > since and on_change(r, t.number)]
            out += ended_by(theirs, ended_elsewhere(theirs, me, undecided))
    return kept(sorted(out, key=lambda a: a.launched), reads)
