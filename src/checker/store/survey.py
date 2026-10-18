"""The values the `store` survey finds, and what it judges of each.

A relation's value is read per case where a column holds the case, and
at each subset of its data columns: one value on every input (`OWNED`),
one family of values keyed by the other columns (`CONSTANT`), or one
value once each set is shifted to its own corner (`TRANSLATED`). Of each
value the survey judges whether some case reads it, whether it is stored
already (`checker.store.stored`), and where a line on it stands."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from itertools import combinations
from typing import TYPE_CHECKING

from checker.branches.witnesses import BuiltBy, NoFit
from checker.finding import Finding
from checker.runs import Runs
from engine import (
    AdtValue,
    Index,
    RecordValue,
    RelationName,
    Row,
    Value,
)
from engine.engine import resolved
from engine.program import (
    Instance,
    RelationDecl,
    own,
)
from solver.aggregate import TOP, Solver
from solver.case_columns import holds_at
from solver.case_types import (
    CaseTypes,
    case_types,
)
from solver.columns import ident_keyed
from solver.dependence import Dependence
from solver.model import (
    Base,
    Case,
    StoreBranch,
    base_case,
    non_concept_at,
)
from solver.names import branch_text
from solver.per_case import case_reading
from solver.stored_value import relation_decl
from solver.value_order import row_key, value_key
from solver.out_grids import position
from solver.vocabulary import (
    BOX,
    CHOICE,
    COLOR,
    IDENT,
    NUMBER,
    OFFSET,
    POSITION,
    UNIT,
)
from solver.witness import Entry

if TYPE_CHECKING:
    from checker.store.witness import FailedRun, Move


ROW_CAP = 20000
"""The most rows a relation holds on an input and is still checked: a
relation over it is a structure over the frame, not a value a solver
would store (cli.py's `store` help)."""

POSITION_TYPES = frozenset({POSITION, BOX})
"""The types whose value is a cell of the frame."""
LABEL_TYPES = frozenset({UNIT, IDENT})
"""The types that label a row rather than hold a value: a column of one
of these, and a case column, is no column of the value."""


# Values


class ValueKind(StrEnum):
    """How a relation's value repeats across the inputs."""

    OWNED = "owned"
    """One value on every input."""
    CONSTANT = "constant"
    """One family of values, keyed by the other columns."""
    TRANSLATED = "translated"
    """One value once each set is shifted to its own corner."""


type Member = tuple[object, ...]
"""One row of a value, at the value's columns. At a cell column of a
value up to translation, the cell's top and left from the set's corner."""
type ValueSet = frozenset[Member]


def corner(value: object) -> tuple[int, int] | None:
    """The top and the left of a Box value (`solver.out_grids.position`)."""
    m = position(value)
    return None if m is None else m.cell


def _normalized(members: set[Member], at: list[int]) -> ValueSet:
    """One set with its cells shifted to its own corner."""
    points = [p for m in members for j in at
              if (p := corner(m[j])) is not None]
    if not points:
        return frozenset(members)
    t0 = min(p[0] for p in points)
    l0 = min(p[1] for p in points)
    out: set[Member] = set()
    for m in members:
        row: list[object] = []
        for j, x in enumerate(m):
            p = corner(x) if j in at else None
            row.append((p[0] - t0, p[1] - l0) if p is not None else x)
        out.add(tuple(row))
    return frozenset(out)


type Family = frozenset[ValueSet]
type Families = dict[tuple[int, ...], tuple[Family, Family | None]]


def _families(rows: Sequence[Row], types: Sequence[str],
              subsets: Sequence[tuple[int, ...]]) -> Families:
    """Subset -> (family, translated family): one projection per value of
    the other columns."""
    out: Families = {}
    for s in subsets:
        rest = [i for i in range(len(types)) if i not in s]
        groups: dict[tuple[object, ...], set[Member]] = {}
        for row in rows:
            groups.setdefault(tuple(row[i] for i in rest), set()).add(
                tuple(row[i] for i in s))
        fam = frozenset(frozenset(g) for g in groups.values())
        at = [j for j, i in enumerate(s) if types[i] in POSITION_TYPES]
        tfam = frozenset(_normalized(g, at) for g in groups.values()) \
            if at else None
        out[s] = (fam, tfam)
    return out


def _spread(family: Family, subset: tuple[int, ...],
            types: Sequence[str]) -> bool:
    """Every set of the family holds two cells or more: one cell is the
    same up to translation whatever the other columns hold."""
    cells = [j for j, i in enumerate(subset) if types[i] in POSITION_TYPES]
    return all(len({tuple(m[j] for j in cells) for m in g}) >= 2
               for g in family)


def _data_types(solver: Solver) -> frozenset[str]:
    return POSITION_TYPES | {OFFSET, NUMBER, COLOR} \
        | frozenset(solver.lib.orientation_types)


def _split(rows: Sequence[Row], key: Callable[[Row], tuple[Value, ...]]
           ) -> dict[tuple[Value, ...], list[Row]]:
    out: dict[tuple[Value, ...], list[Row]] = {}
    for row in rows:
        out.setdefault(key(row), []).append(row)
    return out


_MASKED: Value = ""
"""What a row's case values hold at a field of a record case column
that holds no case (`case_key`)."""


def case_key(reading: CaseTypes, types: Sequence[str],
             case_cols: Sequence[int]) -> Callable[[Row], tuple[Value, ...]]:
    """A row's case values: each case column's value, a record's fields
    that hold no case masked, since a record column with a case field is
    a case column in that field and a key in its other fields."""
    def mask(type: str, value: Value) -> Value:
        fields = reading.fields(type)
        if fields is None \
                or not isinstance(value, RecordValue) \
                or len(fields) != len(value.fields):
            return value
        return RecordValue(tuple(
            mask(f, v) if f in reading.types else _MASKED
            for f, v in zip(fields, value.fields, strict=True)))

    return lambda row: tuple(mask(types[i], row[i]) for i in case_cols)


def keyed_too(reading: CaseTypes, type: str) -> bool:
    """Whether a case column of `type` is a record with a field that
    holds no case, which makes it a key too."""
    fields = reading.fields(type)
    if fields is None:
        return False
    return any(f not in reading.types or keyed_too(reading, f)
               for f in fields)


@dataclass(frozen=True)
class Rect:
    """A rectangle of cells, by its height and width."""

    height: int
    width: int


def rect(points: set[tuple[int, int]]) -> Rect | None:
    """The rectangle the cells fill, where they fill their bounding
    rectangle; None otherwise."""
    if not points:
        return None
    ts = [p[0] for p in points]
    ls = [p[1] for p in points]
    h, w = max(ts) - min(ts) + 1, max(ls) - min(ls) + 1
    return Rect(h, w) if h * w == len(points) else None
def member_key(member: Member) -> tuple[object, ...]:
    """An order on the members of a value, built from their parts."""
    return tuple(value_key(v) if isinstance(v, (int, float, str, AdtValue,
                                                RecordValue))
                 else (4, v) for v in member)


class SearchEnd(StrEnum):
    """How the witness search of a value ended (`find_witness`), but where
    some case that takes it fits the pairs and none fits the pairs with its
    counterpart (`NoFit`)."""

    CASES_FAILED = "cases failed"
    """The run that enumerates the cases failed, so the search looked
    with no case and ran on no grid."""
    UNFIT = "unfit"
    """No case that takes the value fits the pairs, so the search ran on
    no grid."""
    UNTAKEN = "untaken"
    """No judged case of the solver with the value's line standing, of
    the bases the value stands for where its rows hold a case column
    (`Found.bases`), takes the value's branch, so the search ran on no
    grid."""
    FOUND = "found"
    """A grid gave a witness (`Found.move`)."""
    FAILED = "failed"
    """No grid gave a witness, and a run failed (`Found.failed`)."""
    UNSEPARATED = "unseparated"
    """The search ran on every grid with no run failed, and some grid
    changes the value but gives no witness (`Found.unseparated`)."""
    UNCHANGED = "unchanged"
    """The search ran on every grid with no run failed, and no grid
    changes the value."""


@dataclass
class Found:
    """One column subset of one relation whose projected value repeats on
    every input, at the `Choice` cases whose rows hold it where a column
    holds the case. The survey asks some of them for a `@store` line
    (`asks_line`)."""

    relation: RelationName
    """The relation as a top-level clause reads it."""
    decl: RelationDecl
    columns: tuple[str, ...]
    """The names of the columns the value lives in."""
    keys: tuple[str, ...]
    """The names of the other columns, but the case's and `Unit` ones."""
    types: tuple[str, ...]
    sub: bool
    """The value lives in fewer columns than the relation's own."""
    kind: ValueKind
    family: Family
    """One value set per key; one set for an `OWNED` value."""
    subset: tuple[int, ...]
    case_values: tuple[tuple[Value, ...], ...]
    """The values of the case columns of the rows that hold the value;
    empty where no column holds the case."""
    cases: tuple[Case, ...]
    """The `Choice` cases those values stand for."""
    case_names: tuple[str, ...] = field(default=(), kw_only=True)
    """`cases` by the fewest names that denote exactly them."""
    bases: frozenset[Base | None]
    """The bases of the solver's cases those values stand for."""
    site: str | None
    """The instance whose `.init` a line on the relation stands above;
    None where the line stands above the relation's `.decl`."""
    spelled: str
    """The relation as a line at the site spells it."""
    rect: Rect | None = None
    named: str | None = None
    """The relation as a line above the site's `.init` names it; None
    where the line stands above the relation's `.decl`."""
    concept: bool = True
    concept_section: bool = True
    """Where no column holds the case: whether the concept case runs a
    clause that feeds the relation, as the case markers place it
    (`concept_section`); the store section's order reads it."""
    concept_stored: bool = False
    """At the concept case's rows, the value is a parameter's already."""
    stored: bool = False
    """At every case the rows hold, and where no column holds the case
    at every row, the value is stored already (`StoredAlready`), or it is
    the value of stored parameters that feed it, read back
    (`reads_back`)."""
    reads_back: tuple[tuple[str, ...], ...] = ()
    """Each set of stored parameters whose rows, or the product of whose
    rows, the value equals on every input under a renaming of columns,
    and each of which feeds the value (`read_back`); empty where it is no
    such value."""
    read: bool = True
    used_in: tuple[str, ...] = ()
    line: StoreBranch | None = None
    ignored: bool = False
    homonyms: tuple[RelationName, ...] = ()
    ended: SearchEnd | NoFit | None = None
    """How its witness search ended; None where no search ran, as on a
    value with homonyms or with an entry of its name."""
    move: "Move | None" = None
    unseparated: tuple[Case, Case] | None = None
    """Where some grid the witness search tries changes the value and on
    none does a case it looks with (`witness_targets`) give the output a
    witness needs (`witness_divergence`): the first case it looks with
    and that case's counterpart (`find_witness`)."""
    failed: "FailedRun | None" = None
    entry: bool = False
    built: Entry | None = None
    built_by: BuiltBy | None = None
    """What `built` was built from."""

    @property
    def untaken(self) -> bool:
        """No case takes the value (`SearchEnd.UNTAKEN`)."""
        return self.ended is SearchEnd.UNTAKEN

    @property
    def no_witness(self) -> bool:
        """The witness search ran on every grid, no run failed, and no
        grid gave a witness (`SearchEnd.UNSEPARATED`,
        `SearchEnd.UNCHANGED`), or no case that takes the value fits the
        pairs (`SearchEnd.UNFIT`)."""
        return self.ended in (SearchEnd.UNSEPARATED, SearchEnd.UNCHANGED,
                              SearchEnd.UNFIT)

    @property
    def asks_line(self) -> bool:
        """The survey asks for a `@store` line, or a bare `@ignore: store`
        line, on the value."""
        return self.line is None and self.store_branch and not self.no_witness

    @property
    def one(self) -> ValueSet:
        """The value's least set by `member_key`; its only one for an
        `OWNED` value."""
        return min(self.family, key=lambda v: sorted(
            member_key(m) for m in v))

    @property
    def depended(self) -> bool:
        """Some case of the solver depends on the relation."""
        return self.read or bool(self.used_in)

    @property
    def colors(self) -> bool:
        return bool(self.types) and all(t == COLOR for t in self.types)

    @property
    def storable(self) -> bool:
        return self.kind is ValueKind.OWNED and self.depended and not self.ignored

    @property
    def store_branch(self) -> bool:
        """A `@store` branch stores the value: a line stands on the
        relation, or no stored value gives it already and no Params
        parameter stores it: a Params parameter stores a color only where
        the concept case reads it."""
        return self.storable and (self.line is not None or (
            not self.stored
            and not (self.colors and self.read and self.concept)))

    @property
    def asks_params(self) -> bool:
        """The value is a color on every input with no `@store` line, and
        the concept case reads it: its stored reading is a Params
        parameter (docs/handbook/principles.md#stored-or-derived)."""
        return self.storable and not self.store_branch and self.read \
            and self.concept and not self.concept_stored

    @property
    def name(self) -> StoreBranch:
        """The `@store` branch: its line's, or the branch a line on the
        relation would hold, as the survey judges it (`_lineless`)."""
        return self.line or _lineless(self)

    @property
    def case_id(self) -> str:
        """The branch's name, `<spelled>=stored`."""
        return branch_text(self.name)


@dataclass(frozen=True)
class StoreSurvey:
    """The `store` report of one solver: the values it finds, the
    relations over the row cap, the runs on an input that failed, the
    audit's findings, and whether some relation stands between `in` and
    `out`."""

    found: tuple[Found, ...]
    capped: tuple[RelationName, ...]
    failed: tuple[Finding, ...]
    findings: tuple[Finding, ...]
    between: bool

    @property
    def listed(self) -> tuple[Found, ...]:
        """The values the report lists: those some case reads, but a
        value stored already that no `@store` line names, since storing
        it adds no branch
        ([Program](docs/handbook/solver-file.md#program)); a value that
        reads stored parameters back stays, to say which it reads."""
        return tuple(f for f in self.found
                     if f.depended and not (f.stored and f.line is None
                                            and not f.reads_back))


def site_of(solver: Solver, index: Index, path: RelationName,
            decl: RelationDecl) -> tuple[str | None, str, str | None]:
    """The instance whose `.init` a line on the relation stands above, and
    the relation as that line spells it
    ([Program](docs/handbook/solver-file.md#program)): the innermost
    instance on the relation's path that the solver's own text
    initializes; no instance, and the relation's own name, where the
    solver's own text declares it. The third part is the relation as a
    line above the `.init` names it, from that instance on; None where
    the line stands above the `.decl`."""
    got = resolved(index, path, TOP)
    if own(decl.span):
        return None, path.name, None
    parts = path.instances
    at = max((k for k, i in enumerate(got.through)
              if isinstance(d := solver.program.declaration(i), Instance)
              and own(d.span)), default=-1)
    if at < 0:
        return None, path.text, None
    return (parts[at], RelationName(parts[at:], path.name).text,
            RelationName(parts[at + 1:], path.name).text)


def analyze(solver: Solver, runs: Runs, rels: Sequence[RelationName],
            per_input: Sequence[Mapping[RelationName, tuple[Row, ...]]],
            bases: Sequence[Base | None], rd: Dependence
            ) -> tuple[list[Found], list[RelationName]]:
    """Each relation's repeating values at each case and each subset of
    its data columns, and the relations over the row cap. A row's case
    values stand for the bases that hold them (`holds_at`) and depend on
    the relation (`dependence`)."""
    data = _data_types(solver)
    found: list[Found] = []
    capped: list[RelationName] = []
    for path in rels:
        if any(not g.get(path) for g in per_input) \
                or ident_keyed(solver.engine, solver.program, path):
            continue
        decl = relation_decl(runs.engine, solver.program, path)
        held_by_case = case_reading(solver, path)
        types, case_cols = held_by_case.types, held_by_case.case
        rows_per = [g[path] for g in per_input]
        if max(len(r) for r in rows_per) > ROW_CAP:
            capped.append(path)
            continue
        site, spelled, named = site_of(solver, runs.index, path, decl)
        held = case_types(solver)
        keyed = {i for i in case_cols if keyed_too(held, types[i])}
        reading = set(rd.relations.get(path, ()))
        by_case = [_split(rows, case_key(held, types, case_cols))
                   for rows in rows_per]
        common = set(by_case[0]).intersection(*by_case[1:])
        data_cols = [i for i, t in enumerate(types) if t in data]
        names = [c.name for c in decl.columns]
        columns = [i for i in range(len(types))
                   if (i not in case_cols or i in keyed)
                   and types[i] not in LABEL_TYPES]
        for case in sorted(common, key=row_key):
            crow = [b[case] for b in by_case]
            colsets = [[{r[i] for r in rows} for i in range(len(types))]
                       for rows in crow]
            cols = [i for i in data_cols
                    if all(cs[i] == colsets[0][i] for cs in colsets)
                    or types[i] in POSITION_TYPES]
            if not cols:
                continue
            subsets = [s for k in range(1, len(cols) + 1)
                       for s in combinations(cols, k)]
            fams = [_families(rows, types, subsets) for rows in crow]
            hits: dict[tuple[int, ...], ValueKind] = {}
            for s in subsets:
                fam0, tfam0 = fams[0][s]
                if all(f[s][0] == fam0 for f in fams):
                    hits[s] = ValueKind.OWNED if len(fam0) == 1 \
                        else ValueKind.CONSTANT
                elif tfam0 is not None and _spread(tfam0, s, types) \
                        and all(f[s][1] == tfam0 for f in fams):
                    hits[s] = ValueKind.TRANSLATED
            keep = {s: k for s, k in hits.items()
                    if not any(set(s) < set(s2)
                               and hits[s2] in (k, ValueKind.OWNED)
                               for s2 in hits)}
            restricted = frozenset(b for b in bases if case and holds_at(
                solver, b, types, case_cols, case) and b in reading)
            cases_named = _named_case(
                solver, [b for b in bases if b in restricted], types,
                case_cols) if case else ()
            for s, kind in keep.items():
                fam0, tfam0 = fams[0][s]
                family = tfam0 if kind is ValueKind.TRANSLATED else fam0
                assert family is not None
                keys = [i for i in range(len(types)) if i not in s
                        and (i not in case_cols or i in keyed)
                        and types[i] != UNIT]
                shape: Rect | None = None
                if len(s) == 1 and types[s[0]] == POSITION \
                        and len(family) == 1:
                    (one,) = family
                    points = {p for m in one if (p := (
                        m[0] if kind is ValueKind.TRANSLATED
                        else corner(m[0]))) is not None
                        and isinstance(p, tuple)}
                    shape = rect(points)  # type: ignore[arg-type]
                found.append(Found(
                    path, decl, tuple(names[i] for i in s),
                    tuple(names[i] for i in keys),
                    tuple(types[i] for i in s), len(s) < len(columns),
                    kind, family, s, (case,) if case else (),
                    cases_named, restricted, site, spelled, shape,
                    named=named))
    return _merge(found), capped


def _named_case(solver: Solver, restricted: Sequence[Base | None],
                types: Sequence[str], case_cols: Sequence[int]
                ) -> tuple[Case, ...]:
    """The cases a row's case values stand for: of the bases that hold
    them, the model of the constructors they hold, the one that takes
    the concept branch at every point no case column holds
    (docs/handbook/principles.md#choice-points-and-open-parameters, "A branch's
    model"); where no base of the solver is that model, every base that holds
    them."""
    choice = solver.choice
    if choice is None or not restricted:
        return ()
    reading = case_types(solver)
    carried = {t for i in case_cols for t in _case_leaf_types(reading,
                                                              types[i])}
    if CHOICE in carried:
        carried |= {p.type for p in choice.points}
    for b in restricted:
        if b is None:
            continue
        if all(non_concept_at(choice, b, p) is None
               for p in choice.points if p.type not in carried):
            return (base_case(b),)
    return tuple(base_case(b) for b in restricted)


def _case_leaf_types(reading: CaseTypes, type: str) -> set[str]:
    """The types of the case-typed places of a value of `type`
    (`CaseTypes.leaves`)."""
    fields = reading.fields(type)
    if fields is None:
        return {type}
    return {x for f in fields if f in reading.types
            for x in _case_leaf_types(reading, f)}


def _merge(found: list[Found]) -> list[Found]:
    """One entry per value, with the cases that give the same value on
    one line."""
    out: list[Found] = []
    by: dict[tuple[object, ...], Found] = {}
    for f in found:
        sig = (f.relation, f.columns, f.kind, f.family)
        first = by.get(sig)
        if first is None:
            by[sig] = f
            out.append(f)
            continue
        first.case_values = (*first.case_values, *f.case_values)
        first.cases = tuple(dict.fromkeys((*first.cases, *f.cases)))
        first.bases = first.bases | f.bases
    return out


# A value on a grid


def projection(rows: Sequence[Row], f: Found,
               key: Callable[[Row], tuple[Value, ...]],
               types: Sequence[str]) -> Family | None:
    """The finding's value on a grid whose run gave `rows`: None where the
    relation stands empty there at the finding's cases."""
    mine = [r for r in rows
            if not f.case_values or key(r) in f.case_values]
    if not mine:
        return None
    fam, tfam = _families(mine, types, [f.subset])[f.subset]
    return tfam if f.kind is ValueKind.TRANSLATED and tfam is not None \
        else fam


def _lineless(f: Found) -> StoreBranch:
    """The branch a `@store` line on the value's relation would hold, as
    the survey judges a value with its line standing."""
    return StoreBranch(f.relation, f.spelled, None)

