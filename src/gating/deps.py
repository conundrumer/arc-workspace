"""What a gate command depends on, from a traced run of it, and whether a
change can affect it."""

import ast
import json
import os
import re
import runpy
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

import coverage
from coverage.sysmon import SysMonitor

import souffle.run
from engine import checkout
from gating.commands import ACCEPTED, GateCommand
from gating.edits import inert

TRACE = "--trace"
"""The first argument of the gate's own call that runs one traced command
(`trace`)."""

GATE_SCRIPT = "scripts/gate.py"
"""The gate's script, from the checkout's root."""

GATE_READS = (GATE_SCRIPT, "src/gating", "pyproject.toml", "uv.lock")
"""The files and directories every command depends on outside its traced
run: the gate, which writes its arguments and normalizes its output, and
the files that set the environment `uv run` gives it."""

LIST_EVENTS = frozenset({"os.listdir", "os.scandir"})
"""The audit events that list a directory."""

PY_SUFFIXES = frozenset({".py", ".pyc"})
"""The suffixes of the files a command depends on through the lines it
runs alone. A command also reads Python files' bytes, to import them and
to key the run cache."""


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
        return {"lines": {p: ranges(ns) for p, ns in sorted(self.lines.items())},
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


def ranges(ns: Iterable[int]) -> list[list[int]]:
    """`ns` as sorted runs of consecutive numbers, each its first and last."""
    out: list[list[int]] = []
    for n in sorted(ns):
        if out and out[-1][1] == n - 1:
            out[-1][1] = n
        else:
            out.append([n, n])
    return out


def lines_of(paths: Iterable[Path]) -> dict[str, frozenset[int]]:
    """The lines the traced runs whose dependencies `paths` hold ran
    together, by their file; a path that does not stand adds no line."""
    out: dict[str, frozenset[int]] = {}
    for p in paths:
        if not p.exists():
            continue
        for f, ns in Deps.from_json(json.loads(p.read_text())).lines.items():
            out[f] = out.get(f, frozenset()) | ns
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


def pruning_lines() -> dict[str, frozenset[int]]:
    """The lines of the run cache's pruning, by their file from the
    checkout's root: those of `souffle.run.prune` and of each call to it in
    its module."""
    path = Path(souffle.run.__file__)
    rel = _in_checkout(path)
    if rel is None:
        raise RuntimeError(f"{path} stands outside the checkout")
    name = souffle.run.prune.__name__
    lines: set[int] = set()
    for n in ast.walk(ast.parse(path.read_text())):
        if (isinstance(n, ast.FunctionDef) and n.name == name) or (
                isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == name):
            lines.update(range(n.lineno, (n.end_lineno or n.lineno) + 1))
    if not lines:
        raise RuntimeError(f"{rel} holds no function {name}")
    return {rel: frozenset(lines)}


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
                            omit=[str(checkout.ROOT / p / "*") if (checkout.ROOT / p).is_dir()
                                  else str(checkout.ROOT / p) for p in GATE_READS])
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


class Hunk(NamedTuple):
    """A hunk of a `-U0` unified diff: the first line and the count of its
    old side, and of its new side, a count of 0 an insertion after, or a
    deletion after, the first line."""
    old_start: int
    old_count: int
    new_start: int
    new_count: int

    @property
    def old_end(self) -> int:
        """The last line of the old side, where its count is not 0."""
        return self.old_start + self.old_count - 1

    @property
    def new_end(self) -> int:
        """The last line of the new side, where its count is not 0."""
        return self.new_start + self.new_count - 1


@dataclass(frozen=True)
class Touched:
    """A path the change touches, how it touches it, and, for a modified
    Python file, the line ranges of its recorded text it replaces, each its
    first line and its count, a count of 0 an insertion after the first
    line, with the new side of each. `unrecorded` is a Python file that stands at the change's base
    and not at the recorded commit, whose lines no command's record
    holds. `passed` holds the index in `hunks` of each hunk `inert`
    passes."""
    path: str
    status: checkout.Change
    hunks: tuple[Hunk, ...] = ()
    unrecorded: bool = False
    passed: frozenset[int] = frozenset()

    @property
    def live(self) -> tuple[Hunk, ...]:
        return tuple(h for i, h in enumerate(self.hunks) if i not in self.passed)

    @property
    def inert(self) -> bool:
        """Whether the file has hunks and `inert` passes each of them. A
        file with no hunk is run whole (`runs_hunks`)."""
        return bool(self.hunks) and not self.live


_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.M)


def hunks_of(diff: str) -> tuple[Hunk, ...]:
    """Each hunk of the unified diff `diff`, a count git leaves out read as
    1."""
    return tuple(Hunk(int(a), int(b) if b else 1, int(c), int(d) if d else 1)
                 for a, b, c, d in _HUNK_RE.findall(diff))


def moved(ran: frozenset[int], hunks: Sequence[Hunk]) -> frozenset[int]:
    """The lines `ran` of an old text, each numbered as it stands in the
    new text that `hunks` give. A line inside a hunk's old side has no
    number in the new text, and is a fault."""
    out: set[int] = set()
    for n in ran:
        shift = 0
        for h in hunks:
            end = h.old_end if h.old_count else h.old_start
            if h.old_count and h.old_start <= n <= end:
                raise ValueError(f"line {n} stands inside the hunk {h}")
            if n > end:
                shift += h.new_count - h.old_count
        out.add(n + shift)
    return frozenset(out)


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
    not at `base` is modified where the change adds it. The hunks of a
    modified Python file are those of its diff from `base` to the checkout,
    with the old side of each numbered in the recorded text; where the file
    differs between the two commits, `renumbered` numbers them. The hunks
    from `recorded` to `base` count only where a hunk of the change meets
    them: the commits that wrote them passed their own merge's gate, whose
    accepted outputs this gate compares against. Each hunk of a path that
    stands at `base` is classified by `inert` against the `base` text, since the rules it applies are
    properties of the change's own edit."""
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
        hunks: tuple[Hunk, ...] = ()
        passed: frozenset[int] = frozenset()
        if status is checkout.Change.MODIFIED and Path(c.path).suffix in PY_SUFFIXES:
            hunks = _diff_hunks(c.path, base)
            if c.change is checkout.Change.MODIFIED:
                old = text_at(base, c.path)
                new = (checkout.ROOT / c.path).read_text().splitlines(keepends=True)
                passed = frozenset(i for i, h in enumerate(hunks) if inert(
                    c.path, old, new[h.new_start - 1:h.new_start - 1 + h.new_count], h))
            if c.path in moved:
                hunks = renumbered(hunks, _diff_hunks(c.path, recorded, base))
        out.append(Touched(c.path, status, hunks, passed=passed))
    return out


def text_at(commit: str, path: str) -> str:
    return checkout.git_out(checkout.ROOT, "show", f"{commit}:{path}")


def _diff_hunks(path: str, *commits: str) -> tuple[Hunk, ...]:
    """The `-U0` hunks of `path` from the first of `commits` to the second,
    or to the checkout where `commits` give one."""
    return hunks_of(checkout.git_out(checkout.ROOT, "diff", "-U0", "--no-color",
                                     "--no-ext-diff", *commits, "--", path))


def _old_line(n: int, since: Sequence[Hunk]) -> int:
    """The line `n` of the new text of `since`, which stands outside the
    new side of each, numbered in the old text: the inverse of `moved`."""
    shift = 0
    for r in since:
        if n > (r.new_end if r.new_count else r.new_start):
            shift += r.new_count - r.old_count
    return n - shift


def renumbered(hunks: Sequence[Hunk], since: Sequence[Hunk]) -> tuple[Hunk, ...]:
    """The hunks `hunks` of a diff from a text B, each with its old side
    numbered in the text A that the hunks `since` change into B. A line of
    B that a hunk of `since` wrote stands for the lines of A that hunk
    replaced, or for its point of insertion, so a hunk whose old side meets
    the new side of a hunk of `since` takes in that hunk's old side. An
    insertion meets a hunk of `since` where the line it follows is one that
    hunk wrote."""
    out: list[Hunk] = []
    for h in hunks:
        lo, hi = (h.old_start, h.old_end) if h.old_count else (h.old_start, h.old_start)
        met = [r for r in since if r.new_count
               and r.new_start <= hi and lo <= r.new_end]
        lines = {n for r in met for n in range(r.old_start, r.old_end + 1)}
        points = [r.old_start for r in met if not r.old_count]
        if h.old_count:
            lines |= {_old_line(n, since) for n in range(lo, hi + 1)
                      if not any(r.new_start <= n <= r.new_end for r in met)}
        elif not met:
            points.append(_old_line(h.old_start, since))
        out.append(Hunk(min(lines), max(lines) - min(lines) + 1, h.new_start, h.new_count)
                   if lines else Hunk(min(points), 0, h.new_start, h.new_count))
    return tuple(out)


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


def runs_hunks(source: str, hunks: Sequence[Hunk], ran: frozenset[int]) -> bool:
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
    for h in hunks:
        lo, hi = (h.old_start, h.old_end) if h.old_count else (h.old_start, h.old_start + 1)
        inside = [f for f in fs if f.first <= lo and hi <= f.last]
        if not inside:
            return True
        f = max(inside, key=lambda f: f.first)
        header = lo < f.body if h.old_count else h.old_start < f.body - 1
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
    which commands run it. A hunk `inert` passes affects no command, and a
    modified Python file of `GATE_READS` is run whole by every command
    through each other hunk."""
    accepted = ACCEPTED.relative_to(checkout.ROOT)
    own = {str(accepted / f"{cmd.key(stem)}.{e}") for e in cmd.exts}
    copied = [p.relative_to(checkout.ROOT) for p in cmd.copied(stem)]
    for t in touched:
        if t.unrecorded:
            return True
        if t.path in own or any(Path(t.path).is_relative_to(p) for p in copied):
            return True
        if t.inert:
            continue
        if any(Path(t.path).is_relative_to(p) for p in GATE_READS):
            return True
        if Path(t.path).suffix not in PY_SUFFIXES:
            if t.path in deps.reads or ((t.status.added or t.status is checkout.Change.DELETED)
                                        and str(Path(t.path).parent) in deps.listed):
                return True
        elif t.path in deps.lines and not t.status.added:
            if runs_hunks(recorded[t.path],
                          t.live if t.status is checkout.Change.MODIFIED else (),
                          deps.lines[t.path]):
                return True
    return False
