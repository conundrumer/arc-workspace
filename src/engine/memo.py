"""Values computed once and kept: per object while the object lives, once
per key however many threads ask, the most recently used under a cap, a
file written whole or not at all, a value read from a file or made and
kept there, and a file's part in the hash a kept
value is keyed on, and whether a file is being read for it. Every package
may import it."""

import functools
import hashlib
import os
import tempfile
import threading
import weakref
from collections import OrderedDict
from collections.abc import Callable, Hashable, Iterable
from typing import Protocol
from pathlib import Path


class ByIdentity[K, V]:
    """A value kept for each object, by the object's identity, while the
    object lives: an object of the engine's types is immutable, so what is
    computed from one holds as long as it does."""

    def __init__(self) -> None:
        self._held: dict[int, tuple[weakref.ref[K], V]] = {}
        self._lock = threading.RLock()

    def get(self, obj: K) -> V | None:
        """The value kept for `obj`, None where none is."""
        with self._lock:
            held = self._held.get(id(obj))
        return held[1] if held is not None and held[0]() is obj else None

    def put(self, obj: K, value: V) -> V:
        """Keeps `value` for `obj` in place of any value kept for it, and
        returns it."""
        key = id(obj)

        def drop(ref: weakref.ref[K], key: int = key) -> None:
            with self._lock:
                held = self._held.get(key)
                if held is not None and held[0] is ref:
                    del self._held[key]

        with self._lock:
            self._held[key] = (weakref.ref(obj, drop), value)
        return value

    def setdefault(self, obj: K, value: V) -> V:
        """The value kept for `obj`, else `value`, kept for it."""
        with self._lock:
            got = self.get(obj)
            return got if got is not None else self.put(obj, value)

    def compute(self, obj: K, make: Callable[[], V]) -> V:
        """The value kept for `obj`, else the one `make` gives, kept for
        it."""
        got = self.get(obj)
        return got if got is not None else self.put(obj, make())

    def keyed[J, W](self: "ByIdentity[K, dict[J, W]]", obj: K, key: J,
                    make: Callable[[], W]) -> W:
        """The value kept for `obj` and `key`, else the one `make` gives,
        kept for them: one value per key for each object while it
        lives, a value of None among them."""
        memo = self.setdefault(obj, {})
        if key in memo:
            return memo[key]
        return memo.setdefault(key, make())

    def guarded[G, W](self: "ByIdentity[K, tuple[G, W]]", obj: K, guard: G,
                      make: Callable[[], W]) -> W:
        """The value kept for `obj` where it was kept with a guard equal
        to `guard`, else the one `make` gives, kept for `obj` with
        `guard`: a value computed from `obj` and from what `guard`
        holds."""
        held = self.get(obj)
        if held is not None and (held[0] is guard or held[0] == guard):
            return held[1]
        return self.put(obj, (guard, make()))[1]


class Lookup[K, V](Protocol):
    """What a value is looked up in: a dict, or a `Recent`."""

    def get(self, key: K, /) -> V | None: ...


class Once[K: Hashable, V]:
    """A value per key read from `store`, made once however many threads
    ask for it where `store` lacks it: one thread makes it while the others
    wait, then read it."""

    def __init__(self, store: Lookup[K, V]) -> None:
        self.store = store
        self._lock = threading.Lock()
        self._busy: dict[K, threading.Lock] = {}

    def get(self, key: K, make: Callable[[], V]) -> V:
        """What `store` holds under `key`, else what `make` gives; `make`
        keeps in `store` what it makes, where a later call should find
        it."""
        with self._lock:
            busy = self._busy.setdefault(key, threading.Lock())
        with busy:
            got = self.store.get(key)
            if got is None:
                got = make()
            with self._lock:
                self._busy.pop(key, None)
            return got


class Recent[K: Hashable, V]:
    """Values by key, the least recently used leaving once the weights of
    those kept pass `cap`; a value whose own weight passes `cap` is not
    kept."""

    def __init__(self, cap: int,
                 weight: Callable[[V], int] = lambda _v: 1) -> None:
        self.cap = cap
        self.weight = weight
        self._held: OrderedDict[K, V] = OrderedDict()
        self._total = 0
        self._lock = threading.Lock()

    def get(self, key: K) -> V | None:
        """The value under `key`, now the most recently used; None where
        none is."""
        with self._lock:
            got = self._held.get(key)
            if got is not None:
                self._held.move_to_end(key)
            return got

    def put(self, key: K, value: V) -> None:
        """Keeps `value` under `key`, where no value is kept under it."""
        w = self.weight(value)
        if w > self.cap:
            return
        with self._lock:
            if key in self._held:
                return
            self._held[key] = value
            self._total += w
            while self._total > self.cap:
                _k, old = self._held.popitem(last=False)
                self._total -= self.weight(old)


def kept_recent[K: Hashable, V](cap: int
                                ) -> Callable[[Callable[[K], V]],
                                              Callable[[K], V]]:
    """A function of one argument whose results are kept for the `cap`
    arguments most recently used (`Recent`)."""

    def wrap(fn: Callable[[K], V]) -> Callable[[K], V]:
        held: Recent[K, V] = Recent(cap)

        @functools.wraps(fn)
        def call(key: K) -> V:
            got = held.get(key)
            if got is None:
                got = fn(key)
                held.put(key, got)
            return got

        return call

    return wrap


_UMASK = os.umask(0)
os.umask(_UMASK)
"""The process's file mode mask, read at import."""


def write_whole(path: Path, data: bytes) -> None:
    """Writes `data` to a file beside `path` that then replaces it, so a
    write that stops part way leaves `path` as it was. The file gets the
    mode a file the process creates gets."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.",
                               suffix=".tmp")
    try:
        os.fchmod(fd, 0o666 & ~_UMASK)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def read_or_make[V](path: Path, decode: Callable[[bytes], V | None],
                    encode: Callable[[V], bytes],
                    make: Callable[[], tuple[V, bool]]) -> V:
    """The value `decode` gives of the file at `path`; where there is no
    file, or `decode` gives None, the value `make` gives, written whole to
    `path` where `make` gives that it is kept."""
    try:
        kept = decode(path.read_bytes())
    except FileNotFoundError:
        kept = None
    if kept is not None:
        return kept
    value, keep = make()
    if keep:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_whole(path, encode(value))
    return value


def hash_file(h: "hashlib._Hash", path: str, body: bytes | None) -> None:
    """Adds the file at `path` to `h`: its path, then its bytes `body`, or
    its path alone where `body` is None, as the file cannot be read."""
    h.update(b"\0" + path.encode() + b"\0")
    h.update(b"\0" if body is None else b"\1" + body)


class _Keying(threading.local):
    reading = False


_KEYING = _Keying()


def keying() -> bool:
    """Whether the calling thread is reading a file in `hash_files`. Such a
    read goes into a key's hash alone."""
    return _KEYING.reading


def hash_files(h: "hashlib._Hash", files: Iterable[tuple[str, Path]]) -> None:
    """Adds to `h` each file of `files`, a name with the path it is read
    from, in the order `files` gives them, as `hash_file` adds it, with no
    bytes where it cannot be read."""
    for name, path in files:
        _KEYING.reading = True
        try:
            body: bytes | None = path.read_bytes()
        except OSError:
            body = None
        finally:
            _KEYING.reading = False
        hash_file(h, name, body)
