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
from collections.abc import Callable, Iterable, Iterator, Sequence
from pathlib import Path
from typing import Any, BinaryIO

from file_reads import FileStat, stat_of, state_stat
from state_reads import state_cache

from controlled_markdown import mctx
from operations.roles import AGENT_ID as AGENT_ID_FORM

type Entry = dict[str, Any]


class Refused(Exception):
    """A call the command does not run, with the reason."""


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
    from its file (`read_at`). Each read of its text, the first one
    included, goes by chunks of whole lines (`line_chunks`), so that a
    read holds no whole transcript. A transcript is added to at its end, so the
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

    def __init__(self, path: Path, file: tuple[int, int], mtime_ns: int,
                 chunks: Iterable[tuple[int, bytes]]) -> None:
        """The snapshot of the bytes `chunks` gives, each chunk with its
        offset, in order from offset 0, as `line_chunks` gives them."""
        self.path = path
        self.file = file
        self.mtime_ns = mtime_ns
        self.size = 0
        self.closed = True
        self.breaks_cr = False
        self.starts = array("q")
        self.crc = 0
        last = b""
        for base, chunk in chunks:
            self.crc = cut_crc(last, self.size - len(last), self.size, self.crc)
            self.size = base + len(chunk)
            self.breaks_cr = self.breaks_cr or b"\r" in chunk
            line_starts(chunk, base, self.starts)
            last = chunk
        self.closed = last.endswith(b"\n") or not last
        self.crc = cut_crc(last, self.size - len(last), self.settled_end(), self.crc)
        self.found: dict[str, frozenset[int]] = {}
        self.agent_ids: dict[str, tuple[int, ...]] | None = None
        self.generation = object()

    def covers(self, st: FileStat) -> bool:
        """Whether this snapshot was read from the file `st` gives, no
        earlier than its last modification and up to its size at least."""
        return (self.file == (st.dev, st.ino) and self.mtime_ns >= st.mtime_ns
                and self.size >= st.size)

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

    def chunks(self) -> Iterator[tuple[int, bytes]]:
        """The bytes it covers, read again from its file by chunks of whole
        lines (`line_chunks`), each with its offset. Once the last is given,
        a file whose bytes no longer give the size and the CRC-32 of the
        snapshot is refused."""
        crc, end, size = 0, self.settled_end(), 0
        for base, chunk in line_chunks(lambda offset, length: read_at(self, offset, length),
                                       self.size):
            crc = cut_crc(chunk, base, end, crc)
            size = base + len(chunk)
            yield base, chunk
        if size != self.size or crc != self.crc:
            raise Refused(mctx("the transcript {path} changed other than at its end while "
                               "it was read").format(path=self.path))

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
        before are searched in one read of the text again (`chunks`)."""
        ids = {w for w in words if re.fullmatch(AGENT_ID_FORM, w)}
        new = [w for w in words - ids if w not in self.found]
        index = bool(ids) and self.agent_ids is None
        if new or index:
            found: dict[str, frozenset[int]] = {w: frozenset() for w in new}
            agent_ids: dict[str, tuple[int, ...]] = {}
            for base, chunk in self.chunks():
                for w in new:
                    found[w] |= self.lines_holding(chunk, base, w.encode())
                if index:
                    joined(agent_ids, self.index_agent_ids(chunk, base))
            self.found.update(found)
            if index:
                self.agent_ids = agent_ids
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
            i = self.line_of(base + k)
            out.add(i)
            k = chunk.find(w, self.end(i) - base)
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
        out.crc = cut_crc(more, offset, out.settled_end(), self.crc)
        return out

    def agent_ids_on(self, index: dict[str, tuple[int, ...]], out: "Snapshot",
                     more: bytes) -> dict[str, tuple[int, ...]]:
        """The index of agent ids of `out`, this snapshot's whole lines
        followed by `more`, with `index`, this one's, kept for those lines."""
        whole = self.settled()
        kept = {aid: tuple(i for i in lines if i < whole) if whole < self.count else lines
                for aid, lines in index.items()}
        joined(kept, out.index_agent_ids(more, self.settled_end()))
        return {aid: lines for aid, lines in kept.items() if lines}


def joined(index: dict[str, tuple[int, ...]], more: dict[str, tuple[int, ...]]) -> None:
    """Adds to `index`, the lines that hold each agent id, those `more`
    gives, lines after each of `index`."""
    for aid, lines in more.items():
        index[aid] = index.get(aid, ()) + lines


SPAN = 1 << 18
"""How many bytes `Snapshot.lines`, `line_chunks` and `span_crc` read at
most in one read. Each read is a new buffer, and the peak memory of a
process that reads a transcript of 90 MB grows with the size of its
buffers: by about 100 MB at 4 MB each, and by about 12 MB at this
size."""


def cut_crc(chunk: bytes, base: int, end: int, crc: int) -> int:
    """`crc` with the bytes of `chunk`, the bytes of a file from offset
    `base`, before the offset `end` folded in."""
    return zlib.crc32(memoryview(chunk)[:max(0, end - base)], crc)


def span_crc(read: Callable[[int, int], bytes], start: int, end: int, crc: int = 0) -> int:
    """`crc` with the bytes from offset `start` up to `end` that `read`,
    given an offset and a length, gives of a file folded in, read `SPAN`
    bytes at a time, in order."""
    for k in range(start, end, SPAN):
        crc = zlib.crc32(read(k, min(SPAN, end - k)), crc)
    return crc


def line_chunks(read: Callable[[int, int], bytes], end: int) -> Iterator[tuple[int, bytes]]:
    """The bytes from offset 0 up to `end` that `read`, given an offset and
    a length, gives of a file, by chunks, each with its offset. Each chunk
    but the last ends at a newline and holds `SPAN` bytes at most, unless
    one line is longer. The chunks end early where the file does."""
    pos = 0
    while pos < end:
        buf = read(pos, min(SPAN, end - pos))
        while pos + len(buf) < end and b"\n" not in buf:
            more = read(pos + len(buf), min(SPAN, end - pos - len(buf)))
            if not more:
                break
            buf += more
        if not buf:
            return
        cut = buf.rfind(b"\n") + 1 if pos + len(buf) < end else len(buf)
        cut = cut or len(buf)
        yield pos, buf[:cut]
        pos += cut


def unbroken(line: bytes) -> bytes:
    """`line` without the line break that ends it."""
    if line.endswith(b"\r\n"):
        return line[:-2]
    return line[:-1] if line.endswith((b"\n", b"\r")) else line


LINE_BREAK = re.compile(rb"\r\n|\r|\n")
"""A line break, as `bytes.splitlines` takes one."""


def line_starts(chunk: bytes, base: int, before: "array[int]") -> "array[int]":
    """`before`, the offsets of the lines before `base`, with the offset of
    each line of `chunk`, the bytes of a file from offset `base`, a line's,
    as `bytes.splitlines` splits it, added at its end. A chunk with no carriage
    return is split by a search for each newline, which is faster than
    `LINE_BREAK`. The offsets are held as machine integers,
    8 bytes each, as a call holds those of every transcript it reads."""
    out = before
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
            fd = fh.fileno()
            snap = Snapshot(path, file, st.st_mtime_ns,
                            line_chunks(lambda offset, length: os.pread(fd, length, offset),
                                        st.st_size))
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
    offset, by the reads of `fh` (`span_crc`), which leave it at `end`."""
    return span_crc(lambda offset, length: fh.read(length), fh.tell(), end)
