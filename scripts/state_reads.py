"""The reads a state of the process rests on, each held for that state
and, where what it rests on stands, for later states (`state_cache`), and
the reads of files it holds: the stat of a path, the text of a file, and
the entries of a directory."""

import inspect
import os
import stat
import time
from collections.abc import Callable, Hashable, Iterator
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any

_state = 0
"""The count of the states this process has opened (`new_state`)."""


class Held:
    """A held read: the state it was last brought up to date at and the
    state a read last reached it at, its stamp, result and `undecided`
    lines, the held reads its last run made (`made`) with the result each
    gave it, the held reads whose last run made it (`dependents`), and whether a
    source it rests on gave another result since it was last checked
    (`marked`). A held read is a source where its stamp is not `DERIVED`."""
    __slots__ = ("recall", "drop", "source", "state", "reached", "mark", "value",
                 "lines", "made", "dependents", "marked")

    def __init__(self, recall: "Recall", drop: Callable[[], object], source: bool) -> None:
        self.recall = recall
        self.drop = drop
        self.source = source
        self.state = 0
        self.reached = 0
        self.mark: Hashable = None
        self.value: object = None
        self.lines: tuple[str, ...] = ()
        self.made: dict[Held, object] = {}
        self.dependents: dict[Held, None] = {}
        self.marked = False

    def rest_on(self, made: dict["Held", object]) -> None:
        """Replace the reads this one rests on, and their reverse edges, by
        `made`."""
        for below in self.made:
            del below.dependents[self]
        self.made = made
        for below in made:
            below.dependents[self] = None


_held: dict[Held, None] = {}
"""Each held read, in the order it was first held."""

_marking = False
"""Whether the sources are being brought up to date at this state."""

_marked_late: list[Held] = []
"""Each held read marked after a read reached it at this state, whose
dependents are marked again at the next state."""


def new_state() -> float:
    """Open a new state, and give the time it opened: from then on, each
    `state_cache` read gives what it reads as it stands now where its stamp
    changed, and as held where it did not.

    Each held read that no read reached at the last state and no held read
    rests on is dropped. Each held source is then brought up to date, each
    after the sources it rests on, and each one whose result is not its
    held one marks each held read that rests on it, transitively."""
    global _state, _marking
    last = _state
    _state += 1
    late = list(_marked_late)
    _marked_late.clear()
    for below in late:
        mark_dependents(below)
    def unused(h: Held) -> bool:
        return h in _held and h.reached != last and not h.dependents
    idle = [h for h in _held if unused(h)]
    while idle:
        h = idle.pop()
        if not unused(h):
            continue
        del _held[h]
        h.drop()
        made = list(h.made)
        h.rest_on({})
        idle += [below for below in made if unused(below)]
    _marking = True
    try:
        for h in list(_held):
            bring_up(h)
    finally:
        _marking = False
    return time.time()


def bring_up(source: Held) -> None:
    """Bring the held source `source` up to date at this state, after each
    source it rests on: a source whose read fails stays as held, and marks
    each held read that rests on it."""
    if not source.source or source.state == _state or source not in _held:
        return
    for below in list(source.made):
        bring_up(below)
    try:
        source.recall()
    except Exception:
        mark_dependents(source)


def mark_dependents(below: Held) -> None:
    """Mark each held read that rests on `below`, transitively."""
    seen: set[Held] = set()
    stack = list(below.dependents)
    while stack:
        h = stack.pop()
        if h in seen:
            continue
        seen.add(h)
        h.marked = True
        if h.state == _state:
            _marked_late.append(h)
        stack += h.dependents


class Derived:
    """The stamp of a read that rests on nothing but the `state_cache` reads
    it makes (`DERIVED`)."""


DERIVED = Derived()
"""The stamp of a read whose result stands while each `state_cache` read it
made in its last run gives the result it gave then."""


type Recall = Callable[[], object]


_frames: list[dict[Held, object]] = []
"""For each read running, innermost last, the held reads it made, each
with the result it gave."""


def held_still(made: dict[Held, object]) -> bool:
    """Whether each of the reads `made` gives, at this state, the very result
    it gave: a read gives its held result again where its stamp holds or
    where what it reads anew equals it."""
    for below, value in made.items():
        below.reached = _state
        try:
            if below.recall() is not value:
                return False
        except Exception:
            return False
    return True


def state_cache[**P, R](stamp: Callable[P, Hashable] | None | Derived, *,
                        notes: str | None = None) -> Callable[
        [Callable[P, R]], Callable[P, R]]:
    """Hold the result of a read for each of its arguments. Within one state
    the held result stands. At the first call of a new state the read runs
    again, unless `stamp` of its arguments is the stamp of the held result.
    The stamp of a read of files is their stat, and that of a read derived
    from other `state_cache` reads is their results, so it agrees with
    them within a state. A read with nothing to stamp, `stamp` None, runs
    again at each new state. A read whose stamp is `DERIVED` runs again
    where a `state_cache` read it made in its last run gives another result
    (`held_still`).

    `new_state` brings each held source up to date and marks the reads
    that rest on one that changed. A `DERIVED` read that is not marked
    gives its held result with no check of the reads it made, unless the
    sources are being brought up to date; one that is marked checks them.

    A `DERIVED` read makes each read of a file, a directory or a process
    through a `state_cache` read, and takes each other input as an
    argument: a read it makes otherwise takes no part in its stamp.

    Where a read runs again and gives a result equal to the held one, the
    held one stands, so a read derived from it sees no change. Each caller
    gets the held result itself, and changes none of it.

    `notes` names the parameter of the read's list of `undecided` lines,
    which takes no part in the held result's key: the lines a run appends
    are held with its result, and each call appends them to the list it
    passes.

    Each process-life read cache that `operator_state.read_state` reaches,
    in any module, is a `state_cache`, so the readers of one state see one
    state, and a change between two states reaches the second."""
    def hold(read: Callable[P, R]) -> Callable[P, R]:
        held: dict[Hashable, Held] = {}
        at = None if notes is None else list(inspect.signature(read).parameters).index(notes)
        derived = isinstance(stamp, Derived)

        def run(key: Hashable, args: tuple[Any, ...], kwargs: dict[str, Any],
                positional: bool) -> tuple[Any, tuple[str, ...]]:
            hit = held.get(key)
            if hit is not None and hit.state == _state:
                return hit.value, hit.lines
            mark: Hashable = None
            if hit is not None and derived:
                if (not hit.marked and not _marking) or held_still(hit.made):
                    hit.state, hit.marked = _state, False
                    return hit.value, hit.lines
            elif not isinstance(stamp, Derived) and stamp is not None:
                _frames.append({})
                try:
                    mark = stamp(*args, **kwargs)
                finally:
                    _frames.pop()
                if hit is not None and hit.mark == mark:
                    hit.state = _state
                    return hit.value, hit.lines
            lines: list[str] = []
            if at is not None and notes is not None:
                if positional:
                    args = (*args[:at], lines, *args[at:])
                else:
                    kwargs = {**kwargs, notes: lines}
            _frames.append({})
            try:
                value = read(*args, **kwargs)
            finally:
                made = _frames.pop()
            if hit is None:
                hit = Held(lambda: run(key, args, kwargs, positional)[0],
                           lambda: held.pop(key), not derived)
                held[key] = hit
                _held[hit] = None
            elif value is not hit.value and same(value, hit.value):
                value = hit.value
            elif value is not hit.value and hit.source:
                mark_dependents(hit)
            hit.state, hit.mark, hit.value, hit.lines = _state, mark, value, tuple(lines)
            hit.marked = False
            hit.rest_on(made if stamp is None or derived else {})
            return value, hit.lines

        @wraps(read)
        def at_state(*given: P.args, **named: P.kwargs) -> R:
            args: tuple[Any, ...] = tuple(given)
            kwargs: dict[str, Any] = dict(named)
            sink: list[str] | None = None
            positional = False
            if at is not None and notes is not None:
                if len(args) > at:
                    sink = args[at]
                    positional = True
                    args = (*args[:at], *args[at + 1:])
                else:
                    sink = kwargs.pop(notes)
            key = (args, tuple(sorted(kwargs.items())))
            value, lines = run(key, args, kwargs, positional)
            hit = held[key]
            hit.reached = _state
            if sink is not None:
                sink.extend(lines)
            if _frames:
                _frames[-1][hit] = value
            return value
        return at_state
    return hold


def same(value: object, held: object) -> bool:
    """Whether `value` equals `held`, a comparison that fails counting as
    not."""
    try:
        return bool(value == held)
    except Exception:
        return False


def stat_of(path: Path) -> tuple[int, int] | None:
    """The modification time and size of the file at `path`, or None where
    there is none."""
    try:
        st = path.stat()
    except FileNotFoundError:
        return None
    return st.st_mtime_ns, st.st_size


@dataclass(frozen=True)
class FileStat:
    """What a stat that follows links gives of a file, as `stat_read` reads
    it: no time of last access, which a read of the file changes."""
    mtime: float
    mtime_ns: int
    size: int
    ino: int
    is_dir: bool
    is_file: bool


@state_cache(None)
def stat_read(path: Path) -> FileStat | None:
    """The stat of the file at `path`, or None where there is none."""
    try:
        st = path.stat()
    except FileNotFoundError:
        return None
    return FileStat(st.st_mtime, st.st_mtime_ns, st.st_size, st.st_ino,
                    stat.S_ISDIR(st.st_mode), stat.S_ISREG(st.st_mode))


def is_file(path: Path) -> bool:
    """`Path.is_file`, from `stat_read`."""
    return stat_is(path, lambda found: found.is_file)


def is_dir(path: Path) -> bool:
    """`Path.is_dir`, from `stat_read`."""
    return stat_is(path, lambda found: found.is_dir)


def stat_is(path: Path, holds: Callable[[FileStat], bool]) -> bool:
    """Whether `holds` of the stat of the file at `path`, False where none
    reads, as `Path.is_file` takes a path under a file."""
    try:
        found = stat_read(path)
    except NotADirectoryError:
        return False
    return found is not None and holds(found)


def mtime(path: Path) -> float:
    """The time of the last write of the file at `path`, as `Path.stat`
    gives it, from `stat_read`; FileNotFoundError where there is none."""
    found = stat_read(path)
    if found is None:
        raise FileNotFoundError(path)
    return found.mtime


@state_cache(lambda path, errors=None: stat_of(path))
def file_text(path: Path, errors: str | None = None) -> str:
    """`Path.read_text` of the file at `path`, with `errors`."""
    return path.read_text(errors=errors)


@state_cache(None)
def resolved(path: Path) -> Path:
    """`Path.resolve` of `path`."""
    return path.resolve()


@dataclass(frozen=True)
class Named:
    """An entry of a directory, as `os.scandir` gives it: `is_dir` and
    `is_file` follow a link, and `is_link` says whether it is one."""
    name: str
    is_dir: bool
    is_file: bool
    is_link: bool


@state_cache(stat_of)
def listed(path: Path) -> tuple[Named, ...]:
    """The entries of the directory at `path`, or none where it is no
    directory that reads. Its stamp is the directory's stat, which an entry
    added, removed or renamed changes."""
    try:
        with os.scandir(path) as found:
            return tuple(Named(e.name, e.is_dir(), e.is_file(), e.is_symlink()) for e in found)
    except OSError:
        return ()


def names_in(path: Path) -> Iterator[str]:
    """The names of the entries `listed` gives of the directory at `path`."""
    return (e.name for e in listed(path))
