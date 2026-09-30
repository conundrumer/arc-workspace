"""Run a program under the Souffle binary: the program rendered with its
input and output directives, the facts written to files, the result read
back per output relation, and each run stored under the hash of all it
reads."""

import bisect
import contextlib
import hashlib
import json
import math
import os
import random
import re
import signal
import subprocess
import tempfile
import threading
import time
import zlib
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from engine.engine import (
    CompileError,
    CpuLimit,
    Exited,
    GridInput,
    IndexedGrids,
    InputValue,
    Limits,
    RunResult,
    Tuples,
    UndefinedOutput,
    UngroundedVariable,
    WallLimit,
)
from engine.program import Grid, Program, RelationName, Row, Rows, Scope, Value, value_text
from souffle.expand import expand
from souffle.index import Tree, held_index
from souffle.render import rendered_for_run
from souffle.runkey import included_files, program_digest
from souffle.values import printed

FIRST_ERROR_RE = re.compile(r"^Error:", re.M)
ERROR_RE = re.compile(r"^Error: (?P<what>.*?)(?: in file (?P<file>\S+) at line (?P<line>\d+))?$")
"""The line that opens one error Souffle reports: what is wrong, and the
place where it has one."""
CARET_RE = re.compile(r"^-*\^-*$")
"""The line under an error's echoed source line, its `^` under the column
the error points at."""
UNGROUNDED_VARIABLE_RE = re.compile(r"^Ungrounded variable (?P<var>\S+)$")
PROGRAM_NAME = "program.dl"

CACHE_CAP_BYTES = 20 << 30
"""What the stored runs may take on disk. Now and then a write removes the
least recently used runs past it."""
CACHE_PRUNE_EVERY = 200
"""One write in this many prunes."""
CACHE_PRUNE_INTERVAL_SECONDS = 300
"""At most one prune in this interval across processes, which the marker
file's mtime records."""
CACHE_PRUNE_MARKER = ".pruned"
CACHE_STALE_TEMP_SECONDS = 3600
"""A temp file older than this lost its writer before the rename."""
DONE_CAP_ROWS = 2_000_000
"""The most rows a runner holds in memory across the results it read, so
that a run made again in the same process is not read and parsed again;
a result's printed lines count as its rows."""


def _size(got: Tuples) -> int:
    """The lines of the text a result reads its rows from, which bound its
    rows."""
    held = got.relations
    return held._stdout.count("\n") if isinstance(held, _Printed) \
        else sum(len(r) for r in held.values())


@dataclass(frozen=True)
class Ran:
    """What one Souffle process left: its exit code and what it wrote."""

    code: int
    stdout: str
    stderr: str


def grid_rows(grid: Grid, lead: tuple[int, ...] = ()) -> list[str]:
    """One fact line per cell: the leading columns, the cell's place as its
    distances to the top, bottom, left and right edges, and its color."""
    h = len(grid)
    out = []
    for r, row in enumerate(grid):
        w = len(row)
        for c, color in enumerate(row):
            place = f"[{r}, {h - 1 - r}, {c}, {w - 1 - c}]"
            out.append("\t".join([*(str(x) for x in lead), place, str(color)]))
    return out


def fact_lines(value: InputValue) -> list[str]:
    match value:
        case GridInput(grid):
            return grid_rows(grid)
        case IndexedGrids(grids):
            return [line for i, g in enumerate(grids) for line in grid_rows(g, (i,))]
    return ["\t".join(value_text(v) for v in row) for row in value]


@cache
def souffle_version() -> str:
    try:
        out = subprocess.run(["souffle", "--version"], capture_output=True, text=True,
                             timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    return next((ln for ln in out.splitlines() if "Version" in ln), out)


@cache
def preprocessor_flags() -> tuple[str, ...]:
    """The preprocessor Souffle calls, by its full path, where xcrun finds
    clang; Souffle's default otherwise."""
    try:
        clang = subprocess.run(["xcrun", "-f", "clang"], capture_output=True, text=True,
                               timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ()
    if not clang or not os.access(clang, os.X_OK):
        return ()
    return (f"--preprocessor={clang} -x c -E",)


_RUNNING: list[threading.BoundedSemaphore] = []
_RUNNING_LOCK = threading.Lock()


@cache
def performance_cores() -> int | None:
    """The machine's performance cores, where its cores are of two kinds;
    None otherwise."""
    try:
        out = subprocess.run(["sysctl", "-n", "hw.perflevel0.logicalcpu"],
                             capture_output=True, text=True, timeout=10)
        return int(out.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _running() -> threading.BoundedSemaphore:
    """The Souffle processes one process has going at once, one per
    performance core however many threads start them: a run on an
    efficiency core spends more CPU seconds for the same work, and the CPU
    limit counts them."""
    with _RUNNING_LOCK:
        if not _RUNNING:
            _RUNNING.append(threading.BoundedSemaphore(
                performance_cores() or os.cpu_count() or 1))
        return _RUNNING[0]


class Runner:
    def __init__(self, functor_dir: Path | None, cache_dir: Path | None):
        self.functor_dir = functor_dir
        self.cache_dir = cache_dir
        self._lock = threading.Lock()
        self._done: OrderedDict[str, Tuples] = OrderedDict()
        self._done_rows = 0
        self._files: dict[str, tuple[tuple[int, int], bytes | None]] = {}

    def flags(self) -> list[str]:
        out = ["-w"]
        if self.functor_dir is not None:
            out += ["-L", str(self.functor_dir), "-lfunctors"]
        return out

    def run(self, program: Program, inputs: Mapping[RelationName, InputValue],
            outputs: Sequence[RelationName], limits: Limits,
            caps: Mapping[RelationName, int] | None = None) -> RunResult:
        held = held_index(program)
        tree = held.tree if held is not None else Tree(program)
        undefined = tuple(o for o in outputs if tree.resolve(o, Scope(())) is None)
        if undefined:
            return UndefinedOutput(undefined)
        facts: dict[str, str] = {}
        directives: list[str] = []
        for i, (rel, value) in enumerate(sorted(inputs.items(), key=lambda kv: kv[0].text)):
            file = f"in{i}.facts"
            facts[file] = "".join(line + "\n" for line in fact_lines(value))
            directives.append(f'.input {rel.text}(IO=file, filename="{file}")')
        capped = {} if not caps else \
            {rel: caps[rel] for rel in dict.fromkeys(outputs) if rel in caps}
        printed_as: dict[RelationName, str] = {}
        taken = {*tree.decls.get((), {}), *tree.inits.get((), {})}
        for rel in outputs:
            if rel in printed_as:
                continue
            copy = None if rel not in capped else _capped_copy(
                rel, capped[rel], tree, taken)
            if copy is None:
                directives.append(f".output {rel.text}")
            else:
                printed_as[rel], lines_of_copy = copy
                directives += lines_of_copy
        key = self._key(program, directives, facts)
        with self._lock:
            done = self._done.get(key)
            if done is not None:
                self._done.move_to_end(key)
                return done
        lines: list[tuple[str, int | None]] = []

        def text() -> str:
            if not lines:
                lines.extend(rendered_for_run(expand(program)))
                lines.extend((d, None) for d in directives)
            return "".join(t + "\n" for t, _ in lines)

        ran = self._cached(key, text, facts, limits)
        if isinstance(ran, CpuLimit | WallLimit):
            return ran
        if ran.code != 0:
            text()
            return _failure(ran, [o for _, o in lines])
        got = Tuples(_Printed(ran.stdout, outputs, tree, printed_as, capped))
        self._keep(key, got)
        return got

    def _keep(self, key: str, got: Tuples) -> None:
        """Holds `got` as the result of the run under `key`, the least
        recently used results leaving past `DONE_CAP_ROWS` rows."""
        rows = _size(got)
        if rows > DONE_CAP_ROWS:
            return
        with self._lock:
            if key in self._done:
                return
            self._done[key] = got
            self._done_rows += rows
            while self._done_rows > DONE_CAP_ROWS:
                _k, old = self._done.popitem(last=False)
                self._done_rows -= _size(old)

    # cache

    def _key(self, program: Program, directives: list[str],
             facts: dict[str, str]) -> str:
        """The hash of all a run reads: the program's digest
        (`souffle.runkey`), which the text it renders to determines, the
        input and output directives that follow that text, each included
        file's path and bytes, the functor library, the fact files and
        the flags."""
        h = hashlib.sha256()
        h.update(souffle_version().encode())
        h.update(b"\0" + program_digest(program))
        for d in directives:
            h.update(b"\0" + d.encode())
        for path in included_files(program):
            body = self._file(path)
            if body is not None:
                h.update(b"\0" + path.encode() + b"\0")
                h.update(body)
            else:
                h.update(b"\0" + path.encode())
        if self.functor_dir is not None:
            lib = self._file(str(self.functor_dir / "libfunctors.dylib"))
            if lib is not None:
                h.update(b"\0")
                h.update(lib)
        for name in sorted(facts):
            h.update(b"\0" + name.encode() + b"\0" + facts[name].encode())
        h.update(b"\0" + " ".join(self.flags()).encode())
        return h.hexdigest()

    def _file(self, path: str) -> bytes | None:
        """The bytes of the file at `path`, None where it cannot be read;
        read again only where its size or mtime changed."""
        try:
            st = os.stat(path)
        except OSError:
            return None
        stamp = (st.st_mtime_ns, st.st_size)
        held = self._files.get(path)
        if held is not None and held[0] == stamp:
            return held[1]
        try:
            body: bytes | None = Path(path).read_bytes()
        except OSError:
            body = None
        self._files[path] = (stamp, body)
        return body

    def _read(self, key: str) -> dict | None:
        if self.cache_dir is None:
            return None
        path = self.cache_dir / f"{key}.json.z"
        try:
            record = json.loads(zlib.decompress(path.read_bytes()))
        except (OSError, ValueError, zlib.error):
            return None
        with contextlib.suppress(OSError):
            os.utime(path)
        return record

    def _write(self, key: str, record: dict) -> None:
        if self.cache_dir is None:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        data = zlib.compress(json.dumps(record).encode(), 6)
        fd, tmp = tempfile.mkstemp(dir=self.cache_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp, self.cache_dir / f"{key}.json.z")
        except OSError:
            Path(tmp).unlink(missing_ok=True)
        if random.randrange(CACHE_PRUNE_EVERY) == 0:
            prune(self.cache_dir, CACHE_CAP_BYTES)

    def _cached(self, key: str, text: Callable[[], str], facts: dict[str, str],
                limits: Limits) -> Ran | CpuLimit | WallLimit:
        """The stored run under `key`, else the run of `text()`, which
        renders the program only here."""
        cpu = max(1, math.ceil(limits.cpu_seconds))
        hit = self._read(key)
        if hit is not None:
            return Ran(hit["code"], hit["stdout"], hit["stderr"])
        if self._read(f"{key}-cpu{cpu}") is not None:
            return CpuLimit(limits.cpu_seconds)
        ran = self._process(text(), facts, cpu, limits.wall_seconds)
        if isinstance(ran, CpuLimit):
            self._write(f"{key}-cpu{cpu}", {"cpu": cpu})
            return CpuLimit(limits.cpu_seconds)
        if isinstance(ran, Ran) and ran.code >= 0:
            self._write(key, {"code": ran.code, "stdout": ran.stdout, "stderr": ran.stderr})
        if isinstance(ran, WallLimit):
            return WallLimit(limits.wall_seconds)
        return ran

    def _process(self, text: str, facts: dict[str, str], cpu: int,
                 wall: float) -> Ran | CpuLimit | WallLimit:
        with tempfile.TemporaryDirectory(prefix="souffle-") as tmp:
            d = Path(tmp)
            (d / PROGRAM_NAME).write_text(text)
            for name, body in facts.items():
                (d / name).write_text(body)
            cmd = ["souffle", "-D-", *self.flags(), *preprocessor_flags(),
                   "-F", str(d), str(d / PROGRAM_NAME)]
            with _running():
                try:
                    result = subprocess.run(
                        ["/bin/sh", "-c", f'ulimit -t {cpu}; exec "$0" "$@"', *cmd],
                        input="", capture_output=True, text=True, timeout=wall, cwd=d)
                except subprocess.TimeoutExpired:
                    return WallLimit(wall)
            if result.returncode == -signal.SIGXCPU:
                return CpuLimit(cpu)
            stderr = result.stderr.replace(str(d / PROGRAM_NAME), PROGRAM_NAME)
            return Ran(result.returncode, result.stdout, stderr)


def prune(cache_dir: Path, cap: int, now: float | None = None) -> None:
    """Remove the least recently used runs under `cache_dir` past `cap`
    bytes, and temp files their writers left, at most once per interval
    across processes."""
    now = time.time() if now is None else now
    marker = cache_dir / CACHE_PRUNE_MARKER
    try:
        if now - marker.stat().st_mtime < CACHE_PRUNE_INTERVAL_SECONDS:
            return
    except OSError:
        pass
    marker.touch()
    entries: list[tuple[float, int, Path]] = []
    for path in cache_dir.iterdir():
        try:
            st = path.stat()
        except OSError:
            continue
        if path.suffix == ".tmp":
            if now - st.st_mtime > CACHE_STALE_TEMP_SECONDS:
                path.unlink(missing_ok=True)
        elif path.name.endswith(".json.z"):
            entries.append((st.st_mtime, st.st_size, path))
    total = sum(size for _, size, _ in entries)
    for _, size, path in sorted(entries):
        if total <= cap:
            break
        path.unlink(missing_ok=True)
        total -= size


@dataclass(frozen=True)
class _Error:
    """One error Souffle reports: what is wrong, its place in the rendered
    program where it has one, and the text its caret points at."""

    what: str
    file: str | None
    line: int | None
    pointed: str | None


def _errors(stderr: str) -> list[_Error]:
    lines = stderr.splitlines()
    out: list[_Error] = []
    for i, text in enumerate(lines):
        m = ERROR_RE.match(text)
        if m is None:
            continue
        pointed = None
        if i + 2 < len(lines) and CARET_RE.match(lines[i + 2]):
            pointed = _term_at(lines[i + 1], lines[i + 2].index("^"))
        out.append(_Error(m["what"], m["file"], int(m["line"]) if m["line"] else None,
                          pointed))
    return out


def _term_at(source: str, at: int) -> str | None:
    """The term that starts at column `at` of `source`: a record or a
    constructor with its bracketed arguments, or a name."""
    if at >= len(source):
        return None
    end = at
    if source[at] == "$":
        m = re.compile(r"\$[A-Za-z_]\w*").match(source, at)
        if m is None:
            return None
        end = m.end()
        if end < len(source) and source[end] == "(":
            end = _closing(source, end)
    elif source[at] == "[":
        end = _closing(source, at)
    else:
        m = re.compile(r"[A-Za-z_]\w*").match(source, at)
        if m is None:
            return None
        end = m.end()
    return source[at:end] if end > at else None


def _closing(source: str, at: int) -> int:
    """The end of the bracketed text that opens at `at`; `at` where it does
    not close on the line."""
    depth = 0
    for j in range(at, len(source)):
        if source[j] in "([":
            depth += 1
        elif source[j] in ")]":
            depth -= 1
            if depth == 0:
                return j + 1
    return at


def _failure(ran: Ran, origins: list[int | None]) -> RunResult:
    """The failure Souffle's report states. Where any error it reports is
    an ungrounded form (a variable, a record, an ADT branch, a lattice
    variable, or an argument an aggregate grounds used outside it), the
    failure is `UngroundedVariable`: the first error that names an
    ungrounded variable, else the first ungrounded form with the term its
    caret points at. Any other error is a `CompileError` at the first
    error's place, and a failure with no error line is `Exited`."""
    m = FIRST_ERROR_RE.search(ran.stderr)
    if m is None:
        return Exited(ran.code, ran.stderr)

    def origin(error: _Error) -> int | None:
        if error.file != PROGRAM_NAME or error.line is None:
            return None
        return origins[error.line - 1] if 0 < error.line <= len(origins) else None

    errors = _errors(ran.stderr)
    ungrounded = [e for e in errors if "ungrounded" in e.what.lower()]
    named = [(e, v) for e in ungrounded if (v := UNGROUNDED_VARIABLE_RE.match(e.what))]
    if named:
        error, var = named[0]
        return UngroundedVariable(var["var"], origin(error))
    if ungrounded:
        error = ungrounded[0]
        return UngroundedVariable(error.pointed or error.what, origin(error))
    message = ran.stderr[m.start():].rstrip("\n")
    return CompileError(origin(errors[0]) if errors else None, message)


def _marks_only(line: str, mark: str) -> bool:
    return bool(line) and line == mark * len(line)


def _blocks(stdout: str) -> dict[str, list[list[str]]]:
    """The relations Souffle printed, each as its rows of column texts."""
    return {name: [line.split("\t") for line in lines]
            for name, lines in _block_lines(stdout).items()}


def _block_lines(stdout: str) -> dict[str, list[str]]:
    """The relations Souffle printed, each as its rows' lines: a line of
    `-`, the name, the header, a line of `=`, the rows, a line of `=`."""
    lines = stdout.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    # The lines made of `=` alone, by index: the rows between two of them
    # are read without a test per line.
    marks: list[int] = []
    at = line = 0
    for m in _EQUALS_LINE.finditer(stdout):
        line += stdout.count("\n", at, m.start())
        at = m.start()
        if line < len(lines):
            marks.append(line)
    out: dict[str, list[str]] = {}
    i = 0
    while i + 3 < len(lines):
        k = bisect.bisect_left(marks, i + 4)
        end = marks[k] if k < len(marks) else None
        if end is None or not _marks_only(lines[i], "-") or not _marks_only(lines[i + 3], "="):
            break
        out[lines[i + 1]] = lines[i + 4:end]
        i = end + 1
    return out


_EQUALS_LINE = re.compile(r"^=+$", re.M)


_UNREAD: Value = object()  # type: ignore[assignment]
"""A text no column has read yet."""


class _Printed(Mapping[RelationName, Rows]):
    """The rows of each output relation of one run, each value read by its
    column's type from the text Souffle printed, on the first read of the
    relation. Reading a relation raises ValueError, naming the relation
    and the row, for a value the declared types cannot read.

    Two results compare as sets of rows: equal where they hold the same
    relations, each declared with the same column types and holding the
    same set of printed rows, which reads no value, since equal texts
    under equal types read as equal values. Equal results may hold their
    rows in different orders."""

    def __init__(self, stdout: str, outputs: Sequence[RelationName],
                 tree: Tree, printed_as: Mapping[RelationName, str],
                 caps: Mapping[RelationName, int]) -> None:
        self._stdout = stdout
        self._outputs = tuple(dict.fromkeys(outputs))
        self._tree = tree
        self._printed_as = dict(printed_as)
        self._caps = dict(caps)
        self._lines: dict[str, list[str]] | None = None
        self._sets: dict[str, frozenset[str]] = {}
        self._types: dict[RelationName, tuple[str, ...]] = {}
        self._rows: dict[RelationName, Rows] = {}
        self._lock = threading.Lock()

    def __getitem__(self, rel: RelationName) -> Rows:
        if rel not in self._outputs:
            raise KeyError(rel)
        with self._lock:
            got = self._rows.get(rel)
            if got is None:
                got = self._rows[rel] = self._read(rel)
            return got

    def __iter__(self):
        return iter(self._outputs)

    def __len__(self) -> int:
        return len(self._outputs)

    def __contains__(self, rel: object) -> bool:
        return rel in self._outputs

    __hash__ = None  # type: ignore[assignment]

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        if not isinstance(other, Mapping):
            return NotImplemented
        if not isinstance(other, _Printed):
            return set(self) == set(other) and all(
                frozenset(self[r]) == frozenset(other[r]) for r in self)
        if self._outputs != other._outputs or any(
                self._column_types(r) != other._column_types(r)
                for r in self._outputs):
            return False
        if self._stdout == other._stdout and self._printed_as == other._printed_as \
                and self._caps == other._caps:
            return True
        return all(self._set(r) == other._set(r) for r in self._outputs)

    def _column_types(self, rel: RelationName) -> tuple[str, ...]:
        with self._lock:
            got = self._types.get(rel)
            if got is None:
                hit = self._tree.resolve(rel, Scope(()))
                assert hit is not None
                got = self._types[rel] = tuple(c.type for c in hit.decl.columns)
            return got

    def _block(self, rel: RelationName) -> list[str]:
        """The printed rows of `rel`, as lines: at most its cap plus one."""
        if self._lines is None:
            self._lines = _block_lines(self._stdout)
        lines = self._lines.get(self._printed_as.get(rel, rel.text), [])
        cap = self._caps.get(rel)
        return lines if cap is None else lines[:cap + 1]

    def _set(self, rel: RelationName) -> frozenset[str]:
        got = self._sets.get(rel.text)
        if got is None:
            with self._lock:
                block = self._block(rel)
            got = self._sets[rel.text] = frozenset(block)
        return got

    def _read(self, rel: RelationName) -> Rows:
        return _rows_of(rel, self._block(rel), self._tree)


def _capped_copy(rel: RelationName, cap: int, tree: Tree, taken: set[str]
                 ) -> tuple[str, list[str]] | None:
    """The name of a top-level relation that holds at most `cap` plus one
    rows of `rel`, all of them where `rel` has at most `cap`, and the
    lines that declare, feed and print it: a copy of `rel` that numbers
    its rows (`autoinc`), and the rows numbered up to `cap` past the least
    number. The one query that numbers the copy draws its numbers in a
    row from the counter every `autoinc` of the run shares. Souffle prints
    no row of `rel` past those. None where a column's type has no name at
    the top level, and for a relation with no column; the run then prints
    the whole relation."""
    types = _top_level_types(rel, tree)
    if not types:
        return None
    k = 0
    while {f"_cap{k}", f"_cap{k}_n", f"_cap{k}_lo"} & taken:
        k += 1
    name, numbered, least = f"_cap{k}", f"_cap{k}_n", f"_cap{k}_lo"
    taken.update((name, numbered, least))
    xs = [f"x{i}" for i in range(len(types))]
    cols = ", ".join(f"{x}: {t}" for x, t in zip(xs, types, strict=True))
    args = ", ".join(xs)
    blanks = ", ".join("_" for _ in xs)
    return name, [
        f".decl {numbered}(n: unsigned, {cols})",
        f"{numbered}(autoinc(), {args}) :- {rel.text}({args}).",
        f".decl {least}(n: unsigned)",
        f"{least}(m) :- m = min n : {{ {numbered}(n, {blanks}) }}.",
        f".decl {name}({cols})",
        f"{name}({args}) :- {numbered}(n, {args}), {least}(m), n <= m + {cap}.",
        f".output {name}",
    ]


def _top_level_types(rel: RelationName, tree: Tree) -> list[str] | None:
    """The name at the top level of each column type of `rel`: a type an
    instance on the way down declares, or one of its components extends,
    is named through that instance, `inst.T`. None where a column's type
    resolves elsewhere, as through an instance its text names."""
    hit = tree.resolve(rel, Scope(()))
    if hit is None:
        return None
    out: list[str] = []
    for column in hit.decl.columns:
        try:
            decl, place, _start = tree.resolve_type(column.type, hit.place, hit.start)
        except ValueError:
            return None
        if isinstance(decl, str):
            out.append(decl)
            continue
        if len(place) > len(hit.place) \
                or any(a is not b for a, b in zip(place, hit.place, strict=False)):
            return None
        out.append(".".join((*rel.instances[:len(place)], decl.name)))
    return out


def _rows_of(rel: RelationName, lines: list[str], tree: Tree) -> Rows:
    """The rows of `rel` its printed lines give, each value read by its
    column's type. Raises ValueError, naming the relation and the row, for
    a value the declared types cannot read."""
    hit = tree.resolve(rel, Scope(()))
    assert hit is not None
    cols = [c.type for c in hit.decl.columns]
    # Per column, each text already read: a column's values repeat
    # across rows, and reading one resolves its type at each level.
    read: list[dict[str, Value]] = [{} for _ in cols]
    width = len(cols)
    rows: list[Row] = []
    for line in lines:
        texts = line.split("\t")
        if not cols and texts in ([""], ["()"]):
            # Souffle prints a relation with no columns as `()` for its
            # one row.
            rows.append(())
            continue
        if len(texts) == width:
            try:
                rows.append(tuple([seen[t] for seen, t in zip(read, texts)]))
                continue
            except KeyError:
                pass
        try:
            if len(texts) != width:
                raise ValueError(f"{len(texts)} columns, and the declaration {width}")
            row: list[Value] = []
            for t, c, seen in zip(texts, cols, read, strict=True):
                v = seen.get(t, _UNREAD)
                if v is _UNREAD:
                    v = seen[t] = printed(t, c, tree, hit.place, hit.start)
                row.append(v)
            rows.append(tuple(row))
        except ValueError as err:
            raise ValueError(f"{rel.text}: row {chr(9).join(texts)!r}: {err}") from None
    return tuple(rows)
