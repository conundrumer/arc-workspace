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


def new_state() -> float:
    """Open a new state, and give the time it opened: from then on, each
    `state_cache` read gives what it reads as it stands now where its stamp
    changed, and as held where it did not."""
    global _state
    _state += 1
    return time.time()


class Derived:
    """The stamp of a read that rests on nothing but the `state_cache` reads
    it makes (`DERIVED`)."""


DERIVED = Derived()
"""The stamp of a read whose result stands while each `state_cache` read it
made in its last run gives the result it gave then."""


type Recall = Callable[[], object]


_frames: list[dict[Hashable, tuple[Recall, object]]] = []
"""For each read running, innermost last, the `state_cache` reads it made,
each with the call that makes it again and the result it gave."""


def held_still(made: tuple[tuple[Recall, object], ...]) -> bool:
    """Whether each of the reads `made` gives, at this state, the very result
    it gave: a read gives its held result again where its stamp holds or
    where what it reads anew equals it."""
    for recall, value in made:
        try:
            if recall() is not value:
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
        held: dict[Hashable, tuple[int, Hashable, R, tuple[str, ...],
                                   tuple[tuple[Recall, object], ...]]] = {}
        at = None if notes is None else list(inspect.signature(read).parameters).index(notes)

        def run(key: Hashable, args: tuple[Any, ...], kwargs: dict[str, Any],
                positional: bool) -> tuple[R, tuple[str, ...]]:
            hit = held.get(key)
            if hit is not None and hit[0] == _state:
                return hit[2], hit[3]
            _frames.append({})
            try:
                if isinstance(stamp, Derived):
                    mark: Hashable = None
                    again = hit is None or not held_still(hit[4])
                else:
                    mark = stamp(*args, **kwargs) if stamp is not None else None
                    again = hit is None or stamp is None or hit[1] != mark
            finally:
                _frames.pop()
            if not again and hit is not None:
                held[key] = (_state, *hit[1:])
                return hit[2], hit[3]
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
            if hit is not None and value is not hit[2] and same(value, hit[2]):
                value = hit[2]
            held[key] = (_state, mark, value, tuple(lines),
                         tuple(made.values()) if isinstance(stamp, Derived) else ())
            return value, tuple(lines)

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
            if sink is not None:
                sink.extend(lines)
            if _frames:
                _frames[-1][(id(run), key)] = (
                    lambda: run(key, args, kwargs, positional)[0], value)
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
