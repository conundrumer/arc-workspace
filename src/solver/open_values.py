"""The values a case takes at each field of `OpenValue` on a run: the
values of the field's `@open` relation that the derivation gives on the
run's input where the case takes a `@derive` branch on it, else that the
run's assignment gives it, else the facts of the run's program, each
projected onto the columns the field's record names, which tell one open
value from another (solver-file.md, under "Cases")."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

from engine import RecordValue, Row, Rows, Value
from engine.quotes import quotes
from engine.program import RecordType, first_line, own
from solver.aggregate import TOP, Solver
from solver.determine import ProgramFacts
from solver.model import Case, Parameter
from solver.out_grids import FieldValues
from solver.outcome import Assignment
from solver.per_case import parameter_reading, rows_at
from solver.vocabulary import OPEN_VALUE


def open_value_type(solver: Solver) -> RecordType | None:
    """The `OpenValue` record type the solver declares at the top level;
    None where it declares none."""
    return next((t for t in solver.program.types
                 if isinstance(t, RecordType) and t.name == OPEN_VALUE
                 and t.scope == TOP and own(t.span)), None)


class FieldFault(Enum):
    """How a field of `OpenValue` is off the form solver-file.md gives it
    under "Cases"."""

    NO_RELATION = "no relation"
    """The field has the name of no `@open` relation."""
    NO_RECORD = "no record"
    """The field's type is no record the solver declares."""
    NO_COLUMN = "no column"
    """The field's record names columns its relation does not have outside
    its case part."""


@dataclass(frozen=True)
class FieldOff:
    """A field of `OpenValue` off its form: the field, the fault, its type,
    the names its record holds that its relation lacks, and the solver
    line it stands on: the line of the field's record, or of `OpenValue`
    where the solver declares no such record."""

    field: str
    fault: FieldFault
    type_name: str
    missing: tuple[str, ...]
    line: int


@dataclass(frozen=True)
class FieldReading:
    """How a run reads a field of `OpenValue`: its `@open` relation, and
    the places of the record's fields among the relation's columns
    outside its case part."""

    parameter: Parameter
    places: tuple[int, ...]


@quotes("solver-file.md", "Cases",
        "each field with that relation's name and of a record type the "
        "solver names for that relation, whose fields are the relation's "
        "columns that tell one open value from another, under the same "
        "names.")
def field_readings(solver: Solver) -> tuple[FieldReading | FieldOff, ...]:
    """The reading of each field of the solver's `OpenValue`, in field
    order, or how the field is off its form; none where the solver
    declares no `OpenValue` record."""
    decl = open_value_type(solver)
    if decl is None:
        return ()
    marked = {p.name: p for p in solver.params.parameters if p.open}
    records = {t.name: t for t in solver.program.types
               if isinstance(t, RecordType) and t.scope == TOP}
    out: list[FieldReading | FieldOff] = []
    for f in decl.fields:
        p = marked.get(f.name)
        record = records.get(f.type.text)
        if p is None:
            out.append(FieldOff(f.name, FieldFault.NO_RELATION, f.type.text,
                                (), first_line(decl.span)))
            continue
        if record is None:
            out.append(FieldOff(f.name, FieldFault.NO_RECORD, f.type.text,
                                (), first_line(decl.span)))
            continue
        columns = parameter_reading(solver, p.name).outside(
            [c.name for c in p.columns])
        missing = tuple(g.name for g in record.fields
                        if g.name not in columns)
        if missing:
            out.append(FieldOff(f.name, FieldFault.NO_COLUMN, f.type.text,
                                missing, first_line(record.span)))
            continue
        out.append(FieldReading(p, tuple(list(columns).index(g.name)
                                         for g in record.fields)))
    return tuple(out)


@quotes("solver-file.md", "Cases",
        "A relation's values at that case are those the case stores, or "
        "those that the `@derive` branch the case takes on it derives on "
        "that input.")
def open_fields(facts: ProgramFacts, solver: Solver,
                readings: Sequence[FieldReading | FieldOff], case: Case,
                assign: Assignment, derived: Mapping[str, Rows]
                ) -> FieldValues:
    """`case`'s values at each field of `OpenValue` on a run at `assign`
    (`solver.out_grids.FieldValues`), `readings` the solver's
    `field_readings` and `derived` the values each parameter the case
    derives takes on the run's input, as the run fixes them
    (`solver.group_runs.group_program`): those, else the values the
    assignment gives, else the relation's facts in the program of
    `solver`, which `facts` reads, each projected onto the field's record. Raises ValueError
    where a field is off its form, which the lint reports
    (`checker.lint.form.open_value_fields`), and where the assignment gives
    the relation a grid."""
    given = dict(assign.values)
    out: list[tuple[Value, ...]] = []
    for r in readings:
        if isinstance(r, FieldOff):
            raise ValueError(f"the `{OPEN_VALUE}` field `{r.field}` is off "
                             f"its form: {r.fault.value}")
        p = r.parameter
        if p.name in derived:
            out.append(_projected(derived[p.name], r.places))
            continue
        assigned = given.get(p.name)
        if assigned is not None and not isinstance(assigned, tuple):
            raise ValueError(f"the `@open` relation `{p.name}` is assigned "
                             f"a grid")
        rows = list(assigned) if assigned is not None \
            else facts.of(p)
        pc = parameter_reading(solver, p.name)
        values = pc.values(rows) if case.base is None or not pc.case \
            else rows_at(solver, pc, rows, case.base)
        out.append(_projected(values, r.places))
    return tuple(out)


def _projected(values: Iterable[Row], at: Sequence[int]
               ) -> tuple[Value, ...]:
    """The distinct records of `values` at the places `at`, in the order
    they first stand."""
    return tuple(dict.fromkeys(RecordValue(tuple(v[i] for i in at))
                               for v in values))
