"""The store of the `state_cache` reads kept on disk across processes, in
the file `STORE_NAME` gives under `.cache/` of the main worktree: for each read
and its arguments, its result, its `undecided` lines, and the trace of the
reads it rests on, which `state_reads` checks before the result stands. The
folds of `transcript_folds` are kept in it as well, each as a read of the
module of its step.

A record of a read stands only while the code the read's module can run
is the code that wrote it: the files of that module's import closure
(`code_of`). A process reads and writes the store only after `open_store`; until
then, and where the process cannot read or write the store, each read is
computed, as with no store.

SQLite writes each batch of a call's records in one transaction, under a
lock it takes across processes, so no reader sees a record half written; a
reader can see some of a call's records before the rest."""

import ast
import copyreg
import hashlib
import io
import importlib.util
import pickle
import sqlite3
import sys
import time
import weakref
from collections.abc import Iterable
from pathlib import Path, PosixPath, WindowsPath
from typing import Any

from engine import checkout

STORE_NAME = "kept-reads.sqlite"

KEEP_SECONDS = 3600
"""How long the records of code that no process has written stay held: a
worktree that runs other code within that time keeps its records, and the
records of code a merge replaced are dropped."""

LOCK_WAIT_SECONDS = 1
"""How long a process waits on the lock another process holds on the
store before it writes nothing of it. A read does not wait on it."""

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


class Unavailable(BaseException):
    """A required store failed; escape the cache's failed-read handlers."""


class HeldPath(type(Path())):
    __slots__ = ("__weakref__",)


_paths: weakref.WeakValueDictionary[str, Path] = weakref.WeakValueDictionary()
"""The one `Path` of each text that the records this process read, and the
arguments of its reads, give."""


def held_path(text: str) -> Path:
    """The one `Path` of `text` among the records this process reads and
    the arguments its reads take, so that a path a record or a read's
    argument gives is the very object of the same path each other one
    gives, a lookup by it compares no text, and its text is made once."""
    found = _paths.get(text)
    if found is None:
        found = _paths[text] = HeldPath(text)
    return found


class PathText(str):
    """The text of a `Path` that a read takes as an argument, as the key of
    a held read gives it in `state_reads`: a record gives it as the `Path`
    `held_path` gives."""
    __slots__ = ()


def reduce_path(path: Path | PathText) -> tuple[Any, tuple[str]]:
    return held_path, (str(path),)


PICKLED = {**copyreg.dispatch_table, PosixPath: reduce_path, WindowsPath: reduce_path,
           PathText: reduce_path, HeldPath: reduce_path}
"""How a record pickles: each path as `held_path` of its text."""


def pickled(record: object) -> bytes:
    """`record` pickled, each path in it as `held_path` gives it again."""
    out = io.BytesIO()
    pickler = pickle.Pickler(out, pickle.HIGHEST_PROTOCOL)
    pickler.dispatch_table = PICKLED
    pickler.dump(record)
    return out.getvalue()


class StoreFile:
    """The SQLite file of a store whose `records` are dropped by
    `mark_used`, over one connection the process holds open until `close`."""

    def __init__(self, path: Path, schema: str) -> None:
        self.path = path
        self.schema = schema
        self.db: sqlite3.Connection | None = None
        self.failed: sqlite3.Error | OSError | None = None
        self.write_error: sqlite3.Error | OSError | None = None

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
            keep: float) -> bool:
        """Run each statement of `writes` over each of its rows, in one
        transaction with `mark_used` of each code of `used`, and give back
        to the system the pages of the records it drops. Where the store
        cannot be written, nothing is."""
        used = sorted(used)
        if not any(rows for _, rows in writes) and not used:
            return True
        now = time.time()
        try:
            db = self.connect()
            with db:
                for statement, rows in writes:
                    db.executemany(statement, rows)
                for code in used:
                    mark_used(db, code, now, keep)
        except (sqlite3.Error, OSError) as exc:
            self.write_error = exc
            return False
        self.write_error = None
        if used:
            try:
                db.execute("PRAGMA incremental_vacuum").fetchall()
            except sqlite3.Error:
                pass  # The records have already committed.
        return True


class Store(StoreFile):
    """The records of one process: those computed since the last `flush`
    are written together by it."""

    def __init__(self, path: Path, *, required: bool = False) -> None:
        super().__init__(path, SCHEMA)
        self.required = required
        self.used: set[str] = set()
        self.new: dict[tuple[str, str], bytes] = {}
        self.new_bytes = 0
        self.write_at = WRITE_BYTES
        """The bytes of records held at which `keep` next writes them."""
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
            except (sqlite3.Error, OSError) as exc:
                if self.required:
                    raise Unavailable(f"kept-read store {self.path} cannot be read: {exc}") from exc
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
            data = pickled(record)
        except (pickle.PicklingError, TypeError, AttributeError, RecursionError):
            self.new.pop((read, key), None)
            return False
        self.new[(read, key)] = data
        self.new_bytes += len(data)
        self.used.add(code_of(module_of(read)))
        if self.new_bytes > self.write_at and (self.write_error is None or self.locked()):
            if self.write(set()):
                self.write_at = WRITE_BYTES
            elif self.locked():
                # A lock is transient: the records stay held, and the next batch tries again.
                self.write_at = self.new_bytes + WRITE_BYTES
            elif self.required:
                raise Unavailable(f"kept-read store {self.path} cannot preserve completed reads: "
                                  f"{self.write_error}")
        return True

    def flush(self) -> bool:
        """Write the records held since the last flush, note as used the
        code of each read this process looked up or wrote records of, drop
        the records of code that no process has used for `KEEP_SECONDS`,
        and close the connection."""
        written = self.write(self.used)
        if written:
            self.used = set()
            self.write_at = WRITE_BYTES
        self.close()
        self.failed = None  # A later flush can retry a transient open/lock failure.
        return written

    def locked(self) -> bool:
        """Whether the last failed write failed on a lock another process
        held; the records stay held, so a later flush can write them."""
        error = self.write_error
        return (isinstance(error, sqlite3.OperationalError)
                and ("locked" in str(error) or "busy" in str(error)))

    def write(self, used: set[str]) -> bool:
        """Write the records and the parses held, and hold none of them
        after. Where it writes parses, drop those written more than
        `KEEP_SECONDS` ago. The writes, the drop and `mark_used` of each code
        of `used` run in one transaction."""
        written = [(code_of(module_of(r)), r, k, v) for (r, k), v in self.new.items()]
        now = time.time()
        parsed = [(d, pickle.dumps(s, pickle.HIGHEST_PROTOCOL), now)
                  for d, s in sorted(self.parses.items())]
        writes = [("INSERT OR REPLACE INTO records VALUES (?, ?, ?, ?)", written)]
        if parsed:
            writes += [("INSERT OR REPLACE INTO imports VALUES (?, ?, ?)", parsed),
                       ("DELETE FROM imports WHERE written < ?", [(now - KEEP_SECONDS,)])]
        if not self.put(writes, used, KEEP_SECONDS):
            return False
        self.new = {}
        self.new_bytes = 0
        self.parses = {}
        return True


def mark_used(db: sqlite3.Connection, code: str, now: float, keep: float) -> None:
    """Note in `db`, a store with a `records` and a `codes` table, that
    `code` was used at `now`, and drop the records of each code no process
    has used for `keep` seconds."""
    db.execute("INSERT OR REPLACE INTO codes VALUES (?, ?)", (code, now))
    db.execute("DELETE FROM records WHERE code IN (SELECT code FROM codes WHERE used < ?)",
               (now - keep,))
    db.execute("DELETE FROM codes WHERE used < ?", (now - keep,))


def module_of(read: str) -> str:
    """The module of a persistent read's name, before its first colon."""
    return read.split(":", 1)[0]


type Import = tuple[int, str, tuple[str, ...]]
"""One `import` statement of a file: its level of relative import, the
module it names, and, for `from ... import`, the names it takes."""


def imports_of(source: bytes) -> list[Import]:
    """Each `import` statement of `source`, at any depth."""
    return imports_in(ast.parse(source))


def imports_in(tree: ast.AST) -> list[Import]:
    """Each `import` statement of the parsed `tree`, at any depth."""
    return [statement for node in ast.walk(tree) for statement in import_statements(node)]


def import_statements(node: ast.AST) -> list[Import]:
    """The `import` statements `node` makes: one per name of an `import`,
    one for a `from` import, and none for any other node."""
    match node:
        case ast.Import(names=aliases):
            return [(0, a.name, ()) for a in aliases]
        case ast.ImportFrom(level=level, module=base, names=aliases):
            return [(level, base or "", tuple(a.name for a in aliases))]
        case _:
            return []


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
_code_files: dict[Path, bytes] | None = None


def pin_code(module: str) -> None:
    """Keep the source of this interpreter's reads across a mid-call merge.

    Fresh retirement checks still read disk. A read first reached after
    the merge must not label an old interpreter's result with the new code.
    """
    global _code_files
    _code_files = closure_files(module)
    _codes.clear()


def code_of(module: str) -> str:
    """The sha256, in hex, of the path and bytes of each file of the import
    closure of `module`: its own file, and each file of a module that an
    `import` statement of a closure file names, with its parent packages,
    where `module_file` gives one. The `import` statements of each file are
    kept in the open store by the sha256 of its bytes, so a file is parsed
    only once its bytes change, or once `KEEP_SECONDS` pass from the parse
    that wrote them."""
    if module not in _codes:
        files = closure_files(module, _code_files)
        _codes[module] = checkout.files_digest({path: files[path] for path in sorted(files)})
    return _codes[module]


def fresh_code(module: str) -> str:
    """The current import closure identity, with no process-lifetime lookup."""
    files = closure_files(module)
    return checkout.files_digest({path: files[path] for path in sorted(files)})


def closure_files(module: str, pinned: dict[Path, bytes] | None = None) -> dict[Path, bytes]:
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
        if path is None or path in files:
            continue
        if (pinned is None or path not in pinned) and not path.is_file():
            continue
        data = files[path] = (pinned[path] if pinned is not None and path in pinned
                              else path.read_bytes())
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


def open_store(path: Path | None = None, *, required: bool = False) -> None:
    """Read and write the records of this process through the store at
    `path`, `STORE_NAME` under `.cache/` of the main worktree by default."""
    global _store
    _store = Store(path or checkout.caches() / STORE_NAME, required=required)


def store() -> Store | None:
    """The store `open_store` opened, or None."""
    return _store


def flush() -> bool:
    """`Store.flush` of the open store, where one is open."""
    if _store is not None:
        return _store.flush()
    return True
