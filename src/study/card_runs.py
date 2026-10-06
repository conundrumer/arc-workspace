"""A card's solver run on each witness input, and the checks of the card's
captions and option cases against those runs."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from arc.task import Example
from arc.task import load as load_task
from cli.common import LIMITS, failure_lines, parse_fault, parse_grid
from cli.common import engine as _engine
from engine import Grid, RunFailure, checkout
from engine.program import as_grid
from solver.load import load
from solver.model import Case, Solver
from solver.names import name
from solver.problems import Fault, WitnessFileRole
from solver.solve import Assignment, Grids, examples, outcomes, witnessed
from solver.witness import Undefined
from study.card_spec import Card, from_root, option_of


@dataclass(frozen=True)
class Candidate:
    """One case's output on a witness input: its case, its name as the
    tool prints it (`solver.names.name`), and its grid, or the reason it
    gives none."""

    case: Case
    label: str
    grid: Grid
    error: str | None = None


def solver_file(card: Card) -> Path:
    """The card's solver file: its `solver` as a path from the repository
    root where a file stands there, else the file of that name under
    `programs/solvers/`; the task's solver where the card names none."""
    arg = card.solver or card.task_id
    name = arg if arg.endswith(".dl") else f"{arg}.dl"
    path = from_root(name)
    return path if path.exists() else checkout.solvers() / Path(name).name


def outside_solvers(path: Path) -> bool:
    """The file stands outside `programs/solvers/`, which
    `solver.load.load` reads alone."""
    return path.resolve().parent != checkout.solvers().resolve()


def run_solver(solver: Solver, grid: Grid) -> list[Candidate] | RunFailure:
    """Each witnessed case of the solver (`solver.solve.witnessed`), run
    on `grid` at the stored assignment, in the order of the cases; the
    failure of the run that enumerates the cases where it fails. A case
    whose run gives no result carries the failure's line."""
    engine = _engine()
    cases = witnessed(engine, solver, LIMITS, WitnessFileRole.TASK)
    if not isinstance(cases, tuple):
        return cases
    got = outcomes(engine, solver, cases, grid, Assignment(()), LIMITS)
    out: list[Candidate] = []
    for case in cases:
        outcome, label = got[case], name(solver, case)
        if isinstance(outcome, Grids):
            out += [Candidate(case, label, g) for g in outcome.grids]
        elif isinstance(outcome, Undefined):
            out.append(Candidate(case, label, (), "undefined"))
        else:
            out.append(Candidate(case, label, (),
                                 _failure_text(solver, outcome)))
    return out


def _failure_text(solver: Solver, failure: RunFailure | Fault) -> str:
    """What the page prints for a run that gave no result, or for a solver
    that does not parse."""
    return "\n".join(failure_lines(solver, failure))


@dataclass
class Run:
    """One witness input with what the card's solver made of it."""

    label: str
    grid: Grid
    candidates: list[Candidate] = field(default_factory=list[Candidate])
    error: str = ""


def witness_grids(card: Card) -> list[tuple[str, Grid]]:
    """(label, grid) per witness. With no witness file listed, the task's
    first train input is the witness."""
    if not card.witnesses:
        label, example = _fallback(card.task_id)
        return [(label, as_grid(example.input))]
    grids = []
    for spec_path in card.witnesses:
        path = from_root(spec_path)
        grid = parse_grid(path.read_text())
        if grid is None:
            raise ValueError(f"{path} holds no grid")
        grids.append((_listed_label(spec_path), grid))
    return grids


def _fallback(task_id: str) -> tuple[str, Example]:
    pair, example = next(examples(load_task(task_id)))
    return f"{pair.text} input", example


def _listed_label(spec_path: str) -> str:
    return from_root(spec_path).name


def drawable_labels(card: Card) -> list[str]:
    """The label of each witness the page may draw under `dropped`."""
    return [_listed_label(p) for p in card.witnesses] \
        + [_fallback(card.task_id)[0]]


def run_witnesses(card: Card) -> list[Run]:
    """The card's solver run on each witness input. A solver that does not
    parse, or whose cases no run enumerates, gives each input that
    failure's line in place of its cases."""
    solver = load(solver_file(card).stem, _engine())
    fault = parse_fault(solver)
    runs = []
    for label, grid in witness_grids(card):
        got = fault if fault is not None else run_solver(solver, grid)
        if isinstance(got, list):
            runs.append(Run(label, grid, got))
        else:
            runs.append(Run(label, grid, error=_failure_text(solver, got)))
    return runs


def given_cases(run: Run) -> list[str]:
    return list(dict.fromkeys(c.label for c in run.candidates))


def _listed(names: Iterable[str]) -> str:
    return ", ".join(map(repr, names))


def _case_on(case: str, run: Run) -> str:
    return f"case {case!r} on witness {run.label!r}"


def cases_not_given(run: Run, cases: Iterable[str]) -> list[tuple[str, str]]:
    """Each of `cases` the run does not give, with its fault line."""
    given = given_cases(run)
    gives = _listed(given) or "no case"
    return [(case, f"{_case_on(case, run)}: the run gives {gives}")
            for case in cases if case not in given]


def diverges(run: Run, dropped: list[str]) -> bool:
    """Whether a dropped case's grid differs from every kept case's grid."""
    kept = [c.grid for c in run.candidates if c.label not in dropped]
    return any(
        c.grid not in kept for c in run.candidates if c.label in dropped
    )


def filters_witnesses(card: Card) -> bool:
    """Whether `dropped` decides which witnesses the page draws."""
    return bool(card.dropped) and not card.all_witnesses


def drawn_runs(card: Card) -> tuple[list[Run], bool]:
    """The runs the page draws, as the comment of `Card.dropped` gives
    them, and whether they are the fallback."""
    runs = run_witnesses(card)
    if not filters_witnesses(card):
        return runs, False
    diverging = [run for run in runs if diverges(run, card.dropped)]
    if diverging:
        return diverging, False
    fallback = Card(**{**card.__dict__, "witnesses": []})
    return run_witnesses(fallback), True


def check_captions(card: Card, runs: list[Run]) -> None:
    """Fails as the comment of `Card.captions` gives."""
    unsure = filters_witnesses(card)
    labels = drawable_labels(card) if unsure else [r.label for r in runs]
    wrong = []
    for witness, cases in card.captions.items():
        on = [run for run in runs if run.label == witness]
        if not on and witness not in labels:
            may = "may draw" if unsure else "draws"
            wrong.append(f"witness {witness!r}: the page {may} "
                         f"{_listed(labels)}")
        for run in on:
            wrong.extend(line for _, line in cases_not_given(run, cases))
    if wrong:
        raise ValueError("captions keyed to nothing the page draws:\n"
                         + "\n".join(wrong))


def check_option_cases(card: Card, runs: list[Run]) -> None:
    """Fails as the comment of `Option.cases` gives."""
    named = [case for option in card.options for case in option.cases]
    if not named:
        return
    wrong = []
    for run in runs:
        wrong.extend(f"option {option_of(card, case)} names {line}"
                     for case, line in cases_not_given(run, named))
        wrong.extend(
            f"{_case_on(case, run)}: no option names it"
            for case in given_cases(run) if case not in named
        )
    if wrong:
        raise ValueError("the cases of the options do not match the cases "
                         "of the run:\n" + "\n".join(wrong))
