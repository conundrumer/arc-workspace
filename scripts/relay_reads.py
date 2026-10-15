"""What an operator launcher reads (`read_relay`), and the session the
command runs in."""

import os
from pathlib import Path

from context_bound_hook import past_bound
from operator_reads import (
    read_operator,
)
from run_reads import context_size
from transcripts import find
from transcript_entries import Refused, entries_back
from tree_reads import main_tree, scratch

from controlled_markdown import mctx
from operations.final_reply import final_sends_in, sent_final_text
from operations.relay import Relay, Run
from operations.roles import Role


def session_id() -> str:
    """The session `CLAUDE_CODE_SESSION_ID` gives, which the command refuses
    without."""
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not session:
        raise Refused(mctx("the shell gives no `CLAUDE_CODE_SESSION_ID`"))
    return session


def read_relay(me: str) -> tuple[Relay, Path]:
    """What the operator launcher `me` reads, from its own transcript and
    those of the operators it launched, and the session's scratchpad."""
    session = session_id()
    main = main_tree()
    undecided: list[str] = []
    path = find(me)
    own = read_operator(me, path, main, undecided, {})
    runs: list[Run] = []
    for a in sorted(own.agents, key=lambda a: a.launched):
        if a.role is not Role.OPERATOR:
            continue
        final = None
        if a.agent_id is not None:
            theirs = read_operator(a.agent_id, find(a.agent_id), main, undecided, {}).calls
            sends = [c for c in final_sends_in(theirs, a.agent_id, me) if c.time > a.launched]
            final = sent_final_text(sends[0]) if sends else None
        runs.append(Run(a.agent_id, a.launched, a.pending, final))
    relay = Relay(me, tuple(sorted((m for m in own.messages if m.sender is None),
                                   key=lambda m: m.time)),
                  tuple(runs), tuple(sorted(own.calls, key=lambda c: c.time)),
                  past_bound(context_size(entries_back(path))))
    return relay, scratch(session)


def run_index(runs: list[tuple[str, Path]], me: str) -> int:
    """The position of `me` among the operator runs `runs`."""
    return [a for a, _ in runs].index(me)
