"""The agents of other runs on the changes an operator holds: the agents
that operators of other sessions launched on them, and the checks that
their editors launched."""

from collections.abc import Mapping, Sequence
from pathlib import Path

from agent_ends import ended_by, ended_elsewhere
from operator_reads import AgentsRead, kept
from operator_transcript import read_launches
from transcripts import find, launched_find
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
    `roles.LAUNCHING_EDITORS` launched, with the editor as their
    `operator`. Enrolled editors use their assignment's native launches;
    Claude launches also require a readable transcript."""
    out: list[Agent] = []
    reads: list[AgentsRead] = []
    for a in agents:
        if a.role not in LAUNCHING_EDITORS or a.agent_id is None:
            continue
        from codex_reads import native_agents, native_find
        from run_reads import session_of
        from tree_reads import scratch

        try:
            operator_path = find(a.operator)
            session_scratch = scratch(session_of(operator_path).name)
            native = native_find(a.agent_id, session_scratch)
        except (Refused, OSError, ValueError):
            native = None
        if native is not None:
            checks = native_agents(a.agent_id, session_scratch)
            out += [r for r in checks.agents if r.role in CHECKS]
            reads.append(checks)
        path = launched_find(a.agent_id)
        if path is None:
            continue
        theirs = read_launches(a.agent_id, path, main, undecided)
        existing = {r.agent_id for r in out}
        out += [r for r in theirs.agents if r.role in CHECKS and r.agent_id not in existing]
        reads.append(theirs.launched)
    return kept(out, reads)


def elsewhere_agents(tickets: Mapping[str, Ticket], me: str, operators: frozenset[str],
                     main: Path, undecided: list[str]) -> AgentsRead:
    """`TranscriptsRead.elsewhere` over the changes of `tickets` `me` holds, where
    `operators` gives the operators of the session. Where the transcript of
    an operator of another session is not found, an `undecided` line names
    it."""
    out: list[Agent] = []
    reads: list[AgentsRead] = []
    for t in (t for t in tickets.values() if holds(t, me)):
        since = left_draft(t)

        def kept_on(a: Agent) -> bool:
            return a.launched > since and on_change(a, t.number)

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
            one = read_launches(oid, path, main, undecided)
            theirs = [a for a in one.agents if kept_on(a)]
            reviewers = editor_checks(theirs, main, undecided)
            reads += [one.launched, reviewers]
            theirs += [r for r in reviewers.agents if kept_on(r)]
            out += ended_by(theirs, ended_elsewhere(theirs, me, undecided))
    return kept(sorted(out, key=lambda a: a.launched), reads)
