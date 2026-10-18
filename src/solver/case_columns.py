"""What a base holds at a case column: whether a row's case values are
the base's, the values a base holds at a case type, the columns of a
relation that hold the case, and each parameter's column that holds
the case off the form of a case column."""

from collections.abc import Iterator, Sequence
from itertools import product

from engine import RecordValue, RelationName, Value
from solver.aggregate import Solver
from solver.readers import declaration_of, instance_of
from solver.case_types import CaseTypes, case_types
from solver.columns import (
    column_types,
    parameter_case_columns,
    parameter_columns,
)
from solver.model import Base, Choice, value_at
from solver.problems import (
    CaseColumnOffForm,
    Fault,
    InSolver,
    OffFormType,
    ProblemKind,
)
from solver.vocabulary import CHOICE, PARAMS


def holds_at(solver: Solver, base: Base | None, types: Sequence[str],
             case_cols: Sequence[int], values: tuple[Value, ...]) -> bool:
    """Whether the base holds the case values of a row: the base itself
    at a `Choice` column, and at a column of a point's type, the column's
    value at some point of that type, `types` being the column types as
    the model resolves them (`column_types`). Whether the base depends on
    the relation is the caller's to ask."""
    choice = solver.choice
    if choice is None or base is None:
        return False
    reading = case_types(solver)
    for i, v in zip(case_cols, values, strict=True):
        for t, leaf in reading.leaves(types[i], v):
            if leaf not in base_values(choice, reading, base, t):
                return False
    return True


def base_values(choice: Choice, reading: CaseTypes, base: Base, type: str
                ) -> list[Value]:
    """What `base` holds at a case column of `type`: the base itself at a
    `Choice` column, and at a column of a point's type the base's value at
    each point of that type it reaches (`value_at`). Raises `ValueError`
    where `type` is neither: a place of a record case type that holds no
    record of its fields, which no value of the column's type is."""
    if type == CHOICE:
        return [base]
    points = reading.at(choice, type)
    if not points:
        raise ValueError(f"`{type}` is neither `Choice` nor a point's type")
    return [v for p in points
            if (v := value_at(choice, base, p.path)) is not None]


def case_values(solver: Solver, choice: Choice, base: Base, type: str
                ) -> list[Value]:
    """What `base` holds at a case column or field of `type` wholly of the
    case (`CaseTypes.whole`): `base_values` at `Choice` and at a point's
    type, and at a record type each record of what the base holds at its
    fields. Raises `ValueError` where `type` is not wholly of the case."""
    reading = case_types(solver)
    if not reading.whole(type):
        raise ValueError(f"`{type}` is not wholly of the case")
    fields = reading.fields(type)
    if fields is None:
        return base_values(choice, reading, base, type)
    return [RecordValue(tuple(v)) for v in product(
        *(case_values(solver, choice, base, f) for f in fields))]


def case_columns(solver: Solver, of: RelationName | Sequence[str]
                 ) -> tuple[int, ...]:
    """The columns of the relation `of` of the solver's program, or of a
    relation of column types `of`, as the model resolves them
    (`column_types`), that hold the case: of type `Choice`, of an
    ADT that stands in `Choice` (solver-file.md, under "Types"), or of a record
    type with a field of such a type, a component's type parameter read through
    the instance, which holds the case in that field and is a key in its
    other fields (`case_types`, as `dependence` reads them). A
    case column is a key of a stored value, never one of its columns."""
    if solver.choice is None:
        return ()
    types = column_types(solver.engine, solver.program, of) \
        if isinstance(of, RelationName) else of
    case = case_types(solver).types
    return tuple(i for i, t in enumerate(types) if t in case)


def off_form_case_columns(solver: Solver) -> Iterator[Fault]:
    """Each parameter's column that holds the case (`case_columns`) and
    is no case column of a parameter (`parameter_case_columns`). With no
    `Choice` no column holds the case, and with no instance of `Params`
    the program reads no parameter."""
    if solver.choice is None or instance_of(solver.program, PARAMS) is None:
        return
    records = case_types(solver).records
    for p in solver.params.parameters:
        decl = declaration_of(solver.program, p)
        types = parameter_columns(solver, p.name).types
        case = parameter_case_columns(types)
        for i in case_columns(solver, types):
            if i not in case:
                column = decl.columns[i]
                yield Fault(ProblemKind.CASE_COLUMN_OFF_FORM,
                            InSolver(decl.span.first),
                            CaseColumnOffForm(
                                p.name, column.name, column.type,
                                OffFormType.RECORD if types[i] in records
                                else OffFormType.ADT))
