"""The report files of solver passes, read from the main worktree."""

import re
from pathlib import Path

from file_reads import file_text, is_dir, is_file, listed, mtime
from ticket_numbers import TICKET_NUMBER
from operations.reports import CONCEPT_FAULTS, TICKETS_FILED, section, section_items
from operations.roles import Role
from operations.state import PassReport
from operations.task_dirs import refine_report, task_reports


def pass_report(task: str, role: Role, launched: float, main: Path) -> Path | None:
    """The report file the pass of `role` on `task` wrote since its launch
    at `launched`, as `docs/handbook/procedure.md` names it: for Refine,
    the `refine-<n>.md` first written after the launch."""
    work = task_reports(main, task)
    if not is_dir(work):
        return None
    files = (sorted(work / e.name for e in listed(work) if refine_report(e.name))
             if role is Role.REFINE else [work / f"{role.value}.md"])
    written = [(mtime(p), p) for p in files if is_file(p)]
    return min(((t, p) for t, p in written if t > launched), default=(0.0, None))[1]


def pass_read(task: str, role: Role, launched: float, main: Path) -> PassReport:
    """The read of the report file of the pass (`PassReport`)."""
    path = pass_report(task, role, launched, main)
    if path is None:
        return PassReport(None, ())
    text = file_text(path)
    filed = section(text, TICKETS_FILED)
    tickets = None if filed is None else tuple(m.group(0).rstrip("_") for m in re.finditer(
        rf"(?<![\w-]){TICKET_NUMBER.pattern}_", filed))
    return PassReport(tickets, section_items(text, CONCEPT_FAULTS))


