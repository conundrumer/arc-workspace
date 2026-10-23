"""What an operator launcher reads (`read_relay`), the session the
command runs in, and whether a call of the command's `wait` by an agent
runs (`wait_running`), which holds the lock `wait_lock` gives."""

import fcntl
import os
from dataclasses import replace
from pathlib import Path

from agent_turns import latest_time
from context_bound_hook import context_bound, past_bound
from agent_launches import children_of, launches, own_entries
from agent_resumes import resumes
from operator_transcript import OperatorLines, Uses, calls_of, lines_of
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
from operations.roles import Role, described


def session_id() -> str:
    """The session `CLAUDE_CODE_SESSION_ID` gives, which the command refuses
    without."""
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not session:
        raise Refused(mctx("the shell gives no `CLAUDE_CODE_SESSION_ID`"))
    return session


def operator_launches(path: Path, uses: Uses,
                      undecided: list[str]) -> list[tuple[str | None, float, bool]]:
    """The operators the launcher at `path` launched by the calls `uses`,
    in the order of their launch: each agent id, launch time and whether its
    end has not reached the launcher. The launcher's own resumes of an
    operator count, those of other agents do not."""
    resumed = resumes(path, undecided)
    out: list[tuple[str | None, float, bool]] = []
    for launch in launches(path, undecided, own_entries):
        use = uses.get(launch.call)
        d = described(str(use[1].get("description", ""))) if use else None
        if use is None or d is None or d.role is not Role.OPERATOR:
            continue
        since = max(launch.since, resumed.get(launch.agent or "", 0.0))
        out.append((launch.agent, use[0], replace(launch, since=since).pending))
    return sorted(out, key=lambda o: o[1])


def read_relay(me: str) -> tuple[Relay, Path]:
    """What the operator launcher `me` reads, from its own transcript and
    those of the operators it launched, and the session's scratchpad."""
    session = session_id()
    main = main_tree()
    undecided: list[str] = []
    path = find(me)
    own = lines_of(OperatorLines, me, path)
    own_calls, uses = calls_of(me, path, own, frozenset(), undecided)
    messages = own.messages(me, children_of(path, me), undecided)
    runs: list[Run] = []
    for agent_id, launched, pending in operator_launches(path, uses, undecided):
        final = None
        failed = None
        ended = launched
        their_path = launched_find(agent_id) if agent_id is not None else None
        if agent_id is not None and their_path is not None:
            theirs = calls_of(agent_id, their_path, lines_of(OperatorLines, agent_id, their_path),
                              frozenset(), undecided)[0]
            ended = latest_time(their_path) or launched
            sends = [c for c in final_sends_in(theirs, agent_id, me) if c.time > launched]
            final = sent_final_text(sends[-1]) if sends else None
            nexts = [c for c in theirs if c.tool == Tool.BASH and c.result is not None
                     and is_next(str(c.input.get("command", "")), agent_id)]
            last = max(nexts, key=lambda c: c.time, default=None)
            if (last is not None and last.error and last.result is not None
                    and prints_no_call(last.result)):
                failed = last.result.strip()
        runs.append(Run(agent_id, launched, pending, final, ended, failed))
    relay = Relay(me, tuple(sorted((m for m in messages if m.sender is None),
                                   key=lambda m: m.time)),
                  tuple(runs), tuple(sorted(own_calls, key=lambda c: c.time)),
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
