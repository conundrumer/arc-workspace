"""The witness of a stored value: a train input turned or mirrored by a
D4 element, or with a stored color swapped for a free one, on which the
relation's value differs, and the search for it."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from checker.branches.cases import counterpart, ordered, with_line
from checker.branches.witnesses import (
    BuiltBy,
    NoFit,
    swap_entry,
    witness_divergence,
    witness_targets,
)
from checker.finding import AtRelation, Finding, RunKind
from checker.judged import Swap, no_result, swaps
from checker.runs import Runs
from checker.store.survey import Found, SearchEnd, case_key, projection
from engine import Grid, RunFailure
from engine.program import grid_size
from engine.quotes import quotes
from solver.aggregate import Solver
from solver.case_types import case_types
from solver.outcome import Assignment, Grids
from engine.program import as_grid
from solver.run_parts import case_reading
from solver.witness import Entry


class D4(StrEnum):
    """The seven D4 elements other than the identity."""

    CW = "CW"
    HT = "HT"
    CC = "CC"
    LR = "LR"
    TB = "TB"
    DG = "DG"
    AD = "AD"


type Change = D4 | Swap
"""How a witness grid comes from a train input."""


def d4_images(grid: Grid) -> list[tuple[D4, Grid]]:
    """The seven other images of a grid under D4."""
    g = [list(r) for r in grid]
    h, w = grid_size(g)
    rot = [[g[h - 1 - r][c] for r in range(h)] for c in range(w)]

    def lr(x: list[list[int]]) -> list[list[int]]:
        return [row[::-1] for row in x]

    def tb(x: list[list[int]]) -> list[list[int]]:
        return x[::-1]

    def tr(x: list[list[int]]) -> list[list[int]]:
        return [list(c) for c in zip(*x)]

    images = {D4.CW: rot, D4.HT: tb(lr(g)), D4.CC: tb(lr(rot)),
              D4.LR: lr(g), D4.TB: tb(g), D4.DG: tr(g), D4.AD: tb(lr(tr(g)))}
    return [(d, as_grid(images[d])) for d in D4]


@dataclass(frozen=True)
class Move:
    """The grid on which a relation's value differs: the train input it
    comes from, the D4 element or the color swap that made it, and
    whether the first case that takes the value gives it unchanged with
    the relation derived."""

    index: int
    change: Change
    grid: Grid
    identity: bool


@dataclass(frozen=True)
class FailedRun:
    """The first run of the witness search that failed: the grid it ran
    on, and the failure."""

    index: int
    change: Change
    failure: RunFailure


@quotes("principles.md", "Witnesses",
        "A branch's witnesses are divergence witnesses between its model "
        "and the concept branch's model.")
def find_witness(runs: Runs, solver: Solver, f: Found) -> Finding | None:
    """The first grid on which the value differs and a case the survey
    looks with (`witness_targets`, among the cases that take the value)
    gives the output a witness needs (`witness_divergence`): the D4 images
    of each train input in turn, then a color swap of each. A grid the
    relation stands empty on holds no value. It sets `Found.unseparated`
    and `Found.failed`, and records in `Found.ended` how it ended
    (`SearchEnd`, `NoFit`). The failure of the run that enumerates the cases with
    the branch standing, where it fails."""
    task = solver.task
    assert task is not None
    branch = f.name
    lined = solver if f.line is not None else with_line(solver, branch)
    every = runs.cases if f.line is not None else runs.lined(lined)
    if not isinstance(every, tuple):
        f.ended = SearchEnd.CASES_FAILED
        return no_result(every, RunKind.CASE, None, AtRelation(f.relation))
    cases = [c for c in ordered(solver, every, branch)
             if not f.case_values or c.base in f.bases]
    if not cases:
        f.ended = SearchEnd.UNTAKEN
        return None
    models = witness_targets(runs, lined, cases, branch)
    if not models:
        f.ended = NoFit.NO_FIT
        return None
    model = models[0]
    other = counterpart(model, branch)
    held_by_case = case_reading(solver, f.relation)
    types, case_cols = held_by_case.types, held_by_case.case
    grids: list[tuple[int, Change, Grid]] = []
    for i, ex in enumerate(task.train):
        grids += [(i, d, g) for d, g in d4_images(as_grid(ex.input))]
    grids += [(s.index, s, s.grid) for s in swaps(runs.engine, solver, task, cases)]
    for index, change, grid in grids:
        got = runs.defined_relations(grid, [f.relation])
        if isinstance(got, Mapping):
            value = projection(got[f.relation], f, case_key(
                case_types(solver), types, case_cols), types)
            if value == f.family:
                continue
            apart = witness_divergence(runs, lined, models, branch, grid,
                                       Assignment(()))
            if apart is None:
                f.unseparated = (model, other)
                continue
            if isinstance(apart, tuple):
                failure = None
            else:
                failure = apart
        else:
            failure = got
        if failure is not None:
            f.failed = f.failed or FailedRun(index, change, failure)
            continue
        out = runs.outcomes_of(lined, [other], grid, Assignment(()))[other]
        f.move = Move(index, change, grid,
                      isinstance(out, Grids) and out.grids == (grid,))
        f.ended = SearchEnd.FOUND
        made = swap_entry(runs, lined, f.case_id, branch, index, change,
                          grid, every)
        f.built = made if isinstance(made, Entry) else None
        f.built_by = BuiltBy(lined, every)
        if not isinstance(made, Entry):
            return no_result(made, RunKind.WITNESS, None,
                             AtRelation(f.relation))
        return None
    if f.failed is not None:
        f.ended = SearchEnd.FAILED
    elif f.unseparated is not None:
        f.ended = SearchEnd.UNSEPARATED
    else:
        f.ended = SearchEnd.UNCHANGED
    return None

