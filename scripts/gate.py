"""The gate: the gate commands on their gate stems, compared with the
accepted outputs under `tests/gate/accepted/` and the machine's accepted
times.

    uv run python scripts/gate.py <out-dir> [cmd ...]
    uv run python scripts/gate.py --outputs-only [--affected | --record-deps] [--coverage] <out-dir> [cmd ...]
    uv run python scripts/gate.py --accept [--replace] <out-dir> [cmd ...]

A command runs on the stems its `Command.stems` gives. The stems run in
parallel. On each stem, the commands run in the order given, which is the
order a pass runs them, sharing one run cache from empty: this is the cold
pass. Then the same sequence runs again with every result cached: this is
the warm pass.

A command's outputs are its output, in `<key>.txt`, the witness file, in
`<key>.wit.json`, where its subcommand is in `WITNESS_FILE_SUBS`, and its
exit code, in `<key>.rc`, with `<key>` its name and stem joined by `-`. A
command stopped at `TIME_LIMIT` has the exit code `TIMEOUT_RC`.

The cold pass is compared with the accepted outputs and the accepted times,
so a command's exit code is compared with the accepted one.
A `DIFF` line names an output file that differs, a `SLOW` line a time over
1.25 times the accepted time plus 1 s, and a `NOTIME` line a command with no
accepted time. A command's time depends on what the commands before it
cached, so times compare only when the full sequence runs. The warm pass is
compared with the cold pass: a `DIFF` line ending in `warm` names an output
file that differs between them. The last line counts the lines of each kind.

`LIMITS` in `src/cli/common.py` gives a case run a CPU limit and a wall
limit, and under load the wall limit is reached first. The gate sets the
wall limit to `TIME_LIMIT`, through `WALL_LIMIT_ENV`, so that a command is
stopped before any case run of it reaches the wall limit. A command's
outputs then depend on the load it runs under only where the load stretches
it to `TIME_LIMIT`, or a sweep to its own time limit, and either gives a
`DIFF` line.

In a timed run, a cold command holds the lock file exclusively and a warm
command holds it shared, so a cold command never shares the machine with
another command of a timed run, of this checkout or of another worktree of
the repository. An `--outputs-only` run takes no lock.

`--outputs-only` runs the cold pass alone, and compares its outputs alone:
it prints `DIFF` lines, and no `SLOW` or `NOTIME` line, and writes no
times to `new/`. A gate run shares the machine with whatever else runs on
it, and its times measure that load as much as the change, so times are
judged by one timed gate run on `master` after a batch of merges, with no
other agent running. A `SLOW` line of that run is filed as a `delay` issue,
and blocks no merge.

`--coverage` traces each cold command: it records the lines of each Python
file under `src/` and `scripts/` the command runs, through coverage.py, and
the other files of the checkout it opens to read and the directories it
lists, through an audit hook. `<out-dir>/gate/cov/` then holds each
command's coverage data, which `coverage combine` reads, and
`<out-dir>/gate/deps/` each command's dependencies.

`--record-deps` traces every command as `--coverage` does, and writes their
dependencies, with the `HEAD` commit, to the dependency record
(`deps_file`). It runs on a checkout with no change to a tracked file
against `HEAD`, so that the lines it records are the lines of that commit.

`--affected` runs only the commands the changes since the recorded commit
can affect, as `affects` decides, and every command where no dependency
record stands. Its first line names the record and counts the commands it
runs.

Every command reads the solver files from `tests/gate/solvers/` and the
witness files from `tests/gate/witnesses/`. A command that takes a witness
file is given one at `<out-dir>/gate/wit/cur/`, copied from
`tests/gate/frozen/` before the command runs. In an output, the path of
`<out-dir>/gate/` is written as `<out>/gate/`, and a time the command prints
is dropped.

`<out-dir>/gate/new/` holds the cold pass's outputs and times,
`<out-dir>/gate/new/warm/` the warm pass's outputs, `<out-dir>/gate/times.txt`
both passes' wall times, and `<out-dir>/gate/log.txt` the lines printed
above the last line.

The accepted times depend on the machine, so every worktree of the
repository reads them from one file: the gitignored
`tests/gate/accepted/times.json` of the main worktree, the directory that
holds the repository's common git directory. The dependency record is
read and written in the main worktree too. The accepted outputs are read
from the worktree the gate runs in.

`--accepted` names an accepted directory other than `tests/gate/accepted/`.
Its accepted outputs and its accepted times, in its own `times.json`, are
read in place of those above.

`--accept` takes an `<out-dir>` with no `gate/` under it, runs the gate, and
then writes each cold time and output as accepted where no accepted time or
output of its name stands, and over one that stands only with `--replace`,
so that an accepting run after a regression keeps the faster times. `--accept` and `--outputs-only` are
not given together.

Exit status: without `--accept`, 1 when the last line counts a line of any
kind, and 0 otherwise; with `--accept`, 0 once the accepted times and
outputs are written.
"""

import argparse
import ast
import contextlib
import fcntl
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

import coverage

from cli.common import WALL_LIMIT_ENV
from controlled_markdown import mctx
from engine import checkout
from engine.memo import write_whole

GATE = checkout.ROOT / "tests" / "gate"
SOLVERS = GATE / "solvers"
WITNESSES = GATE / "witnesses"
FROZEN = GATE / "frozen"
INPUTS = GATE / "inputs"
ACCEPTED = GATE / "accepted"
TIME_EXT = ".time"
"""The extension of the file in `new/` holding a cold run's time."""
TIMES_FILE = "times.json"
"""The accepted times, a JSON object from `<name>-<stem>` to seconds
(`times_file`)."""
DEPS_FILE = checkout.scratch().relative_to(checkout.ROOT) / "gate" / "deps.json"
"""The dependency record, under the main worktree (`deps_file`)."""

STEMS = ("ac0c5833", "a934301b", "abbfd121")
"""The stems every command runs on, but for those that read a grid input."""
RECORD_STEM = "ac0c5833"
"""The stem the commands that read a grid input run on, whose witness file
the inputs fit."""
LIB_STEMS = ("6e453dd6", "33067df9", "97a05b5b", "6d1d5c90", "99306f82", "6165ea8f",
             "ca8de6ea", "f8b3ba0a", "ff28f65a", "409aa875", "aa62e3f4", "50846271",
             "89565ca0", "696d4842")
"""The stems `run` runs on besides `STEMS`, whose solvers together use every
component of the lib that no solver of `STEMS` uses."""

TIME_LIMIT = 560
KILL_AFTER = 5
TIMEOUT_RC = 124
"""The exit code of a command stopped at `TIME_LIMIT`, as `timeout` gives."""

SLOW_FACTOR = 1.25
SLOW_MARGIN = 1.0

type Sub = Literal["run", "lint", "witness", "derive", "store", "audit",
                   "record", "sweep", "determination-plan", "deletions", "grid",
                   "relation", "drop-one", "derived-constant", "expand", "size",
                   "keywords"]
"""The `run_dl.py` subcommands the gate runs."""

WITNESS_FILE_SUBS: frozenset[Sub] = frozenset({"derive", "audit", "store", "witness", "record"})
"""The subcommands given a witness file, which is then one of the
command's outputs."""

type Ext = Literal["txt", "wit.json", "rc"]
"""The extension of an output file: the normalized output, the witness file,
and the exit code."""
EXTS: tuple[Ext, ...] = ("txt", "wit.json", "rc")
"""Every output file's extension, in the order a command's are compared."""


@dataclass(frozen=True)
class Command:
    """A gate command: its name in output file names, the `run_dl.py`
    subcommand, the arguments between the stem and the witness file, the
    arguments after the witness file, and the stems it runs on."""
    name: str
    sub: Sub
    args: tuple[str, ...] = ()
    extra: tuple[str, ...] = ()
    stems: tuple[str, ...] = STEMS

    @property
    def takes_witness_file(self) -> bool:
        return self.sub in WITNESS_FILE_SUBS

    def argv(self, stem: str, witness_file: Path) -> list[str]:
        """The `run_dl.py` arguments of the command on `stem`."""
        wf = ["--witness-file", str(witness_file)] if self.takes_witness_file else []
        return [self.sub, stem, *self.args, *wf, *self.extra]

    def key(self, stem: str) -> str:
        """The name of the command's output files and accepted time on
        `stem`, less the extension."""
        return f"{self.name}-{stem}"

    @property
    def exts(self) -> tuple[Ext, ...]:
        return tuple(e for e in EXTS if e != "wit.json" or self.takes_witness_file)


def _record(name: str, label: str, input_file: str, *extra: str) -> Command:
    """A `record` command adding the entry `label` to the witness file, with
    the inputs of a replay call read from `input_file` under `inputs/`."""
    return Command(name, "record", (label, str(INPUTS / input_file), *extra),
                   stems=(RECORD_STEM,))


COMMANDS = {c.name: c for c in (
    Command("run", "run", stems=(*STEMS, *LIB_STEMS)),
    Command("lint", "lint"),
    Command("witness", "witness"),
    Command("witnesseverycase", "witness", extra=("--every-case",)),
    Command("derive", "derive"),
    Command("store", "store"),
    Command("audit", "audit"),
    _record("record52", "rarest-bg", "rarest_bg.txt", "--separates",
            "Three markers hold nine 4 cells and the solid 4x4 template sixteen 2 cells, so the rarest color is the marker color: background=RarestColor drops 4 from the marker candidates and is undefined, while the stored background keeps 4 and the copies land at the empty corners (12, 5) and (12, 14)."),
    _record("record62", "exact=stored", "stray.txt", "--separates", "test"),
    _record("record67", "exact=stored", "exact_stored.txt", "--separates",
            "At side bounds 6 to 8 the 4 cells (8, 3), (2, 3), (8, 5) form a second triple, whose empty corner is the template marker's (2, 5), so they share cells with the marker at (10, 3): $RectMarker finds the split inexact there and is undefined, while exact=stored keeps color 4 at every bound and draws the copy at (10, 3)."),
    _record("recordassign", "stride-three-side-8", "w_stride3.txt",
            "--assign", '{"marker_max_side": [[8]]}', "--separates",
            "The stride-three input with marker_max_side reassigned to 8 alone: $RectMarker reads the two 4x4 markers and draws the copy at (12, 5); marker_max_side=TileCount also reads side 2, at which no triple forms, and is undefined."),
    Command("sweep", "sweep"),
    Command("determination-plan", "determination-plan"),
    Command("deletions", "deletions"),
    Command("grid", "grid", (str(INPUTS / "rarest_bg.txt"),), stems=(RECORD_STEM,)),
    Command("relation", "relation", ("out", str(INPUTS / "rarest_bg.txt")),
            stems=(RECORD_STEM,)),
    Command("drop-one", "drop-one"),
    Command("derived-constant", "derived-constant"),
    Command("expand", "expand"),
    Command("size", "size"),
    Command("keywords", "keywords"),
)}
"""Every gate command, in the order a pass runs them."""


def keys_of(cmds: Iterable[Command]) -> set[str]:
    return {c.key(s) for c in cmds for s in c.stems}


class LineKind(StrEnum):
    """The kinds of line the last line counts."""

    DIFF = "DIFF"
    """An output file that differs."""
    SLOW = "SLOW"
    """A time over the accepted one."""
    NOTIME = "NOTIME"
    """A command with no accepted time."""


TIME_KINDS = frozenset({LineKind.SLOW, LineKind.NOTIME})
"""The kinds of line that judge a time."""


@dataclass(frozen=True)
class Line:
    """A line the gate prints above the last line: its kind, the command,
    the stem, and what follows them."""
    kind: LineKind
    cmd: str
    stem: str
    rest: str

    def __str__(self) -> str:
        return f"{self.kind} {self.cmd} {self.stem} {self.rest}"


_ELAPSED_RE = re.compile(r" \([0-9.]+s\) ---$", re.M)
_LIMIT_RE = re.compile(r"^(time limit [0-9]+s; elapsed )[0-9]+s$", re.M)
_DROPPED = "runner and lib:"
OUT_MARK = "<out>/gate/"


def lock_file() -> Path:
    """The lock file in the repository's common git directory, which every
    worktree of the repository shares."""
    return checkout.git_common_dir(checkout.ROOT) / "arc-gate.lock"


def times_file(accepted: Path) -> Path:
    """The accepted times of the accepted directory `accepted`: for
    `ACCEPTED`, the machine's, `TIMES_FILE` in the main worktree's
    `ACCEPTED`; for another directory, its own `TIMES_FILE`."""
    if accepted.resolve() != ACCEPTED.resolve():
        return accepted / TIMES_FILE
    return checkout.main_worktree(checkout.ROOT) / ACCEPTED.relative_to(checkout.ROOT) / TIMES_FILE


def deps_file() -> Path:
    return checkout.main_worktree(checkout.ROOT) / DEPS_FILE


def load() -> str:
    """The machine's load averages over 1, 5 and 15 minutes."""
    return " ".join(f"{x:.2f}" for x in os.getloadavg())


def _git(*argv: str) -> str:
    """The stdout of a git command in the checkout, which must succeed."""
    done = subprocess.run(["git", *argv], cwd=checkout.ROOT, capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(argv)} failed: {done.stderr.strip()}")
    return done.stdout


# The dependencies

TRACE = "--trace"
"""The first argument of the gate's own call that runs one traced command
(`trace`)."""

GATE_READS = ("scripts/gate.py", "pyproject.toml", "uv.lock")
"""The files every command depends on outside its traced run: the gate,
which writes its arguments and normalizes its output, and the files that
set the environment `uv run` gives it."""

LIST_EVENTS = frozenset({"os.listdir", "os.scandir"})
"""The audit events that list a directory."""

PY_SUFFIXES = frozenset({".py", ".pyc"})
"""The suffixes of the files a command depends on through the lines it
runs alone. A command also reads Python files' bytes, to import them and
to key the run cache, and the warm pass shows that the cache changes no
output."""


@dataclass(frozen=True)
class Deps:
    """What one command depends on, from its traced run: the lines it ran
    of each Python file, the other files of the checkout it opened to read,
    and the directories of the checkout it listed, each path from the
    checkout's root."""
    lines: dict[str, frozenset[int]]
    reads: frozenset[str]
    listed: frozenset[str]

    def to_json(self) -> dict[str, object]:
        return {"lines": {p: _ranges(ns) for p, ns in sorted(self.lines.items())},
                "reads": sorted(self.reads), "listed": sorted(self.listed)}

    @staticmethod
    def from_json(data: dict[str, object]) -> "Deps":
        lines = data["lines"]
        reads = data["reads"]
        listed = data["listed"]
        if not (isinstance(lines, dict) and isinstance(reads, list)
                and isinstance(listed, list)):
            raise ValueError(f"a dependency record entry of no known shape: {data}")
        return Deps({p: frozenset(n for a, b in rs for n in range(a, b + 1))
                     for p, rs in lines.items()},
                    frozenset(reads), frozenset(listed))


def _ranges(ns: Iterable[int]) -> list[list[int]]:
    """`ns` as sorted runs of consecutive numbers, each its first and last."""
    out: list[list[int]] = []
    for n in sorted(ns):
        if out and out[-1][1] == n - 1:
            out[-1][1] = n
        else:
            out.append([n, n])
    return out


def _reading(mode: object, flags: object) -> bool:
    """Whether an `open` audit event's mode or flags open the file to read."""
    if isinstance(mode, str):
        return not any(c in mode for c in "wax")
    if isinstance(flags, int):
        return flags & (os.O_WRONLY | os.O_RDWR) == 0
    raise ValueError(f"an open event with mode {mode!r} and flags {flags!r}")


def _in_checkout(path: object) -> str | None:
    """`path`, an audit event's path argument, from the checkout's root, or
    None where it is a file descriptor or stands outside the checkout."""
    if isinstance(path, int) or path is None:
        return None
    if not isinstance(path, (str, bytes, os.PathLike)):
        raise ValueError(f"an audit event's path of no known type: {path!r}")
    p = Path(os.fsdecode(path)).resolve()
    root = checkout.ROOT.resolve()
    return str(p.relative_to(root)) if p.is_relative_to(root) else None


def trace(deps_out: Path, cov_out: Path, script: Path, args: Sequence[str]) -> int:
    """Run `script` with `args` as `__main__`, and write what it depends on
    to `deps_out`, as `Deps`, and its coverage data to `cov_out`; its exit
    status."""
    reads: set[str] = set()
    listed: set[str] = set()

    def hook(event: str, a: tuple[object, ...]) -> None:
        if event == "open" and _reading(a[1], a[2]):
            rel = _in_checkout(a[0])
            if rel is not None and Path(rel).suffix not in PY_SUFFIXES:
                reads.add(rel)
        elif event in LIST_EVENTS:
            rel = _in_checkout(a[0] if a[0] is not None else ".")
            if rel is not None:
                listed.add(rel)

    cov = coverage.Coverage(data_file=str(cov_out), config_file=False,
                            source=[str(checkout.ROOT / "src"), str(checkout.scripts())],
                            omit=[str(Path(__file__).resolve())])
    sys.argv = [str(script), *args]
    sys.addaudithook(hook)
    status: int = 0
    cov.start()
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as e:
        if e.code is None or isinstance(e.code, int):
            status = e.code or 0
        else:
            print(e.code, file=sys.stderr)
            status = 1
    finally:
        cov.stop()
        cov.save()
        data = cov.get_data()
        lines = {rel: frozenset(ran) for f in data.measured_files()
                 if (ran := data.lines(f)) and (rel := _in_checkout(f)) is not None}
        deps = Deps(lines, frozenset(reads), frozenset(listed))
        deps_out.write_text(json.dumps(deps.to_json()) + "\n")
    return status


class Status(StrEnum):
    """How a change since the recorded commit touches a path."""

    ADDED = "A"
    DELETED = "D"
    MODIFIED = "M"
    TYPE_CHANGED = "T"


@dataclass(frozen=True)
class Touched:
    """A path the changes since the recorded commit touch, and, for a
    modified Python file, the line ranges of its recorded text they replace,
    each its first line and its count, a count of 0 an insertion after the
    first line."""
    path: str
    status: Status
    hunks: tuple[tuple[int, int], ...] = ()


_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+", re.M)


def hunks_of(diff: str) -> tuple[tuple[int, int], ...]:
    """The old side of each hunk of the unified diff `diff`: its first line
    and its count, which git leaves out where it is 1."""
    return tuple((int(a), int(b) if b else 1) for a, b in _HUNK_RE.findall(diff))


def touched_since(commit: str) -> list[Touched]:
    """Each path whose content in the checkout differs from `commit`: the
    tracked ones, each side of a rename, and the untracked ones git does
    not ignore."""
    named = _git("diff", "--name-status", "--no-renames", "-z", commit).split("\0")
    out: list[Touched] = []
    for status, path in zip(named[0:-1:2], named[1::2], strict=True):
        hunks: tuple[tuple[int, int], ...] = ()
        if Status(status) is Status.MODIFIED and Path(path).suffix in PY_SUFFIXES:
            diff = _git("diff", "-U0", "--no-color", "--no-ext-diff", commit, "--", path)
            hunks = hunks_of(diff)
        out.append(Touched(path, Status(status), hunks))
    untracked = _git("ls-files", "--others", "--exclude-standard", "-z").split("\0")
    out += [Touched(p, Status.ADDED) for p in untracked if p]
    return out


@dataclass(frozen=True)
class Function:
    """A function of a Python text: the first line of its header, its
    decorators included, the first line of its body, and its last line."""
    first: int
    body: int
    last: int


def functions(source: str) -> list[Function]:
    return [Function(min([n.lineno, *(d.lineno for d in n.decorator_list)]),
                     n.body[0].lineno, n.end_lineno or n.lineno)
            for n in ast.walk(ast.parse(source))
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def runs_hunks(source: str, hunks: Sequence[tuple[int, int]], ran: frozenset[int]) -> bool:
    """Whether a command that ran the lines `ran` of the Python text
    `source` runs a part that `hunks` replace. A hunk inside the body of a
    function is run where a line of the innermost such function's body
    ran; a hunk elsewhere, a header among them, runs when the file is
    imported, so it is run where any line of the file ran. An insertion
    after a function's last line may stand in its body or after it, so it
    is taken to stand after it. A file with no
    hunk, whose change git shows as no lines, is run where any line ran."""
    if not ran:
        return False
    if not hunks:
        return True
    fs = functions(source)
    for start, count in hunks:
        lo, hi = (start, start + count - 1) if count else (start, start + 1)
        inside = [f for f in fs if f.first <= lo and hi <= f.last]
        if not inside:
            return True
        f = max(inside, key=lambda f: f.first)
        header = lo < f.body if count else start < f.body - 1
        if header or any(f.body <= n <= f.last for n in ran):
            return True
    return False


def affects(cmd: Command, stem: str, deps: Deps, touched: Sequence[Touched],
            recorded: dict[str, str]) -> bool:
    """Whether the changes `touched` can affect `cmd` on `stem`, which
    depends on `deps`, with `recorded` the recorded text of each Python file
    they modify or delete. A change affects it where it touches a
    file of `GATE_READS`, the command's accepted outputs, the frozen
    witness file it is given, or a file it opened to read; where it adds or
    deletes a file in a directory it listed; and where it changes a Python
    file part of which it runs, as `runs_hunks` decides. A Python file
    affects it through the lines it runs alone (`PY_SUFFIXES`), so a Python
    file the change adds affects it through the lines that import it."""
    accepted = ACCEPTED.relative_to(checkout.ROOT)
    own = {*GATE_READS, *(str(accepted / f"{cmd.key(stem)}.{e}") for e in cmd.exts)}
    if cmd.takes_witness_file:
        own.add(str(FROZEN.relative_to(checkout.ROOT) / f"{stem}.wit.json"))
    for t in touched:
        if t.path in own:
            return True
        if Path(t.path).suffix not in PY_SUFFIXES:
            if t.path in deps.reads or (t.status in (Status.ADDED, Status.DELETED)
                                        and str(Path(t.path).parent) in deps.listed):
                return True
        elif t.path in deps.lines and t.status is not Status.ADDED:
            if runs_hunks(recorded[t.path], t.hunks if t.status is Status.MODIFIED else (),
                          deps.lines[t.path]):
                return True
    return False


@dataclass(frozen=True)
class Record:
    """The dependency record: the commit whose lines it records, and each
    command's dependencies by its key."""
    commit: str
    deps: dict[str, Deps]

    @staticmethod
    def read(path: Path) -> "Record":
        data = json.loads(path.read_text())
        return Record(data["commit"],
                      {k: Deps.from_json(v) for k, v in data["commands"].items()})

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        body = {"commit": self.commit,
                "commands": {k: d.to_json() for k, d in sorted(self.deps.items())}}
        write_whole(path, (json.dumps(body) + "\n").encode())


def affected(cmds: Sequence[Command]) -> tuple[set[str], str]:
    """The keys of `cmds` on their stems that the changes since the
    recorded commit can affect, each key with no dependency record among
    them, and the first line `--affected` prints."""
    keys = keys_of(cmds)
    path = deps_file()
    if not path.exists():
        return keys, mctx("affected: no dependency record stands at {path}, so every one of "
                          "the {n} commands runs").format(path=path, n=len(keys))
    record = Record.read(path)
    touched = touched_since(record.commit)
    recorded = {t.path: _git("show", f"{record.commit}:{t.path}") for t in touched
                if Path(t.path).suffix in PY_SUFFIXES and t.status is not Status.ADDED}
    run = {k for c in cmds for s in c.stems for k in [c.key(s)]
           if k not in record.deps or affects(c, s, record.deps[k], touched, recorded)}
    return run, mctx("affected: {run} of the {n} commands run, by the dependency record of "
                     "{commit}").format(run=len(run), n=len(keys), commit=record.commit[:12])


class Gate:
    """One gate run into `out/gate/`."""

    def __init__(self, out: Path, accepted: Path, timed: bool, traced: bool) -> None:
        self.dir = out.resolve() / "gate"
        self.new = self.dir / "new"
        self.warm = self.new / "warm"
        self.wit = self.dir / "wit" / "cur"
        self.deps = self.dir / "deps"
        self.cov = self.dir / "cov"
        self.accepted = accepted
        self.timed = timed
        """Whether the run makes the warm pass and judges the cold times;
        `--outputs-only` clears it."""
        self.traced = traced
        """Whether each cold command runs under `trace`."""
        self.times_file = times_file(accepted)
        self.times: dict[str, float] = (
            json.loads(self.times_file.read_text()) if self.times_file.exists() else {})
        self.shown = f"{checkout.shown(self.dir)}/"
        self.lock = lock_file()
        self.log_lock = threading.Lock()

    def env(self, cache: Path) -> dict[str, str]:
        return {**os.environ,
                checkout.CACHE_ENV: str(cache),
                checkout.SOLVER_FILES_ENV: str(SOLVERS),
                checkout.WITNESSES_ENV: str(WITNESSES),
                WALL_LIMIT_ENV: str(TIME_LIMIT)}

    def normalize(self, raw: str) -> str:
        """`raw` with the lines naming the runner and lib dropped, the out
        directory written as `OUT_MARK`, and the times dropped."""
        lines = [ln for ln in raw.splitlines(keepends=True) if _DROPPED not in ln]
        text = "".join(lines).replace(self.shown, OUT_MARK)
        text = _ELAPSED_RE.sub(" ---", text)
        return _LIMIT_RE.sub(r"\1Ns", text)

    @contextlib.contextmanager
    def locked(self, cold: bool) -> Iterator[None]:
        if not self.timed:
            yield
            return
        with open(self.lock, "a") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX if cold else fcntl.LOCK_SH)
            yield

    def run_one(self, cmd: Command, stem: str, cold: bool, cache: Path) -> tuple[int, float]:
        """`cmd` on `stem` under the lock, its normalized output, witness
        file and exit code written to the pass's directory; the exit code
        and wall time."""
        wf = self.wit / f"{stem}.wit.json"
        if cmd.takes_witness_file:
            shutil.copyfile(FROZEN / f"{stem}.wit.json", wf)
        key = cmd.key(stem)
        run_dl = [str(checkout.scripts() / "run_dl.py"), *cmd.argv(stem, wf)]
        if self.traced and cold:
            run_dl = [str(Path(__file__).resolve()), TRACE, str(self.deps / f"{key}.json"),
                      str(self.cov / f".coverage.{key}"), *run_dl]
        argv = ["uv", "run", "--project", str(checkout.ROOT), "python", *run_dl]
        base = (self.new if cold else self.warm) / key
        with self.locked(cold):
            start = time.time()
            proc = subprocess.Popen(argv, cwd=checkout.ROOT, env=self.env(cache),
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            try:
                raw, _ = proc.communicate(timeout=TIME_LIMIT)
                rc = proc.returncode
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    raw, _ = proc.communicate(timeout=KILL_AFTER)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    raw, _ = proc.communicate()
                rc = TIMEOUT_RC
            wall = round(time.time() - start, 1)
        Path(f"{base}.raw").write_bytes(raw)
        Path(f"{base}.txt").write_text(self.normalize(raw.decode()))
        if "wit.json" in cmd.exts:
            shutil.copyfile(wf, f"{base}.wit.json")
        Path(f"{base}.rc").write_text(f"{rc}\n")
        with self.log_lock, open(self.dir / "times.txt", "a") as fh:
            fh.write(f"{cmd.name} {stem} pass{1 if cold else 2} rc={rc} wall={wall}s\n")
        return rc, wall

    def compare(self, cmd: Command, stem: str, wall: float) -> list[Line]:
        """The cold run's lines: a `DIFF` line per output file that differs
        from the accepted one, and in a timed run a `SLOW` or `NOTIME` line
        for its time."""
        key = cmd.key(stem)
        lines = [Line(LineKind.DIFF, cmd.name, stem, ext) for ext in cmd.exts
                 if not _same(self.accepted / f"{key}.{ext}", self.new / f"{key}.{ext}")]
        if not self.timed:
            return lines
        Path(self.new / f"{key}{TIME_EXT}").write_text(f"{wall}\n")
        accepted = self.times.get(key)
        if accepted is None:
            lines.append(Line(LineKind.NOTIME, cmd.name, stem, f"time={wall}s"))
        elif wall > SLOW_FACTOR * accepted + SLOW_MARGIN:
            lines.append(Line(LineKind.SLOW, cmd.name, stem,
                              f"time={wall}s accepted={accepted}s load={load()}"))
        return lines

    def compare_warm(self, cmd: Command, stem: str) -> list[Line]:
        """The warm run's lines: a `DIFF` line ending in `warm` per output
        file that differs from the cold run's."""
        key = cmd.key(stem)
        return [Line(LineKind.DIFF, cmd.name, stem, f"{ext} warm") for ext in cmd.exts
                if not _same(self.new / f"{key}.{ext}", self.warm / f"{key}.{ext}")]

    def stem_sequence(self, stem: str, cmds: Sequence[Command]) -> list[Line]:
        """Both passes of `cmds` on `stem`, their lines written to the
        stem's log."""
        cache = self.dir / "cache" / stem
        shutil.rmtree(cache, ignore_errors=True)
        cache.mkdir(parents=True)
        lines: list[Line] = []
        try:
            for cold in (True, False) if self.timed else (True,):
                for cmd in cmds:
                    _, wall = self.run_one(cmd, stem, cold, cache)
                    lines += (self.compare(cmd, stem, wall) if cold
                              else self.compare_warm(cmd, stem))
        finally:
            (self.dir / f"log-{stem}.txt").write_text("".join(f"{ln}\n" for ln in lines))
            shutil.rmtree(cache, ignore_errors=True)
        return lines

    def run(self, cmds: Sequence[Command], keys: set[str]) -> list[Line]:
        for d in (self.new, self.warm, self.wit, self.deps, self.cov):
            d.mkdir(parents=True, exist_ok=True)
        stems = sorted({s for c in cmds for s in c.stems})
        lines: dict[str, list[Line]] = {}
        errors: list[BaseException] = []

        def sequence(stem: str) -> None:
            try:
                lines[stem] = self.stem_sequence(
                    stem, [c for c in cmds if stem in c.stems and c.key(stem) in keys])
            except BaseException as e:
                errors.append(e)
                raise

        threads = [threading.Thread(target=sequence, args=(s,)) for s in stems]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        if errors:
            raise RuntimeError(f"{len(errors)} stem sequences failed") from errors[0]
        out = [ln for s in stems for ln in lines[s]]
        (self.dir / "log.txt").write_text("".join(f"{ln}\n" for ln in out))
        return out

    def kinds(self) -> tuple[LineKind, ...]:
        """The kinds of line the run makes, which the last line counts."""
        return tuple(k for k in LineKind if self.timed or k not in TIME_KINDS)

    def record(self) -> Record:
        """The dependencies of every command the run traced, with the `HEAD`
        commit."""
        deps = {p.stem: Deps.from_json(json.loads(p.read_text()))
                for p in sorted(self.deps.glob("*.json"))}
        return Record(_git("rev-parse", "HEAD").strip(), deps)

    def accept(self, replace: bool) -> tuple[int, int]:
        """Each cold time and output written as accepted where none of its
        name stands, or over it with `replace`; the counts of times and
        outputs written."""
        times = {key: float(p.read_text()) for p in sorted(self.new.glob(f"*{TIME_EXT}"))
                 if _writes(replace, (key := p.name.removesuffix(TIME_EXT)) in self.times)}
        merged = dict(sorted({**self.times, **times}.items()))
        write_whole(self.times_file,
                    (json.dumps(merged, indent=1) + "\n").encode())
        written = 0
        for p in sorted(p for ext in EXTS for p in self.new.glob(f"*.{ext}")):
            dest = self.accepted / p.name
            if _writes(replace, dest.exists()):
                shutil.copyfile(p, dest)
                written += 1
        return len(times), written


def _writes(replace: bool, stands: bool) -> bool:
    """Whether `--accept` writes a time or output: where none of its name
    stands, and over one that stands with `--replace`."""
    return replace or not stands


def _same(a: Path, b: Path) -> bool:
    return a.exists() and b.exists() and a.read_bytes() == b.read_bytes()


def main(argv: Sequence[str]) -> int:
    if argv[:1] == [TRACE]:
        deps_out, cov_out, script, *args = argv[1:]
        return trace(Path(deps_out), Path(cov_out), Path(script), args)
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path, help="the output directory")
    ap.add_argument("cmds", nargs="*", metavar="cmd",
                    help=f"one of {', '.join(COMMANDS)}; every one by default, in that order")
    ap.add_argument("--accept", action="store_true",
                    help="write the run's times and outputs as accepted where none stands")
    ap.add_argument("--replace", action="store_true",
                    help="with --accept, write every time and output over the accepted one")
    ap.add_argument("--outputs-only", action="store_true",
                    help="run the cold pass alone and compare its outputs, judging no time")
    picked = ap.add_mutually_exclusive_group()
    picked.add_argument("--affected", action="store_true",
                        help="with --outputs-only, run only the commands the changes since "
                             "the dependency record can affect")
    picked.add_argument("--record-deps", action="store_true",
                        help="with --outputs-only, trace every command and write the "
                             "dependency record")
    ap.add_argument("--coverage", action="store_true",
                    help="with --outputs-only, trace every command run, writing its coverage "
                         "data and dependencies under the out-dir")
    ap.add_argument("--accepted", type=Path, default=ACCEPTED,
                    help="the accepted directory (default: tests/gate/accepted)")
    a = ap.parse_args(argv)
    if a.replace and not a.accept:
        ap.error("--replace is given without --accept")
    if a.accept and a.outputs_only:
        ap.error("--accept writes the cold times, which --outputs-only does not judge")
    if (a.affected or a.record_deps or a.coverage) and not a.outputs_only:
        ap.error(mctx("--affected, --record-deps and --coverage each run a part or a trace "
                      "of the sequence, whose times do not compare, so each needs "
                      "--outputs-only"))
    unknown = [c for c in a.cmds if c not in COMMANDS]
    if unknown:
        ap.error(f"no gate command named {', '.join(unknown)}")
    if a.record_deps and a.cmds:
        ap.error(mctx("--record-deps records every command, so it takes no command"))
    if a.record_deps and _git("status", "--porcelain", "--untracked-files=no"):
        ap.error(mctx("--record-deps records the lines of HEAD, and the checkout changes "
                      "a tracked file against it"))
    cmds = [COMMANDS[c] for c in a.cmds] or list(COMMANDS.values())
    gate = Gate(a.out, a.accepted.resolve(), timed=not a.outputs_only,
                traced=a.record_deps or a.coverage)
    keys = keys_of(cmds)
    if a.affected:
        keys, said = affected(cmds)
        print(said, flush=True)
    if a.accept:
        if gate.dir.exists():
            ap.error(f"{gate.dir} exists; give an empty out-dir")
        a.accepted.mkdir(parents=True, exist_ok=True)
        print(f"load before: {load()}", flush=True)
    lines = gate.run(cmds, keys)
    for ln in lines:
        print(ln)
    counts = {k: sum(ln.kind is k for ln in lines) for k in gate.kinds()}
    print("gate: " + ", ".join(f"{n} {k}" for k, n in counts.items()))
    if a.record_deps:
        gate.record().write(deps_file())
        print(mctx("deps: the dependencies of {n} commands are written to {path}").format(
            n=len(keys), path=deps_file()))
    if a.accept:
        print(f"load after: {load()}")
        times, outputs = gate.accept(a.replace)
        print(f"baseline: {times} accepted times written to {gate.times_file}, "
              f"and {outputs} new accepted outputs to {a.accepted}")
        return 0
    return 1 if any(counts.values()) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
