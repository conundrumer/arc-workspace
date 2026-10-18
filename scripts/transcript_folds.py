"""The folds over the entries of transcripts that go on from where the
last fold stopped (`fold`): each held in the process, and, where the
process opened the store of `kept_reads`, kept there, so that a later
process folds only the lines added since."""

import zlib
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import kept_reads
from state_reads import canonical
from transcript_entries import own_range, selected_lines
from transcript_snapshots import SPAN, Entry, Snapshot, parse, read_at, snapshot


@dataclass(frozen=True)
class Folded:
    """Where a fold stood in a transcript when it was kept: the `generation`
    of the snapshot it read, the file it read (`Snapshot.file`), the first
    of the run's own lines then (`own_range`), the line it stopped before,
    each line before it a whole line, the offset after that line's last
    byte (`end`), and the CRC-32 of the bytes before that offset."""
    path: Path
    generation: object
    file: tuple[int, int]
    own: int
    done: int
    end: int
    crc: int

    def read_on(self, snap: Snapshot) -> bool:
        """Whether `snap` gives the lines this fold read as they were: it is
        of the same `generation`, or of the same file with the same bytes
        before `end`, as a snapshot read whole in a later process is."""
        if self.generation is snap.generation:
            return True
        if snap.file != self.file or self.done > snap.settled():
            return False
        if end_before(snap, self.done) != self.end:
            return False
        return crc_before(snap, self.end) == self.crc


def end_before(snap: Snapshot, line: int) -> int:
    """The offset after the last byte of the lines of `snap` before `line`."""
    return snap.end(line - 1) if line else 0


def crc_before(snap: Snapshot, end: int) -> int:
    """The CRC-32 of the bytes of the file of `snap` before the offset
    `end`, which a whole line ends."""
    if end == snap.settled_end():
        return snap.crc
    crc = 0
    for k in range(0, end, SPAN):
        crc = zlib.crc32(read_at(snap, k, min(SPAN, end - k)), crc)
    return crc


def folded_at(path: Path, snap: Snapshot, own: range, done: int) -> Folded:
    """Where a fold stands that read the lines of `snap` before `done`."""
    end = end_before(snap, done)
    return Folded(path, snap.generation, snap.file, own.start, done, end, crc_before(snap, end))


type Step[S] = Callable[[S, Path, int, Entry], None]
"""A fold's step: it adds to the state an entry, with its transcript and
the index of its line."""

type Kept = tuple[Any, tuple[Folded, ...]]
"""The state of a fold, with where it stood in each transcript it read."""

_folds: dict[Hashable, Kept] = {}
"""The state of each fold held by its step and run."""


def fold[S](step: Step[S], start: Callable[[], S], run: Hashable, paths: Sequence[Path],
            naming: frozenset[str] | None = None) -> S:
    """The state `step` gives from `start()` over each entry of the run's
    own lines of each transcript of `paths`, in their order, or with
    `naming` each entry `read_entries` gives with it, as the transcripts
    stand at the state this process is in. A later call with the same
    `step` and `run`, in this process or, through the store, in a later
    one, parses only the lines added since, where `goes_on` holds, and
    otherwise starts the fold again, as for a transcript written anew,
    cut, or changed before its end. A fold whose step fails is not kept.
    A state over a line that is not whole is given and not kept. The
    caller changes none of the state it gets, and holds none of it past
    its read, as a later fold adds to it."""
    key = step, run
    held = _folds.pop(key, None)
    if held is None:
        held = stored(step, run)
    now = [(p, snapshot(p), own_range(p)) for p in paths]
    if held is not None and goes_on(held[1], now):
        state, marks = held[0], held[1]
    else:
        state, marks = start(), ()
    kept: list[Folded] = []
    for j, (p, snap, own) in enumerate(now):
        done = marks[j].done if j < len(marks) else own.start
        whole = max(own.start, min(own.stop, snap.settled()))
        fold_lines(state, step, p, snap, range(done, whole), naming)
        kept.append(folded_at(p, snap, own, whole))
    _folds[key] = state, tuple(kept)
    if [m.done for m in kept] != [m.done for m in marks]:
        store(step, run, (state, tuple(kept)))
    if not any(parse(line) for _, snap, own in now
               for line in snap.lines(selected_lines(snap, range(max(own.start, snap.settled()),
                                                         own.stop), naming))):
        return state
    state = start()
    for p, snap, own in now:
        fold_lines(state, step, p, snap, own, naming)
    return state


def store_names(step: Step[Any], run: Hashable) -> tuple[str, str] | None:
    """The read and the key the store keeps the fold of `step` and `run`
    by, the read in the module of `step`, so that a change of its code
    drops the record; None where `run` has no canonical form."""
    try:
        key = repr(canonical(run))
    except TypeError:
        return None
    return f"{step.__module__}:{step.__qualname__}:fold", key


def stored(step: Step[Any], run: Hashable) -> Kept | None:
    """The fold of `step` and `run` the open store keeps, or None."""
    found = kept_reads.store()
    names = store_names(step, run)
    if found is None or names is None:
        return None
    record = found.held(*names)
    return record if isinstance(record, tuple) else None


def store(step: Step[Any], run: Hashable, kept: Kept) -> None:
    """Keep `kept`, the fold of `step` and `run`, in the open store."""
    found = kept_reads.store()
    names = store_names(step, run)
    if found is not None and names is not None:
        found.keep(*names, kept)


def goes_on(marks: tuple[Folded, ...], now: list[tuple[Path, Snapshot, range]]) -> bool:
    """Whether a fold that stood at `marks` goes on over the transcripts
    `now` gives, each with its snapshot and own lines: each transcript of
    `marks` is the one at its place in `now`, read on by its snapshot
    (`Folded.read_on`), of the same first own line, and only the last of
    them has lines past where the fold stopped."""
    if len(marks) > len(now):
        return False
    for j, m in enumerate(marks):
        p, snap, own = now[j]
        if m.path != p or m.own != own.start or m.done > own.stop or not m.read_on(snap):
            return False
        if j < len(marks) - 1 and m.done != own.stop:
            return False
    return True


def fold_lines[S](state: S, step: Step[S], path: Path, snap: Snapshot, lines: range,
                  naming: frozenset[str] | None) -> None:
    """Fold into `state` the entries of `lines` of `snap`, the snapshot of
    the transcript at `path`, or with `naming` of those lines that hold one
    of its words."""
    found = selected_lines(snap, lines, naming)
    for i, line in zip(found, snap.lines(found)):
        for e in parse(line):
            step(state, path, i, e)
