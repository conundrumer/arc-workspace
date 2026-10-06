"""Each option's output on each witness of a concept-decision card: the
option's solver loaded in its own checkout, and its case run on the
entry's input at the entry's assignment."""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from arc.task import Task
from arc.task import load as load_task
from cli.common import LIMITS, engine, failure_lines, parse_fault
from engine import Grid, checkout
from engine.program import as_grid
from solver import witness as witness_reader
from solver.load import load
from checker.judged import verdict_case
from solver.model import Case, Solver, read_witness
from solver.cases import cases
from solver.names import denote, model_of
from solver.problems import Fault, NameFault, WitnessFileRole
from solver.solve import Grids, assignment, outcomes
from solver.witness import (
    ConflictingCells,
    InconsistentBounds,
    MissingCells,
    NegativeEdges,
    NoDerivedValue,
    NoOutput,
    RejectedOutput,
    Undefined,
    UndefinedReason,
)
from study.deck_spec import CardSpec, Option


@dataclass(frozen=True)
class Output:
    """The grids an option gives on an input: one, or one per tiebreak
    resolution."""

    grids: tuple[Grid, ...]


@dataclass(frozen=True)
class NoGrid:
    """An option that gives no grid on an input: `undefined` where its
    model is undefined there, `failed` where its run gave no result, and
    `inapplicable` where the entry reassigns something its solver does not
    have. `text` says which, as the tool prints it."""

    kind: Literal["undefined", "failed", "inapplicable"]
    text: str


type Slot = Output | NoGrid


@dataclass(frozen=True)
class Witness:
    """One drawn entry of the witness file: its id, its `separates` text,
    its input, the names it reassigns, and the output the annotator judged
    the generator to pair with the input, None where the file and the
    solver's `@witness` line record none."""

    id: str
    separates: str
    input: Grid
    reassigns: tuple[str, ...]
    judged: Grid | None


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


def witness_path(spec: CardSpec) -> Path:
    """The witness file the card draws: the spec's, else the task's file in
    the first option's checkout."""
    if spec.witness_file is not None:
        return spec.witness_file
    with at_root(spec.options[0].root):
        return witness_reader.path(spec.task_id)


def witness_root(spec: CardSpec) -> Path:
    """The checkout whose solver the witness file belongs to: the one the
    file stands in under `programs/witnesses/`, else the first option's."""
    path = witness_path(spec)
    if path.parent.name == "witnesses" and path.parents[1].name == "programs":
        return path.parents[2]
    return spec.options[0].root


def drawn_by_default(id: str, reassigns: bool) -> bool:
    """Whether an entry is drawn when the spec picks none: one that is no
    `@derive` or `@store` branch's witness, whose id is the branch's name,
    and reassigns nothing. Those test a parameterization, not the
    concept."""
    return "=" not in id and not reassigns


def _role(spec: CardSpec) -> WitnessFileRole:
    return WitnessFileRole.GIVEN if spec.witness_file is not None \
        else WitnessFileRole.TASK


def shown_root(root: Path) -> str:
    """A checkout as the page names it: `the main tree`, or its path from
    the main tree."""
    main = checkout.ROOT.resolve()
    here = root.resolve()
    if here == main:
        return "the main tree"
    try:
        return here.relative_to(main).as_posix()
    except ValueError:
        return here.as_posix()


def run_card(spec: CardSpec) -> CardRuns:
    """The card's runs. A witness file, an option or a case the spec names
    that is not there is a `ValueError`."""
    path = witness_path(spec)
    if not path.exists():
        raise ValueError(f"{path}: no witness file")
    text = path.read_text()
    raw, problems = witness_reader.read(text, _role(spec))
    if raw is None:
        raise ValueError(f"{path}: not a witness file")
    ids = spec.witness_ids or tuple(
        e.id for e in raw.entries if drawn_by_default(e.id, bool(e.assign)))
    for id in ids:
        if raw.entry(id) is None:
            raise ValueError(f"{path}: no witness {id!r}")
    if not ids:
        raise ValueError(f"{path}: no witness to draw")
    columns = [_option_slots(spec, o, text, ids) for o in spec.options]
    judged = _judged(spec, text, ids)
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
    with at_root(option.root):
        eng = engine()
        solver = load(spec.task_id, eng)
        where = f"option {option.name!r}: {solver.stem} in " \
            f"{shown_root(option.root)}"
        fault = parse_fault(solver)
        if fault is not None:
            failed = NoGrid("failed", "\n".join(failure_lines(solver, fault)))
            return [failed] * len(ids)
        every = cases(solver, eng, LIMITS)
        if not isinstance(every, tuple):
            raise ValueError(f"{where}: the run that enumerates its cases "
                             "failed:\n" + "\n".join(failure_lines(solver, every)))
        case = _case_named(solver, every, option.case, where)
        file, _ = read_witness(text, solver.params, _role(spec))
        assert file is not None
        out: list[Slot] = []
        for id in ids:
            entry = file.entry(id)
            assert entry is not None
            at = assignment(eng, solver, entry, _role(spec))
            if isinstance(at, Fault):
                out.append(NoGrid("inapplicable",
                                  "\n".join(failure_lines(solver, at))))
                continue
            got = outcomes(eng, solver, every, as_grid(entry.input), at,
                           LIMITS)[case]
            if isinstance(got, Grids):
                out.append(Output(got.grids))
            elif isinstance(got, Undefined):
                out.append(NoGrid("undefined", undefined_text(got.reason)))
            else:
                out.append(NoGrid("failed",
                                  "\n".join(failure_lines(solver, got))))
        return out


def _judged(spec: CardSpec, text: str, ids: Sequence[str]
            ) -> list[Grid | None]:
    """The output the annotator judged the generator to give on each entry
    of `ids`: the entry's bare grid where its verdict is `other`, else the
    output of the case its `@witness` line's verdict denotes in the witness
    file's own solver (`checker.judged.verdict_case`), run on the entry's
    input; None where no line gives one, or that case is undefined there.
    The judgment is the pass's, from the solver the file belongs to."""
    with at_root(witness_root(spec)):
        eng = engine()
        solver = load(spec.task_id, eng)
        file, _ = read_witness(text, solver.params, _role(spec))
        assert file is not None
        enumerated = cases(solver, eng, LIMITS) if parse_fault(solver) is None \
            else None
        every: tuple[Case, ...] = enumerated if isinstance(enumerated, tuple) \
            else ()
        lines = {line.id: line for line in solver.annotations.witnesses}
        out: list[Grid | None] = []
        for id in ids:
            entry = file.entry(id)
            assert entry is not None
            if isinstance(entry.output, RejectedOutput):
                out.append(entry.output.grid)
                continue
            line = lines.get(id)
            case = None if line is None or not every \
                else verdict_case(solver, line.verdict, every, None)
            at = assignment(eng, solver, entry, _role(spec))
            if not isinstance(case, Case) or isinstance(at, Fault):
                out.append(None)
                continue
            got = outcomes(eng, solver, every, as_grid(entry.input), at,
                           LIMITS)[case]
            out.append(got.grids[0] if isinstance(got, Grids) else None)
        return out


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


def undefined_text(reason: UndefinedReason | None) -> str:
    """Why a case is undefined on an input, in a few words."""
    match reason:
        case NoOutput():
            return "no output"
        case MissingCells(cells=cells):
            return f"{len(cells)} cells get no color"
        case ConflictingCells(cells=cells):
            return f"two colors at {len(cells)} cells"
        case NegativeEdges():
            return "a cell lies off the frame"
        case InconsistentBounds():
            return "two frame sizes"
        case NoDerivedValue(parameter=parameter, proposer=proposer):
            return f"{proposer} derives no {parameter}"
        case _:
            return "undefined"
