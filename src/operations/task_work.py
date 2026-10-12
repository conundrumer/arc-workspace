"""The work on a task that a solver pipeline sets aside in the main worktree
before an Analyze or a Create pass, and puts back with the release of the
task's claim once the pipeline ends, as the section `Passes on a task` of
[Launching notes](prompts/agents/notes/launching.md#passes-on-a-task)
gives. `scripts/operate.py set-aside` and `restore` run these, as steps
`passes` prints; this is the one module of the package that writes."""

import re
import shutil
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout
from operations.roles import Role
from solver.vocabulary import SOLVER_SUFFIX, WITNESS_SUFFIX

BEFORE_CREATE = ("create.md", "progress.md")
"""The entries of the task's work directory a Create pass sets aside, with
each Refine report (`refine_report`)."""


def refine_report(name: str) -> bool:
    """Whether `name` is `refine-<n>.md` with `<n>` all digits."""
    return re.fullmatch(r"refine-\d+\.md", name) is not None

CLAIM = "claim"

CLAIM_HELD = mctx("the claim on task {task} fails: session {holder} holds it")


def tasks_work(main: Path) -> Path:
    """The directory of each task's work and claim, in the main worktree
    `main`."""
    return main / "work" / "task"


def claim(main: Path, task: str, session: str) -> str | None:
    """Claim the task for `session` by the exclusive create of its claim
    file, or give the session that holds it where that file stands."""
    path = tasks_work(main) / task / CLAIM
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x") as f:
            f.write(session + "\n")
    except FileExistsError:
        return path.read_text().strip()
    return None


def task_paths(task: str) -> tuple[Path, Path]:
    """The task's solver and witness file, from the root of a worktree."""
    return (checkout.SOLVERS / f"{task}{SOLVER_SUFFIX}",
            checkout.WITNESSES / f"{task}{WITNESS_SUFFIX}")


def numbered(directory: Path) -> list[int]:
    return sorted(int(p.name) for p in directory.iterdir() if p.is_dir() and p.name.isdigit())


def set_aside(main: Path, task: str, role: Role) -> Path:
    """Set aside the task's earlier work before a pass of `role`, and give
    the directory it went to."""
    work = tasks_work(main) / task
    taken = numbered(work)
    target = work / str((taken[-1] if taken else 0) + 1)
    target.mkdir()
    paths = task_paths(task)
    (target / "uncommitted.diff").write_text(
        checkout.git_out(main, "diff", "HEAD", "--", *map(str, paths)))
    for p in paths:
        if (main / p).exists():
            shutil.move(main / p, target / p.name)
    for entry in sorted(work.iterdir()):
        if entry == target or entry.name == CLAIM or entry.name.isdigit():
            continue
        if role is Role.ANALYZE or entry.name in BEFORE_CREATE or refine_report(entry.name):
            shutil.move(entry, target / entry.name)
    for p in paths:
        if checkout.git_out(main, "ls-files", str(p)).strip():
            checkout.git_out(main, "update-index", "--skip-worktree", str(p))
    return target


def restore(main: Path, task: str) -> None:
    """Move back the solver and the witness file the latest set-aside that
    holds each took, where nothing stands at its path, clear their marks,
    and remove the claim."""
    work = tasks_work(main) / task
    for p in task_paths(task):
        if not (main / p).exists():
            for n in reversed(numbered(work)):
                kept = work / str(n) / p.name
                if kept.exists():
                    shutil.move(kept, main / p)
                    break
        if checkout.git_out(main, "ls-files", str(p)).strip():
            checkout.git_out(main, "update-index", "--no-skip-worktree", str(p))
    (work / CLAIM).unlink(missing_ok=True)
