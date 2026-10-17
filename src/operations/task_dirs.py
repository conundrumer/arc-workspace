"""Where each task's work and claim stand in the main worktree, and the
record of the `restore` calls that `operations.task_work` writes there."""

import json
import re
from pathlib import Path

from operations.state import Restore

CLAIM = "claim"


def refine_report(name: str) -> bool:
    return re.fullmatch(r"refine-\d+\.md", name) is not None


def tasks_work(main: Path) -> Path:
    """The directory of each task's work and claim, in the main worktree
    `main`."""
    return main / "work" / "task"


def restores_file(main: Path) -> Path:
    """The file that records each `restore` call on any task, one JSON
    object per line, in the main worktree `main`."""
    return tasks_work(main).parent / "restores"


def restore_records(text: str) -> dict[str, tuple[Restore, ...]]:
    """The `restore` calls the text of `restores_file` records, by task,
    each task's in order."""
    out: dict[str, list[Restore]] = {}
    for r in map(json.loads, text.splitlines()):
        out.setdefault(r["task"], []).append(Restore(float(r["time"]), r["argument"]))
    return {task: tuple(found) for task, found in out.items()}
