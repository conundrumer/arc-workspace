"""Per-call readers of accepted messages, independent of state reads."""

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import operate_service

from agent_deliveries import delivery, handback_accepted, succeeded
from agent_launches import launched_or_resumed
from file_reads import Named
from run_reads import run_sessions
from transcript_entries import epoch
from transcript_ownership import blocks, own_result, read_meta
from transcript_snapshots import Entry, parse
from transcripts import agent_id, main_transcript, subagent_transcripts


def listing(path: Path) -> tuple[Named, ...]:
    try:
        with os.scandir(path) as entries:
            return tuple(Named(e.name, e.is_dir(), e.is_file(), e.is_symlink()) for e in entries)
    except FileNotFoundError:
        return ()


@dataclass
class Tail:
    """Complete own records read from one file, with unmatched calls and results."""
    identity: tuple[int, int] | None = None
    revision: tuple[int, int, int, int] | None = None
    offset: int = 0
    own: bool = False
    calls: dict[str, tuple[Entry, float]] = field(default_factory=dict)
    results: dict[str, tuple[Entry, float]] = field(default_factory=dict)

    last_user: float = 0.0
    deliveries: list[tuple[Entry, Entry, float, float]] = field(default_factory=list)

    def record(self, entry: Entry) -> None:
        if not entry.get("timestamp"):
            return
        at = epoch(entry["timestamp"])
        changed: list[str] = []
        if entry.get("type") == "assistant":
            for block in blocks(entry, "tool_use"):
                if block.get("name") in {"SendMessage", "SubagentHandback"}:
                    ident = block.get("id", "")
                    self.calls[ident] = block, at
                    changed.append(ident)
        elif entry.get("type") == "user":
            self.last_user = max(self.last_user, at)
            if isinstance(result := entry.get("toolUseResult"), dict):
                for block in blocks(entry, "tool_result"):
                    ident = block.get("tool_use_id", "")
                    self.results[ident] = result, at
                    changed.append(ident)
        for ident in changed:
            if ident not in self.calls or ident not in self.results:
                continue
            call, started = self.calls.pop(ident)
            result, ended = self.results.pop(ident)
            self.deliveries.append((call, result, started, ended))

    def read(self, path: Path) -> list[Entry]:
        try:
            stat = path.stat()
            if self.revision == (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns):
                return []
            with path.open("rb") as stream:
                stat = os.fstat(stream.fileno())
                identity = stat.st_dev, stat.st_ino
                if self.identity != identity or stat.st_size < self.offset:
                    self.identity, self.offset = identity, 0
                    self.calls.clear()
                    self.results.clear()
                    self.own = False
                    self.last_user = 0.0
                    self.deliveries.clear()
                meta = read_meta(path) or {}
                call = meta.get("toolUseId") if meta.get("isFork") is True else None
                self.own = self.own or not isinstance(call, str)
                stream.seek(self.offset)
                entries: list[Entry] = []
                for number, line in enumerate(stream):
                    if number % 128 == 0:
                        operate_service.check()
                    if not line.endswith(b"\n"):
                        break
                    for entry in parse(line):
                        if not self.own:
                            assert isinstance(call, str)
                            self.own = own_result(entry, call)
                        if self.own:
                            self.record(entry)
                            entries.append(entry)
                    self.offset += len(line)
                self.revision = stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns
                return entries
        except FileNotFoundError:
            return []


@dataclass
class Inventory:
    """Transcript paths and ids, shared while every traversed listing stands."""
    directories: dict[Path, tuple[Named, ...]]
    paths: tuple[Path, ...]
    agents: frozenset[str]


_resident_tails: dict[Path, Tail] = {}
"""Only the resident serving thread uses these; every tail verifies its file revision."""


class Inbox:
    """Acceptance since the recipient's frozen last-delivery boundary.
    Each check parses only complete records appended since its previous check."""

    def __init__(self, path: Path, undecided: list[str]) -> None:
        self.entered = time.time()
        self.undecided = undecided
        self.path = path
        self.sessions = run_sessions(path)
        self.roots = {s.parent for s in self.sessions}
        self.directories: dict[Path, tuple[tuple[int, int, int], tuple[Named, ...]]] = {}
        self.tails: dict[Path, Tail] = ({} if operate_service.CURRENT.get() is None
                                       else _resident_tails)
        self.inventories: dict[Path, Inventory] = {}
        self.agent = agent_id(path)
        self.names = {self.agent}
        if name := (read_meta(path) or {}).get("name"):
            self.names.add(str(name))
        self.since = 0.0
        for session in self.sessions:
            candidates = [main_transcript(session), *self.subagents(session).paths]
            for p in candidates:
                if agent_id(p) == self.agent:
                    tail = self.tails.setdefault(p, Tail())
                    tail.read(p)
                    self.since = max(self.since, tail.last_user)

    def entries(self, path: Path) -> tuple[Named, ...]:
        try:
            stat = path.stat()
        except FileNotFoundError:
            self.directories.pop(path, None)
            return ()
        stamp = stat.st_dev, stat.st_ino, stat.st_mtime_ns
        before = self.directories.get(path)
        if before is None or before[0] != stamp:
            before = stamp, listing(path)
            self.directories[path] = before
        return before[1]

    def subagents(self, session: Path) -> Inventory:
        """Reuse paths and ids; stat every traversed directory before reusing them.

        A new nested directory changes one of those listings. Transcript
        appends need no inventory rebuild: each tail still checks its file.
        """
        before = self.inventories.get(session)
        if before is None or any(self.entries(p) is not entries
                                 for p, entries in before.directories.items()):
            directories: dict[Path, tuple[Named, ...]] = {}

            def listed(path: Path) -> tuple[Named, ...]:
                entries = self.entries(path)
                directories[path] = entries
                return entries

            paths = tuple(subagent_transcripts(session, listed))
            before = self.inventories[session] = Inventory(
                directories, paths, frozenset(agent_id(p) for p in paths))
        return before

    def accepted(self) -> bool:
        mine = launched_or_resumed(self.path, self.undecided, before=self.entered)
        for root in self.roots:
            for entry in self.entries(root):
                session = root / entry.name
                if not entry.is_dir or session in self.sessions:
                    continue
                inventory = self.subagents(session)
                if self.agent in inventory.agents:
                    self.sessions.append(session)
        for session in self.sessions:
            for path in [main_transcript(session), *self.subagents(session).paths]:
                tail = self.tails.setdefault(path, Tail())
                tail.read(path)
                for call, result, started, at in tail.deliveries:
                    if at <= self.since or at < started:
                        continue
                    if (call.get("name") == "SubagentHandback" and agent_id(path) in mine
                            and handback_accepted(result)):
                        return True
                    if (call.get("name") == "SendMessage" and succeeded(result)
                            and delivery(result) is not None
                            and str((call.get("input") or {}).get("to", "")) in self.names):
                        return True
        return False


def accepted_after(path: Path, since: float, undecided: list[str]) -> bool:
    """Acceptance after an explicit boundary, using the per-call reader."""
    inbox = Inbox(path, undecided)
    inbox.since = since
    return inbox.accepted()
