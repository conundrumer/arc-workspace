"""The store of the `state_cache` reads kept on disk across processes, in
`state-reads.sqlite` under `.cache/` of the main worktree: for each read
and its arguments, its result, its `undecided` lines, and the trace of the
reads it rests on, which `state_reads` checks before the result stands.

A record of a read stands only while the code the read's module can run
is the code that wrote it: the files of that module's import closure
(`code_of`). A process reads and writes the store only after `open_store`; until
then, and where the process cannot read or write the store, each read is
computed, as with no store.

SQLite writes each batch of a call's records in one transaction, under a
lock it takes across processes, so no reader sees a record half written; a
reader can see some of a call's records before the rest."""

import ast
import hashlib
import importlib.util
import pickle
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

from engine import checkout

STORE_NAME = "state-reads.sqlite"

KEEP_SECONDS = 3600
"""How long the records of code that no process has written stay held: a
worktree that runs other code within that time keeps its records, and the
records of code a merge replaced are dropped."""

LOCK_WAIT_SECONDS = 30
"""How long a process waits on the lock another process holds on the
store before it reads or writes nothing of it."""

WRITE_BYTES = 16 * 1024 * 1024
"""How many bytes of records a process holds before it writes them, so
that a call holds at most that much of what it writes."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    code TEXT, read TEXT, key TEXT, record BLOB,
    PRIMARY KEY (code, read, key));
CREATE TABLE IF NOT EXISTS codes (code TEXT PRIMARY KEY, used REAL);
CREATE TABLE IF NOT EXISTS imports (file TEXT PRIMARY KEY, names BLOB, written REAL);
"""

UNREADABLE = (pickle.UnpicklingError, EOFError, AttributeError, ImportError,
              IndexError, TypeError, ValueError)
"""What `pickle.loads` raises on a record it cannot read."""


class Store:
    """The records of one process: those of each read, loaded from the
    store at the first lookup of that read, and those computed since the
    last `flush`, written together by it."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.used: set[str] = set()
        self.loaded: dict[str, dict[str, bytes]] = {}
        self.new: dict[tuple[str, str], bytes] = {}
        self.new_bytes = 0

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
                if self.loaded[read]:
                    self.used.add(code_of(module_of(read)))
            found = self.loaded[read].pop(key, None)
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
                    (code_of(module_of(read)), read)).fetchall())
            finally:
                db.close()
        except (sqlite3.Error, OSError):
            return {}

    def keep(self, read: str, key: str, record: object) -> bool:
        """Hold `record` for the next write, where it pickles, and give
        whether it does."""
        try:
            data = pickle.dumps(record, pickle.HIGHEST_PROTOCOL)
        except (pickle.PicklingError, TypeError, AttributeError, RecursionError):
            self.new.pop((read, key), None)
            return False
        self.new[(read, key)] = data
        self.new_bytes += len(data)
        self.used.add(code_of(module_of(read)))
        if self.new_bytes > WRITE_BYTES:
            self.write(set())
        return True

    def flush(self) -> None:
        """Write the records held since the last flush, note as used the
        code of each read this process loaded or wrote records of, and drop
        the records of code that no process has used for `KEEP_SECONDS`."""
        self.write(self.used)
        self.used = set()

    def write(self, used: set[str]) -> None:
        """Write the records held, in one transaction with `mark_used` of
        each code of `used`, and hold none of them after."""
        written = [(code_of(module_of(r)), r, k, v) for (r, k), v in self.new.items()]
        self.new = {}
        self.new_bytes = 0
        if not written and not used:
            return
        now = time.time()
        try:
            db = self.connect()
            try:
                with db:
                    db.executemany("INSERT OR REPLACE INTO records VALUES (?, ?, ?, ?)",
                                   written)
                    for code in sorted(used):
                        mark_used(db, code, now, KEEP_SECONDS)
            finally:
                db.close()
        except (sqlite3.Error, OSError):
            pass


def mark_used(db: sqlite3.Connection, code: str, now: float, keep: float) -> None:
    """Note in `db`, a store with a `records` and a `codes` table, that
    `code` was used at `now`, and drop the records of each code no process
    has used for `keep` seconds."""
    db.execute("INSERT OR REPLACE INTO codes VALUES (?, ?)", (code, now))
    db.execute("DELETE FROM records WHERE code IN (SELECT code FROM codes WHERE used < ?)",
               (now - keep,))
    db.execute("DELETE FROM codes WHERE used < ?", (now - keep,))


def module_of(read: str) -> str:
    """The module of `read`, a `state_reads.ReadInfo.name`."""
    return read.split(":", 1)[0]


type Import = tuple[int, str, tuple[str, ...]]
"""One `import` statement of a file: its level of relative import, the
module it names, and, for `from ... import`, the names it takes."""


def imports_of(source: bytes) -> list[Import]:
    """Each `import` statement of `source`, at any depth."""
    out: list[Import] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            out.extend((0, a.name, ()) for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            out.append((node.level, node.module or "", tuple(a.name for a in node.names)))
    return out


def module_file(name: str) -> Path | None:
    """The file of module `name` as this process resolves it, where it lies
    under `checkout.ROOT` and outside its `.venv`."""
    loaded = sys.modules.get(name)
    origin = getattr(loaded, "__file__", None) if loaded is not None else None
    if loaded is None:
        try:
            spec = importlib.util.find_spec(name)
        except (ImportError, ValueError):
            return None
        origin = spec.origin if spec is not None else None
    if origin is None:
        return None
    path = Path(origin).resolve()
    if not path.is_relative_to(checkout.ROOT) or path.is_relative_to(checkout.ROOT / ".venv"):
        return None
    return path


def named_modules(module: str, path: Path, statement: Import) -> list[str]:
    """The modules `statement` of `module`, whose file is `path`, can
    import, each parent package with it."""
    level, base, names = statement
    if level:
        package = module if path.name == "__init__.py" else module.rpartition(".")[0]
        try:
            base = importlib.util.resolve_name("." * level + base, package)
        except (ImportError, ValueError):
            return []
    named = [base, *(f"{base}.{n}" for n in names if n != "*")]
    parts = base.split(".")
    return [".".join(parts[:i]) for i in range(1, len(parts))] + named


_codes: dict[str, str] = {}


def code_of(module: str) -> str:
    """The sha256, in hex, of the path and bytes of each file of the import
    closure of `module`: its own file, and each file of a module that an
    `import` statement of a closure file names, with its parent packages,
    where `module_file` gives one. The `import` statements of each file are
    kept in the open store by the sha256 of its bytes, so a file is parsed
    only once its bytes change, or once `KEEP_SECONDS` pass from the parse
    that wrote them."""
    if module not in _codes:
        _codes[module] = _closure_digest(module)
    return _codes[module]


def _closure_digest(module: str) -> str:
    known: dict[str, list[Import]] = {}
    found: dict[str, list[Import]] = {}
    db = _imports_db()
    files: dict[Path, bytes] = {}
    todo = named_modules(module, Path(), (0, module, ()))
    seen: set[str] = set()
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        path = module_file(name)
        if path is None or path in files or not path.is_file():
            continue
        data = files[path] = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        statements = known.get(digest) or found.get(digest)
        if statements is None and db is not None:
            row = db.execute("SELECT names FROM imports WHERE file = ?", (digest,)).fetchone()
            if row is not None:
                try:
                    statements = known[digest] = pickle.loads(row[0])
                except UNREADABLE:
                    statements = None
        if statements is None:
            try:
                statements = found[digest] = imports_of(data)
            except (SyntaxError, ValueError):
                statements = []
        for statement in statements:
            todo.extend(named_modules(name, path, statement))
    if db is not None:
        try:
            if found:
                now = time.time()
                with db:
                    db.executemany("INSERT OR REPLACE INTO imports VALUES (?, ?, ?)",
                                   [(d, pickle.dumps(s, pickle.HIGHEST_PROTOCOL), now)
                                    for d, s in found.items()])
                    db.execute("DELETE FROM imports WHERE written < ?", (now - KEEP_SECONDS,))
        except sqlite3.Error:
            pass
        db.close()
    return checkout.files_digest({path: files[path] for path in sorted(files)})


def _imports_db() -> sqlite3.Connection | None:
    """A connection to the open store, where one is open and it opens."""
    if _store is None:
        return None
    try:
        return _store.connect()
    except (sqlite3.Error, OSError):
        return None


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
