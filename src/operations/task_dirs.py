"""Where each task's work and claim stand in the main worktree, and the
record of the `restore` calls that `operations.task_work` writes there."""

import json
import re
from pathlib import Path

from engine.checkout import REPORTS
from operations.state import Restore

CLAIM = "claim"


REFINE_STEM = r"refine-\d+"


def refine_report(name: str) -> bool:
    return re.fullmatch(REFINE_STEM + r"\.md", name) is not None


def create_pass_file(name: str) -> bool:
    """Whether the entry of a reports directory is the Create report, a
    Refine report, or the issue notes (`progress-<report name>`) of the
    Create pass or of a Refine pass."""
    return (name in ("create.md", "progress-create.md") or refine_report(name)
            or re.fullmatch("progress-" + REFINE_STEM + r"\.md", name) is not None)


def tasks_work(main: Path) -> Path:
    """The directory of each task's work and claim, in the main worktree
    `main`."""
    return main / "work" / "task"


def task_reports(main: Path, task: str) -> Path:
    """The task's reports directory in the main worktree `main`."""
    return main / REPORTS / task


def restores_file(main: Path) -> Path:
    """The file that records each `restore` call on any task, one JSON
    object per line, in the main worktree `main`."""
    return tasks_work(main).parent / "restores"


def restore_records(text: str) -> dict[str, tuple[Restore, ...]]:
    """The `restore` calls the text of `restores_file` records, by task,
    each task's in order."""
    out: dict[str, list[Restore]] = {}
    rows = text.splitlines(keepends=True)
    for i, row in enumerate(rows):
        try:
            r = json.loads(row)
        except json.JSONDecodeError:
            if i == len(rows) - 1 and not row.endswith("\n"):
                continue
            raise
        out.setdefault(r["task"], []).append(Restore(float(r["time"]), r["argument"]))
    return {task: tuple(found) for task, found in out.items()}
