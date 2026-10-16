"""The checks `merge_change.py` runs on a change: the paths
that call for the code checks, the files each code check takes, and the
runs of the checks in a tree."""

import contextlib
import fnmatch
import subprocess
import sys
import threading
import tomllib
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from dependents import PYTHON_SUFFIX, Graph, Reach

from cli.common import SOURCES
from controlled_markdown import mctx
from engine import checkout, duration
from operations.merging import CHECK_FAILED, PREFIX, check_name

CODE_DIRS = ("src", "scripts", "tests", "data/tasks")
"""The directories a change under which runs the code checks."""

CODE_FILES = ("pyproject.toml", "uv.lock")
"""The files that set the environment every code check runs in."""

TYPE_FILES = (".pyi", "py.typed")
"""The endings of the paths, besides Python files, whose content pyright
reads for the types of the files it checks."""

PYRIGHT = ("uv", "run", "pyright")
PYTEST = ("uv", "run", "pytest", "-q")

TEST_FILES = ["test_*.py", "*_test.py"]
"""The names of the files pytest collects tests from where
`python_files` of `pyproject.toml` gives none: pytest's default."""

TAIL = 40
"""Lines of a failed command's output a refusal shows."""


@dataclass(frozen=True)
class Check:
    """A check's command `argv`, with the files it takes after it."""
    argv: tuple[str, ...]
    files: tuple[str, ...] = ()

    @property
    def command(self) -> tuple[str, ...]:
        return (*self.argv, *self.files)

    @property
    def name(self) -> str:
        return check_name(self.argv, self.files)


def said(done: subprocess.CompletedProcess[str]) -> str:
    """What a command wrote, its last `TAIL` lines."""
    lines = (done.stdout + done.stderr).strip().splitlines()
    return "\n".join(lines[-TAIL:]) or f"exit status {done.returncode}"


def code_paths(tree: Path, main: Path, touched: set[str]) -> set[str]:
    """The paths of `touched` whose content the results of pyright and
    pytest can depend on. A path `SOURCES` matches is found in `tree`, where the
    change adds or edits it, or in the main worktree `main`, where the
    change deletes it."""
    sources = {str(p.relative_to(root)) for root in (tree, main)
               for pattern in SOURCES for p in root.glob(pattern)}
    return {p for p in touched
            if p in CODE_FILES or p in sources
            or any(p.startswith(f"{d}/") for d in CODE_DIRS)}


def code_checks(tree: Path, main: Path, touched: set[str]) -> list[Check]:
    """The code checks of a change that touches `touched`, with the files
    each takes, as the `--help` of `merge_change.py` gives them."""
    code = code_paths(tree, main, touched)
    if not code:
        return []
    config = tomllib.loads((tree / "pyproject.toml").read_text())["tool"]
    graph = Graph(tree, touched)
    checks: list[Check] = []
    if any(p in CODE_FILES or p.endswith(TYPE_FILES) for p in touched):
        checks.append(Check(PYRIGHT))
    else:
        checked = config["pyright"]
        files = {p for p in graph.dependents(Reach.IMPORTS)
                 if under(p, checked["include"]) and not under(p, checked["exclude"])}
        if files:
            checks.append(Check(PYRIGHT, tuple(sorted(files))))
    if any(not p.endswith(PYTHON_SUFFIX) for p in code):
        checks.append(Check(PYTEST))
    else:
        collected = config["pytest"]["ini_options"]
        tests = {p for p in graph.dependents(Reach.RUN)
                 if under(p, collected["testpaths"])
                 and any(fnmatch.fnmatchcase(Path(p).name, t)
                         for t in collected.get("python_files", TEST_FILES))}
        if tests:
            checks.append(Check(PYTEST, tuple(sorted(tests))))
    return checks


def under(path: str, patterns: Sequence[str]) -> bool:
    """Whether `path`, or a directory above it, matches one of `patterns`,
    paths and glob patterns from the checkout's root."""
    parents = [str(p) for p in Path(path).parents][:-1]
    return any(fnmatch.fnmatchcase(d, pattern.rstrip("/"))
               for d in [path, *parents] for pattern in patterns)


def run_in(tree: Path, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """A `uv run` command in `tree`, in that tree's own environment."""
    return subprocess.run(list(argv), cwd=tree, env=checkout.tree_env(), capture_output=True,
                          text=True)


def timed(step: str) -> contextlib.AbstractContextManager[None]:
    """A step of `merge_change.py`, which writes its step line
    (`engine.duration.STEP`) as it ends."""
    return duration.step("merge_change", step)


def run_check(tree: Path, argv: Sequence[str], shown: str) -> subprocess.CompletedProcess[str]:
    """A check run as `run_in` runs a command, each line it writes on stderr
    written on this script's stderr as it comes, timed as the step
    `shown`."""
    with timed(shown):
        proc = subprocess.Popen(list(argv), cwd=tree, env=checkout.tree_env(), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        assert proc.stdout is not None and proc.stderr is not None
        stdout = proc.stdout
        out: list[str] = []
        reader = threading.Thread(target=lambda: out.append(stdout.read()))
        reader.start()
        err: list[str] = []
        for line in proc.stderr:
            print(line, end="", file=sys.stderr, flush=True)
            err.append(line)
        reader.join()
        return subprocess.CompletedProcess(list(argv), proc.wait(), "".join(out), "".join(err))


def failures(tree: Path, checks: Sequence[Check]) -> list[str]:
    """Run `checks` in `tree` concurrently: the output of each that fails."""
    shown = [c.name for c in checks]
    for s in shown:
        print(PREFIX + mctx("running {s}").format(s=s), flush=True)
    with ThreadPoolExecutor(max_workers=max(1, len(checks))) as pool:
        dones = list(pool.map(lambda c, s: run_check(tree, c.command, s), checks, shown))
    return [CHECK_FAILED.format(s=s) + "\n" + said(done)
            for s, done in zip(shown, dones, strict=True) if done.returncode != 0]
