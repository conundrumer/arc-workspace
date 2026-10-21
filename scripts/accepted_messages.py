"""Per-call readers of accepted messages, independent of state reads."""

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

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
    offset: int = 0
    own: bool = False
    calls: dict[str, tuple[Entry, float]] = field(default_factory=dict)
    results: dict[str, tuple[Entry, float]] = field(default_factory=dict)

    def read(self, path: Path) -> list[Entry]:
        try:
            with path.open("rb") as stream:
                stat = os.fstat(stream.fileno())
                identity = stat.st_dev, stat.st_ino
                if self.identity != identity or stat.st_size < self.offset:
                    self.identity, self.offset = identity, 0
                    self.calls.clear()
                    self.results.clear()
                    self.own = False
                meta = read_meta(path) or {}
                call = meta.get("toolUseId") if meta.get("isFork") is True else None
                self.own = self.own or not isinstance(call, str)
                stream.seek(self.offset)
                entries: list[Entry] = []
                for line in stream:
                    if not line.endswith(b"\n"):
                        break
                    self.offset += len(line)
                    for entry in parse(line):
                        if not self.own:
                            assert isinstance(call, str)
                            self.own = own_result(entry, call)
                        if self.own:
                            entries.append(entry)
                return entries
        except FileNotFoundError:
            return []


class Inbox:
    """Acceptance since the recipient's frozen last-delivery boundary.
    Each check parses only complete records appended since its previous check."""

    def __init__(self, path: Path, undecided: list[str]) -> None:
        entered = time.time()
        self.path = path
        self.sessions = run_sessions(path)
        self.roots = {s.parent for s in self.sessions}
        self.directories: dict[Path, tuple[tuple[int, int, int], tuple[Named, ...]]] = {}
        self.tails: dict[Path, Tail] = {}
        self.names = {agent_id(path)}
        if name := (read_meta(path) or {}).get("name"):
            self.names.add(str(name))
        self.since = 0.0
        for session in self.sessions:
            candidates = [main_transcript(session), *subagent_transcripts(session, listing)]
            for p in candidates:
                if agent_id(p) == agent_id(path):
                    self.since = max(self.since, *(epoch(e["timestamp"])
                        for e in Tail().read(p) if e.get("type") == "user" and e.get("timestamp")), 0.0)
        self.mine = launched_or_resumed(path, undecided, before=entered)

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

    def accepted(self) -> bool:
        for root in self.roots:
            for entry in self.entries(root):
                session = root / entry.name
                if not entry.is_dir or session in self.sessions:
                    continue
                paths = subagent_transcripts(session, self.entries)
                if any(agent_id(p) == agent_id(self.path) for p in paths):
                    self.sessions.append(session)
        for session in self.sessions:
            for path in [main_transcript(session), *subagent_transcripts(session, self.entries)]:
                tail = self.tails.setdefault(path, Tail())
                for e in tail.read(path):
                    if not e.get("timestamp"):
                        continue
                    if e.get("type") == "assistant":
                        for b in blocks(e, "tool_use"):
                            if b.get("name") in {"SendMessage", "SubagentHandback"}:
                                tail.calls[b.get("id", "")] = b, epoch(e["timestamp"])
                    elif e.get("type") == "user" and isinstance(r := e.get("toolUseResult"), dict):
                        for b in blocks(e, "tool_result"):
                            tail.results[b.get("tool_use_id", "")] = r, epoch(e["timestamp"])
                for ident in list(tail.calls.keys() & tail.results.keys()):
                    call, started = tail.calls.pop(ident)
                    result, at = tail.results.pop(ident)
                    if at <= self.since or at < started:
                        continue
                    if (call.get("name") == "SubagentHandback" and agent_id(path) in self.mine
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
