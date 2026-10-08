"""The aggregate `Solver` and what `load` reads into it, and what the model
reads of the solver's cases (`solver.cases`). `solver.readers` holds the
functions that read each part of the model from a parsed program, and
`solver.form_checks` the checks of the solver's form that `load` runs."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

from arc.task import Task
from engine import checkout
from engine import (
    AdtValue,
    Engine,
    Limits,
    ParseFailure,
    Program,
    RecordValue,
    RelationName,
    RunFailure,
    RunResult,
    Scope,
    Tuples,
)
from engine.program import (
    own,
    Component,
    RelationDecl,
    TypeDecl,
)
from engine.quotes import quotes
from solver import witness as witness_reader
from solver.annotations import (
    Annotations,
    CaseMarker,
    IgnoreForm,
    IgnoreLine,
    WitnessLine,
)
from solver.problems import (
    ProblemKind,
    Fault,
    WitnessFileRole,
)
from solver.vocabulary import (
    DETERMINE,
    ENUMERATOR,
    IMPL,
    INPUT,
    LIB_FILE,
    PROPOSERS_FILE,
    SOLVER_SUFFIX,
)
from solver.witness import WitnessFile
from solver.model import (
    Base,
    Branch,
    Case,
    Choice,
    DeriveBranch,
    Lib,
    Params,
    StoreBranch,
    StoredAtDerive,
    StoredGrid,
    derived_parameters,
    non_concept_at,
)


# Solver


@quotes("solver-file.md", "File structure",
        "A solver is one file, `<task_id>.dl`.")
@dataclass(frozen=True)
class Solver:
    """One solver: its program and the model read from it. `problems`
    holds the faults: what `load` could not read."""

    stem: str
    task_id: str
    program: Program
    annotations: Annotations
    choice: Annotated[Choice | None,
        quotes("solver-file.md", "Cases",
               "A solver with one case has no `Choice`, case markers, or case "
               "column on `out`.")]
    """None for a solver with one case."""
    branches: tuple[Branch, ...]
    params: Params
    witness_file: WitnessFile | None
    """None where the task has no witness file, or where its shape gives
    no file (`solver.witness.read`), which `problems` then reports."""
    task: Task | None
    """None where the task has no task file."""
    lib: Lib
    problems: tuple[Fault, ...]
    engine: Engine = field(compare=False, repr=False)
    """The engine `load` read the solver through, whose index of the
    program resolves the types the model reads (`Graph`)."""

    def fault(self, kind: ProblemKind) -> Fault | None:
        """The first of `problems` of `kind`; None where none is."""
        return next((p for p in self.problems if p.kind == kind), None)

    @property
    def given_task(self) -> Task:
        """The task, for a part that reads its pairs, which a command
        reaches only after it refuses a solver whose task has no task
        file. Raises `ValueError` where it has none."""
        if self.task is None:
            raise ValueError(f"{self.stem} has no task")
        return self.task


# Paths

def solver_file(stem: str) -> Path:
    """The file of the solver `stem` under `checkout.solvers()`."""
    return checkout.solvers() / f"{stem}{SOLVER_SUFFIX}"


def proposers_path() -> Path:
    """The proposers file under the checkout's `programs/`."""
    return checkout.programs() / PROPOSERS_FILE


TOP = Scope(())


def parse_with_lib(engine: Engine, text: str) -> Program | ParseFailure:
    """`text` parsed against `programs/`, where the lib stands, with the
    lib's include added where the parse holds none."""
    parsed = engine.parse(text, checkout.programs())
    if isinstance(parsed, Program) and any(
            Path(i.path).name == LIB_FILE for i in parsed.includes):
        return parsed
    return engine.parse_including(text, LIB_FILE, checkout.programs())


# Load


def branch_witnesses(solver: Solver, ctor: str) -> list[WitnessLine]:
    """The `@witness` lines the branch comment of the constructor named
    `ctor` holds, in file order."""
    return [w for w in solver.annotations.witnesses if w.constructor == ctor]


def assignable(solver: Solver, key: str) -> bool:
    """Whether an `assign` key names something an entry may assign
    (solver-file.md, under "Witness file"): a parameter, or a `@store` relation
    as its line spells it."""
    return any(p.name == key for p in solver.params.parameters) \
        or store_branch(solver, key) is not None


def store_branch(solver: Solver, spelled: str) -> StoreBranch | None:
    """The `@store` branch whose line spells its relation `spelled`, the
    first in file order; None where no line does."""
    return next((b for b in solver.branches
                 if isinstance(b, StoreBranch) and b.spelled == spelled),
                None)


def read_witness(text: str, params: Params, role: WitnessFileRole
                 ) -> tuple[WitnessFile | None, tuple[Fault, ...]]:
    """The witness file `text` states (`solver.witness.read`), each
    `assign` value of a parameter `params` stores by a GRID call read as a
    grid (`solver.witness.with_grids`), and what could not be read, placed
    in the file `role`."""
    file, problems = witness_reader.read(text, role)
    if file is None:
        return None, problems
    return witness_reader.with_grids(file, grid_stored(params)), problems


def grid_stored(params: Params) -> frozenset[str]:
    """The parameters stored by GRID calls, whose `assign` values read as
    grids (solver-file.md, under "Witness file")."""
    return frozenset(p.name for p in params.parameters
                     if isinstance(p.stored, StoredGrid))


def lists_case(solver: Solver, marker: CaseMarker) -> bool:
    """Whether a marker lists a case: a part of it denotes one."""
    from solver.names import Denoted, denote
    return any(isinstance(denote(solver, p.name), Denoted)
               for p in marker.parts)


# The solver's cases


def run_empty(engine: Engine, program: Program, outputs: list[RelationName],
              limits: Limits) -> RunResult:
    """`outputs` of a run of `program` on the empty input."""
    return engine.run(program, {INPUT: ()}, outputs, limits)


def enumerated(engine: Engine, program: Program, limits: Limits
               ) -> tuple[Base, ...] | RunFailure:
    """The bases `impl_choice` holds on a run of `program` on the empty
    input, in the order the run gives them; the run's failure where it
    fails."""
    got = run_empty(engine, program, [IMPL], limits)
    if not isinstance(got, Tuples):
        return got
    return tuple(r[0] for r in got.relations[IMPL]
                 if len(r) == 1 and isinstance(r[0], AdtValue | RecordValue))


def own_top[D: RelationDecl | Component | TypeDecl](
        parts: tuple[D, ...], name: str) -> D | None:
    """The part of `parts` named `name` that the solver's own text
    declares at the top level; None where none is."""
    return next((x for x in parts
                 if x.name == name and x.scope == TOP and own(x.span)), None)


def enumerates(program: Program) -> bool:
    """Whether the solver's own text declares `impl_choice` at the top
    level (solver-file.md, under "Cases")."""
    return own_top(program.relations, ENUMERATOR) is not None


def takes(solver: Solver, case: Case, branch: Branch) -> bool:
    """Whether `case` takes `branch`: a `@derive` or `@store` branch it
    lists, or `<param>=stored` where it lists no `@derive` branch of the
    parameter."""
    if isinstance(branch, StoredAtDerive):
        return branch.parameter not in derived_parameters(case.branches)
    return branch in case.branches


def branch_under(solver: Solver, line: IgnoreLine) -> Branch | None:
    """The branch of the `@derive` or `@store` line a named `@ignore: derive`
    or `@ignore: store` line stands under: the nearest line of its kind above
    it on the same declaration (solver-file.md, under "Params" and
    "Program")."""
    found: tuple[int, DeriveBranch | StoreBranch] | None = None
    for b in solver.branches:
        if isinstance(b, StoredAtDerive) or b.line is None \
                or line.above is None or b.line.above != line.above \
                or b.line.line > line.line:
            continue
        if (line.form is IgnoreForm.DERIVE) != isinstance(b, DeriveBranch):
            continue
        if found is None or b.line.line > found[0]:
            found = (b.line.line, b)
    return None if found is None else found[1]


def has_determine(solver: Solver) -> bool:
    """Whether the solver's own file declares the top-level `Determine` comp
    that holds its determination (solver-file.md, under "Determination")."""
    return own_top(solver.program.components, DETERMINE) is not None


def is_concept(solver: Solver, base: Base | None) -> bool:
    """Whether `base` is the concept case's: the first constructor at each
    point it reaches (solver-file.md, under "Witness file"; principles.md,
    "concept branch")."""
    choice = solver.choice
    if choice is None or base is None:
        return base is None
    return all(non_concept_at(choice, base, p) is None for p in choice.points)



def is_concept_case(solver: Solver, case: Case) -> bool:
    """Whether `case` is the concept case: the base case
    (`solver.model.base_case`) of the concept case's base (`is_concept`)
    (principles.md, under "The concept")."""
    return case.is_base_case and is_concept(solver, case.base)
