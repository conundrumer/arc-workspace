"""The store of the `state_cache` reads kept on disk across processes, in
the file `STORE_NAME` gives under `.cache/` of the main worktree: for each read
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
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from engine import checkout

STORE_NAME = "kept-reads.sqlite"

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


class StoreFile:
    """The SQLite file of a store whose `records` are dropped by
    `mark_used`, over one connection the process holds open until `close`."""

    def __init__(self, path: Path, schema: str) -> None:
        self.path = path
        self.schema = schema
        self.db: sqlite3.Connection | None = None
        self.failed: sqlite3.Error | OSError | None = None

    def connect(self) -> sqlite3.Connection:
        """The connection this process holds open to the store, opened and
        the store created where none is. A store this creates runs in the
        WAL journal mode, so that a process reads while another writes, and
        with incremental auto-vacuum, so that `write` gives back to the
        system the pages of the records `mark_used` drops. Where the store
        did not open, each later call raises what the open raised, so that
        no lookup waits on the lock again. The auto-vacuum mode is set only
        on a store with no tables, since setting it waits on another
        process's write lock."""
        if self.failed is not None:
            raise self.failed
        if self.db is None:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                db = sqlite3.connect(self.path, timeout=LOCK_WAIT_SECONDS)
            except (sqlite3.Error, OSError) as e:
                self.failed = e
                raise
            try:
                if db.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone() is None:
                    db.execute("PRAGMA auto_vacuum = INCREMENTAL")
                db.execute("PRAGMA journal_mode = WAL").fetchall()
                db.executescript(self.schema)
            except sqlite3.Error as e:
                db.close()
                self.failed = e
                raise
            self.db = db
        return self.db

    def close(self) -> None:
        if self.db is not None:
            self.db.close()
            self.db = None

    def put(self, writes: list[tuple[str, list[tuple[Any, ...]]]], used: Iterable[str],
            keep: float) -> None:
        """Run each statement of `writes` over each of its rows, in one
        transaction with `mark_used` of each code of `used`, and give back
        to the system the pages of the records it drops. Where the store
        cannot be written, nothing is."""
        used = sorted(used)
        if not any(rows for _, rows in writes) and not used:
            return
        now = time.time()
        try:
            db = self.connect()
            with db:
                for statement, rows in writes:
                    db.executemany(statement, rows)
                for code in used:
                    mark_used(db, code, now, keep)
            if used:
                db.execute("PRAGMA incremental_vacuum").fetchall()
        except (sqlite3.Error, OSError):
            pass


class Store(StoreFile):
    """The records of one process: those computed since the last `flush`
    are written together by it."""

    def __init__(self, path: Path) -> None:
        super().__init__(path, SCHEMA)
        self.used: set[str] = set()
        self.new: dict[tuple[str, str], bytes] = {}
        self.new_bytes = 0
        self.parses: dict[str, list[Import]] = {}
        """The `import` statements `closure_files` parsed since the last
        write, by the sha256 of the file's bytes: a lookup takes no write
        lock, so `write` writes them with the records."""

    def held(self, read: str, key: str) -> Any | None:
        """The record of `read` with the key `key`, as `keep` was given it,
        or None where the store holds none that reads."""
        found = self.new.get((read, key))
        if found is None:
            code = code_of(module_of(read))
            try:
                row = self.connect().execute(
                    "SELECT record FROM records WHERE code = ? AND read = ? AND key = ?",
                    (code, read, key)).fetchone()
            except (sqlite3.Error, OSError):
                return None
            if row is None:
                return None
            found = row[0]
            self.used.add(code)
        try:
            return pickle.loads(found)
        except UNREADABLE:
            return None

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
        code of each read this process looked up or wrote records of, drop
        the records of code that no process has used for `KEEP_SECONDS`,
        and close the connection."""
        self.write(self.used)
        self.used = set()
        self.close()

    def write(self, used: set[str]) -> None:
        """Write the records and the parses held, and hold none of them
        after. Where it writes parses, drop those written more than
        `KEEP_SECONDS` ago. The writes, the drop and `mark_used` of each code
        of `used` run in one transaction."""
        written = [(code_of(module_of(r)), r, k, v) for (r, k), v in self.new.items()]
        now = time.time()
        parsed = [(d, pickle.dumps(s, pickle.HIGHEST_PROTOCOL), now)
                  for d, s in sorted(self.parses.items())]
        self.new = {}
        self.new_bytes = 0
        self.parses = {}
        writes = [("INSERT OR REPLACE INTO records VALUES (?, ?, ?, ?)", written)]
        if parsed:
            writes += [("INSERT OR REPLACE INTO imports VALUES (?, ?, ?)", parsed),
                       ("DELETE FROM imports WHERE written < ?", [(now - KEEP_SECONDS,)])]
        self.put(writes, used, KEEP_SECONDS)


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
    return imports_in(ast.parse(source))


def imports_in(tree: ast.AST) -> list[Import]:
    """Each `import` statement of the parsed `tree`, at any depth."""
    out: list[Import] = []
    for node in ast.walk(tree):
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
        files = closure_files(module)
        _codes[module] = checkout.files_digest({path: files[path] for path in sorted(files)})
    return _codes[module]


def closure_files(module: str) -> dict[Path, bytes]:
    """The files of the import closure of `module` that `code_of` digests,
    each with its bytes. The parses it makes are held in the open store
    for its next `Store.write`."""
    known: dict[str, list[Import]] = {}
    found: dict[str, list[Import]] = _store.parses if _store is not None else {}
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
    return files


def _imports_db() -> sqlite3.Connection | None:
    """The connection of the open store, where one is open and it opens."""
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
