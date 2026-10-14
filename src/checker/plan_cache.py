"""The determination plan's lines, kept under `checkout.cache()` beside the
Souffle run cache, so that a rerun on the same inputs prints them and makes
no run.

A plan that holds a run that reached the wall limit is not kept, as the run
cache keeps no such run: the wall limit depends on the machine's load. A
kept plan is written whole or not at all (`engine.memo.write_whole`)."""

import hashlib
from dataclasses import fields, is_dataclass
from pathlib import Path

from arc.task import task_file
from checker.determination_plan import survey_determination_plan
from checker.render.surveys import render_determination_plan
from checker.runs import Runs
from engine import WallLimit, checkout
from engine.memo import write_whole
from solver import witness

PLAN_DIR = "determination-plan"
"""The directory of the kept plans under `checkout.cache()`."""


def plan_lines(runs: Runs, source: Path, stamp: str, verdicts: bool
               ) -> list[str]:
    """The plan's lines (`render_determination_plan`) of the solver of
    `runs`, read from `source`: those kept under the key of what they are
    made from, else those the survey makes now. `stamp` is the hash
    of the code and the Souffle sources the run loads
    (`cli.common.stamp`)."""
    key = _key(runs, source, stamp, verdicts)
    path = checkout.cache() / PLAN_DIR / key
    try:
        return path.read_text().split("\n")
    except FileNotFoundError:
        pass
    result = survey_determination_plan(runs.solver, runs)
    lines = render_determination_plan(runs.solver, result, verdicts)
    if not _reaches_wall(result):
        path.parent.mkdir(parents=True, exist_ok=True)
        write_whole(path, "\n".join(lines).encode())
    return lines


def _key(runs: Runs, source: Path, stamp: str, verdicts: bool) -> str:
    """The hash of what the plan's lines are made from, what runs the
    programs among them (`engine.Engine.runtime_identity`). A file that
    does not stand counts as its path alone."""
    task_id = runs.solver.task_id
    h = hashlib.sha256()
    h.update(f"{stamp}\0{runs.solver.stem}\0{runs.limits!r}\0{verdicts}"
             .encode())
    h.update(b"\0" + runs.solver.engine.runtime_identity() + b"\0")
    for path in (source.resolve(), task_file(task_id),
                 witness.path(task_id)):
        h.update(b"\0" + str(path).encode() + b"\0")
        try:
            h.update(b"\1" + path.read_bytes())
        except FileNotFoundError:
            h.update(b"\0")
    return h.hexdigest()


def _reaches_wall(x: object) -> bool:
    if isinstance(x, WallLimit):
        return True
    if isinstance(x, tuple | list | frozenset | set):
        return any(_reaches_wall(y) for y in x)
    if isinstance(x, dict):
        return any(_reaches_wall(y) for y in x.values())
    if is_dataclass(x) and not isinstance(x, type):
        return any(_reaches_wall(getattr(x, f.name)) for f in fields(x))
    return False

