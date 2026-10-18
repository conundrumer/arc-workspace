"""The folds over the entries of transcripts that go on from where the
last fold stopped (`fold`): each held in the process, and, where the
process opened the store of `kept_reads`, kept there, so that a later
process folds only the lines added since; and the items a read makes
from a fold's state (`Makes`), each made anew only where a value it is
made from changed since the last read of the same state."""

from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import kept_reads
from state_reads import canonical
from transcript_entries import own_range, selected_lines
from transcript_snapshots import Entry, Snapshot, parse, read_at, snapshot, span_crc


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
    return span_crc(lambda offset, length: read_at(snap, offset, length), 0, end)


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
"""The state of each fold held by its step, run and `naming`."""


def fold[S](step: Step[S], start: Callable[[], S], run: Hashable, paths: Sequence[Path],
            naming: frozenset[str] | None = None) -> S:
    """The state `step` gives from `start()` over each entry of the run's
    own lines of each transcript of `paths`, in their order, or with
    `naming` each entry `read_entries` gives with it, as the transcripts
    stand at the state this process is in. `run` gives each value
    `start()` reads, so that a kept state is one `start()` would begin
    again. A later call with the same `step`, `run` and `naming`, in this
    process or, through the store, in a later one, parses only the lines
    added since, where `goes_on` holds, and
    otherwise starts the fold again, as for a transcript written anew,
    cut, or changed before its end. A fold whose step fails is not kept.
    A state over a line that is not whole is given and not kept. The
    caller changes none of the state it gets, and holds none of it past
    its read, as a later fold adds to it."""
    key = run, naming
    held = _folds.pop((step, key), None)
    if held is None:
        held = stored(step, key)
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
    _folds[step, key] = state, tuple(kept)
    if [m.done for m in kept] != [m.done for m in marks]:
        store(step, key, (state, tuple(kept)))
    if not any(parse(line) for _, snap, own in now
               for line in snap.lines(selected_lines(snap, range(max(own.start, snap.settled()),
                                                         own.stop), naming))):
        return state
    state = start()
    for p, snap, own in now:
        fold_lines(state, step, p, snap, own, naming)
    return state


def store_names(step: Step[Any], key: Hashable) -> tuple[str, str] | None:
    """The read and the key the store keeps the fold of `step` and `key`,
    its run with its `naming`, by, the read in the module of `step`, so
    that a change of its code drops the record; None where `key` has no
    canonical form."""
    try:
        name = repr(canonical(key))
    except TypeError:
        return None
    return f"{step.__module__}:{step.__qualname__}:fold", name


def stored(step: Step[Any], key: Hashable) -> Kept | None:
    """The fold of `step` and `key`, its run with its `naming`, the open
    store keeps, or None."""
    found = kept_reads.store()
    names = store_names(step, key)
    if found is None or names is None:
        return None
    record = found.held(*names)
    return record if isinstance(record, tuple) else None


def store(step: Step[Any], key: Hashable, kept: Kept) -> None:
    """Keep `kept`, the fold of `step` and `key`, its run with its
    `naming`, in the open store."""
    found = kept_reads.store()
    names = store_names(step, key)
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


@dataclass(frozen=True)
class Made[T]:
    """An item a read made from a fold's state, with the values it was
    made from (`given`) and the `undecided` lines its making gave."""
    given: object
    item: T
    lines: tuple[str, ...]


class Makes[T]:
    """The items a read last made for each run from the state of a fold,
    by the id of each, with that state and the further key the read gives.
    A read of the same state and key keeps each item whose values are as
    they were, and makes the others anew."""

    def __init__(self) -> None:
        self._held: dict[Hashable, tuple[object, Hashable, dict[str, Made[T]]]] = {}

    def read(self, run: Hashable, state: object, key: Hashable = None) -> "Making[T]":
        """The making of the items of `run` from `state`, the fold's state,
        with `key`, which keeps the items made from the same state object
        and an equal key."""
        held = self._held.get(run)
        before = held[2] if held is not None and held[0] is state and held[1] == key else {}
        made: dict[str, Made[T]] = {}
        self._held[run] = state, key, made
        return Making(before, made)


@dataclass(frozen=True)
class Making[T]:
    """The items of one read of `Makes`: those kept from the last read
    (`before`), and those this read gives (`made`)."""
    before: dict[str, Made[T]]
    made: dict[str, Made[T]]

    def item(self, ident: str, given: Callable[[T], object], make: Callable[[list[str]], T],
             undecided: list[str]) -> T:
        """The item `ident`: the one kept, where `given` of it is the value
        it was made from, or else the one `make` makes, with the lines it
        adds to the list it is given. Each item adds its `undecided` lines
        to `undecided`, as its making gave them."""
        m = self.before.get(ident)
        if m is None or m.given != given(m.item):
            lines: list[str] = []
            item = make(lines)
            m = Made(given(item), item, tuple(lines))
        self.made[ident] = m
        undecided.extend(m.lines)
        return m.item
