"""The store of the `state_cache` reads kept on disk across processes, in
`state-reads.sqlite` under `.cache/` of the main worktree: for each read
and its arguments, its result, its `undecided` lines, and the trace of the
reads it rests on, which `state_reads` checks before the result stands.

A record stands only while the code that wrote it is the code that reads
it. A process reads and writes the store only after `open_store`; until
then, and where the process cannot read or write the store, each read is
computed, as with no store.

SQLite writes the records of a call in one transaction, under a lock it
takes across processes, so no reader sees a record half written."""

import pickle
import sqlite3
import time
from pathlib import Path
from typing import Any

from engine import checkout

STORE_NAME = "state-reads.sqlite"

SOURCES = ("scripts/**/*.py", "src/**/*.py", "tools/console/solver_console/**/*.py")
"""The code a record rests on."""

KEEP_SECONDS = 3600
"""How long the records of code that no process has written stay held: a
worktree that runs other code within that time keeps its records, and the
records of code a merge replaced are dropped."""

LOCK_WAIT_SECONDS = 30
"""How long a process waits on the lock another process holds on the
store before it reads or writes nothing of it."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    code TEXT, read TEXT, key TEXT, record BLOB,
    PRIMARY KEY (code, read, key));
CREATE TABLE IF NOT EXISTS codes (code TEXT PRIMARY KEY, used REAL);
"""

UNREADABLE = (pickle.UnpicklingError, EOFError, AttributeError, ImportError,
              IndexError, TypeError, ValueError)
"""What `pickle.loads` raises on a record it cannot read."""


class Store:
    """The records of one process: those of each read, loaded from the
    store at the first lookup of that read, and those computed since the
    last `flush`, written together by it."""

    def __init__(self, path: Path) -> None:
        self.code = checkout.sources_digest(SOURCES)
        self.path = path
        self.loaded: dict[str, dict[str, bytes]] = {}
        self.new: dict[tuple[str, str], bytes] = {}

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=LOCK_WAIT_SECONDS)
        db.executescript(SCHEMA)
        return db

    def held(self, read: str, key: str) -> Any | None:
        """The record of `read` with the key `key`, as `keep` was given it,
        or None where the store holds none that reads."""
        found = self.new.get((read, key))
        if found is None:
            if read not in self.loaded:
                self.loaded[read] = self.load(read)
            found = self.loaded[read].get(key)
        if found is None:
            return None
        try:
            return pickle.loads(found)
        except UNREADABLE:
            return None

    def load(self, read: str) -> dict[str, bytes]:
        try:
            db = self.connect()
            try:
                return dict(db.execute(
                    "SELECT key, record FROM records WHERE code = ? AND read = ?",
                    (self.code, read)).fetchall())
            finally:
                db.close()
        except (sqlite3.Error, OSError):
            return {}

    def keep(self, read: str, key: str, record: object) -> bool:
        """Hold `record` for the next `flush`, where it pickles, and give
        whether it does."""
        try:
            self.new[(read, key)] = pickle.dumps(record, pickle.HIGHEST_PROTOCOL)
            return True
        except (pickle.PicklingError, TypeError, AttributeError, RecursionError):
            self.new.pop((read, key), None)
            return False

    def flush(self) -> None:
        """Write the records held since the last flush, and drop those of
        code that no process has read for `KEEP_SECONDS`."""
        if not self.new:
            return
        now = time.time()
        try:
            db = self.connect()
            try:
                with db:
                    db.executemany("INSERT OR REPLACE INTO records VALUES (?, ?, ?, ?)",
                                   [(self.code, r, k, v) for (r, k), v in self.new.items()])
                    mark_used(db, self.code, now, KEEP_SECONDS)
            finally:
                db.close()
        except (sqlite3.Error, OSError):
            pass
        for (r, k), v in self.new.items():
            self.loaded.setdefault(r, {})[k] = v
        self.new = {}


def mark_used(db: sqlite3.Connection, code: str, now: float, keep: float) -> None:
    """Note in `db`, a store with a `records` and a `codes` table, that
    `code` was used at `now`, and drop the records of each code no process
    has used for `keep` seconds."""
    db.execute("INSERT OR REPLACE INTO codes VALUES (?, ?)", (code, now))
    db.execute("DELETE FROM records WHERE code IN (SELECT code FROM codes WHERE used < ?)",
               (now - keep,))
    db.execute("DELETE FROM codes WHERE used < ?", (now - keep,))


_store: Store | None = None


def open_store(path: Path | None = None) -> None:
    """Read and write the records of this process through the store at
    `path`, `STORE_NAME` under `.cache/` of the main worktree by default."""
    global _store
    _store = Store(path or checkout.caches() / STORE_NAME)


def store() -> Store | None:
    """The store `open_store` opened, or None."""
    return _store


def flush() -> None:
    """`Store.flush` of the open store, where one is open."""
    if _store is not None:
        _store.flush()
