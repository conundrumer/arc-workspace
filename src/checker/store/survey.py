"""The values the `store` survey finds, and what it judges of each.

A relation's value is read per case where a column carries the case, and
at each subset of its data columns: one value on every input (`OWNED`),
one family of values keyed by the other columns (`CONSTANT`), or one
value once each set is shifted to its own corner (`TRANSLATED`). Of each
value the survey judges whether some case reads it, whether it is stored
already, and where a line on it stands."""

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from itertools import combinations, permutations
from typing import TYPE_CHECKING

from checker.branches.witnesses import BuiltBy
from checker.finding import Finding
from checker.lint.view import literal_vars, term_vars
from checker.runs import Runs
from engine import (
    AdtValue,
    DeclId,
    Index,
    RecordValue,
    RelationName,
    Resolved,
    Row,
    Scope,
    Value,
)
from engine.engine import resolved
from engine.program import (
    Atom,
    AtomLiteral,
    BodyLiteral,
    Disjunction,
    Instance,
    Qualifier,
    RelationDecl,
    Term,
    Unit,
    own,
)
from engine.quotes import quotes
from solver.model import (
    choice_values,
    Base,
    Case,
    base_case,
    StoreBranch,
    non_concept_at,
)
from solver.aggregate import TOP, Solver, lists_case
from solver.readers import marker_at
from solver.columns import ident_keyed
from solver.graph import Graph, InstancePath
from solver.case_columns import holds_at
from solver.case_types import (
    CaseTypes,
    Pattern,
    joined,
    known,
    case_types,
)
from solver.dependence import Dependence, dependent_bases
from solver.names import branch_text, marker_lists
from solver.solve import (
    case_reading,
    parameter_reading,
    per_case,
    position,
    relation_decl,
    row_key,
    rows_at,
    value_key,
)
from solver.vocabulary import (
    BOX,
    CHOICE,
    COLOR,
    IDENT,
    NUMBER,
    OFFSET,
    PARAMS_SCOPE,
    POSITION,
    RUN_RELATIONS,
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
SKIP = frozenset(r.name for r in RUN_RELATIONS)
"""The names of the run's own relations, which no survey proposes."""


# The relations between `in` and `out`


def _declaration(index: Index, rel: RelationName, scope: Scope
                 ) -> DeclId | None:
    got = index.resolve(rel, scope)
    return got.declaration if isinstance(got, Resolved) else None


def between(solver: Solver, index: Index, rd: Dependence
            ) -> tuple[RelationName, ...]:
    """The relations between `in` and `out`: each relation a base's
    derivation of `out` depends on (`dependence`) whose rows depend on
    `in` by dataflow, relation by relation, a lib instance's relations
    each on their own (`solver.graph.Graph.reads_input`), by the name a
    top-level clause reads it by, but the run's own relations and the
    inline ones."""
    graph = Graph(solver.program, solver.engine)
    out: list[RelationName] = []
    for rel in rd.relations:
        d = _declaration(index, rel, TOP)
        r = None if d is None else solver.program.relation(d)
        if r is None or not graph.reads_input(rel) \
                or rel.name in SKIP \
                or Qualifier.INLINE in r.qualifiers:
            continue
        out.append(rel)
    return tuple(sorted(out, key=lambda r: r.text))


def feeding(solver: Solver, index: Index, decl: DeclId) -> list[Unit]:
    """The clauses that put rows into a relation, through the engine's
    index; a subsumptive clause puts none in."""
    return [u for occ in index.feeding(decl)
            if (u := solver.program.unit(occ.unit)) is not None
            and not u.subsumptive]


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
    """The top and the left of a Box value (`solver.solve.position`)."""
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
that carries no case (`case_key`)."""


def case_key(reading: CaseTypes, types: Sequence[str],
             case_cols: Sequence[int]) -> Callable[[Row], tuple[Value, ...]]:
    """A row's case values: each case column's value, a record's fields
    that carry no case masked, since a record column with a case field is
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


def _keyed_too(reading: CaseTypes, type: str) -> bool:
    """Whether a case column of `type` is a record with a field that
    carries no case, which makes it a key too."""
    fields = reading.fields(type)
    if fields is None:
        return False
    return any(f not in reading.types or _keyed_too(reading, f)
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
    """How the witness search of a value ended (`find_witness`)."""

    CASES_FAILED = "cases failed"
    """The run that enumerates the cases failed, so the search looked
    with no case and ran on no grid."""
    UNTAKEN = "untaken"
    """No case takes the value, so the search ran on no grid."""
    NO_FIT = "no fit"
    """No case that takes the value fits the pairs with its counterpart
    (`witness_targets`), so the search ran on no grid."""
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
    carries the case. Where it has no `@store` line and a `@store` branch
    stores it (`store_branch`), the survey asks for a `@store` line or a
    bare `@ignore: store` line on it, but where its witness search ran on
    every grid with no run failed and found no witness (`no_witness`)."""

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
    empty where no column carries the case."""
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
    """Where no column carries the case: whether the concept case runs a
    clause that feeds the relation, as the case markers place it
    (`concept_section`); the store section's order reads it."""
    concept_stored: bool = False
    """At the concept case's rows, the value is a parameter's already."""
    stored: bool = False
    """At every case the rows hold, and where no column carries the case
    at every row, the value is stored already (`StoredAlready`), or it is
    stored parameters' value read back (`reads_back`)."""
    reads_back: tuple[str, ...] = ()
    """The stored parameters whose rows, or the product of whose rows,
    the value is on every input under a renaming of columns
    (`read_back`); empty where it is no such value."""
    read: bool = True
    used_in: tuple[str, ...] = ()
    line: StoreBranch | None = None
    ignored: bool = False
    homonyms: tuple[RelationName, ...] = ()
    ended: SearchEnd | None = None
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
        `SearchEnd.UNCHANGED`)."""
        return self.ended in (SearchEnd.UNSEPARATED, SearchEnd.UNCHANGED)

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
        relation, or it is no color, which a Params parameter stores
        instead, and no stored value gives it already."""
        return self.storable and (self.line is not None or (
            not self.colors and not self.stored))

    @property
    def asks_params(self) -> bool:
        """The value is a color on every input with no `@store` line, and
        the concept case reads it: its stored reading is a Params
        parameter (principles.md, under "Stored or derived")."""
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
        keyed = {i for i in case_cols if _keyed_too(held, types[i])}
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
    them, the model of the constructors they carry, the one that takes
    the concept branch at every point no case column carries
    (principles.md, "A branch's model"); where no base of the solver is
    that model, every base that holds them."""
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


# Stored already


def _literals(body: Sequence[BodyLiteral] | None) -> Iterator[BodyLiteral]:
    """A clause's body literals, each disjunction's branches in place,
    its aggregates' bodies left out."""
    for lit in body or ():
        if isinstance(lit, Disjunction):
            for b in lit.branches:
                yield from _literals(b)
        else:
            yield lit


type Place = tuple[InstancePath, DeclId]
"""A relation at the instance it stands at: the instance path that
declares it (`solver.graph.Graph.place`), and its declaration."""


@dataclass(frozen=True)
class _Frame:
    """One clause of a relation read at a row (`Pattern`): the clause, the
    instance path it runs at, and the value the row fixes of each variable
    of its head."""

    unit: Unit
    at: InstancePath
    env: dict[str, Value]


class StoredAlready:
    """Whether the value of a relation at some of its columns, at a row
    (`Pattern`), is stored already: a Params read
    ([Stored or derived](docs/handbook/principles.md#stored-or-derived)
    and [Params](docs/handbook/solver-file.md#params)). It is where some
    clause may put the row into the relation, and in each clause that may,
    each variable of the head's terms at those columns takes stored values
    alone, following its bindings through stored relations (`_var`). A
    term with no variable, a literal fact's among them, is not stored
    already, nor is a value read on a cycle of the relations. A relation
    is read at each instance it stands at (`Place`), with the clauses
    that feed it there (`solver.graph.Graph.feeding`)."""

    def __init__(self, solver: Solver, index: Index) -> None:
        self.solver = solver
        self.index = index
        self.graph = Graph(solver.program, solver.engine)
        self.program = solver.program
        self.done: dict[tuple[Place, frozenset[int], Pattern], bool] = {}
        self.open: set[tuple[Place, frozenset[int], Pattern]] = set()
        self.holds: dict[tuple[Place, Pattern], bool] = {}
        self.constants = solver.lib.constants

    def place(self, unit: Unit, at: InstancePath, rel: RelationName
              ) -> Place | None:
        """The relation a unit running at `at` names by `rel`
        (`Graph.place`)."""
        return self._placed(at, rel, unit.scope)

    def top(self, rel: RelationName) -> Place | None:
        """The relation a top-level clause names by `rel`."""
        return self._placed((), rel, TOP)

    def _placed(self, at: InstancePath, rel: RelationName, scope: Scope
                ) -> Place | None:
        """The relation a unit of `scope` running at `at` names by
        `rel`."""
        q = self.graph.place(at, rel)
        d = _declaration(self.index, rel, scope)
        return None if q is None or d is None else (q.instances, d)

    def at(self, place: Place, cols: frozenset[int], row: Pattern) -> bool:
        """Whether the value of the relation at `place` at its columns
        `cols`, at the row `row`, is stored already."""
        key = (place, cols, row)
        if key in self.done:
            return self.done[key]
        if key in self.open:
            return False
        self.open.add(key)
        frames = [f for f in self._frames(place, row) if self._feasible(f)]
        got = bool(frames) and all(
            self._term(frame.unit.head.args[c], frame)
            for frame in frames for c in sorted(cols))
        self.open.remove(key)
        self.done[key] = got
        return got

    def _feeding(self, place: Place) -> list[tuple[Unit, InstancePath]]:
        """The clauses that put rows into the relation at `place`
        (`Graph.feeding`)."""
        path, decl = place
        return self.graph.feeding(
            RelationName(path, self.program.declared_relation(decl).name))

    def _frames(self, place: Place, row: Pattern) -> list[_Frame]:
        """Each clause that may put the row into the relation."""
        out: list[_Frame] = []
        for u, at in self._feeding(place):
            env = joined(u.head.args, row, self.constants.get)
            if env is not None:
                out.append(_Frame(u, at, env))
        return out

    def _feasible(self, frame: _Frame) -> bool:
        """Whether each positive atom of the clause's body may hold a row
        with the values the frame fixes of its terms (`_can_hold`): a
        clause whose body reads a relation that holds no such row puts no
        row in."""
        for lit in frame.unit.body or ():
            if not isinstance(lit, AtomLiteral) or lit.negated:
                continue
            decl = self._decl(lit.atom, frame)
            if decl is None:
                continue
            row = tuple(known(t, frame.env, self.constants.get) for t in lit.atom.args)
            if all(v is None for v in row):
                continue
            if not self._can_hold(decl, row):
                return False
        return True

    def _can_hold(self, place: Place, row: Pattern) -> bool:
        """Whether the relation at `place` may hold a row that `row`
        admits: a relation no clause feeds may, and one some clause feeds
        where a clause that may put such a row in is feasible."""
        key = (place, row)
        if key in self.holds:
            return self.holds[key]
        self.holds[key] = True
        feeding = self._feeding(place)
        got = not feeding or any(self._feasible(f)
                                 for f in self._frames(place, row))
        self.holds[key] = got
        return got

    def _term(self, term: Term, frame: _Frame) -> bool:
        names = sorted(term_vars(term))
        return bool(names) and all(self._var(n, frame) for n in names)

    def _var(self, name: str, frame: _Frame) -> bool:
        """Whether a variable takes stored values alone: the row does not
        fix it, and a positive atom of the body binds it at columns whose
        value is stored (`_bound_stored`). Every other literal that holds
        it, a test or a join, only narrows the stored values it takes, so
        a relation fed from the values of an open parameter is stored
        already."""
        return name not in frame.env \
            and self._bound_stored(frame.unit.body, name, frame)

    def _bound_stored(self, body: Sequence[BodyLiteral] | None, name: str,
                      frame: _Frame) -> bool:
        """Whether some positive atom of `body` binds `name` at columns
        whose value is stored (`_atom`); a disjunction binds it so where
        each of its branches does."""
        for lit in body or ():
            if isinstance(lit, Disjunction):
                if lit.branches and all(self._bound_stored(b, name, frame)
                                        for b in lit.branches):
                    return True
                continue
            if not isinstance(lit, AtomLiteral) or lit.negated:
                continue
            atom = lit.atom
            cols = tuple(j for j, t in enumerate(atom.args)
                         if name in term_vars(t))
            binding = self._binding(atom, cols, frame)
            if binding and self._atom(atom, binding, frame):
                return True
        return False

    def _decl(self, atom: Atom, frame: _Frame) -> Place | None:
        return self.place(frame.unit, frame.at, atom.relation)

    def _binding(self, atom: Atom, cols: tuple[int, ...], frame: _Frame
                 ) -> tuple[int, ...]:
        decl = self._decl(atom, frame)
        if not cols or decl is None or not self._inline(decl):
            return cols
        return tuple(j for j in cols if self._binds(decl, len(atom.args), j))

    def _binds(self, decl: Place, width: int, col: int) -> bool:
        """Whether each clause of an inline relation binds its column
        `col`: Souffle puts its clauses in place of its atoms."""
        return all(
            term_vars(f.unit.head.args[col]) <= {
                v for lit in _literals(f.unit.body)
                if isinstance(lit, AtomLiteral) and not lit.negated
                for v in literal_vars(lit)}
            for f in self._frames(decl, (None,) * width))

    def _atom(self, atom: Atom, cols: tuple[int, ...], frame: _Frame
              ) -> bool:
        """Whether a body atom gives a stored value at its columns `cols`:
        it reads a Params relation, or a relation whose value there is
        stored already at the row the atom's other terms fix."""
        decl = self._decl(atom, frame)
        if decl is None:
            return False
        if self._params(decl):
            return True
        row = tuple(None if j in cols else known(t, frame.env, self.constants.get)
                    for j, t in enumerate(atom.args))
        return self.at(decl, frozenset(cols), row)

    def _params(self, place: Place) -> bool:
        return self.program.declared_relation(place[1]).scope == PARAMS_SCOPE

    def _inline(self, place: Place) -> bool:
        return Qualifier.INLINE in self.program.declared_relation(place[1]).qualifiers


def read_back(solver: Solver, f: Found) -> tuple[str, ...]:
    """The stored parameters whose value the found value is on every
    input: the same rows as one parameter's, or as the product of several
    parameters' rows, under a renaming of columns, each column of the
    value of a parameter column's type (principles.md, under "Stored or
    derived"); a parameter that stores a value per case gives its value at
    the found value's bases (`_stored_reading`). The fewest parameters
    that give it, in `Params` order; empty where none do."""
    if len(f.family) != 1:
        return ()
    (value,) = f.family
    width = len(f.types)
    stored: dict[str, tuple[tuple[str, ...], tuple[Row, ...]]] = {}
    for p in solver.params.parameters:
        if not isinstance(p.stored, tuple) or not p.stored:
            continue
        read = _stored_reading(solver, p.name, p.stored, f.bases)
        if read is None:
            stored[p.name] = (parameter_reading(solver, p.name).types,
                              p.stored)
        elif read[1]:
            stored[p.name] = read
    params = [n for n, (t, _r) in stored.items() if 0 < len(t) <= width]
    want = f.types
    for k in range(1, width + 1):
        for chosen in combinations(params, k):
            if sum(len(stored[n][0]) for n in chosen) != width:
                continue
            product = [()]
            for n in chosen:
                product = [r + tuple(s) for r in product
                           for s in stored[n][1]]
            got_types = tuple(t for n in chosen for t in stored[n][0])
            for order in permutations(range(width)):
                if any(got_types[order[i]] != want[i] for i in range(width)):
                    continue
                if frozenset(tuple(r[order[i]] for i in range(width))
                             for r in product) == value:
                    return tuple(chosen)
    return ()


@quotes("solver-file.md", "Params",
        "**Case column.** Where the cases that read a relation in Params "
        "store different values of it, the relation takes a case column in "
        "the form of `out`'s, and each fact's case column is the `Choice` "
        "value of the case that stores the fact.")
def _stored_reading(solver: Solver, name: str, rows: Sequence[Row],
                    bases: frozenset[Base | None]
                    ) -> tuple[tuple[str, ...], tuple[Row, ...]] | None:
    """For a parameter that stores a value per case (`per_case`), its
    value at the bases that hold a found value, with the value's column
    types: the one value they store, or no rows where they store
    different values; None for any other parameter."""
    pc = per_case(solver, name)
    if pc is None:
        return None
    values = {frozenset(rows_at(solver, pc, rows, b))
              for b in choice_values(bases)}
    if len(values) != 1:
        return pc.value_types, ()
    return pc.value_types, tuple(sorted(next(iter(values)), key=row_key))


def stored_already(solver: Solver, runs: Runs, stored: StoredAlready,
                   f: Found, concept: Base | None = None,
                   every: bool = True) -> bool:
    """Whether the value is stored already (`StoredAlready`): at the rows
    of every case that holds it, and at every row where no column carries
    the case; with `every` false, at the concept case's rows alone."""
    held_by_case = case_reading(solver, f.relation)
    types, case_cols = held_by_case.types, held_by_case.case
    place = stored.top(f.relation)
    if place is None:
        return False
    rows: tuple[tuple[Value, ...], ...] = f.case_values or ((),)
    if not every:
        values = next((v for v in f.case_values
                       if holds_at(solver, concept, types, case_cols, v)), None)
        if values is None:
            return False
        rows = (values,)
    for values in rows:
        held = case_types(solver)
        given = {i: v for i, v in zip(case_cols, values, strict=True)
                 if not _keyed_too(held, types[i])} if values else {}
        row = tuple(given.get(i) for i in range(len(types)))
        if not stored.at(place, frozenset(f.subset), row):
            return False
    return True


def concept_section(solver: Solver, graph: Graph, f: Found,
                    concept: Base | None) -> bool:
    """Whether the concept case runs a clause that feeds the value's
    relation at its instance path, as the case markers place the clause
    (solver-file.md, under "Cases"): a clause of the solver's own text under no
    marker that lists a case, or under a marker that lists the concept
    case, runs on it. The clauses that feed a relation of a lib instance
    are those that feed the instance (`Graph.heads`). A relation no clause
    of the solver's own text feeds holds one value for every case, the
    concept case's among them (the old tool's `_section_cases`)."""
    node = graph.resolve((), f.relation)
    lines = [(u.scope, u.span.first)
             for u, _at in (graph.heads.get(node, ()) if node else ())
             if u.span is not None]
    if not lines:
        return True
    for scope, line in lines:
        marker = marker_at(solver, scope, line)
        if marker is None or not lists_case(solver, marker) \
                or marker_lists(solver, marker, concept):
            return True
    return False


def concept_runs(solver: Solver, runs: Runs, rd: Dependence,
                 decl: RelationDecl, concept: Base | None) -> bool:
    """Whether the concept case's derivation depends on a clause of the
    solver's own text that feeds the relation; true where no such clause
    feeds it."""
    mine = [u for u in feeding(solver, runs.index, decl.id) if own(u.span)]
    return not mine or concept in dependent_bases(rd, (u.id for u in mine))


def _lineless(f: Found) -> StoreBranch:
    """The branch a `@store` line on the value's relation would hold, as
    the survey judges a value with its line standing."""
    return StoreBranch(f.relation, f.spelled, None)

