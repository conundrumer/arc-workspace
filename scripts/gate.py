"""The gate: the gate commands on their gate stems, compared with the
accepted outputs under `tests/gate/accepted/` and the machine's accepted
times.

    uv run python scripts/gate.py <out-dir> [cmd ...]
    uv run python scripts/gate.py --outputs-only [--affected <base> | --record-deps] [--coverage] <out-dir> [cmd ...]
    uv run python scripts/gate.py --accept [--replace] <out-dir> [cmd ...]
    uv run python scripts/gate.py --adopt-record <out-dir>

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

A timed run holds the heavy commands' lock (`engine.rwlock`) exclusively,
and an `--outputs-only` run holds it shared, so a timed run shares the
machine with no other heavy command, of this checkout or of another
worktree of the repository. Within a timed run, a cold command holds the
gate's lock file exclusively and a warm command holds it shared, so a cold
command never shares the machine with another command of the run.

`--outputs-only` runs the cold pass alone, and compares its outputs alone:
it prints `DIFF` lines, and no `SLOW` or `NOTIME` line, and writes no
times to `new/`. An `--outputs-only` run shares the machine with the other
heavy commands, and its times measure that load as much as the change, so
times are judged by one timed gate run on `master` after a batch of merges.
A `SLOW` line of that run is filed as a `delay` issue, and blocks no merge.

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

`--affected` runs only the commands that the change can affect, as
`affects` decides, and every command where no dependency record stands. The
change is the difference between the commit `<base>`, which the change
branched from, and the checkout. Its first line names the record and the
base, and counts the commands it runs. Where it runs every command, on a
checkout with no change to a tracked file against `HEAD`, it traces them as
`--record-deps` does, and writes their dependencies, with the `HEAD`
commit, to `<out-dir>/gate/record.json` (`RECORD_OUT`).

`--adopt-record` runs no command: it writes the `RECORD_OUT` that an
earlier run wrote under `<out-dir>` as the dependency record, where its
commit is the `HEAD` commit of the checkout it runs in, and fails where it
is another.
Where no `RECORD_OUT` stands, it says so and leaves the dependency record
as it is.

Every command reads the solver files from `tests/gate/solvers/` and the
witness files from `tests/gate/witnesses/`. A command that takes a witness
file is given one at `<out-dir>/gate/wit/cur/`, copied from
`tests/gate/frozen/` before the command runs. The `record` commands, `grid`
and `relation` read their input files from `tests/gate/inputs/`. The
`context` command renders each of its readers' contexts from
`<out-dir>/gate/documents/`, copied from `tests/gate/documents/` before the
commands run, so a change to the checkout's own documents changes none of
its outputs. Its readers are the session, codex, and each name
`tests/gate/documents/` defines for a reader that takes a name. In an output, the path of
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
from typing import ClassVar, Literal

import coverage
from coverage.sysmon import SysMonitor

from cli.common import WALL_LIMIT_ENV
from controlled_markdown import mctx
from engine import checkout, rwlock
from engine.memo import write_whole
from handbook.context import CONTEXT_READERS, ArgumentForm
from handbook.paths import DOCUMENTS_ENV

GATE = checkout.ROOT / "tests" / "gate"
SOLVERS = GATE / "solvers"
WITNESSES = GATE / "witnesses"
FROZEN = GATE / "frozen"
INPUTS = GATE / "inputs"
ACCEPTED = GATE / "accepted"
DOCUMENTS = GATE / "documents"
"""The documents a context command renders, laid out as the checkout is."""
TIME_EXT = ".time"
"""The extension of the file in `new/` holding a cold run's time."""
TIMES_FILE = "times.json"
"""The accepted times, a JSON object from `<name>-<stem>` to seconds
(`times_file`)."""
DEPS_FILE = checkout.scratch().relative_to(checkout.ROOT) / "gate" / "deps.json"
"""The dependency record, under the main worktree (`deps_file`)."""
RECORD_OUT = "record.json"
"""The file under `<out-dir>/gate/` that holds the dependencies an
`--affected` run traced, as a dependency record."""

STEMS = ("9c1e755f", "9b30e358", "9b2a60aa", "a61ba2ce", "a04b2602", "a096bf4d",
         "9b4c17c4", "a5f85a15")
"""The stems `run` runs on, of which each other command that reads no grid
input runs on those with the least accepted time whose runs together cover
every line of `src/` and `scripts/` that its runs on all of them cover, but
the lines of the run cache's pruning, which a run reaches by a random draw.
`sweep` also runs on 9b30e358, whose swept parameters' values are symbols."""
SWEEP_STEM = "a934301b"
"""The stem `sweep` runs on besides those of `STEMS`, whose sweep marks the
gaps of a parameter under a case marker."""
BRANCH_STEM = "abbfd121"
"""The stem `audit` and `derive` run on besides those of `STEMS`, whose branches
render with their recorded witnesses."""
RECORD_STEM = "a61ba2ce"
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


def frozen_witness(stem: str) -> Path:
    """The frozen witness file of `stem`, which a command that takes a
    witness file is given a copy of."""
    return FROZEN / f"{stem}.wit.json"


@dataclass(frozen=True)
class Named:
    """A gate command's name in output file names."""
    name: str

    def key(self, stem: str) -> str:
        """The name of the command's output files and accepted time on
        `stem`, less the extension."""
        return f"{self.name}-{stem}"


@dataclass(frozen=True)
class Command(Named):
    """A gate command: its name in output file names, the `run_dl.py`
    subcommand, the arguments between the stem and the witness file, the
    arguments after the witness file, and the stems it runs on."""
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

    @property
    def exts(self) -> tuple[Ext, ...]:
        return tuple(e for e in EXTS if e != "wit.json" or self.takes_witness_file)

    script = "run_dl.py"
    """The script under `scripts/` the command runs."""

    def copied(self, stem: str) -> tuple[Path, ...]:
        """The files and directories the gate copies for the command on
        `stem` before it runs: the frozen witness file it is given."""
        return (frozen_witness(stem),) if self.takes_witness_file else ()


@dataclass(frozen=True)
class ContextCommand(Named):
    """A gate command that prints readers' contexts through
    `scripts/context.py context`, rendered from a copy of `DOCUMENTS`: its
    name in output file names, and each reader with its arguments. Its
    stems are its readers, each its arguments joined by `-`."""
    readers: tuple[tuple[str, ...], ...]

    takes_witness_file = False
    exts: ClassVar[tuple[Ext, ...]] = ("txt", "rc")
    script = "context.py"
    """The script under `scripts/` the command runs."""

    @property
    def stems(self) -> tuple[str, ...]:
        return tuple("-".join(r) for r in self.readers)

    def argv(self, stem: str, witness_file: Path) -> list[str]:
        """The `context.py` arguments of the command on the reader `stem`."""
        return ["context", *dict(zip(self.stems, self.readers, strict=True))[stem]]

    def copied(self, stem: str) -> tuple[Path, ...]:
        """The files and directories the gate copies for the command
        before it runs: `DOCUMENTS`."""
        return (DOCUMENTS,)


type GateCommand = Command | ContextCommand


def _record(name: str, label: str, input_file: str, *extra: str) -> Command:
    """A `record` command adding the entry `label` to the witness file, with
    the inputs of a replay call read from `input_file` under `inputs/`."""
    return Command(name, "record", (label, str(INPUTS / input_file), *extra),
                   stems=(RECORD_STEM,))


def named_readers() -> list[tuple[str, str]]:
    """Each reader the `context` command takes by name, with each name
    `DOCUMENTS` defines for it."""
    return [(reader, name) for reader, known in CONTEXT_READERS.items()
            if known.form is ArgumentForm.NAME for name in known.values(DOCUMENTS)]


COMMANDS: dict[str, GateCommand] = {c.name: c for c in (
    Command("run", "run", stems=(*STEMS, SWEEP_STEM, BRANCH_STEM, *LIB_STEMS)),
    Command("lint", "lint", stems=("9b30e358", "9b2a60aa", "a61ba2ce", "a04b2602", "9b4c17c4",
                                   "a5f85a15")),
    Command("witness", "witness", stems=("9c1e755f", "9b30e358", "9b2a60aa", "a61ba2ce",
                                         "a04b2602", "a5f85a15")),
    Command("witnesseverycase", "witness", extra=("--every-case",),
            stems=("9c1e755f", "9b30e358", "9b2a60aa", "a61ba2ce", "a04b2602", "a5f85a15")),
    Command("derive", "derive", stems=("9c1e755f", "9b30e358", "9b2a60aa", "a61ba2ce", "a04b2602",
                                       "a096bf4d", "a5f85a15", BRANCH_STEM)),
    Command("store", "store", stems=("9c1e755f", "9b30e358", "9b2a60aa", "a61ba2ce", "a04b2602",
                                     "a096bf4d", "a5f85a15")),
    Command("audit", "audit", stems=("9c1e755f", "9b30e358", "9b2a60aa", "a61ba2ce", "a04b2602",
                                     "a096bf4d", "a5f85a15", BRANCH_STEM)),
    _record("recordnew", "touching-pieces", "a61ba2ce_edge-touch.txt", "--separates",
            "The edge-touch input under a new id."),
    _record("recordreplace", "two-color-l", "a61ba2ce_edge-touch.txt", "--separates", "test"),
    _record("recordassign", "gap-outward", "a61ba2ce_gap-outward.txt", "--assign",
            '{"corner_quadrant": [["DIAG_TL", "DIAG_BR"], ["DIAG_TR", "DIAG_BL"], '
            '["DIAG_BL", "DIAG_TR"], ["DIAG_BR", "DIAG_TL"]]}', "--separates",
            "The gap-outward input with the stored map sending each missing corner to the opposite quadrant, as the concept does."),
    Command("sweep", "sweep", stems=("9c1e755f", "9b30e358", "9b2a60aa", "a61ba2ce", "a04b2602",
                                     "a5f85a15", SWEEP_STEM)),
    Command("determination-plan", "determination-plan",
            stems=("9c1e755f", "9b30e358", "9b2a60aa", "a61ba2ce", "a04b2602", "9b4c17c4",
                   "a5f85a15")),
    Command("deletions", "deletions", stems=("9b30e358", "9b2a60aa", "a61ba2ce", "a04b2602",
                                             "a096bf4d", "9b4c17c4", "a5f85a15")),
    Command("grid", "grid", (str(INPUTS / "a61ba2ce_two-color-l.txt"),), stems=(RECORD_STEM,)),
    Command("relation", "relation", ("out", str(INPUTS / "a61ba2ce_two-color-l.txt")),
            stems=(RECORD_STEM,)),
    Command("drop-one", "drop-one", stems=("9c1e755f", "9b2a60aa", "a61ba2ce", "a04b2602",
                                           "9b4c17c4", "a5f85a15")),
    Command("derived-constant", "derived-constant",
            stems=("9b2a60aa", "a61ba2ce", "a04b2602", "9b4c17c4", "a5f85a15")),
    Command("expand", "expand", stems=("9b2a60aa", "a61ba2ce", "a04b2602", "9b4c17c4", "a5f85a15")),
    Command("size", "size", stems=("9c1e755f", "9b2a60aa", "a61ba2ce", "a04b2602", "a5f85a15")),
    Command("keywords", "keywords", stems=("9c1e755f", "9b2a60aa", "a61ba2ce", "a04b2602",
                                           "a5f85a15")),
    ContextCommand("context", (("session",), ("codex",), *named_readers())),
)}
"""Every gate command, in the order a pass runs them."""


def keys_of(cmds: Iterable[GateCommand]) -> set[str]:
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


def head_clean() -> bool:
    """Whether the checkout changes no tracked file against `HEAD`, so that
    a traced run records the lines of the `HEAD` commit."""
    return all(c.change is checkout.Change.UNTRACKED
               for c in checkout.changed_paths(checkout.ROOT, "HEAD"))


def head() -> str:
    return checkout.git_out(checkout.ROOT, "rev-parse", "HEAD").strip()


def load() -> str:
    """The machine's load averages over 1, 5 and 15 minutes."""
    return " ".join(f"{x:.2f}" for x in os.getloadavg())


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
    # A command keeps its own wall-clock limits when traced, and the default
    # core slows it past them, so that it gives other outputs than untraced.
    cov.set_option("run:core", "sysmon")
    sys.argv = [str(script), *args]
    status: int = 0
    cov.start()
    core = dict(cov.sys_info())["core"]
    if core != SysMonitor.__name__:
        cov.stop()
        raise RuntimeError(f"coverage.py traces with the {core} core, not {SysMonitor.__name__}")
    sys.addaudithook(hook)
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


@dataclass(frozen=True)
class Touched:
    """A path the change touches, how it touches it, and, for a modified
    Python file, the line ranges of its recorded text it replaces, each its
    first line and its count, a count of 0 an insertion after the first
    line. `unrecorded` is a Python file that stands at the change's base
    and not at the recorded commit, whose lines no command's record
    holds."""
    path: str
    status: checkout.Change
    hunks: tuple[tuple[int, int], ...] = ()
    unrecorded: bool = False


_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+", re.M)


def hunks_of(diff: str) -> tuple[tuple[int, int], ...]:
    """The old side of each hunk of the unified diff `diff`: its first line
    and its count, which git leaves out where it is 1."""
    return tuple((int(a), int(b) if b else 1) for a, b in _HUNK_RE.findall(diff))


def between(old: str, new: str, *flags: str) -> set[str]:
    """The paths whose content differs between the commits `old` and `new`,
    of the statuses that `flags` filter."""
    return set(filter(None, checkout.git_out(checkout.ROOT, "diff", "--name-only",
                                             "--no-renames", "-z", *flags, old, new,
                                             ).split("\0")))


def touched_from(base: str, recorded: str) -> list[Touched]:
    """Each path whose content in the checkout differs from the commit
    `base` (`checkout.changed_paths`), as the commit `recorded` sees it. A
    path that stands at `base` and not at `recorded` is `unrecorded` where
    it is a Python file, and is otherwise added, or deleted where the change
    deletes it; a path that stands at `recorded` and
    not at `base` is modified where the change adds it. A modified Python
    file that differs between the two commits has no hunk, since its hunks
    number the lines of `base` and not the recorded lines."""
    moved = between(recorded, base)
    absent = between(recorded, base, "--diff-filter=A")
    gone = between(recorded, base, "--diff-filter=D")
    out: list[Touched] = []
    for c in checkout.changed_paths(checkout.ROOT, base):
        status = c.change
        if c.path in absent:
            if Path(c.path).suffix in PY_SUFFIXES:
                out.append(Touched(c.path, status, unrecorded=True))
                continue
            if status is not checkout.Change.DELETED:
                status = checkout.Change.ADDED
        elif c.path in gone:
            status = checkout.Change.MODIFIED
        hunks: tuple[tuple[int, int], ...] = ()
        if (status is checkout.Change.MODIFIED and Path(c.path).suffix in PY_SUFFIXES
                and c.path not in moved):
            hunks = hunks_of(checkout.git_out(checkout.ROOT, "diff", "-U0", "--no-color",
                                              "--no-ext-diff", base, "--", c.path))
        out.append(Touched(c.path, status, hunks))
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
    hunk is run where any line ran."""
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


def affects(cmd: GateCommand, stem: str, deps: Deps, touched: Sequence[Touched],
            recorded: dict[str, str]) -> bool:
    """Whether the changes `touched` can affect `cmd` on `stem`, which
    depends on `deps`, with `recorded` the recorded text of each Python file
    they modify or delete. A change affects it where it touches a
    file of `GATE_READS`, the command's accepted outputs, a file the gate
    copies for it (`copied`), or a file it opened to read; where it adds or
    deletes a file in a directory it listed; and where it changes a Python
    file part of which it runs, as `runs_hunks` decides. A Python file
    affects it through the lines it runs alone (`PY_SUFFIXES`), so a Python
    file the change adds affects it through the lines that import it. An
    `unrecorded` file affects every command, since the record cannot say
    which commands run it."""
    accepted = ACCEPTED.relative_to(checkout.ROOT)
    own = {*GATE_READS, *(str(accepted / f"{cmd.key(stem)}.{e}") for e in cmd.exts)}
    copied = [p.relative_to(checkout.ROOT) for p in cmd.copied(stem)]
    for t in touched:
        if t.unrecorded:
            return True
        if t.path in own or any(Path(t.path).is_relative_to(p) for p in copied):
            return True
        if Path(t.path).suffix not in PY_SUFFIXES:
            if t.path in deps.reads or ((t.status.added or t.status is checkout.Change.DELETED)
                                        and str(Path(t.path).parent) in deps.listed):
                return True
        elif t.path in deps.lines and not t.status.added:
            if runs_hunks(recorded[t.path],
                          t.hunks if t.status is checkout.Change.MODIFIED else (),
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


def affected(cmds: Sequence[GateCommand], base: str) -> tuple[set[str], str]:
    """The keys of `cmds` on their stems that the change from the commit
    `base` can affect, each key with no dependency record among them, and
    the first line `--affected` prints."""
    keys = keys_of(cmds)
    path = deps_file()
    if not path.exists():
        return keys, mctx("affected: no dependency record stands at {path}, so every one of "
                          "the {n} commands runs").format(path=path, n=len(keys))
    record = Record.read(path)
    touched = touched_from(base, record.commit)
    recorded = {t.path: checkout.git_out(checkout.ROOT, "show", f"{record.commit}:{t.path}")
                for t in touched if Path(t.path).suffix in PY_SUFFIXES
                and not (t.status.added or t.unrecorded)}
    run = {k for c in cmds for s in c.stems for k in [c.key(s)]
           if k not in record.deps or affects(c, s, record.deps[k], touched, recorded)}
    return run, mctx("affected: {run} of the {n} commands run, by the dependency record of "
                     "{commit} and the change from {base}").format(
        run=len(run), n=len(keys), commit=record.commit[:12], base=base)


class Gate:
    """One gate run into `out/gate/`."""

    def __init__(self, out: Path, accepted: Path, timed: bool, traced: bool) -> None:
        self.dir = out.resolve() / "gate"
        self.new = self.dir / "new"
        self.warm = self.new / "warm"
        self.wit = self.dir / "wit" / "cur"
        self.deps = self.dir / "deps"
        self.cov = self.dir / "cov"
        self.documents = self.dir / "documents"
        """The copy of `DOCUMENTS` the context commands render."""
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
                DOCUMENTS_ENV: str(self.documents),
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

    def run_one(self, cmd: GateCommand, stem: str, cold: bool, cache: Path) -> tuple[int, float]:
        """`cmd` on `stem` under the lock, its normalized output, witness
        file and exit code written to the pass's directory; the exit code
        and wall time."""
        wf = self.wit / f"{stem}.wit.json"
        if cmd.takes_witness_file:
            shutil.copyfile(frozen_witness(stem), wf)
        key = cmd.key(stem)
        script = [str(checkout.scripts() / cmd.script), *cmd.argv(stem, wf)]
        if self.traced and cold:
            script = [str(Path(__file__).resolve()), TRACE, str(self.deps / f"{key}.json"),
                      str(self.cov / f".coverage.{key}"), *script]
        argv = ["uv", "run", "--project", str(checkout.ROOT), "python", *script]
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

    def compare(self, cmd: GateCommand, stem: str, wall: float) -> list[Line]:
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

    def compare_warm(self, cmd: GateCommand, stem: str) -> list[Line]:
        """The warm run's lines: a `DIFF` line ending in `warm` per output
        file that differs from the cold run's."""
        key = cmd.key(stem)
        return [Line(LineKind.DIFF, cmd.name, stem, f"{ext} warm") for ext in cmd.exts
                if not _same(self.new / f"{key}.{ext}", self.warm / f"{key}.{ext}")]

    def stem_sequence(self, stem: str, cmds: Sequence[GateCommand]) -> list[Line]:
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

    def run(self, cmds: Sequence[GateCommand], keys: set[str]) -> list[Line]:
        for d in (self.new, self.warm, self.wit, self.deps, self.cov):
            d.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(self.documents, ignore_errors=True)
        shutil.copytree(DOCUMENTS, self.documents)
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
        return Record(head(), deps)

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


def adopt_record(out: Path) -> int:
    """Write the `RECORD_OUT` under `out` as the dependency record, where
    its commit is `HEAD`."""
    path = out.resolve() / "gate" / RECORD_OUT
    if not path.exists():
        print(mctx("record: no {path} stands, so the dependency record at {deps} stays as "
                   "it is").format(path=path, deps=deps_file()))
        return 0
    record = Record.read(path)
    at = head()
    if record.commit != at:
        print(mctx("record: {path} records {commit}, and HEAD is {head}").format(
            path=path, commit=record.commit[:12], head=at[:12]), file=sys.stderr)
        return 1
    record.write(deps_file())
    print(mctx("record: the dependency record of {commit} is written to {deps}").format(
        commit=record.commit[:12], deps=deps_file()))
    return 0


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
    picked.add_argument("--affected", metavar="BASE",
                        help="with --outputs-only, run only the commands that the change "
                             "from the commit BASE, which it branched from, can affect")
    picked.add_argument("--record-deps", action="store_true",
                        help="with --outputs-only, trace every command and write the "
                             "dependency record")
    ap.add_argument("--coverage", action="store_true",
                    help="with --outputs-only, trace every command run, writing its coverage "
                         "data and dependencies under the out-dir")
    ap.add_argument("--accepted", type=Path, default=ACCEPTED,
                    help="the accepted directory (default: tests/gate/accepted)")
    ap.add_argument("--adopt-record", action="store_true",
                    help="write the dependencies an --affected run traced under the out-dir "
                         "as the dependency record, and run no command")
    a = ap.parse_args(argv)
    if a.adopt_record:
        if a.cmds or a.accept or a.replace or a.outputs_only or a.affected is not None \
                or a.record_deps or a.coverage or a.accepted != ACCEPTED:
            ap.error(mctx("--adopt-record runs no command, so it takes no command and "
                          "no other option"))
        return adopt_record(a.out)
    if a.replace and not a.accept:
        ap.error("--replace is given without --accept")
    if a.accept and a.outputs_only:
        ap.error("--accept writes the cold times, which --outputs-only does not judge")
    if (a.affected is not None or a.record_deps or a.coverage) and not a.outputs_only:
        ap.error(mctx("--affected, --record-deps and --coverage each run a part or a trace "
                      "of the sequence, whose times do not compare, so each needs "
                      "--outputs-only"))
    unknown = [c for c in a.cmds if c not in COMMANDS]
    if unknown:
        ap.error(f"no gate command named {', '.join(unknown)}")
    if a.record_deps and a.cmds:
        ap.error(mctx("--record-deps records every command, so it takes no command"))
    if a.record_deps and not head_clean():
        ap.error(mctx("--record-deps records the lines of HEAD, and the checkout changes "
                      "a tracked file against it"))
    cmds = [COMMANDS[c] for c in a.cmds] or list(COMMANDS.values())
    keys = keys_of(cmds)
    if a.affected is not None:
        keys, said = affected(cmds, a.affected)
        print(said, flush=True)
    records = a.affected is not None and keys == keys_of(COMMANDS.values()) and head_clean()
    gate = Gate(a.out, a.accepted.resolve(), timed=not a.outputs_only,
                traced=a.record_deps or a.coverage or records)
    if a.accept:
        if gate.dir.exists():
            ap.error(f"{gate.dir} exists; give an empty out-dir")
        a.accepted.mkdir(parents=True, exist_ok=True)
    with rwlock.held(rwlock.Hold.EXCLUSIVE if gate.timed else rwlock.Hold.SHARED):
        if a.accept:
            print(f"load before: {load()}", flush=True)
        lines = gate.run(cmds, keys)
        if a.accept:
            print(f"load after: {load()}")
    for ln in lines:
        print(ln)
    counts = {k: sum(ln.kind is k for ln in lines) for k in gate.kinds()}
    print("gate: " + ", ".join(f"{n} {k}" for k, n in counts.items()))
    record_to = deps_file() if a.record_deps else gate.dir / RECORD_OUT if records else None
    if record_to is not None:
        gate.record().write(record_to)
        print(mctx("deps: the dependencies of {n} commands are written to {path}").format(
            n=len(keys), path=record_to))
    if a.accept:
        times, outputs = gate.accept(a.replace)
        print(f"baseline: {times} accepted times written to {gate.times_file}, "
              f"and {outputs} new accepted outputs to {a.accepted}")
        return 0
    return 1 if any(counts.values()) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
