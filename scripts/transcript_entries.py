"""Read the entries of a Claude Code transcript, each read held for one
state of the process (`state_cache`): the snapshot of its lines, the
lines that hold a word, the lines that are its run's own, and its
`.meta.json` file. No held read holds a parsed entry: each read parses
the lines it reads anew, so its entries are held by its caller alone."""

import bisect
import hashlib
import json
from array import array
from dataclasses import dataclass
import os
import re
import sys
from collections.abc import Iterable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from file_reads import stat_of
from state_reads import DERIVED, state_cache

from controlled_markdown import mctx
from operations.roles import AGENT_ID as AGENT_ID_FORM

type Entry = dict[str, Any]


class Refused(Exception):
    """A call the command does not carry out, with the reason."""


def print_refused(reason: object) -> None:
    print(mctx("refused: {reason}").format(reason=reason), file=sys.stderr)


HEX = bytes(ord("1") if chr(c) in "0123456789abcdef" else ord("0") for c in range(256))
"""The table that maps each hexadecimal digit to `1` and each other byte to
`0`."""
HEX_RUN = b"1" * (len("a") + 16)
"""The mask of the shortest run of digits that holds an agent id."""


def agent_ids_in(text: bytes, start: int) -> Iterator[tuple[bytes, int]]:
    """Each substring of `text` from `start` on of the form of an agent id,
    overlapping ones too, with its offset: each `a` of a run of hexadecimal
    digits with 16 digits after it in the run. The runs are found in a mask
    of the text, so the text is scanned once. `start` is the offset of a
    line, which no run crosses."""
    mask = text[start:].translate(HEX)
    k = mask.find(HEX_RUN)
    while k >= 0:
        end = mask.find(b"0", k)
        end = len(mask) if end < 0 else end
        j = text.find(b"a", start + k, start + end - 16)
        while j >= 0:
            yield text[j:j + 17], j
            j = text.find(b"a", j + 1, start + end - 16)
        k = mask.find(HEX_RUN, end)


class Snapshot:
    """The lines of a transcript as they stood when it was read, with the
    lines that hold each word asked about.

    It holds no text, so that a read of many transcripts holds little:
    `starts` gives the offset of each line and `size` the bytes it covers,
    and a line, or the text a word is first searched for in, is read again
    from its file (`read_at`). A transcript is added to at its end, so the
    bytes a snapshot covers stand while its file is the one it read; a read
    again of a file that is not, or whose bytes at either end of the
    snapshot's whole lines (`edges`) changed, is refused.

    At its read, one search indexes every substring of the form of an agent
    id, overlapping ones too, by the lines that hold it.

    A snapshot read on from an earlier one (`extended`) keeps what that one
    found in its whole lines."""

    def __init__(self, path: Path, file: tuple[int, int], text: bytes) -> None:
        self.path = path
        self.file = file
        self.size = len(text)
        self.closed = text.endswith(b"\n") or not text
        self.breaks_cr = b"\r" in text
        self.starts = line_starts(text, 0, array("q"))
        self.found: dict[str, frozenset[int]] = {}
        self.agent_ids = self.index_agent_ids(text, 0)
        self.edges = edges(text, self.settled_end())

    @property
    def count(self) -> int:
        """The number of its lines."""
        return len(self.starts)

    def line(self, i: int) -> bytes:
        """The `i`-th line, without the line break that ends it, as
        `bytes.splitlines` gives it."""
        end = self.starts[i + 1] if i + 1 < len(self.starts) else self.size
        line = read_at(self, self.starts[i], end - self.starts[i])
        if line.endswith(b"\r\n"):
            return line[:-2]
        return line[:-1] if line.endswith((b"\n", b"\r")) else line

    def text(self) -> bytes:
        """The bytes it covers, read again from its file."""
        text = read_at(self, 0, self.size)
        if len(text) != self.size or edges(text, self.settled_end()) != self.edges:
            raise Refused(mctx("the transcript {path} changed other than at its end while "
                               "it was read").format(path=self.path))
        return text

    def settled(self) -> int:
        """The number of its whole lines, those a newline ends."""
        return self.count - (0 if self.closed else 1)

    def settled_end(self) -> int:
        """The offset after its whole lines."""
        whole = self.settled()
        return self.starts[whole] if whole < self.count else self.size

    def line_of(self, offset: int) -> int:
        return bisect.bisect_right(self.starts, offset) - 1

    def holding(self, word: str) -> frozenset[int]:
        if re.fullmatch(AGENT_ID_FORM, word):
            return frozenset(self.agent_ids.get(word, ()))
        if word not in self.found:
            self.found[word] = self.lines_holding(self.text(), 0, word.encode())
        return self.found[word]

    def lines_holding(self, chunk: bytes, base: int, w: bytes) -> frozenset[int]:
        """The lines of `chunk`, the bytes of its file from offset `base`, a
        line's, that hold `w`, a word with no line break in it."""
        if not w or b"\n" in w or b"\r" in w:
            raise ValueError(f"{w!r} is no word a line holds")
        out: set[int] = set()
        k = chunk.find(w)
        while k >= 0:
            out.add(self.line_of(base + k))
            k = chunk.find(w, k + 1)
        return frozenset(out)

    def index_agent_ids(self, chunk: bytes, base: int) -> dict[str, tuple[int, ...]]:
        """Each substring of the form of an agent id in `chunk`, the bytes of
        its file from offset `base`, a line's, by the lines that hold it, in
        order. The lines are a tuple, a quarter of the size of a set of
        one, as a call holds the index of every transcript it reads."""
        index: dict[bytes, dict[int, None]] = {}
        for aid, k in agent_ids_in(chunk, 0):
            index.setdefault(aid, {})[self.line_of(base + k)] = None
        return {aid.decode(): tuple(found) for aid, found in index.items()}

    def entry(self, i: int) -> list[Entry]:
        return parse(self.line(i))

    def extended(self, more: bytes) -> "Snapshot":
        """This snapshot's whole lines followed by `more`, the bytes of its
        file after them, with no carriage return in either, with what this
        one found in them kept."""
        whole = self.settled()
        offset = self.settled_end()
        out = Snapshot.__new__(Snapshot)
        out.path, out.file, out.size = self.path, self.file, offset + len(more)
        out.closed = more.endswith(b"\n") or not more
        out.breaks_cr = False
        out.starts = line_starts(more, offset, self.starts[:whole])
        out.found = {w: frozenset(i for i in lines if i < whole)
                     | out.lines_holding(more, offset, w.encode())
                     for w, lines in self.found.items()}
        kept = {aid: tuple(i for i in lines if i < whole) if whole < self.count else lines
                for aid, lines in self.agent_ids.items()}
        for aid, lines in out.index_agent_ids(more, offset).items():
            kept[aid] = kept.get(aid, ()) + lines
        out.agent_ids = {aid: lines for aid, lines in kept.items() if lines}
        end = out.settled_end()
        head = read_at(out, 0, min(CHECKED, end))
        tail_at = max(len(head), end - CHECKED)
        out.edges = Edges.of(head, read_at(out, tail_at, end - tail_at))
        return out


LINE_BREAK = re.compile(rb"\r\n|\r|\n")
"""A line break, as `bytes.splitlines` takes one."""


def line_starts(chunk: bytes, base: int, before: "array[int]") -> "array[int]":
    """`before`, the offsets of the lines before `base`, followed by the
    offset of each line of `chunk`, the bytes of a file from offset `base`,
    a line's, as `bytes.splitlines` splits it. A chunk with no carriage
    return is split by a search for each newline, which is faster than
    `LINE_BREAK`. The offsets are held as machine integers,
    8 bytes each, as a call holds those of every transcript it reads."""
    out = array("q", before)
    if not chunk:
        return out
    out.append(base)
    if b"\r" in chunk:
        out.extend(base + m.end() for m in LINE_BREAK.finditer(chunk) if m.end() < len(chunk))
        return out
    n = chunk.find(b"\n")
    while 0 <= n < len(chunk) - 1:
        out.append(base + n + 1)
        n = chunk.find(b"\n", n + 1)
    return out


def epoch(iso: str) -> float:
    return datetime.fromisoformat(iso).timestamp()


def parse(line: str | bytes) -> list[Entry]:
    """The entry of `line`, or none where it is no JSON."""
    try:
        return [json.loads(line)]
    except json.JSONDecodeError:
        return []


_read: dict[Path, Snapshot] = {}
"""The last snapshot of each transcript, which a later read of a
transcript that grew goes on from."""

CHECKED = 4096
"""How many bytes at each end of the whole lines of a transcript's last
snapshot a later read compares, to find a file that was written anew
rather than added to."""

OPEN = 64
"""How many transcript files `read_at` holds open."""

_open: dict[Path, tuple[int, tuple[int, int]]] = {}
"""The descriptor of each transcript file `read_at` holds open, with the
device and inode of its file, the one it opened last at the end."""


@dataclass(frozen=True)
class Edges:
    """The bytes at either end of a snapshot's whole lines, as their sizes
    and a digest of them, as a call holds those of every transcript it
    reads."""
    head: int
    tail: int
    digest: bytes

    @staticmethod
    def of(head: bytes, tail: bytes) -> "Edges":
        return Edges(len(head), len(tail), hashlib.blake2b(head + b"\n" + tail).digest())


def edges(text: bytes, end: int) -> Edges:
    """The first `CHECKED` bytes of `text` up to `end`, and the last
    `CHECKED` bytes up to `end` after those."""
    head = text[:min(CHECKED, end)]
    return Edges.of(head, text[max(len(head), end - CHECKED):end])


def read_at(snap: Snapshot, offset: int, length: int) -> bytes:
    """`length` bytes from `offset` of the file of `snap`, refused where its
    path now holds another file."""
    held = _open.pop(snap.path, None)
    if held is None:
        fd = os.open(snap.path, os.O_RDONLY)
        st = os.fstat(fd)
        held = fd, (st.st_dev, st.st_ino)
        if len(_open) >= OPEN:
            os.close(_open.pop(next(iter(_open)))[0])
    _open[snap.path] = held
    if held[1] != snap.file:
        raise Refused(mctx("the transcript {path} was written anew while it was read")
                      .format(path=snap.path))
    return os.pread(held[0], length, offset)


@state_cache(stat_of)
def snapshot(path: Path) -> Snapshot:
    """The transcript at `path` as it stands at the state this process is
    in (`state_cache`). A transcript is added to at its end, so where the
    file is the one of its last snapshot and its bytes there still stand,
    only the bytes after that snapshot's whole lines are read."""
    with path.open("rb") as fh:
        st = os.fstat(fh.fileno())
        file = st.st_dev, st.st_ino
        before = _read.get(path)
        snap = None
        if before is not None and before.file == file and not before.breaks_cr:
            offset = before.settled_end()
            if st.st_size >= offset:
                head = fh.read(before.edges.head)
                fh.seek(offset - before.edges.tail)
                if Edges.of(head, fh.read(before.edges.tail)) == before.edges:
                    more = fh.read()
                    if b"\r" not in more:
                        snap = before.extended(more)
        if snap is None:
            fh.seek(0)
            snap = Snapshot(path, file, fh.read())
    _read[path] = snap
    return snap


def read_entries(path: Path, naming: Iterable[str] | None = None) -> list[Entry]:
    """The entries of the transcript at `path` as it stands at the state this
    process is in, or with `naming` only those whose line holds one of its
    words, which spares parsing the rest."""
    lines = entries_naming(path, None if naming is None else frozenset(naming))
    # The snapshot `entries_naming` read, taken from `_read` so that the
    # caller rests on the lines it gives and not on each change of the file.
    snap = _read[path]
    return [e for i in lines for e in snap.entry(i)]


@state_cache(DERIVED)
def entries_naming(path: Path, naming: frozenset[str] | None) -> list[int]:
    """The lines whose entries `read_entries` gives, held so that a read
    derived from it sees a change of the transcript only where those lines
    change: a transcript is added to at its end, so a line keeps its bytes
    while its index stands here."""
    if naming is None:
        return list(own_range(path))
    return named_lines(snapshot(path), own_range(path), naming)


def named_lines(snap: Snapshot, own: range, naming: frozenset[str]) -> list[int]:
    """The lines of `snap` within `own` that hold a word of `naming`, in
    their order."""
    return sorted(i for i in frozenset[int]().union(*(snap.holding(w) for w in naming))
                  if i in own)


def entries_forward(path: Path) -> Iterator[Entry]:
    """The entries of the transcript at `path` as it stands at the state this
    process is in, in their order, each line parsed only when it is reached."""
    snap = snapshot(path)
    for i in own_range(path):
        yield from snap.entry(i)


def entries_back(path: Path) -> Iterator[Entry]:
    """The entries of the transcript at `path` as it stands at the state this
    process is in, last first, each line parsed only when it is reached."""
    snap = snapshot(path)
    for i in reversed(own_range(path)):
        yield from snap.entry(i)


def meta_path(path: Path) -> Path:
    """The `.meta.json` file of the transcript at `path`."""
    return path.with_suffix(".meta.json")


@state_cache(lambda path: stat_of(meta_path(path)))
def transcript_meta(path: Path) -> dict[str, Any] | None:
    m = meta_path(path)
    return json.loads(m.read_text()) if m.is_file() else None


def blocks(entry: Entry, kind: str) -> list[dict[str, Any]]:
    content = (entry.get("message") or {}).get("content")
    if not isinstance(content, list):
        return []
    return [b for b in content if isinstance(b, dict) and b.get("type") == kind]


@state_cache(DERIVED)
def own_range(path: Path) -> range:
    """The indices of the lines of the transcript at `path` that are its
    run's own. A fork's transcript opens with a copy of its parent's
    entries, through the Agent call that launched the fork, which its
    `.meta.json` gives as `toolUseId`, and its own entries run from the
    first line whose entry holds that call's result to its last line.
    For a fork's transcript where no line holds that result, it is empty.
    For each other transcript, it is every line."""
    meta = transcript_meta(path) or {}
    call = meta.get("toolUseId")
    snap = snapshot(path)
    if meta.get("isFork") is not True or not isinstance(call, str):
        return range(snap.count)
    start = next((i for i in sorted(snap.holding(call))
                  if any(b.get("tool_use_id") == call
                         for e in snap.entry(i) for b in blocks(e, "tool_result"))), None)
    return range(0) if start is None else range(start, snap.count)


def forked_from(path: Path) -> str | None:
    """The id of the session that the session whose transcript is at
    `path` was forked from, which the transcript's first line names, or
    None where that line names none."""
    with path.open() as fh:
        first = fh.readline()
    entry = next(iter(parse(first)), None)
    if not isinstance(entry, dict):
        raise Refused(mctx("the first line of {path} is no transcript entry").format(path=path))
    fork = entry.get("forkedFrom")
    return fork["sessionId"] if fork else None
