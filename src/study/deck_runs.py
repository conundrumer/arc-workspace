"""Each option's output on each witness of a concept-decision card, and the
output of each witness's verdict: a solver loaded in its own checkout, and
a case of it run on the entry's input at the entry's assignment."""

import os
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from arc.task import Task
from arc.task import load as load_task
from checker.finding import AtLine, Finding, Kind
from checker.judged import (AnyCase, NoCase, VerdictCase, parse_fault,
                            verdict_case)
from checker.payloads.witness import VerdictOutputUnknown
from checker.render import finding_lines
from checker.render.built import takes_branch, undefined_text
from checker.runs import witness_file_role
from cli.common import LIMITS, engine
from engine import Engine, Grid, RunFailure, checkout
from engine.program import as_grid
from solver import witness as witness_reader
from solver.aggregate import Solver, read_witness
from solver.annotations import WitnessLine, verdict_text
from solver.cases import cases
from solver.load import load
from solver.model import Case
from solver.names import denote, model_of
from solver.problems import Fault, InSolver, NameFault, WitnessFileRole
from solver.solve import assignment, outcomes
from solver.outcome import Grids
from solver.undefined import Undefined
from solver.witness import Entry, RejectedOutput, WitnessFile
from study.card_runs import run_failure_text
from study.deck_spec import CardSpec, Option


@dataclass(frozen=True)
class Output:
    """The grids an option gives on an input: one, or one per tiebreak
    resolution."""

    grids: tuple[Grid, ...]


class NoGridKind(Enum):
    """Why a run gives no grid on an input, its value the CSS class of the
    page's box for it."""

    UNDEFINED = "undefined"
    """The case is undefined there."""
    FAILED = "failed"
    """The run gave no result."""
    INAPPLICABLE = "inapplicable"
    """The entry reassigns something the solver does not have."""
    UNKNOWN = "unknown"
    """A verdict whose output no case of the solver gives."""


@dataclass(frozen=True)
class NoGrid:
    """A run that gives no grid on an input: why, and `text`, which says
    it as the tool prints it."""

    kind: NoGridKind
    text: str


type Slot = Output | NoGrid


@dataclass(frozen=True)
class Witness:
    """One drawn entry of the witness file: its id, its `separates` text,
    its input, the names it reassigns, and the output the annotator judged
    the generator to pair with the input, why that output is not known
    where a verdict is recorded, or None where none is."""

    id: str
    separates: str
    input: Grid
    reassigns: tuple[str, ...]
    judged: Slot | None


@dataclass(frozen=True)
class CardRuns:
    """A card with its runs: the task, the drawn witnesses, and by witness
    then by option, what each option gives on it."""

    spec: CardSpec
    task: Task
    witnesses: tuple[Witness, ...]
    slots: tuple[tuple[Slot, ...], ...]


@contextmanager
def at_root(root: Path) -> Iterator[None]:
    """Every checkout directory read from `root` while the block runs."""
    held = checkout.ROOT
    checkout.ROOT = root
    try:
        yield
    finally:
        checkout.ROOT = held


@dataclass(frozen=True)
class Loaded:
    """The task's solver loaded in a checkout: the engine it runs through,
    the solver, the witness file read under its params, and its cases, or
    the fault or the failed run that leaves them unknown."""

    engine: Engine
    solver: Solver
    file: WitnessFile
    role: WitnessFileRole
    cases: tuple[Case, ...] | Fault | RunFailure


@contextmanager
def loaded(root: Path, spec: CardSpec, text: str) -> Iterator[Loaded]:
    """The task's solver loaded in the checkout `root`, with the witness
    file `text`; the block runs in that checkout (`at_root`)."""
    with at_root(root):
        eng = engine()
        solver = load(spec.task_id, eng)
        role = witness_file_role(spec.witness_file)
        file, _ = read_witness(text, solver.params, role)
        assert file is not None
        fault = parse_fault(solver)
        yield Loaded(eng, solver, file, role,
                     fault if fault is not None else cases(solver, eng, LIMITS))


def case_slot(run: Loaded, every: tuple[Case, ...], case: Case, entry: Entry
              ) -> Slot:
    """What `case` gives on the entry's input at the entry's assignment."""
    at = assignment(run.engine, run.solver, entry, run.role)
    if isinstance(at, Fault):
        return NoGrid(NoGridKind.INAPPLICABLE,
                      run_failure_text(run.solver, at))
    got = outcomes(run.engine, run.solver, every, as_grid(entry.input), at,
                   LIMITS)[case]
    if isinstance(got, Grids):
        return Output(got.grids)
    if isinstance(got, Undefined):
        return NoGrid(NoGridKind.UNDEFINED, undefined_text(got.reason,
                                                         counted=True))
    return NoGrid(NoGridKind.FAILED, run_failure_text(run.solver, got))


def witness_path(spec: CardSpec) -> Path:
    """The witness file the card draws (`study.deck_spec`)."""
    if spec.witness_file is not None:
        return spec.witness_file
    with at_root(spec.options[0].root):
        return witness_reader.path(spec.task_id)


def witness_root(spec: CardSpec) -> Path:
    """The checkout whose solver the witness file belongs to: the first
    option's where the spec names no file, else the one the file stands in
    under `programs/witnesses/`. A file the spec names that stands under no
    such directory is a `ValueError`, since that solver is then unknown."""
    if spec.witness_file is None:
        return spec.options[0].root
    path = spec.witness_file.resolve()
    if checkout.WITNESSES_ENV in os.environ:
        raise ValueError(f"{path}: {checkout.WITNESSES_ENV} is set, so no "
                         "checkout's witness files stand under its "
                         "programs/witnesses/, and the solver whose "
                         "`@witness` lines hold the file's verdicts is "
                         "unknown")
    for parent in path.parents:
        with at_root(parent):
            if checkout.witnesses().resolve() == path.parent:
                return parent
    raise ValueError(f"{path}: the witness file stands under no checkout's "
                     "programs/witnesses/, so the solver whose `@witness` "
                     "lines hold its verdicts is unknown")


def drawn_by_default(run: Loaded, entry: Entry) -> bool:
    """Whether an entry is drawn where the spec picks none
    (`study.deck_spec`)."""
    return not takes_branch(run.solver, entry.id) and not entry.assign


def shown_root(root: Path) -> str:
    """A checkout as an error names it: as `checkout.shown` prints it, and
    the checkout the command runs in by its absolute path, since
    `checkout.shown` gives `.` for it, which names no checkout a reader of
    the error can tell apart."""
    if root.resolve() == checkout.ROOT.resolve():
        return root.resolve().as_posix()
    return checkout.shown(root).as_posix()


def run_card(spec: CardSpec) -> CardRuns:
    """The card's runs. A witness file, an option or a case the spec names
    that is not there is a `ValueError`."""
    path = witness_path(spec)
    if not path.exists():
        raise ValueError(f"{path}: no witness file")
    text = path.read_text()
    raw, _ = witness_reader.read(text, witness_file_role(spec.witness_file))
    if raw is None:
        raise ValueError(f"{path}: not a witness file")
    root = witness_root(spec)
    with loaded(root, spec, text) as run:
        if spec.witness_ids is None and isinstance(run.cases, Fault):
            raise ValueError(
                f"{path}: the entries to draw are unknown, since "
                f"{run.solver.stem} in {shown_root(root)} does not parse:\n"
                + run_failure_text(run.solver, run.cases))
        ids = spec.witness_ids or tuple(
            e.id for e in run.file.entries if drawn_by_default(run, e))
        for id in ids:
            if raw.entry(id) is None:
                raise ValueError(f"{path}: no witness {id!r}")
        if not ids:
            raise ValueError(f"{path}: no witness to draw")
        judged = [_judged(run, id) for id in ids]
    columns = [_option_slots(spec, o, text, ids) for o in spec.options]
    witnesses = []
    for id, grid in zip(ids, judged, strict=True):
        entry = raw.entry(id)
        assert entry is not None
        witnesses.append(Witness(entry.id, entry.separates,
                                 as_grid(entry.input),
                                 tuple(name for name, _ in entry.assign),
                                 grid))
    return CardRuns(spec, load_task(spec.task_id), tuple(witnesses),
                    tuple(tuple(col[i] for col in columns)
                          for i in range(len(ids))))


def _option_slots(spec: CardSpec, option: Option, text: str,
                  ids: Sequence[str]) -> list[Slot]:
    """What `option` gives on each entry of `ids`, in the witness file
    `text`, run in the option's checkout."""
    shown = shown_root(option.root)
    with loaded(option.root, spec, text) as run:
        where = f"option {option.name!r}: {run.solver.stem} in {shown}"
        if isinstance(run.cases, Fault):
            failed = NoGrid(NoGridKind.FAILED,
                            run_failure_text(run.solver, run.cases))
            return [failed] * len(ids)
        if not isinstance(run.cases, tuple):
            raise ValueError(f"{where}: the run that enumerates its cases "
                             "failed:\n"
                             + run_failure_text(run.solver, run.cases))
        case = _case_named(run.solver, run.cases, option.case, where)
        return [case_slot(run, run.cases, case, _entry(run, id)) for id in ids]


def _judged(run: Loaded, id: str) -> Slot | None:
    """The output the annotator judged the generator to give on the entry
    `id`, `run` being the solver the witness file belongs to: the entry's
    bare grid where its verdict is `other`, else the output of the case
    its `@witness` line's verdict denotes (`checker.judged.verdict_case`),
    run on the entry's input, every tiebreak resolution of it; why that
    output is not known, where a verdict is recorded
    or the solver does not parse; None where no line gives the entry a
    verdict."""
    entry = _entry(run, id)
    if isinstance(entry.output, RejectedOutput):
        return Output((entry.output.grid,))
    if isinstance(run.cases, Fault):
        return NoGrid(NoGridKind.FAILED,
                      run_failure_text(run.solver, run.cases))
    line = {w.id: w for w in run.solver.annotations.witnesses}.get(id)
    if line is None:
        return None
    if not isinstance(run.cases, tuple):
        return NoGrid(NoGridKind.FAILED,
                      run_failure_text(run.solver, run.cases))
    case = verdict_case(run.solver, line.verdict, run.cases, None)
    if isinstance(case, Case) and case in run.cases:
        return case_slot(run, run.cases, case, entry)
    return NoGrid(NoGridKind.UNKNOWN, _unknown_text(run.solver, line, case))


def _unknown_text(solver: Solver, line: WitnessLine,
                  case: VerdictCase) -> str:
    """Why the verdict of the `@witness` line `line` gives no output: a
    case it denotes outside the solver's cases gives none either."""
    match case:
        case NameFault():
            return run_failure_text(solver, case.at(InSolver(line.line)))
        case None | Case():
            return "\n".join(finding_lines(solver, Finding(
                Kind.ANNOTATION, AtLine(line.line),
                VerdictOutputUnknown(line.verdict))))
        case AnyCase() | NoCase():
            return f"the verdict `{verdict_text(line.verdict)}` names no " \
                "one output"


def _entry(run: Loaded, id: str) -> Entry:
    entry = run.file.entry(id)
    assert entry is not None
    return entry


def _case_named(solver: Solver, every: Sequence[Case], text: str,
                where: str) -> Case:
    """The case of `every` that the name `text` denotes
    (`solver.names.model_of`)."""
    denoted = denote(solver, text)
    if isinstance(denoted, NameFault):
        raise ValueError(f"{where}: {text!r} is no case name")
    case = model_of(solver, denoted, every)
    if case is None or case not in every:
        raise ValueError(f"{where}: {text!r} names no case of the solver")
    return case
