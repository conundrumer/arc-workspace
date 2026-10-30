"""The determination plan's lines, kept under `checkout.cache()` beside the
Souffle run cache, so that a rerun on the same inputs prints them and makes
no run.

A plan that holds a run that reached the wall limit is not kept, as the run
cache keeps no such run: the wall limit depends on the machine's load. A
kept plan is written whole or not at all (`engine.memo.read_or_make`)."""

import hashlib
from dataclasses import fields, is_dataclass
from pathlib import Path

from arc.task import task_file
from checker.determination_plan import survey_determination_plan
from checker.render.surveys import render_determination_plan
from checker.runs import Runs
from engine import WallLimit, checkout
from engine.memo import hash_files, read_or_make
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
    def made() -> tuple[list[str], bool]:
        result = survey_determination_plan(runs.solver, runs, moves=True)
        return (render_determination_plan(runs.solver, result, verdicts),
                not reaches_wall(result))

    return read_or_make(
        checkout.cache() / PLAN_DIR / _key(runs, source, stamp, verdicts),
        lambda data: data.decode().split("\n"),
        lambda lines: "\n".join(lines).encode(), made)

def _key(runs: Runs, source: Path, stamp: str, verdicts: bool) -> str:
    """The hash of what the plan's lines are made from, what runs the
    programs among them (`engine.Engine.runtime_identity`)."""
    task_id = runs.solver.task_id
    h = hashlib.sha256()
    h.update(f"{stamp}\0{runs.solver.stem}\0{runs.limits!r}\0{verdicts}"
             .encode())
    h.update(b"\0" + runs.solver.engine.runtime_identity() + b"\0")
    hash_solver_files(h, source, task_id)
    return h.hexdigest()


def hash_solver_files(h: "hashlib._Hash", source: Path, task_id: str
                      ) -> None:
    """Adds to `h` the solver file `source`, and the task file and the
    witness file of its task `task_id`, each by its path from the
    checkout's root where it stands under it (`checkout.shown`), so that
    two checkouts with the same files by content give the same hash."""
    hash_files(h, ((str(checkout.shown(p, checkout.ROOT)), p)
                   for p in (source.resolve(), task_file(task_id),
                             witness.path(task_id))))


def reaches_wall(x: object) -> bool:
    """Whether `x` holds a run that reached the wall limit."""
    if isinstance(x, WallLimit):
        return True
    if isinstance(x, tuple | list | frozenset | set):
        return any(reaches_wall(y) for y in x)
    if isinstance(x, dict):
        return any(reaches_wall(y) for y in x.values())
    if is_dataclass(x) and not isinstance(x, type):
        return any(reaches_wall(getattr(x, f.name)) for f in fields(x))
    return False

