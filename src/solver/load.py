"""`load`, the one entry that builds a solver's `Solver` from its file."""

import re
from dataclasses import replace
from pathlib import Path

from arc import task as arc_task
from arc.task import Task
from engine import Engine, ParseFailure, Program
from solver import annotations as annotations_reader
from solver import witness as witness_reader
from solver.model import Params, every_base
from solver.aggregate import (
    Solver,
    lists_case,
    parse_with_lib,
    read_witness,
    solver_file,
)
from solver.form_checks import instance_faults, name_problems
from solver.readers import (
    choice_line,
    proposer_names,
    proposers_program,
    read_branches,
    read_choice,
    read_lib,
    read_params,
)
from solver.case_columns import off_form_case_columns
from solver.witness_swap import with_witness_file
from solver.problems import (
    Fault,
    InSolver,
    Named,
    ProblemKind,
    Undecided,
    UndecidedForm,
    WitnessFileRole,
)
from engine.program import own

_STEM_RE = re.compile(r"^[0-9a-f]{8}")


def _empty_program() -> Program:
    """A program with no part, for a solver whose text does not parse."""
    return Program((), (), (), (), (), (), (), (), (), ())


def task_id_of(stem: str) -> str:
    """The task a solver's stem names: its leading eight hex digits, or
    the whole stem where it does not start with eight."""
    m = _STEM_RE.match(stem)
    return m[0] if m else stem


def load(stem: str, engine: Engine, path: Path | None = None) -> Solver:
    """The solver of `stem`, the one entry every command uses: the text of
    `path`, a solver file anywhere whose name starts with the task id,
    else of `<stem>.dl` under `checkout.solvers()`. Every solver reads the
    lib: `load` adds the lib's `#include` to the text when the text lacks
    it (`parse_with_lib`), and parses it against `programs/`, wherever the
    file stands.

    A form the tool no longer reads gives a fault, never a reading of the
    form it replaced, so a file fails as written until it is brought to
    the form the tool reads."""
    task_id = task_id_of(stem)
    problems: list[Fault] = []
    parsed = parse_with_lib(engine, (path or solver_file(stem)).read_text())
    if isinstance(parsed, ParseFailure):
        problems.append(Fault(ProblemKind.PARSE_FAILURE,
                                       InSolver(parsed.line), parsed))
        program = _empty_program()
        lib_parse = parse_with_lib(engine, "")
        lib = read_lib(lib_parse if isinstance(lib_parse, Program)
                       else _empty_program())
    else:
        program = parsed
        lib = read_lib(program)
    annotations, read_problems = annotations_reader.read(program)
    problems += read_problems
    declared = {c.name for c in program.components}
    problems += [Fault(ProblemKind.INSTANCE_OF_NOTHING,
                                InSolver(i.span.first), Named(i.component))
                 for i in program.instances
                 if own(i.span) and i.span is not None
                 and i.component not in declared]
    problems += instance_faults(program)
    choice = read_choice(program, engine.index(program), problems)
    if choice is not None and every_base(choice) is None:
        problems.append(Fault(
            ProblemKind.UNDECIDED,
            InSolver(choice_line(program, choice)),
            Undecided(UndecidedForm.CHOICE_NOT_ENUMERABLE, None)))
    proposers: frozenset[str] | None = None
    if annotations.derives:
        probe_program = proposers_program(engine)
        if isinstance(probe_program, Program):
            proposers = frozenset(proposer_names(probe_program))
    branches = read_branches(program, annotations, proposers, problems)
    unread = Solver(stem, task_id, program, annotations, choice, branches,
                    Params(()), None, None, lib, (), engine)
    params = read_params(program, annotations, lib.constants,
                         lambda m: lists_case(unread, m), problems)
    try:
        task: Task | None = arc_task.load(task_id)
    except FileNotFoundError:
        task = None
    if annotations.representative is not None and not solver_file(
            annotations.representative.task_id).exists():
        problems.append(Fault(
            ProblemKind.REPRESENTATIVE_MISSING,
            InSolver(annotations.representative.line),
            Named(annotations.representative.task_id)))
    solver = Solver(stem, task_id, program, annotations, choice, branches,
                    params, None, task, lib, tuple(problems), engine)
    solver = replace(solver, problems=(
        *problems, *name_problems(solver), *off_form_case_columns(solver)))
    wpath = witness_reader.path(task_id)
    if not wpath.exists():
        return solver
    witness_file, file_problems = read_witness(
        wpath.read_text(), params, WitnessFileRole.TASK)
    return with_witness_file(solver, witness_file, file_problems)
