"""Each solver's lint result, kept under `checkout.cache()` beside the
Souffle run cache, so that a later lint on the same inputs prints it and
loads no solver.

A result's key covers every file of the worktree that git lists, other
than the solver files, witness files and task files, and of those it
covers the solver's own. A lint check that reads the file of another
solver, task or witness than its own adds that file to the solver's part
of the key (`_key`).

A result that holds a run that reached the wall limit is not kept, as the
run cache keeps no such run. A kept result is written whole or not at all
(`engine.memo.write_whole`)."""

import hashlib
import pickle
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from arc.task import TASKS_DIR
from checker.finding import Finding, is_hint
from checker.plan_cache import hash_solver_files, reaches_wall
from checker.render.commands import gathered_lint
from engine import Engine, Limits, checkout
from engine.memo import write_whole
from solver.aggregate import Solver

LINT_DIR = "lint"
"""The directory of the kept results under `checkout.cache()`."""

UNKEYED = (checkout.SOLVERS, checkout.WITNESSES,
           TASKS_DIR.relative_to(checkout.ROOT))
"""The directories whose files a result's key covers only as the solver's
own."""


@dataclass(frozen=True)
class LintResult:
    """One solver's lint: the lines of its findings and of its hints, as
    the report over several solvers prints them, and the findings."""

    finding_lines: tuple[str, ...]
    hint_lines: tuple[str, ...]
    findings: tuple[Finding, ...]

    def lines(self, hints: bool) -> tuple[str, ...]:
        """The lines of the hints, or of the other findings."""
        return self.hint_lines if hints else self.finding_lines

    def count(self, hints: bool) -> int:
        """How many hints, or other findings, the lint gives."""
        return sum(is_hint(f) == hints for f in self.findings)


def lint_result(solver: Solver, findings: Sequence[Finding]) -> LintResult:
    """The lint result of `solver`'s `findings`."""
    def lines(hints: bool) -> tuple[str, ...]:
        return tuple(gathered_lint(
            [(solver, [f for f in findings if is_hint(f) == hints])]))
    return LintResult(lines(False), lines(True), tuple(findings))


def kept_lint(source: Path, task_id: str, engine: Engine, limits: Limits,
              hints: bool, make: Callable[[], LintResult]) -> LintResult:
    """The lint result of the solver file `source`, of the task `task_id`:
    the one kept under the key of what it is made from, else the one `make`
    gives now."""
    path = checkout.cache() / LINT_DIR / _key(source, task_id, engine,
                                              limits, hints)
    try:
        kept = pickle.loads(path.read_bytes())
    except FileNotFoundError:
        pass
    else:
        if isinstance(kept, LintResult):
            return kept
    result = make()
    if not reaches_wall(result.findings):
        path.parent.mkdir(parents=True, exist_ok=True)
        write_whole(path, pickle.dumps(result))
    return result


def _key(source: Path, task_id: str, engine: Engine, limits: Limits,
         hints: bool) -> str:
    h = hashlib.sha256()
    h.update(f"{_shared()}\0{limits!r}\0{hints}\0".encode())
    h.update(engine.runtime_identity() + b"\0")
    hash_solver_files(h, source, task_id)
    return h.hexdigest()


@cache
def _shared() -> str:
    """The hash of the path and content of each file that git lists in
    the worktree, tracked or untracked and not ignored, outside `UNKEYED`:
    a listed file that is gone, or a submodule, is left out."""
    listed = checkout.git_out(
        checkout.ROOT, "ls-files", "-co", "--exclude-standard", "-z", "--",
        ".", *(f":!{d.as_posix()}" for d in UNKEYED))
    files: dict[Path, bytes] = {}
    for name in sorted(filter(None, listed.split("\0"))):
        path = checkout.ROOT / name
        try:
            files[path] = path.read_bytes()
        except OSError:
            pass
    return checkout.files_digest(files)
