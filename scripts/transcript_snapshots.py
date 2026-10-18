"""The snapshots of Claude Code transcripts: the offsets of a transcript's
lines and the lines that hold each word asked about, read again from the
file where it grew at its end (`read_snapshot`), held for one state of
the process (`snapshot`), and the parse of a line into its entry
(`parse`). A read that a transcript's file does not support is refused
(`Refused`)."""

import bisect
import json
import os
import re
import sys
import zlib
from array import array
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, BinaryIO

from file_reads import stat_of, state_stat
from state_reads import state_cache

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
    again of a file that is not, or whose whole lines no longer give their
    CRC-32 (`crc`), is refused.

    At the first word asked of it of the form of an agent id, one search
    indexes every substring of that form, overlapping ones too, by the
    lines that hold it.

    A snapshot read on from an earlier one (`extended`) keeps what that one
    found in its whole lines, and its `generation`, which a snapshot read
    whole takes anew: the snapshots of one generation agree on the whole
    lines of each."""

    def __init__(self, path: Path, file: tuple[int, int], mtime_ns: int, text: bytes) -> None:
        self.path = path
        self.file = file
        self.mtime_ns = mtime_ns
        self.size = len(text)
        self.closed = text.endswith(b"\n") or not text
        self.breaks_cr = b"\r" in text
        self.starts = line_starts(text, 0, array("q"))
        self.found: dict[str, frozenset[int]] = {}
        self.agent_ids: dict[str, tuple[int, ...]] | None = None
        self.crc = self.whole_crc(text)
        self.generation = object()

    def covers(self, st: os.stat_result) -> bool:
        """Whether this snapshot was read from the file `st` gives, no
        earlier than its last modification and up to its size at least."""
        return (self.file == (st.st_dev, st.st_ino) and self.mtime_ns >= st.st_mtime_ns
                and self.size >= st.st_size)

    @property
    def count(self) -> int:
        """The number of its lines."""
        return len(self.starts)

    def end(self, i: int) -> int:
        """The offset after the `i`-th line."""
        return self.starts[i + 1] if i + 1 < len(self.starts) else self.size

    def line(self, i: int) -> bytes:
        """The `i`-th line, without the line break that ends it, as
        `bytes.splitlines` gives it."""
        return unbroken(read_at(self, self.starts[i], self.end(i) - self.starts[i]))

    def lines(self, found: Sequence[int]) -> Iterator[bytes]:
        """Each line of `found`, indices in order, as `line` gives it. Each
        run of consecutive lines up to `SPAN` bytes is read in one read of
        its file."""
        k = 0
        while k < len(found):
            first = j = found[k]
            while (k + 1 < len(found) and found[k + 1] == j + 1
                   and self.end(j + 1) - self.starts[first] <= SPAN):
                k, j = k + 1, j + 1
            base = self.starts[first]
            chunk = read_at(self, base, self.end(j) - base)
            for i in range(first, j + 1):
                yield unbroken(chunk[self.starts[i] - base:self.end(i) - base])
            k += 1

    def text(self) -> bytes:
        """The bytes it covers, read again from its file."""
        text = read_at(self, 0, self.size)
        if len(text) != self.size or self.whole_crc(text) != self.crc:
            raise Refused(mctx("the transcript {path} changed other than at its end while "
                               "it was read").format(path=self.path))
        return text

    def whole_crc(self, text: bytes) -> int:
        """The CRC-32 of the bytes of `text`, the bytes it covers, up to the
        end of its whole lines."""
        return zlib.crc32(memoryview(text)[:self.settled_end()])

    def settled(self) -> int:
        """The number of its whole lines, those a newline ends."""
        return self.count - (0 if self.closed else 1)

    def settled_end(self) -> int:
        """The offset after its whole lines."""
        whole = self.settled()
        return self.starts[whole] if whole < self.count else self.size

    def line_of(self, offset: int) -> int:
        return bisect.bisect_right(self.starts, offset) - 1

    def holding(self, words: frozenset[str]) -> frozenset[int]:
        """The lines that hold a word of `words`. The words not searched
        before are searched in one read of the text again."""
        ids = {w for w in words if re.fullmatch(AGENT_ID_FORM, w)}
        new = [w for w in words - ids if w not in self.found]
        if new or (ids and self.agent_ids is None):
            text = self.text()
            if ids and self.agent_ids is None:
                self.agent_ids = self.index_agent_ids(text, 0)
            for w in new:
                self.found[w] = self.lines_holding(text, 0, w.encode())
        indexed = self.agent_ids or {}
        return frozenset[int]().union(*(indexed.get(w, ()) for w in ids),
                                      *(self.found[w] for w in words - ids))

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

    def extended(self, more: bytes, mtime_ns: int) -> "Snapshot":
        """This snapshot's whole lines followed by `more`, the bytes of its
        file after them, with no carriage return in either, with what this
        one found in them kept, its file as `mtime_ns` gives its modification
        time."""
        whole = self.settled()
        offset = self.settled_end()
        out = Snapshot.__new__(Snapshot)
        out.path, out.file, out.size = self.path, self.file, offset + len(more)
        out.mtime_ns = mtime_ns
        out.generation = self.generation
        out.closed = more.endswith(b"\n") or not more
        out.breaks_cr = False
        out.starts = line_starts(more, offset, self.starts[:whole])
        out.found = {w: frozenset(i for i in lines if i < whole)
                     | out.lines_holding(more, offset, w.encode())
                     for w, lines in self.found.items()}
        out.agent_ids = (None if self.agent_ids is None
                         else self.agent_ids_on(self.agent_ids, out, more))
        out.crc = zlib.crc32(more[:out.settled_end() - offset], self.crc)
        return out

    def agent_ids_on(self, index: dict[str, tuple[int, ...]], out: "Snapshot",
                     more: bytes) -> dict[str, tuple[int, ...]]:
        """The index of agent ids of `out`, this snapshot's whole lines
        followed by `more`, with `index`, this one's, kept for those lines."""
        whole = self.settled()
        kept = {aid: tuple(i for i in lines if i < whole) if whole < self.count else lines
                for aid, lines in index.items()}
        for aid, lines in out.index_agent_ids(more, self.settled_end()).items():
            kept[aid] = kept.get(aid, ()) + lines
        return {aid: lines for aid, lines in kept.items() if lines}


SPAN = 1 << 22
"""How many bytes `Snapshot.lines` and `prefix_crc` read at most in one
read."""


def unbroken(line: bytes) -> bytes:
    """`line` without the line break that ends it."""
    if line.endswith(b"\r\n"):
        return line[:-2]
    return line[:-1] if line.endswith((b"\n", b"\r")) else line


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


def parse(line: str | bytes) -> list[Entry]:
    """The entry of `line`, or none where it is no JSON."""
    try:
        return [json.loads(line)]
    except json.JSONDecodeError:
        return []


_read: dict[Path, Snapshot] = {}
"""The last snapshot of each transcript, which a later read of a
transcript that grew goes on from."""

OPEN = 64
"""How many transcript files `read_at` holds open."""

_open: dict[Path, tuple[int, tuple[int, int]]] = {}
"""The descriptor of each transcript file `read_at` holds open, with the
device and inode of its file, the one it opened last at the end."""


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
    in (`state_cache`), as `read_snapshot` reads it."""
    return read_snapshot(path)


def read_snapshot(path: Path) -> Snapshot:
    """The transcript at `path` as it stands now, kept as its last snapshot.
    A transcript is added to at its end, so where the file is the one of
    its last snapshot and the bytes of that snapshot's whole lines still
    give their CRC-32, it goes on from that snapshot: none of those lines
    is parsed or searched again. Otherwise it is read whole, as a new
    `generation`."""
    with path.open("rb") as fh:
        st = os.fstat(fh.fileno())
        file = st.st_dev, st.st_ino
        before = _read.get(path)
        snap = None
        if before is not None and before.file == file and not before.breaks_cr:
            offset = before.settled_end()
            if st.st_size >= offset and prefix_crc(fh, offset) == before.crc:
                more = fh.read()
                if b"\r" not in more:
                    snap = before.extended(more, st.st_mtime_ns)
        if snap is None:
            fh.seek(0)
            snap = Snapshot(path, file, st.st_mtime_ns, fh.read())
    _read[path] = snap
    return snap


def last_snapshot(path: Path) -> Snapshot:
    """The last snapshot of the transcript at `path`, where it covers the
    file as the stat of this state gives it (`Snapshot.covers`), and
    otherwise one `read_snapshot` reads now. It is no `state_cache` read,
    so a read derived from lines a snapshot gave, by their indices, rests
    on those lines and not on each change of the file: a transcript is
    added to at its end, so a line keeps its bytes while its index
    stands."""
    snap = _read.get(path)
    st = state_stat(str(path))
    if snap is None or st is None or not snap.covers(st):
        return read_snapshot(path)
    return snap


def prefix_crc(fh: BinaryIO, end: int) -> int:
    """The CRC-32 of the bytes of `fh` from where it stands up to `end`, an
    offset, read `SPAN` bytes at a time."""
    crc = 0
    for k in range(fh.tell(), end, SPAN):
        crc = zlib.crc32(fh.read(min(SPAN, end - k)), crc)
    return crc
