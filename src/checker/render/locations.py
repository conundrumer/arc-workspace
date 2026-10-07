"""Locations as a finding's line states them: a line of the solver in
the form its section writes, a solver's file, a witness entry, and the
other places a finding stands."""

from collections.abc import Sequence
from enum import StrEnum

from checker.finding import (
    AtCase,
    AtEntry,
    AtFile,
    AtLine,
    AtPair,
    AtParameter,
    AtRelation,
    Where,
    WholeFile,
)
from controlled_markdown import mctx
from solver import names
from solver.aggregate import Solver, solver_file
from solver.problems import WitnessFileRole


class LineForm(StrEnum):
    """How a section writes a line of the solver."""

    FILE = "file"
    """`<stem>.dl:N`, the lint section's form."""
    LINE = "line"
    """`line N`, the form of the audit, witness, derive and store
    sections."""


def line_text(line: int) -> str:
    """A solver line as a sentence names it."""
    return mctx("line {n}").format(n=line)


def line_list(lines: Sequence[int]) -> str:
    """Solver lines as a sentence names them."""
    if len(lines) == 1:
        return line_text(lines[0])
    return mctx("lines {ns}").format(ns=", ".join(str(n) for n in lines))


def file_name(stem: str) -> str:
    """A solver's file by its name (`solver.aggregate.solver_file`), as every
    line gives it."""
    return solver_file(stem).name


def file_line(stem: str, line: int) -> str:
    """A line of a solver's file, as a lint line gives it."""
    return f"{file_name(stem)}:{line}"


def solver_name(solver: Solver) -> str:
    """The solver's file, as a finding line gives it."""
    return file_name(solver.stem)


def where_text(solver: Solver, where: Where,
               form: LineForm = LineForm.LINE) -> str:
    """A finding's location as its line states it; a line of the solver
    in `form`, which is `line N` in every section but the lint's."""
    match where:
        case AtLine(line=line) if form == LineForm.FILE:
            return file_line(solver.stem, line)
        case AtLine(line=line):
            return line_text(line)
        case AtEntry(entry=entry, assigned=False):
            return entry
        case AtEntry(entry=entry, file=role):
            return entry_label(solver, entry, role)
        case AtCase(case=case):
            return names.name(solver, case)
        case AtRelation(relation=rel):
            return rel.text
        case AtParameter(parameter=p):
            return p
        case AtPair(pair=pair):
            return pair.text
        case AtFile(file=WholeFile.SOLVER):
            return solver_name(solver)
        case AtFile():
            return mctx("the witness file")


def entry_label(solver: Solver, entry: str, role: WitnessFileRole) -> str:
    """A witness entry by its id, followed by the parameters and relations
    its `assign` reassigns, as `<id> [<name>, ...]`. An entry of a given
    file is by its id alone: the location does not hold its `assign`."""
    file = solver.witness_file
    if role != WitnessFileRole.TASK or file is None:
        return entry
    found = next((e for e in file.entries if e.id == entry), None)
    if found is None or not found.assign:
        return entry
    return f"{entry} [{', '.join(k for k, _v in found.assign)}]"
