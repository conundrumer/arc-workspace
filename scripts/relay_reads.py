"""What an operator launcher reads (`read_relay`), the session the
command runs in, and whether a call of the command's `wait` by an agent
runs (`wait_running`), which holds the lock `wait_lock` gives."""

import fcntl
import os
from pathlib import Path

from agent_turns import latest_time
from context_bound_hook import context_bound, past_bound
from operator_transcript import read_operator
from printed_bash_check import prints_no_call
from run_reads import context_size
from transcripts import find, launched_find
from entry_reads import entries_back
from transcript_snapshots import Refused
from tree_reads import main_tree, scratch

from controlled_markdown import mctx
from operations.command_words import is_next
from operations.state import Tool
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
        failed = None
        ended = a.launched
        their_path = launched_find(a.agent_id) if a.agent_id is not None else None
        if a.agent_id is not None and their_path is not None:
            theirs = read_operator(a.agent_id, their_path, main, undecided, {}).calls
            ended = latest_time(their_path) or a.launched
            sends = [c for c in final_sends_in(theirs, a.agent_id, me) if c.time > a.launched]
            final = sent_final_text(sends[-1]) if sends else None
            nexts = [c for c in theirs if c.tool == Tool.BASH and c.result is not None
                     and is_next(str(c.input.get("command", "")), a.agent_id)]
            last = max(nexts, key=lambda c: c.time, default=None)
            if (last is not None and last.error and last.result is not None
                    and prints_no_call(last.result)):
                failed = last.result.strip()
        runs.append(Run(a.agent_id, a.launched, a.pending, final, ended, failed))
    relay = Relay(me, tuple(sorted((m for m in own.messages if m.sender is None),
                                   key=lambda m: m.time)),
                  tuple(runs), tuple(sorted(own.calls, key=lambda c: c.time)),
                  past_bound(context_size(entries_back(path)), context_bound(main)),
                  wait_running(me))
    return relay, scratch(session)


LOCK_DIR = Path("/tmp")


def wait_lock(agent: str) -> Path:
    """The file whose lock a call of the command's `wait` by `agent` holds
    while it runs."""
    return LOCK_DIR / f"operate-wait-{agent}.lock"


def wait_running(agent: str) -> bool:
    """Whether a call of the command's `wait` by `agent` runs: another
    process holds the lock of `wait_lock`."""
    try:
        fd = os.open(wait_lock(agent), os.O_RDONLY)
    except FileNotFoundError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        return False
    except BlockingIOError:
        return True
    finally:
        os.close(fd)


def run_index(runs: list[tuple[str, Path]], me: str) -> int:
    """The position of `me` among the operator runs `runs`."""
    return [a for a, _ in runs].index(me)
