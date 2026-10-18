"""What a gate command depends on, from a traced run of it."""

import ast
import json
import os
import runpy
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import coverage
from coverage.sysmon import SysMonitor

import souffle.run
from engine import checkout
from gating.hunks import PY_SUFFIXES

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
