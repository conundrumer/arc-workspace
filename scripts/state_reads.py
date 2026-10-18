"""The reads a state of the process rests on, each held for that state
and, where what it rests on stands, for later states (`state_cache`) and,
for a read kept on disk, for later processes (`Kept`, the store of
`kept_reads`). The reads of files it holds are in `file_reads`."""

import importlib
import inspect
import time
import uuid
from collections.abc import Callable, Hashable, Mapping
from enum import Enum
from functools import wraps
from pathlib import Path
from types import MappingProxyType
from typing import Any

import kept_reads

_state = 0
"""The count of the states this process has opened (`new_state`)."""

_opened = time.time()
"""A time no later than the first read of each held source at this state:
when `new_state` began to bring the sources up to date, or the import of
this module before the first state."""


EMPTY: Mapping[Any, object] = MappingProxyType({})
"""The `stamped` or `made` of a held read that has none, one mapping for
each, as a call holds tens of thousands of held reads that rest on
nothing, such as the stat of a path."""


class Held:
    """A held read: the read and its arguments (`read`, `call`), whether
    its `notes` are passed by position (`positional`), the state
    it was last brought up to date at and the state a read last reached it
    at, its stamp, with the held reads its stamp made (`stamped`), its
    result and `undecided` lines, the version of its result in the store of
    `kept_reads`, where it is kept there (`Kept.DISK`), the held reads its
    last run made (`made`) with the result each gave it, the held reads
    whose last run made it (`dependents`), and whether a source it rests on
    gave another result since it was last checked (`marked`). A held read
    is a source where its stamp is not `DERIVED`."""
    __slots__ = ("source", "read", "call", "positional", "state", "reached", "mark",
                 "stamped", "value", "lines", "version", "made", "dependents", "marked")

    def __init__(self, source: bool, read: "ReadInfo", call: "Call", positional: bool) -> None:
        self.source = source
        self.read = read
        self.call = call
        self.positional = positional
        self.stamped: Mapping[Held, object] = EMPTY
        self.version: str | None = None
        self.state = 0
        self.reached = 0
        self.mark: Hashable = None
        self.value: object = None
        self.lines: tuple[str, ...] = ()
        self.made: Mapping[Held, object] = EMPTY
        self.dependents: dict[Held, None] = {}
        self.marked = False

    def recall(self) -> object:
        """The read's result at this state for its arguments."""
        assert self.read.run is not None
        return self.read.run(self.call, self.positional)[0]

    def drop(self) -> None:
        """Drop this read from the held reads of its read."""
        self.read.held.pop(self.call)

    def rest_on(self, made: Mapping["Held", object]) -> None:
        """Replace the reads this one rests on, and their reverse edges, by
        `made`."""
        for below in self.made:
            del below.dependents[self]
        self.made = made or EMPTY
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

    The records the last state kept are written to the store first
    (`kept_reads`). Each held read that no read reached at the last state
    and no held read rests on is dropped. Each held source is then brought up to date, each
    after the sources it rests on, and each one whose result is not its
    held one marks each held read that rests on it, transitively."""
    global _state, _marking
    kept_reads.flush()
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
        h.rest_on(EMPTY)
        idle += [below for below in made if unused(below)]
    global _opened
    _opened = time.time()
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


_frames: list[dict[Held, object]] = []
"""For each read running, innermost last, the held reads it made, each
with the result it gave."""


def reach(hit: Held) -> None:
    """Note that a read reached the held read `hit` at this state, and that
    the read running, where one is, made it with its held result."""
    hit.reached = _state
    if _frames:
        _frames[-1][hit] = hit.value


def state() -> int:
    """The count of the states this process has opened."""
    return _state


def opened() -> float:
    """A time no later than the read of each source this state holds."""
    return _opened


def in_read() -> bool:
    """Whether a `state_cache` read is running."""
    return bool(_frames)


def held_still(made: Mapping[Held, object]) -> bool:
    """Whether each of the reads `made` gives, at this state, the very result
    it gave: a read gives its held result again where its stamp holds or
    where what it reads anew equals it. A read up to date at this state, or
    a `DERIVED` read that is not marked while no source is being brought up
    to date, gives its held result with no run (`run`), so it is compared
    by that result."""
    for below, value in made.items():
        below.reached = _state
        if below.state == _state or not (below.marked or below.source or _marking):
            if below.value is not value:
                return False
            continue
        try:
            if below.recall() is not value:
                return False
        except Exception:
            return False
    return True


class Kept(Enum):
    """How a `state_cache` read stands across processes, in the store of
    `kept_reads`, where a process opened it."""
    DISK = "disk"
    """Its result is kept in the store, with the trace of the reads it
    rests on (`trace_of`), and stands in a later process while each read of
    that trace gives what it gave (`holds`). A kept read that made it gives
    its result in its trace."""
    VALUE = "value"
    """A kept read that made it gives its result in its trace, in place of
    the reads that result rests on: it is computed again in a later
    process, which a change of those reads that leaves the result as it
    was does not make miss."""


type Call = tuple[tuple[Any, ...], tuple[tuple[str, Any], ...]]
"""The arguments of a read, positional and named, less its `notes`."""


class By(Enum):
    """What a trace gives of a read it rests on (`trace_of`)."""
    STAMP = "stamp"
    VALUE = "value"
    VERSION = "version"
    """The version of its result in the store, which a result that equals
    the one before keeps."""


type Run = Callable[[Call, bool], tuple[Any, tuple[str, ...]]]
"""A read's run for its arguments, its `notes` passed by position or not:
its result and `undecided` lines."""


type Leaf = tuple[By, str, tuple[Any, ...], tuple[tuple[str, Any], ...], object]
"""A read of a trace (`trace_of`): what the trace gives of it, the read's
name (`ReadInfo.name`), its arguments, and its stamp, result or version."""


type Record = tuple[tuple[Leaf, ...], object, tuple[str, ...], str]
"""What the store keeps of a read for its arguments: the trace of the reads
it rests on, its result, its `undecided` lines, and its version."""


class ReadInfo:
    """A `state_cache` read: its name, `module:qualname`, by which a trace
    gives it, its stamp, where its `notes` parameter stands, how it is
    kept, the read as `state_cache` wraps it, the run of the read for a
    held read's arguments (`Run`), and its held reads by their arguments."""
    __slots__ = ("name", "stamp", "notes", "notes_at", "kept", "wrapped", "run", "held")

    def __init__(self, name: str, stamp: Callable[..., Hashable] | None | Derived,
                 notes: str | None, notes_at: int | None, kept: Kept | None) -> None:
        self.name = name
        self.stamp = stamp
        self.notes = notes
        self.notes_at = notes_at
        self.kept = kept
        self.wrapped: Callable[..., Any] | None = None
        self.run: Run | None = None
        self.held: dict[Hashable, Held] = {}

    def again(self, args: tuple[Any, ...], kwargs: tuple[tuple[str, Any], ...]) -> object:
        """The read's result at this state for `args` and `kwargs`, its notes
        dropped: the held result where it was brought up to date at this
        state, reached as `at_state` reaches it (`reach`)."""
        hit = self.held.get((args, kwargs))
        if hit is not None and hit.state == _state:
            reach(hit)
            return hit.value
        named = dict(kwargs)
        if self.notes is not None and self.notes_at is not None:
            if len(args) >= self.notes_at:
                args = (*args[:self.notes_at], [], *args[self.notes_at:])
            else:
                named[self.notes] = []
        assert self.wrapped is not None
        return self.wrapped(*args, **named)


_reads: dict[str, ReadInfo] = {}
"""Each `state_cache` read of this process, by its name."""


def read_named(name: str) -> ReadInfo:
    """The `state_cache` read `name` gives, its module imported where it is
    not yet."""
    if name not in _reads:
        importlib.import_module(kept_reads.module_of(name))
    return _reads[name]


def trace_of(made: dict[Held, object]) -> tuple[Leaf, ...]:
    """The reads that the held reads `made`, with the result each gave, rest
    on, in the order they were made: a read kept on disk by its version, a
    read kept by its result and a source with no stamp by its result, a
    source with a stamp by that stamp, or by the reads its stamp made, and a
    `DERIVED` read by the reads it made."""
    out: dict[tuple[str, Hashable], Leaf] = {}
    seen: set[Held] = set()

    def visit(h: Held, value: object) -> None:
        if h in seen:
            return
        seen.add(h)
        ident = (h.read.name, h.call)
        if h.read.kept is Kept.DISK and h.version is not None:
            out.setdefault(ident, (By.VERSION, h.read.name, *h.call, h.version))
        elif h.read.kept is not None or (h.source and h.read.stamp is None):
            out.setdefault(ident, (By.VALUE, h.read.name, *h.call, value))
        elif h.source and h.stamped:
            for below, given in h.stamped.items():
                visit(below, given)
        elif h.source:
            out.setdefault(ident, (By.STAMP, h.read.name, *h.call, h.mark))
        else:
            for below, given in h.made.items():
                visit(below, given)
    for h, value in made.items():
        visit(h, value)
    return tuple(out.values())


def holds(leaf: Leaf) -> bool:
    """Whether the read of `leaf` gives at this state the stamp, the result
    or the version it gives, a read that fails counting as not."""
    by, name, args, kwargs, given = leaf
    try:
        if by is By.STAMP:
            return same(stamp_now(name, args, kwargs), given)
        info = read_named(name)
        now = info.again(args, kwargs)
    except Exception:
        return False
    if by is By.VERSION:
        return info.held[(args, kwargs)].version == given
    return same(now, given)


def canonical(value: object) -> object:
    """`value`, an argument of a read, in a form whose `repr` is the same in
    each process: a set's members in order. TypeError for a value of no
    such form."""
    if value is None or isinstance(value, (str, int, float)):
        return value
    if isinstance(value, Path):
        return ("path", str(value))
    if isinstance(value, (tuple, list)):
        return (type(value).__name__, tuple(canonical(v) for v in value))
    if isinstance(value, (set, frozenset)):
        return ("set", tuple(sorted(repr(canonical(v)) for v in value)))
    raise TypeError(f"{value!r} has no canonical form")


def state_cache[**P, R](stamp: Callable[P, Hashable] | None | Derived, *,
                        notes: str | None = None, kept: Kept | None = None) -> Callable[
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

    `kept` gives how a `DERIVED` read stands across processes (`Kept`).

    Each process-life read cache that `state_assembly.read_state` reaches,
    in any module, is a `state_cache`, so the readers of one state see one
    state, and a change between two states reaches the second."""
    def hold(read: Callable[P, R]) -> Callable[P, R]:
        at = None if notes is None else list(inspect.signature(read).parameters).index(notes)
        derived = isinstance(stamp, Derived)
        info = ReadInfo(f"{read.__module__}:{read.__qualname__}", stamp, notes, at, kept)
        held = info.held
        _reads[info.name] = info

        def recalled(key: Call) -> tuple[Record | None, dict[Held, object] | None]:
            """The record the store keeps for `key`, and where each read of
            its trace `holds`, the held reads its check made."""
            store = kept_reads.store()
            if kept is not Kept.DISK or store is None:
                return None, None
            try:
                record: Record | None = store.held(info.name, repr(canonical(key)))
            except TypeError:
                return None, None
            if record is None:
                return None, None
            _frames.append({})
            try:
                good = all(holds(leaf) for leaf in record[0])
            finally:
                made = _frames.pop()
            return record, made if good else None

        def keep(key: Call, made: dict[Held, object], value: object,
                 lines: tuple[str, ...], version: str | None) -> str | None:
            """The version of `value` once it is kept for `key`, `version`
            where one is given, or None where it is not kept."""
            store = kept_reads.store()
            if kept is not Kept.DISK or store is None:
                return None
            try:
                name = repr(canonical(key))
            except TypeError:
                return None
            version = version or uuid.uuid4().hex
            kept_now = store.keep(info.name, name, (trace_of(made), value, lines, version))
            return version if kept_now else None

        def run(key: Call, positional: bool) -> tuple[Any, tuple[str, ...]]:
            args: tuple[Any, ...] = key[0]
            kwargs: dict[str, Any] = dict(key[1])
            hit = held.get(key)
            if hit is not None and hit.state == _state:
                return hit.value, hit.lines
            mark: Hashable = None
            stamped: dict[Held, object] = {}
            if hit is not None and derived:
                if (not hit.marked and not _marking) or held_still(hit.made):
                    hit.state, hit.marked = _state, False
                    return hit.value, hit.lines
            elif not isinstance(stamp, Derived) and stamp is not None:
                _frames.append({})
                try:
                    mark = stamp(*args, **kwargs)
                finally:
                    stamped = _frames.pop()
                if hit is not None and hit.mark == mark:
                    hit.state, hit.stamped = _state, stamped or EMPTY
                    return hit.value, hit.lines
            record, made = recalled(key) if hit is None else (None, None)
            if record is not None and made is not None:
                _, value, kept_lines, version = record
            else:
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
                kept_lines = tuple(lines)
                before = (record[1], record[3]) if record is not None else (
                    (hit.value, hit.version) if hit is not None else None)
                version = keep(key, made, value, kept_lines,
                               before[1] if before is not None and same(value, before[0]) else None)
            if hit is None:
                hit = Held(not derived, info, key, positional)
                held[key] = hit
                _held[hit] = None
            elif value is not hit.value and same(value, hit.value):
                value = hit.value
            elif value is not hit.value and hit.source:
                mark_dependents(hit)
            hit.state, hit.mark, hit.value, hit.lines = _state, mark, value, kept_lines
            hit.stamped, hit.marked, hit.version = stamped or EMPTY, False, version
            hit.rest_on(made if stamp is None or derived else EMPTY)
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
            value, lines = run(key, positional)
            hit = held[key]
            reach(hit)
            if sink is not None:
                sink.extend(lines)
            return value
        info.wrapped = at_state
        info.run = run
        return at_state
    return hold


def same(value: object, held: object) -> bool:
    """Whether `value` equals `held`, a comparison that fails counting as
    not."""
    try:
        return bool(value == held)
    except Exception:
        return False


@state_cache(None)
def stamp_now(name: str, args: tuple[Any, ...],
              kwargs: tuple[tuple[str, Any], ...]) -> Hashable:
    """The stamp, at this state, of the read `name` with `args` and
    `kwargs`, which a trace gives by its stamp (`holds`)."""
    stamp = read_named(name).stamp
    if not callable(stamp):
        raise TypeError(f"{name} has no stamp")
    return stamp(*args, **dict(kwargs))
