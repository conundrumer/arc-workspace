"""The pyright and pytest checks of a change: the paths that call for
them and the files each takes; the paths a change touches; and the runs
of checks in a tree, which `merge_steps.py` also uses for the checks of a
merge.

    uv run python scripts/change_checks.py

Run in a change's worktree, the command runs there the pyright and pytest
checks that the change calls for:

    uv run pyright [<file> ...]
    uv run pytest -q [<file> ...]

It takes as touched the paths outside `work` whose content differs from
the merge base of `master` and `HEAD`, committed or not. A check runs
where the change touches a path whose content its results can depend on:
a path under src/, scripts/, tests/, data/tasks/ or tools/console/, one
`cli.common.SOURCES` matches, pyproject.toml or uv.lock, apart from each
Python file that stands at the merge base and whose edits change nothing
but bare string statements, blank lines, comments that hold no
type-checker directive, and argparse help values that are plain strings
(`gating.edits.same_code`). A comment that holds such a directive counts
with the code of its line, and an import counts as code, since an import
edit can remove a name a module uses. A source file the change deletes is
found in the main tree.

Pyright checks each file of its `include` from which a Python file the
change touches is reached along `import` statements, and pytest runs each
test file from which one is reached along the loads of code a run can
make (`dependents`). Pyright checks the whole tree where the change
touches pyproject.toml, uv.lock, or a `.pyi` or `py.typed` file, and
pytest runs every test where it touches one of those paths that is no
Python file. A check with no file to take does not run, and the lines of
the command name a check that takes files by its command and the number
of its files.

Exit status: 0 where each check passes or no check runs, 1 where one
fails, with the output of each that fails.
"""

import argparse
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

from change_worktree import as_copied
from dependents import PYTHON_SUFFIX, Graph, Reach

from cli.common import stamped_paths
from controlled_markdown import mctx
from engine import checkout, duration
from gating.edits import same_code
from operations.merging import CHECK_FAILED, PREFIX, TOOL, check_name
from operations.worktrees import BASE

CODE_DIRS = ("src", "scripts", "tests", "data/tasks", "tools/console")
"""The directories a change under which calls for the code checks."""

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


def outside_work() -> tuple[str, str, str]:
    """The pathspec of every path of a worktree but `work` and what lies
    under it (`checkout.work`)."""
    name = checkout.work().name
    glob = f"{name[:-1]}[{name[-1]}]"
    return (".", f":(exclude,top,glob){glob}", f":(exclude,top,glob){glob}/**")


def changed_outside_work(worktree: Path, base: str) -> list[str]:
    """The paths of `worktree` outside `work` (`outside_work`) whose
    content differs from the commit `base` (`checkout.changed_paths`),
    sorted, apart from each untracked file that `change_worktree.as_copied`
    gives."""
    copied = as_copied(worktree)
    return sorted(c.path for c in checkout.changed_paths(worktree, base, *outside_work())
                  if not (c.change is checkout.Change.UNTRACKED and c.path in copied))


def merge_base(worktree: Path) -> str:
    """The commit the change of `worktree` stands on: the merge base of
    `BASE` and its `HEAD`."""
    return checkout.git_out(worktree, "merge-base", BASE, "HEAD").strip()


def code_paths(tree: Path, main: Path, touched: set[str]) -> set[str]:
    """The paths of `touched` whose content the results of pyright and
    pytest can depend on. A path `stamped_paths` gives is found in `tree`, where the
    change adds or edits it, or in the main worktree `main`, where the
    change deletes it."""
    sources = stamped_paths(tree) | stamped_paths(main)
    return {p for p in touched
            if p in CODE_FILES or p in sources
            or any(p.startswith(f"{d}/") for d in CODE_DIRS)}


def same_code_paths(tree: Path, base: str, touched: set[str]) -> set[str]:
    """The Python files of `touched` that stand at the commit `base` and in
    `tree` and whose text in `tree` gives pyright and pytest the code their
    text at `base` gives (`gating.edits.same_code`)."""
    python = sorted(p for p in touched if p.endswith(PYTHON_SUFFIX) and (tree / p).is_file())
    if not python:
        return set()
    at_base = set(checkout.git_out(tree, "ls-tree", "--name-only", base, "--", *python).splitlines())
    return {p for p in python if p in at_base and same_code(
        p, checkout.git_out(tree, "show", f"{base}:{p}"), (tree / p).read_text())}


def code_checks(tree: Path, main: Path, base: str, touched: set[str]) -> list[Check]:
    """The code checks of changes from the commit `base` that touch
    `touched`, with the files each takes, as the module docstring gives
    them."""
    touched = touched - same_code_paths(tree, base, touched)
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
    return duration.step(TOOL, step)


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


NO_CHECK = mctx("the change calls for no pyright or pytest check")


def main(argv: Sequence[str]) -> int:
    argparse.ArgumentParser(description=__doc__,
                            formatter_class=argparse.RawDescriptionHelpFormatter).parse_args(argv)
    tree = Path(checkout.git_out(Path.cwd(), "rev-parse", "--show-toplevel").strip())
    base = merge_base(tree)
    checks = code_checks(tree, checkout.main_worktree(tree), base,
                         set(changed_outside_work(tree, base)))
    if not checks:
        print(NO_CHECK)
        return 0
    failed = failures(tree, checks)
    print("\n".join(failed), end="\n" if failed else "")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
