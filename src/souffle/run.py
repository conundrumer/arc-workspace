"""Run a program under the Souffle binary: the program rendered with its
input and output directives, the facts written to files, the result read
back per output relation, and each run stored under the hash of all it
reads."""

import contextlib
import fcntl
import gc
import hashlib
import json
import math
import os
import random
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import zlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import IO

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
from engine.memo import ByIdentity, Once, Recent, hash_file, kept_recent, write_whole
from engine.program import (
    Primitive,
    Grid,
    Program,
    RecordValue,
    RelationName,
    TypeName,
    Row,
    Rows,
    Scope,
    Value,
    cell_place,
)
from souffle.expand import expand
from souffle.grounding import ungrounded
from souffle.index import Hit, Tree, tree_of
from souffle.install import binary_identity, preprocessor_flags, souffle_include
from souffle.render import lines_text, rendered_for_run
from souffle.runkey import included_files, reached
from souffle.text import PREFIX, declared, fact_text
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
CPU_FIELD = "cpu_seconds"
"""The field of a stored record that holds the CPU seconds of its run."""

CACHE_CAP_BYTES = 20 << 30
"""What the stored runs may take on disk. Now and then a write starts a
prune (`prune`) that removes the least recently used runs past it."""
CACHE_PRUNE_EVERY = 200
"""One write in this many prunes."""
CACHE_PRUNE_INTERVAL_SECONDS = 300
"""At most one prune in this interval across processes, which the marker
file's mtime records."""
CACHE_PRUNE_MARKER = ".pruned"
CACHE_PRUNE_LOCK = ".prune.lock"
"""The file a prune holds through `flock`, from its check of the marker
in the writer to the end of the process that removes the runs, so that one
prune at a time runs across processes."""
CACHE_PRUNE_ERRORS = ".prune.err"
"""Where the process of the latest prune writes its stderr, since no
command waits on it."""
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
    """What one Souffle process left: its exit code, what it wrote, and
    the CPU seconds it spent, user and system, with those of the processes
    it waited for."""

    code: int
    stdout: str
    stderr: str
    cpu_seconds: float


def grid_rows(grid: Grid, lead: tuple[int, ...] = ()) -> list[str]:
    """One fact line per cell: the leading columns, the cell's place as its
    distances to the top, bottom, left and right edges, and its color."""
    h = len(grid)
    out = []
    for r, row in enumerate(grid):
        w = len(row)
        for c, color in enumerate(row):
            place = RecordValue(cell_place(r, c, h, w))
            out.append("\t".join(fact_text(v) for v in (*lead, place, color)))
    return out


def fact_lines(value: InputValue) -> list[str]:
    match value:
        case GridInput(grid):
            return grid_rows(grid)
        case IndexedGrids(grids):
            return [line for i, g in enumerate(grids) for line in grid_rows(g, (i,))]
    return ["\t".join(fact_text(v) for v in row) for row in value]


GRID_FILES_HELD = 64
"""How many grids' fact files a process keeps written: the runs of every
group of cases on one input read the same file."""


def fact_file(value: InputValue) -> str:
    """The fact file that gives `value` (`fact_lines`), a grid's written
    once while it is among the last grids written (`_grid_file`)."""
    if isinstance(value, GridInput):
        return _grid_file(value.grid)
    return lines_text(fact_lines(value))


@kept_recent(GRID_FILES_HELD)
def _grid_file(grid: Grid) -> str:
    return lines_text(fact_lines(GridInput(grid)))


FUNCTOR_LIB_NAME = "functors"
"""The name Souffle links the functor library by, after `-l`."""
FUNCTOR_LIB = f"lib{FUNCTOR_LIB_NAME}.dylib"
"""The functor library's file in the functor directory."""
FUNCTOR_SOURCE = "lib_functors.cpp"
"""The functor library's source in the functor directory."""

_BUILDING = threading.Lock()


def build_functors(functor_dir: Path) -> None:
    """Compile the functor library from its source, with the clang++ of the
    SDK xcrun selects, where the library is absent or older than the
    source. The library is written whole, so a run in another process reads
    the old library or the new one."""
    source = functor_dir / FUNCTOR_SOURCE
    lib = functor_dir / FUNCTOR_LIB
    with _BUILDING:
        source_mtime = source.stat().st_mtime_ns
        if lib.exists() and lib.stat().st_mtime_ns >= source_mtime:
            return
        with tempfile.TemporaryDirectory(prefix="functors-") as tmp:
            out = Path(tmp) / FUNCTOR_LIB
            done = subprocess.run(
                ["xcrun", "clang++", "-std=c++17", "-shared", "-fPIC",
                 f"-I{souffle_include()}", f"-Wl,-install_name,{lib}",
                 "-o", str(out), str(source)],
                capture_output=True, text=True)
            if done.returncode != 0:
                raise RuntimeError(f"building {lib} from {source} failed:\n{done.stderr}")
            write_whole(lib, out.read_bytes())


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


STORED_SUFFIX = ".json.z"
"""The end of a stored record's file name in the cache directory."""


def _stored_name(key: str) -> str:
    """The file name of the record stored under `key`."""
    return f"{key}{STORED_SUFFIX}"


def _cpu_limit_key(key: str, cpu: int) -> str:
    """The key of the record that the run under `key` reached a CPU limit
    of `cpu` seconds."""
    return f"{key}-cpu{cpu}"


_STATEMENTS: ByIdentity[Program, tuple[list[tuple[str, int | None]], str]] \
    = ByIdentity()
"""`_statements` of each program while it lives: a group's program runs
on every input."""


_UNGROUNDED: ByIdentity[Program, tuple[UngroundedVariable | None]] = ByIdentity()
"""`_ungrounded` of each program while it lives, held in a tuple, since
None is a value of it."""


def _ungrounded(program: Program) -> UngroundedVariable | None:
    """`souffle.grounding.ungrounded` of `program` with its macros
    expanded, which Souffle would reject, so that no process starts for
    it; computed once per program while it lives."""
    return _UNGROUNDED.compute(program, lambda: (ungrounded(expand(program)),))[0]


def _statements(program: Program) -> tuple[list[tuple[str, int | None]], str]:
    """The lines a run of `program` gives Souffle before its directives,
    each with its origin line (`rendered_for_run` of the program with its
    macros expanded), and their text; computed once per program while it
    lives."""

    def make() -> tuple[list[tuple[str, int | None]], str]:
        lines = rendered_for_run(expand(program))
        return lines, lines_text(t for t, _ in lines)

    return _STATEMENTS.compute(program, make)


class Runner:
    def __init__(self, functor_dir: Path | None, cache_dir: Path | None):
        self.functor_dir = functor_dir
        self.cache_dir = cache_dir
        self._done: Recent[str, Tuples] = Recent(DONE_CAP_ROWS, _size)
        """The results of the runs made, by key, the least recently used
        leaving past `DONE_CAP_ROWS` rows."""
        self._once: Once[str, RunResult] = Once(self._done)
        self._files: dict[str, tuple[tuple[int, int], bytes | None]] = {}

    def flags(self) -> list[str]:
        out = ["-w"]
        if self.functor_dir is not None:
            out += ["-L", str(self.functor_dir), f"-l{FUNCTOR_LIB_NAME}"]
        return out

    def run(self, program: Program, inputs: Mapping[RelationName, InputValue],
            outputs: Sequence[RelationName], limits: Limits,
            caps: Mapping[RelationName, int] | None = None) -> RunResult:
        tree = tree_of(program)
        undefined = tuple(o for o in outputs if tree.resolve(o, Scope(())) is None)
        if undefined:
            return UndefinedOutput(undefined)
        facts: dict[str, str] = {}
        directives: list[str] = []
        for i, (rel, value) in enumerate(sorted(
                inputs.items(), key=lambda kv: (kv[0].instances, kv[0].name))):
            file = f"in{i}.facts"
            facts[file] = fact_file(value)
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
        named = [hit.decl.id for rel in (*inputs, *outputs)
                 if (hit := tree.resolve(rel, Scope(()))) is not None]
        kept = reached(program, named)
        bad = _ungrounded(kept)
        if bad is not None:
            return bad
        lines, statements = _statements(kept)
        text = statements + lines_text(directives)
        if self.functor_dir is not None:
            build_functors(self.functor_dir)
        key = self._key(program, text, facts)
        # The same run being made in another thread is read once it ends.
        return self._once.get(key, lambda: self._result(
            key, text, facts, limits, lines, directives, outputs, tree, printed_as, capped))

    def _result(self, key: str, text: str, facts: dict[str, str],
                limits: Limits, lines: list[tuple[str, int | None]],
                directives: list[str], outputs: Sequence[RelationName],
                tree: Tree, printed_as: Mapping[RelationName, str],
                capped: Mapping[RelationName, int]) -> RunResult:
        """The run under `key`, stored or made now, read and held."""
        ran = self._cached(key, text, facts, limits)
        if isinstance(ran, CpuLimit | WallLimit):
            return ran
        if ran.code != 0:
            return _failure(ran, [o for _, o in lines] + [None] * len(directives))
        got = Tuples(_Printed(ran.stdout, outputs, tree, printed_as, capped),
                     ran.cpu_seconds)
        self._done.put(key, got)
        return got

    # cache

    def _key(self, program: Program, text: str, facts: dict[str, str]) -> str:
        """The hash of all a run reads: the text Souffle reads, the
        program's statements (`rendered_for_run`) with the declarations its
        units reach alone (`reached`) and the input and output directives
        after them, each included file's path and bytes,
        the functor library, the fact files and the flags."""
        h = hashlib.sha256()
        h.update(binary_identity())
        h.update(b"\0" + text.encode())
        for path in included_files(program):
            hash_file(h, path, self._file(path))
        if self.functor_dir is not None:
            lib = str(self.functor_dir / FUNCTOR_LIB)
            hash_file(h, lib, self._file(lib))
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
        path = self.cache_dir / _stored_name(key)
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
        with contextlib.suppress(OSError):
            write_whole(self.cache_dir / _stored_name(key), data)
        if random.randrange(CACHE_PRUNE_EVERY) == 0:
            prune(self.cache_dir, CACHE_CAP_BYTES)

    def _cached(self, key: str, text: str, facts: dict[str, str],
                limits: Limits) -> Ran | CpuLimit | WallLimit:
        """The stored run under `key`, else the run of `text`. A record
        stored with no CPU seconds is no record, so its run is made again
        once."""
        cpu = max(1, math.ceil(limits.cpu_seconds))
        hit = self._read(key)
        if hit is not None and CPU_FIELD in hit:
            return Ran(hit["code"], hit["stdout"], hit["stderr"], hit[CPU_FIELD])
        over = _cpu_limit_key(key, cpu)
        if self._read(over) is not None:
            return CpuLimit(limits.cpu_seconds)
        ran = self._process(text, facts, cpu, limits.wall_seconds)
        if isinstance(ran, CpuLimit):
            self._write(over, {"cpu": cpu})
            return CpuLimit(limits.cpu_seconds)
        if isinstance(ran, Ran) and ran.code >= 0:
            self._write(key, {"code": ran.code, "stdout": ran.stdout, "stderr": ran.stderr,
                              CPU_FIELD: ran.cpu_seconds})
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
                ended = _measured(
                    ["/bin/sh", "-c", f'ulimit -t {cpu}; exec "$0" "$@"', *cmd],
                    wall, d)
            if ended is None:
                return WallLimit(wall)
            code, stdout, stderr, cpu_seconds = ended
            if code == -signal.SIGXCPU:
                return CpuLimit(cpu)
            stderr = stderr.replace(str(d / PROGRAM_NAME), PROGRAM_NAME)
            return Ran(code, stdout, stderr, cpu_seconds)


def _measured(argv: list[str], wall: float, cwd: Path
              ) -> tuple[int, str, str, float] | None:
    """The process of `argv` run to its end with no input: its exit code,
    negative for the signal that ended it, its stdout, its stderr and the
    CPU seconds `os.wait4` gives it, user and system; None where it was
    still writing at `wall` seconds and was killed. The process is reaped
    here alone, so the kill reaches no other process that took its id."""
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, cwd=cwd)
    assert proc.stdout is not None and proc.stderr is not None
    texts: dict[str, str] = {}

    def read(name: str, stream: IO[str]) -> None:
        texts[name] = stream.read()

    readers = [threading.Thread(target=read, args=(n, f), daemon=True)
               for n, f in (("stdout", proc.stdout), ("stderr", proc.stderr))]
    for t in readers:
        t.start()
    deadline = time.monotonic() + wall
    for t in readers:
        t.join(max(0.0, deadline - time.monotonic()))
    killed = any(t.is_alive() for t in readers)
    if killed:
        proc.kill()
    _pid, status, usage = os.wait4(proc.pid, 0)
    proc.returncode = os.waitstatus_to_exitcode(status)
    for t in readers:
        t.join()
    proc.stdout.close()
    proc.stderr.close()
    if killed:
        return None
    return (proc.returncode, texts["stdout"], texts["stderr"],
            usage.ru_utime + usage.ru_stime)


_EVICT = ("import sys; sys.path.insert(0, sys.argv[3]); from pathlib import Path; "
          "from souffle.run import evict; evict(Path(sys.argv[1]), int(sys.argv[2]))")
"""The program of a prune's process, given the cache directory, the cap,
and the directory this module's package stands in, so that it runs this
code."""


def prune(cache_dir: Path, cap: int) -> None:
    """Start a prune of `cache_dir` down to `cap` bytes (`evict`), where no
    prune runs and none started in the interval, and return without waiting
    on it. The prune runs in a process of its own, in a session of its own,
    so that it runs to its end after the writer exits, and holds
    `CACHE_PRUNE_LOCK` until it ends."""
    with open(cache_dir / CACHE_PRUNE_LOCK, "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        marker = cache_dir / CACHE_PRUNE_MARKER
        try:
            if time.time() - marker.stat().st_mtime < CACHE_PRUNE_INTERVAL_SECONDS:
                return
        except FileNotFoundError:
            pass
        marker.touch()
        with open(cache_dir / CACHE_PRUNE_ERRORS, "w") as err:
            subprocess.run(["/bin/sh", "-c", '"$@" &', "sh", sys.executable, "-c", _EVICT,
                            str(cache_dir), str(cap), str(Path(__file__).resolve().parents[1])],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=err,
                           pass_fds=(lock.fileno(),), start_new_session=True,
                           check=True)


def evict(cache_dir: Path, cap: int) -> None:
    """Remove the least recently used runs under `cache_dir` past `cap`
    bytes, and temp files their writers left."""
    now = time.time()
    entries: list[tuple[float, int, Path]] = []
    for path in cache_dir.iterdir():
        try:
            st = path.stat()
        except OSError:
            continue
        if path.suffix == ".tmp":
            if now - st.st_mtime > CACHE_STALE_TEMP_SECONDS:
                path.unlink(missing_ok=True)
        elif path.name.endswith(STORED_SUFFIX):
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
    if source[at] == PREFIX:
        m = re.compile(re.escape(PREFIX) + r"[A-Za-z_]\w*").match(source, at)
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
    return {name: [line.split("\t") for line in _lines(stdout, span)]
            for name, span in _block_spans(stdout).items()}


def _block_spans(stdout: str) -> dict[str, tuple[int, int]]:
    """The relations Souffle printed, each as the span of `stdout` its
    rows' lines stand in: a line of `-`, the name, the header, a line of
    `=`, the rows, a line of `=`. A block is found by its lines alone, and
    the rows are not split into lines here."""
    out: dict[str, tuple[int, int]] = {}
    at, n = 0, len(stdout)
    while at < n:
        ends: list[int] = []
        pos = at
        for _ in range(4):
            e = stdout.find("\n", pos)
            if e < 0:
                break
            ends.append(e)
            pos = e + 1
        if len(ends) < 3:
            break
        if len(ends) == 3:
            ends.append(n)
        dashes, name_end, header_end, equals_end = ends
        if not _marks_only(stdout[at:dashes], "-") \
                or not _marks_only(stdout[header_end + 1:equals_end], "="):
            break
        start = equals_end + 1
        end = _equals_line(stdout, start)
        if end is None:
            break
        out[stdout[dashes + 1:name_end]] = (start, end)
        at = stdout.find("\n", end)
        at = n if at < 0 else at + 1
    return out


def _equals_line(stdout: str, start: int) -> int | None:
    """Where the first line at or after `start`, a line's start, that is
    made of `=` alone begins."""
    at = start
    while at < len(stdout):
        if stdout.startswith("=", at):
            end = stdout.find("\n", at)
            end = len(stdout) if end < 0 else end
            if _marks_only(stdout[at:end], "="):
                return at
        nxt = stdout.find("\n=", at)
        if nxt < 0:
            return None
        at = nxt + 1
    return None


def _lines(stdout: str, span: tuple[int, int]) -> list[str]:
    """The lines of `stdout` in `span`, which ends after a line's end."""
    start, end = span
    return stdout[start:end - 1].split("\n") if end > start else []


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
        self._spans: dict[str, tuple[int, int]] | None = None
        self._sets: dict[str, frozenset[str]] = {}
        self._types: dict[RelationName, tuple[TypeName, ...]] = {}
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
        return all((self._caps.get(r) == other._caps.get(r)
                    and self._text(r) == other._text(r))
                   or self._set(r) == other._set(r) for r in self._outputs)

    def _column_types(self, rel: RelationName) -> tuple[TypeName, ...]:
        with self._lock:
            got = self._types.get(rel)
            if got is None:
                got = self._types[rel] = tuple(
                    c.type for c in _output_decl(self._tree, rel).decl.columns)
            return got

    def _span(self, rel: RelationName) -> tuple[int, int]:
        """Where the printed rows of `rel` stand in the text, all of them
        where the run printed more than its cap plus one."""
        if self._spans is None:
            self._spans = _block_spans(self._stdout)
        return self._spans.get(self._printed_as.get(rel, rel.text), (0, 0))

    def _text(self, rel: RelationName) -> str:
        """The printed rows of `rel` as one text: equal texts hold equal
        sets of rows, and the rows of one set print in one order."""
        start, end = self._span(rel)
        return self._stdout[start:end]

    def _block(self, rel: RelationName) -> list[str]:
        """The printed rows of `rel`, as lines: at most its cap plus one."""
        lines = _lines(self._stdout, self._span(rel))
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
        rows = _rows_of(rel, self._block(rel), self._tree)
        # The rows hold no reference cycle, and a result holds many of
        # them: the collector leaves the objects that stand now out of its
        # passes, which would otherwise walk every row held.
        gc.freeze()
        return rows


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
    cols = declared(zip(xs, types, strict=True))
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


def _output_decl(tree: Tree, rel: RelationName) -> Hit:
    """The declaration an output relation of a run resolves to from the
    top level; the run printed it, so it resolves."""
    hit = tree.resolve(rel, Scope(()))
    assert hit is not None, "an output of a run resolves"
    return hit


def _top_level_types(rel: RelationName, tree: Tree) -> list[TypeName] | None:
    """The name at the top level of each column type of `rel`: a type an
    instance on the way down declares, or one of its components extends,
    is named through that instance, `inst.T`. None where a column's type
    resolves elsewhere, as through an instance its text names."""
    hit = tree.resolve(rel, Scope(()))
    if hit is None:
        return None
    out: list[TypeName] = []
    for column in hit.decl.columns:
        try:
            decl, place, _start = tree.resolve_type(column.type, hit.place, hit.start)
        except ValueError:
            return None
        if isinstance(decl, Primitive):
            out.append(TypeName((), decl.value))
            continue
        if len(place) > len(hit.place) \
                or any(a is not b for a, b in zip(place, hit.place, strict=False)):
            return None
        out.append(TypeName(rel.instances[:len(place)], decl.name))
    return out


_READERS: ByIdentity[Tree, dict[RelationName, list[dict[str, Value]]]] \
    = ByIdentity()
"""The values read from each printed text, per output relation and
column, for each tree while it lives: the programs one operation derives
from another share their tree, so the runs of a group on every input read
a column's texts through one reader."""


def _readers(rel: RelationName, tree: Tree, width: int
             ) -> list[dict[str, Value]]:
    """The one reader of each column of `rel` under `tree`: each text it
    has read, with its value."""
    return _READERS.keyed(tree, rel, lambda: [{} for _ in range(width)])


def _read_text(seen: dict[str, Value], text: str, type_name: TypeName,
               tree: Tree, hit: Hit) -> Value:
    """The value of `text` in a column of type `type_name` of the
    relation `hit` declares, through the column's reader `seen`
    (`_readers`), which reads it where it has not yet. Raises ValueError
    where the type cannot read it."""
    got = seen.get(text, _UNREAD)
    if got is _UNREAD:
        got = seen[text] = printed(text, type_name, tree, hit.place,
                                   hit.start)
    return got


def _rows_of(rel: RelationName, lines: list[str], tree: Tree) -> Rows:
    """The rows of `rel` its printed lines give, each value read by its
    column's type through the column's reader (`_readers`), which reads
    each distinct text once. Raises ValueError, naming the relation and
    the row, for a value the declared types cannot read."""
    hit = _output_decl(tree, rel)
    cols = [c.type for c in hit.decl.columns]
    read = _readers(rel, tree, len(cols))
    if cols and lines:
        # Column by column: the rows share the value read from a text.
        try:
            columns = list(zip(*[line.split("\t") for line in lines],
                               strict=True))
            if len(columns) == len(cols):
                values = []
                for column, c, seen in zip(columns, cols, read, strict=True):
                    for t in dict.fromkeys(column):
                        _read_text(seen, t, c, tree, hit)
                    values.append(list(map(seen.__getitem__, column)))
                return tuple(zip(*values, strict=True))
        except ValueError:
            pass
    # Row by row, where a row is not of the relation's width or a value
    # is not read, so that the error names the first such row.
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
                row.append(_read_text(seen, t, c, tree, hit))
            rows.append(tuple(row))
        except ValueError as err:
            raise ValueError(f"{rel.text}: row {chr(9).join(texts)!r}: {err}") from None
    return tuple(rows)
