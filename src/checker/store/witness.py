"""The witness of a stored value: a train input turned or mirrored by a
D4 element, or with a stored color swapped for a free one, on which the
relation's value differs, and the search for it."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from checker.branches.cases import (
    branch_models,
    counterpart,
    ordered,
    with_line,
)
from checker.branches.witnesses import (
    BuiltBy,
    NoFit,
    fitting,
    fitting_both,
    looked_with,
    swap_entry,
    witness_divergence,
    witness_targets,
)
from checker.finding import AtRelation, Finding, RunKind
from checker.judged import Swap, no_result, stored_colors, swaps
from checker.runs import Runs
from checker.store.survey import Found, SearchEnd, case_key, projection
from engine import Grid, RelationName, RunFailure
from engine.program import grid_size
from engine.quotes import quotes
from solver import witnessed_cases
from solver.aggregate import Solver
from solver.case_types import case_types
from solver.model import Case
from solver.outcome import Assignment, Grids
from engine.program import as_grid
from solver.per_case import case_reading
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


def _taking(solver: Solver, every: Sequence[Case], f: Found) -> list[Case]:
    """The cases of `every` that take the value's branch (`ordered`), of
    the bases the value stands for where its rows hold a case column."""
    return [c for c in ordered(solver, every, f.name)
            if not f.case_values or c.base in f.bases]


def _model_alone(runs: Runs, solver: Solver, lined: Solver,
                 every: tuple[Case, ...], taking: Sequence[Case], f: Found
                 ) -> Case | None:
    """The case the search looks with alone, found without the witnessed
    cases of `lined`, the solver with the value's line standing. `every`
    is every case of `lined`, and `taking` those of them that take the
    branch (`_taking`). The case is the branch's model among `taking`,
    where the witnessed cases keep it as a branch's model
    (`solver.witnessed_cases.branch_models`) and it fits the pairs with its
    counterpart (`fitting_both`). The witnessed cases that take the
    branch then hold it, so it is their model too, and `witness_targets`
    gives it alone (`looked_with`). None otherwise."""
    models = branch_models(solver, taking, f.name)
    if not models or models[0] not in witnessed_cases.branch_models(lined, every):
        return None
    model = models[0]
    fit = fitting_both(runs, lined, models, f.name)
    return model if looked_with([model], fit) == [model] else None


def _swap_cases(runs: Runs, solver: Solver, lined: Solver,
                taking: Sequence[Case], f: Found, model: Case) -> list[Case]:
    """The cases whose stored colors give the color swaps (`swaps`), where
    the search looks with `model` alone (`_model_alone`): `model`, where
    its stored colors are those of `taking`, every case of `lined` that
    takes the branch, so that the witnessed cases that take it, which hold
    `model`, store those colors too; else those witnessed cases."""
    if stored_colors(runs.engine, solver, [model]) == stored_colors(
            runs.engine, solver, taking):
        return [model]
    return _taking(solver, _judged(runs, lined), f)


def _judged(runs: Runs, lined: Solver) -> tuple[Case, ...]:
    """The judged cases of `lined` (`Runs.lined`), whose enumeration
    the search read already."""
    got = runs.lined(lined)
    assert isinstance(got, tuple)
    return got


@quotes("principles.md", "Witnesses",
        "A branch's witnesses are divergence witnesses between its model "
        "and the concept branch's model.")
def find_witness(runs: Runs, solver: Solver, f: Found,
                 relations: Sequence[RelationName]) -> Finding | None:
    """The first grid on which the value differs and a case the survey
    looks with (`witness_targets`, among the cases that take the value)
    gives the output a witness needs (`witness_divergence`): the D4 images
    of each train input in turn, then a color swap of each. A grid the
    relation stands empty on holds no value. It sets `Found.unseparated`
    and `Found.failed`, and records in `Found.ended` how it ended
    (`SearchEnd`, `NoFit`). The failure of the run that enumerates the cases with
    the branch standing, where it fails.

    The value on a grid is read from one run of `relations`, the
    relations of every value the survey searches, so that the searches
    share it. For a value with no `@store` line, the witnessed cases of
    the solver with its line standing are computed only where the search
    reads them: not where no case of that solver takes the branch, since
    they are among its cases; and where the model looks alone
    (`_model_alone`), only for the color swaps where their stored colors
    can differ from the model's (`_swap_cases`), and for the entry of a
    witness found."""
    task = solver.task
    assert task is not None
    branch = f.name
    lined = solver if f.line is not None else with_line(solver, branch)
    every = runs.cases if f.line is not None \
        else runs.lined_runs(lined).solver_cases
    if not isinstance(every, tuple):
        f.ended = SearchEnd.CASES_FAILED
        return no_result(every, RunKind.CASE, None, AtRelation(f.relation))
    judged = every if f.line is not None else None
    taking = _taking(solver, every, f)
    alone = None if judged is not None or not taking \
        else _model_alone(runs, solver, lined, every, taking, f)
    if alone is None and judged is None and taking:
        judged = _judged(runs, lined)
        taking = _taking(solver, judged, f)
    if not taking:
        f.ended = SearchEnd.UNTAKEN
        return None
    if alone is not None:
        models = [alone]
        swap_from = _swap_cases(runs, solver, lined, taking, f, alone)
    else:
        models = witness_targets(runs, lined, taking, branch)
        swap_from = taking
        if not models:
            f.ended = NoFit.NO_FIT if fitting(runs, lined, taking) \
                else SearchEnd.UNFIT
            return None
    model = models[0]
    other = counterpart(model, branch)
    held_by_case = case_reading(solver, f.relation)
    types, case_cols = held_by_case.types, held_by_case.case
    grids: list[tuple[int, Change, Grid]] = []
    for i, ex in enumerate(task.train):
        grids += [(i, d, g) for d, g in d4_images(as_grid(ex.input))]
    grids += [(s.index, s, s.grid)
              for s in swaps(runs.engine, solver, task, swap_from)]
    for index, change, grid in grids:
        got = runs.defined_relations(grid, relations)
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
        if judged is None:
            judged = _judged(runs, lined)
        made = swap_entry(runs, lined, f.case_id, branch, index, change,
                          grid, judged)
        f.built = made if isinstance(made, Entry) else None
        f.built_by = BuiltBy(lined, judged)
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

