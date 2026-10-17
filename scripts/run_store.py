"""The store of what `budgets.group_budgets` reads of each run, held on
disk across processes in the file `STORE_NAME` gives under `.cache/` of
the main worktree: the last transcript and the agent type of each agent,
and the profile of a run with the `undecided` lines its profile appends.

A held record stands only while the code that reads it is the code that
held it, and while each file whose read reaches it has the stat it had
when it was held, a file that is not there included:
- the last transcript and the agent type of an agent rest on each
  transcript of the agent and its `.meta.json` file;
- the profile of a run rests on each transcript, and its `.meta.json`
  file, of each agent of each session of the run's transcripts, wherever
  that transcript lies, and on each other file its profile noted
  (`noted_reads`). A profile that rests on the state of a running process
  is not held.
Otherwise the record is computed again and held again.

SQLite writes the records of a call in one transaction, under a lock it
takes across processes, so no reader sees a record half written. Where the
process cannot read or write the store, each record is computed, as with
no store."""

import hashlib
import pickle
import sqlite3
from collections.abc import Hashable
from enum import StrEnum
from pathlib import Path

from engine import checkout
from kept_reads import UNREADABLE, StoreFile
from noted_reads import recording
from run_profiler import profile
from run_records import Run
from run_reads import agent_type, meta_path, run_sessions, session_agents
from file_reads import stat_of
from state_reads import state_cache
from transcripts import agent_id, agent_transcripts, chain

STORE_NAME = "run-records.sqlite"

SOURCES = ("scripts/**/*.py", "src/**/*.py", "tools/console/solver_console/**/*.py")
"""The code a held record rests on."""

KEEP_SECONDS = 24 * 3600
"""How long the records of code that no process has read stay held: a
worktree that runs other code within that time keeps its records."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    code TEXT, kind TEXT, agent TEXT, stamp TEXT, value BLOB,
    PRIMARY KEY (code, kind, agent));
CREATE TABLE IF NOT EXISTS codes (code TEXT PRIMARY KEY, used REAL);
"""



class Kind(StrEnum):
    """What a record holds."""
    TYPE = "type"
    """The last transcript and the agent type of an agent."""
    PROFILE = "profile"
    """The profile of a run."""


def digest(stamp: Hashable) -> str:
    return hashlib.sha256(repr(stamp).encode()).hexdigest()


@state_cache(None)
def agent_stamp(agent: str) -> tuple[tuple[str, tuple[int, int] | None,
                                           tuple[int, int] | None], ...]:
    return tuple((str(p), stat_of(p), stat_of(meta_path(p)))
                 for p in agent_transcripts().get(agent, []))


@state_cache(None)
def session_stamp(session: Path) -> str:
    return digest(tuple(agent_stamp(a) for a in sorted(session_agents(session))))


def profile_stamp(path: Path, files: list[str]) -> Hashable:
    return (tuple(session_stamp(s) for s in run_sessions(path)),
            tuple((f, stat_of(Path(f))) for f in files))


class RunStore(StoreFile):
    """The records of one call: those computed are written to the store
    together by `flush`."""

    def __init__(self) -> None:
        super().__init__(checkout.caches() / STORE_NAME, SCHEMA)
        self.code = checkout.sources_digest(SOURCES)
        self.new: list[tuple[Kind, str, str, bytes]] = []

    def held(self, kind: Kind, agent: str) -> tuple[str, bytes] | None:
        try:
            return self.connect().execute(
                "SELECT stamp, value FROM records WHERE code = ? AND kind = ? AND agent = ?",
                (self.code, kind, agent)).fetchone()
        except (sqlite3.Error, OSError):
            return None

    def last_and_type(self, agent: str) -> tuple[Path, str | None]:
        """The last transcript of the run of `agent`, and its agent type
        (`run_reads.agent_type`)."""
        stamp = digest(agent_stamp(agent))
        held = self.held(Kind.TYPE, agent)
        if held is not None and held[0] == stamp:
            try:
                last, kind = pickle.loads(held[1])
                return Path(last), kind
            except UNREADABLE:
                pass
        last = chain(agent_transcripts()[agent][0])[-1]
        kind = agent_type(last)
        self.new.append((Kind.TYPE, agent, stamp, pickle.dumps((str(last), kind))))
        return last, kind

    def profile(self, path: Path, undecided: list[str]) -> Run:
        """The profile of the run whose last transcript is at `path`, with
        the `undecided` lines it appends (`run_profiler.profile`)."""
        agent = agent_id(path)
        held = self.held(Kind.PROFILE, agent)
        if held is not None:
            try:
                run, lines, files = pickle.loads(held[1])
                if held[0] == digest(profile_stamp(path, files)):
                    undecided.extend(lines)
                    return run
            except UNREADABLE:
                pass
        lines: list[str] = []
        with recording() as reads:
            run = profile(path, lines)
        undecided.extend(lines)
        if not reads.live:
            files = sorted(str(p) for p in reads.paths)
            self.new.append((Kind.PROFILE, agent, digest(profile_stamp(path, files)),
                             pickle.dumps((run, lines, files))))
        return run

    def flush(self) -> None:
        """Write the records computed since the store was read, and drop
        those of code that no process has read for `KEEP_SECONDS`."""
        self.put([("INSERT OR REPLACE INTO records VALUES (?, ?, ?, ?, ?)",
                   [(self.code, *r) for r in self.new])], [self.code], KEEP_SECONDS)
        self.close()
        self.new = []
