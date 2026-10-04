"""The `store` survey (procedure.md, under "Develop"): each program relation between
`in` and `out` whose projection onto some of its columns is the same on
every input of the task, with its witness, and the findings on the
solver's `@store` lines and on those relations.

A relation's value is read per case where a column carries the case, and
at each subset of its data columns: one value on every input (`OWNED`),
one family of values keyed by the other columns (`CONSTANT`), or one
value once each set is shifted to its own corner (`TRANSLATED`). The
witness of a stored value is a train input turned or mirrored by a D4
element, or with a stored color swapped for a free one, on which the
relation's value differs."""

from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from itertools import combinations, permutations

from checker.branches import (
    BuiltBy,
    bare_ignored,
    counterpart,
    entry_findings,
    excluded_finding,
    witness_divergence,
    witness_targets,
    idle_ignores,
    ordered,
    swap_entry,
    untaken,
    with_line,
)
from checker.finding import (
    AtFile,
    AtLine,
    AtPair,
    AtRelation,
    Finding,
    Kind,
    RunKind,
    UndecidedPayload,
    WholeFile,
)
from checker.judged import (
    NO_TASK,
    Swap,
    base_names,
    concept_among,
    enumeration_failed,
    no_result,
    swaps,
)
from checker.lint.view import literal_vars, term_vars
from checker.payloads.branches import (
    BranchPayload,
    ColorAskPayload,
    DiffersOn,
    DuplicatePayload,
    HomonymsPayload,
    KeyedBy,
    MarkerUnownedPayload,
    MissingLinePayload,
    NoAnchor,
    NoRows,
    NotBetween,
    NotCheckedPayload,
    NoValue,
    RelationPayload,
    RowCapPayload,
    StoreNoValuePayload,
    StoreValuesPayload,
    Unread,
)
from checker.runs import Runs
from engine import (
    AdtValue,
    DeclId,
    Engine,
    Grid,
    Index,
    RecordValue,
    RelationName,
    Resolved,
    Row,
    RunFailure,
    Scope,
    Value,
)
from engine.engine import resolved
from engine.program import (
    Atom,
    AtomLiteral,
    BodyLiteral,
    ConstructorTerm,
    DefinedName,
    Disjunction,
    Instance,
    NumberTerm,
    Qualifier,
    RecordTerm,
    RelationDecl,
    StringTerm,
    Term,
    Unit,
    Variable,
)
from engine.quotes import quotes
from solver.annotations import (
    CaseMarker,
    IgnoreForm,
)
from solver.model import (
    bases_of,
    choice_values,
    TOP,
    Base,
    Case,
    base_case,
    CaseTypes,
    Dependence,
    Graph,
    InstancePath,
    Pattern,
    joined,
    known,
    NodeKind,
    Solver,
    StoreBranch,
    case_types,
    dependence,
    every_base,
    ident_keyed,
    holds_at,
    is_concept,
    lists_case,
    marker_at,
    non_concept_at,
    own,
    readers,
)
from solver.names import branch_text, cover, marker_lists
from solver.problems import ProblemKind
from solver.solve import (
    Assignment,
    Grids,
    PairId,
    as_grid,
    at_once,
    case_reading,
    parameter_reading,
    examples,
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
    each on their own (`solver.model.Graph.reads_input`), by the name a
    top-level clause reads it by, but the run's own relations and the
    inline ones."""
    graph = Graph(solver.program)
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
that carries no case (`_case_key`)."""


def _case_key(reading: CaseTypes, types: Sequence[str],
              case_cols: Sequence[int]) -> Callable[[Row], tuple[Value, ...]]:
    """A row's case values: each case column's value, a record's fields
    that carry no case masked, since a record column with a case field is
    a case column in that field and a key in its other fields (plan §D5
    "Derive and store")."""
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


class D4(StrEnum):
    """The seven D4 elements other than the identity."""

    CW = "CW"
    HT = "HT"
    CC = "CC"
    LR = "LR"
    TB = "TB"
    DG = "DG"
    AD = "AD"


type Change = D4 | Swap
"""How a witness grid comes from a train input."""


def d4_images(grid: Grid) -> list[tuple[D4, Grid]]:
    """The seven other images of a grid under D4."""
    g = [list(r) for r in grid]
    h, w = len(g), len(g[0])
    rot = [[g[h - 1 - r][c] for r in range(h)] for c in range(w)]

    def lr(x: list[list[int]]) -> list[list[int]]:
        return [row[::-1] for row in x]

    def tb(x: list[list[int]]) -> list[list[int]]:
        return x[::-1]

    def tr(x: list[list[int]]) -> list[list[int]]:
        return [list(c) for c in zip(*x)]

    images = {D4.CW: rot, D4.HT: tb(lr(g)), D4.CC: tb(lr(rot)),
              D4.LR: lr(g), D4.TB: tb(g), D4.DG: tr(g), D4.AD: tb(lr(tr(g)))}
    return [(d, as_grid(images[d])) for d in D4]


@dataclass(frozen=True)
class Move:
    """The grid on which a relation's value differs: the train input it
    comes from, the D4 element or the color swap that made it, and
    whether the first case that takes the value gives it unchanged with
    the relation derived."""

    index: int
    change: Change
    grid: Grid
    identity: bool


@dataclass(frozen=True)
class FailedRun:
    """The first run of the witness search that failed: the grid it ran
    on, and the failure."""

    index: int
    change: Change
    failure: RunFailure


def member_key(member: Member) -> tuple[object, ...]:
    """An order on the members of a value, built from their parts."""
    return tuple(value_key(v) if isinstance(v, (int, float, str, AdtValue,
                                                RecordValue))
                 else (4, v) for v in member)


@dataclass
class Found:
    """One column subset of one relation whose projected value repeats on
    every input, at the `Choice` cases whose rows hold it where a column
    carries the case."""

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
    (`_concept_section`); the store section's order reads it."""
    concept_stored: bool = False
    """At the concept case's rows, the value is a parameter's already."""
    stored: bool = False
    """At every case the rows hold, and where no column carries the case
    at every row, the value is stored already (`StoredAlready`), or it is
    stored parameters' value read back (`reads_back`)."""
    reads_back: tuple[str, ...] = ()
    """The stored parameters whose rows, or the product of whose rows,
    the value is on every input under a renaming of columns
    (`_read_back`); empty where it is no such value."""
    read: bool = True
    used_in: tuple[str, ...] = ()
    line: StoreBranch | None = None
    ignored: bool = False
    homonyms: tuple[RelationName, ...] = ()
    untaken: bool = False
    move: Move | None = None
    unseparated: tuple[Case, Case] | None = None
    """Where some grid the witness search tries changes the value and on
    none does a case it looks with (`witness_targets`) give the output a
    witness needs (`witness_divergence`): the first case it looks with
    and that case's counterpart (`_witness`)."""
    failed: FailedRun | None = None
    entry: bool = False
    built: Entry | None = None
    built_by: BuiltBy | None = None
    """What `built` was built from."""

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
    markers under which cases they do not list read clauses, the audit's
    findings, and whether some relation stands between `in` and `out`."""

    found: tuple[Found, ...]
    capped: tuple[RelationName, ...]
    failed: tuple[Finding, ...]
    markers: tuple[Finding, ...]
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


def _analyze(solver: Solver, runs: Runs, rels: Sequence[RelationName],
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
                or ident_keyed(solver.program, path):
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
        by_case = [_split(rows, _case_key(held, types, case_cols))
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


# The survey


def _projection(rows: Sequence[Row], f: Found,
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


def _bases(solver: Solver, solver_cases: Sequence[Case]
           ) -> tuple[list[Base | None], Base | None]:
    """The bases of the solver's cases, and the concept case's base, added
    where no case of the solver is the concept case."""
    bases = bases_of(solver_cases)
    concept = concept_among(solver, bases)
    if concept is None and solver.choice is not None:
        every = every_base(solver.choice) or ()
        concept = concept_among(solver, every)
        if concept is not None:
            bases.append(concept)
    elif solver.choice is None and not bases:
        bases.append(None)
    return bases, concept


def marker_findings(engine: Engine, solver: Solver,
                    bases: Sequence[Base | None]) -> list[Finding]:
    """Each top-level marker that lists a case, where a base it does not
    list depends on a clause under it: with that marker set aside and
    every other standing, the model's `dependence` gives the base's
    derivation of `out` depending on the clause
    ([Cases](docs/handbook/solver-file.md#cases))."""
    if solver.choice is None:
        return []
    markers = solver.annotations.markers
    under: dict[int, list[Unit]] = {}
    for u in solver.program.units:
        if u.scope != TOP or not own(u.span) or u.span is None:
            continue
        marker = marker_at(solver, u.scope, u.span.first)
        if marker is not None:
            under.setdefault(marker.line, []).append(u)
    out: list[Finding] = []
    for m in markers:
        if m.line not in under or not lists_case(solver, m):
            continue
        aside = tuple(CaseMarker((), x.gloss, x.line) if x == m else x
                      for x in markers)
        rd = dependence(engine, replace(solver, annotations=replace(
            solver.annotations, markers=aside)), bases)
        lines = sorted({u.span.first for u in under[m.line]
                        if u.span is not None
                        and any(not marker_lists(solver, m, b)
                                for b in readers(rd, [u.id]))})
        if lines:
            out.append(Finding(Kind.MARKER_UNOWNED, AtLine(m.line),
                               MarkerUnownedPayload(m, tuple(lines))))
    return out


def store_survey(runs: Runs) -> StoreSurvey:
    """The `store` report (procedure.md, under "Develop"), and the findings
    the audit prints on the `@store` lines and on the values (`StoreSurvey`)."""
    solver = runs.solver
    solver_cases = runs.cases
    if not isinstance(solver_cases, tuple):
        stop = enumeration_failed(solver_cases)
        return StoreSurvey((), (), (stop,), (), (stop,), True)
    bases, concept = _bases(solver, solver_cases)
    rd = dependence(runs.engine, solver, bases)
    markers = tuple(marker_findings(runs.engine, solver, bases))
    task = solver.task
    rels = between(solver, runs.index, rd)
    if not rels:
        return StoreSurvey((), (), (), markers, (Finding(
            Kind.NOT_CHECKED, AtFile(WholeFile.SOLVER), NotCheckedPayload()),
            *markers, *_line_findings(runs, solver, rels, [], [], set(), {},
                                      solver_cases)), False)
    if task is None:
        stop = NO_TASK
        return StoreSurvey((), (), (stop,), markers, (stop, *markers), True)
    failed: list[Finding] = []
    per_input: list[Mapping[RelationName, tuple[Row, ...]]] = []
    labels: list[PairId] = []
    exs = list(examples(task))
    values = at_once(lambda pe: runs.defined_relations(as_grid(pe[1].input),
                                                   rels, ROW_CAP), exs)
    for (pair, _ex), got in zip(exs, values, strict=True):
        if isinstance(got, Mapping):
            per_input.append(got)
            labels.append(pair)
        else:
            failed.append(no_result(got, RunKind.STORE_SEARCH, None,
                                    AtPair(pair)))
    # A value is one value on every input only where every input ran: an
    # input whose run failed or timed out leaves every relation unjudged.
    if failed:
        return StoreSurvey((), (), tuple(failed), markers,
                           (*failed, *markers), True)
    found, capped = _analyze(solver, runs, rels, per_input, bases, rd)
    differs = {p: next((labels[i] for i, g in enumerate(per_input)
                        if set(g.get(p, ())) != set(per_input[0].get(p, ()))),
                       None) for p in rels}
    lines = {b.relation: b for b in solver.branches
             if isinstance(b, StoreBranch)}
    ignored = {t for t, _p in bare_ignored(solver, IgnoreForm.STORE)}
    stored = StoredAlready(solver, runs.index)
    graph = Graph(solver.program)
    among = bases_of(solver_cases)
    for f in found:
        f.case_names = base_names(solver, [c.base for c in f.cases], among)
        f.line = lines.get(f.relation)
        if f.line is not None:
            f.spelled = f.line.spelled
        f.ignored = f.line is None and f.relation in ignored
        by = rd.relations.get(f.relation, ())
        f.read = concept in by or (solver.choice is None and bool(by))
        f.used_in = () if f.read else base_names(solver, [
            b for b in by if not is_concept(solver, b)], bases)
        f.stored = _stored_already(solver, runs, stored, f)
        if not f.stored and f.kind is ValueKind.OWNED:
            f.reads_back = _read_back(solver, f)
            f.stored = bool(f.reads_back)
        if f.case_values:
            f.concept = concept in f.bases
            f.concept_stored = f.concept and _stored_already(
                solver, runs, stored, f, concept, every=False)
        else:
            f.concept = _concept_runs(solver, runs, rd, f.decl, concept)
            f.concept_stored = f.concept and f.stored
            f.concept_section = _concept_section(solver, graph, f, concept)
        if f.reads_back:
            f.concept_stored = f.concept
    wanted = [f for f in found if f.store_branch]
    spelled: dict[str, set[RelationName]] = {}
    for f in wanted:
        spelled.setdefault(f.name.spelled, set()).add(f.relation)
    for f in wanted:
        f.homonyms = tuple(sorted(spelled[f.name.spelled] - {f.relation},
                                  key=lambda p: p.text))
    searched: list[Found] = []
    for f in wanted:
        if f.homonyms:
            continue
        if runs.branch_entry(f.name) is not None:
            f.entry = True
            continue
        searched.append(f)
    for stop in at_once(lambda f: _witness(runs, solver, f), searched):
        if stop is not None:
            failed.append(stop)
    empty = {p for p in rels if all(not g.get(p) for g in per_input)}
    findings = [*failed, *markers, *_line_findings(
        runs, solver, rels, found, capped, empty, differs, solver_cases)]
    if capped:
        findings.append(Finding(Kind.STORE_ROW_CAP, AtFile(WholeFile.SOLVER),
                                RowCapPayload(tuple(capped), ROW_CAP)))
    return StoreSurvey(tuple(found), tuple(capped), tuple(failed), markers,
                       tuple(findings), True)


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
declares it (`solver.model.Graph.place`), and its declaration."""


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
    that feed it there (`solver.model.Graph.feeding`)."""

    def __init__(self, solver: Solver, index: Index) -> None:
        self.solver = solver
        self.index = index
        self.graph = Graph(solver.program)
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


def _read_back(solver: Solver, f: Found) -> tuple[str, ...]:
    """The stored parameters whose value the found value is on every
    input: the same rows as one parameter's, or as the product of several
    parameters' rows, under a renaming of columns, each column of the
    value of a parameter column's type (plan §D5 "Derive and store"); a
    parameter that stores a value per case gives its value at the found
    value's bases (`_stored_reading`). The fewest parameters that give
    it, in `Params` order; empty where none do."""
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


def _stored_already(solver: Solver, runs: Runs, stored: StoredAlready,
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


def _concept_section(solver: Solver, graph: Graph, f: Found,
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


def _concept_runs(solver: Solver, runs: Runs, rd: Dependence,
                  decl: RelationDecl, concept: Base | None) -> bool:
    """Whether the concept case's derivation depends on a clause of the
    solver's own text that feeds the relation; true where no such clause
    feeds it."""
    mine = [u for u in feeding(solver, runs.index, decl.id) if own(u.span)]
    return not mine or concept in readers(rd, (u.id for u in mine))


def _lineless(f: Found) -> StoreBranch:
    """The branch a `@store` line on the value's relation would hold, as
    the survey judges a value with its line standing."""
    return StoreBranch(f.relation, f.spelled, None)


@quotes("principles.md", "Witnesses",
        "A branch's witnesses are divergence witnesses between its model "
        "and the concept branch's model.")
def _witness(runs: Runs, solver: Solver, f: Found) -> Finding | None:
    """The first grid on which the value differs and a case the survey
    looks with (`witness_targets`, among the cases that take the value)
    gives the output a witness needs (`witness_divergence`): the D4 images
    of each train input in turn, then a color swap of each. A grid the
    relation stands empty on holds no value. It sets `Found.unseparated`
    and `Found.failed`. The failure of the run that enumerates the cases
    with the branch standing, where it fails."""
    task = solver.task
    assert task is not None
    branch = f.name
    lined = solver if f.line is not None else with_line(solver, branch)
    every = runs.cases if f.line is not None else runs.lined(lined)
    if not isinstance(every, tuple):
        return no_result(every, RunKind.CASE, None, AtRelation(f.relation))
    cases = [c for c in ordered(solver, every, branch)
             if not f.case_values or c.base in f.bases]
    if not cases:
        f.untaken = True
        return None
    models = witness_targets(runs, lined, cases, branch)
    if not models:
        return None
    model = models[0]
    other = counterpart(model, branch)
    held_by_case = case_reading(solver, f.relation)
    types, case_cols = held_by_case.types, held_by_case.case
    grids: list[tuple[int, Change, Grid]] = []
    for i, ex in enumerate(task.train):
        grids += [(i, d, g) for d, g in d4_images(as_grid(ex.input))]
    grids += [(s.index, s, s.grid) for s in swaps(runs.engine, solver, task, cases)]
    for index, change, grid in grids:
        got = runs.defined_relations(grid, [f.relation])
        if isinstance(got, Mapping):
            value = _projection(got[f.relation], f, _case_key(
                case_types(solver), types, case_cols), types)
            if value == f.family:
                continue
            apart = witness_divergence(runs, lined, models, branch, grid,
                                       Assignment(()))
            if apart is None:
                f.unseparated = (model, other)
                continue
            if isinstance(apart, tuple):
                failure = None
            else:
                failure = apart
        else:
            failure = got
        if failure is not None:
            f.failed = f.failed or FailedRun(index, change, failure)
            continue
        out = runs.outcomes_of(lined, [other], grid, Assignment(()))[other]
        f.move = Move(index, change, grid,
                      isinstance(out, Grids) and out.grids == (grid,))
        made = swap_entry(runs, lined, f.case_id, branch, index, change,
                          grid, every)
        f.built = made if isinstance(made, Entry) else None
        f.built_by = BuiltBy(lined, every)
        if not isinstance(made, Entry):
            return no_result(made, RunKind.WITNESS, None,
                             AtRelation(f.relation))
        return None
    return None


def _line_findings(runs: Runs, solver: Solver, rels: Sequence[RelationName],
                   found: Sequence[Found], capped: Sequence[RelationName],
                   empty: set[RelationName],
                   differs: Mapping[RelationName, PairId | None],
                   solver_cases: tuple[Case, ...]) -> list[Finding]:
    """The findings the audit prints: on each `@store` line, a second
    line on its relation, a relation that is also a parameter's name, a
    relation that gives no value the runner can store and why, cases
    that take two values of it, a name that denotes other relations too,
    an entry that witnesses nothing, and a value no case that reads the
    relation has; then the named `@ignore: store` lines that exclude no
    case; then each value with no `@store` line, and each color the
    concept case reads that asks for a Params parameter."""
    out: list[Finding] = []
    unread = {f.relation for f in found
              if f.kind is ValueKind.OWNED and not f.depended}
    first: dict[RelationName, StoreBranch] = {}
    stores = sorted(((b, b.line.line) for b in solver.branches
                     if isinstance(b, StoreBranch) and b.line is not None),
                    key=lambda bl: bl[1])
    first_line: dict[RelationName, int] = {}
    for b, line in stores:
        at = AtLine(line)
        if b.relation in first:
            out.append(Finding(Kind.DUPLICATE_BRANCH_LINE,
                               AtLine(first_line[b.relation]),
                               DuplicatePayload(first[b.relation],
                                                first_line[b.relation],
                                                line)))
            continue
        first[b.relation] = b
        first_line[b.relation] = line
        if solver.params.parameter(b.spelled) is not None:
            out.append(Finding(Kind.STORE_PARAMETER_NAME, at,
                               BranchPayload(b)))
            continue
        if ident_keyed(solver.program, b.relation):
            out.append(Finding(Kind.STORE_IDENT_KEY, at,
                               RelationPayload(b.relation)))
            continue
        if untaken(runs, solver, b):
            excluded = excluded_finding(runs, solver, b, at)
            if excluded is not None:
                out.append(excluded)
                continue
        mine = [f for f in found if f.relation == b.relation]
        owned = [f for f in mine if f.store_branch]
        if not owned:
            if b.relation in capped:
                continue
            why = _no_value(b.relation, rels, unread, empty, mine, differs)
            if why is None:
                out.append(Finding(Kind(ProblemKind.UNDECIDED), at,
                                   UndecidedPayload(b.relation)))
            else:
                out += [Finding(Kind.STORE_NO_VALUE, at, StoreNoValuePayload(
                    b.relation, w)) for w in why]
            continue
        out += _two_values(solver, b, line, [
            f for f in mine if f.kind is ValueKind.OWNED], solver_cases)
        for f in owned:
            if f.homonyms:
                out.append(Finding(Kind.STORE_HOMONYMS, at, HomonymsPayload(
                    f.name, (f.relation, *f.homonyms))))
            elif f.entry:
                entry = runs.branch_entry(f.name)
                if entry is not None:
                    out += entry_findings(
                        runs, solver, b, f.name, f.case_id,
                        ordered(solver, solver_cases, b),
                        entry)
            elif f.untaken:
                out.append(Finding(Kind.STORE_UNTAKEN, at,
                                   RelationPayload(b.relation)))
    out += idle_ignores(runs, IgnoreForm.STORE)
    shown = shown_case_names(found)
    for f in found:
        if not f.depended or (f.stored and f.line is None):
            continue
        names = shown(f)
        where = AtRelation(f.relation)
        if f.store_branch and f.line is None:
            out.append(Finding(Kind.MISSING_BRANCH_LINE, where,
                               MissingLinePayload(f.name, names)))
        if f.homonyms and f.line is None:
            out.append(Finding(Kind.STORE_HOMONYMS, where, HomonymsPayload(
                f.name, (f.relation, *f.homonyms))))
        if f.asks_params:
            out.append(Finding(Kind.STORE_PARAMS_ASK, where, ColorAskPayload(
                f.relation, f.columns if f.sub else (), f.types,
                tuple(sorted((tuple(m) for m in f.one),  # type: ignore[misc]
                             key=row_key)),  # type: ignore[arg-type]
                names)))
    return out


def _no_value(path: RelationName, rels: Sequence[RelationName],
              unread: set[RelationName], empty: set[RelationName],
              mine: Sequence[Found],
              differs: Mapping[RelationName, PairId | None]
              ) -> list[NoValue] | None:
    """Why a `@store` line's relation gives no value the runner can
    store: one reason per value of it that is not the same on every
    input. None where no reason is known."""
    if path not in rels:
        return [NotBetween()]
    if path in unread:
        return [Unread()]
    held_back = [f for f in mine if f.kind is not ValueKind.OWNED]
    if held_back:
        return [NoAnchor() if f.kind is ValueKind.TRANSLATED
                else KeyedBy(f.keys) for f in held_back]
    pair = differs.get(path)
    if pair is not None:
        return [DiffersOn(pair)]
    if path in empty:
        return [NoRows()]
    return None


def _two_values(solver: Solver, b: StoreBranch, line: int,
                values: Sequence[Found], solver_cases: Sequence[Case]
                ) -> list[Finding]:
    """Where cases of the solver take two values or more of one relation: the
    branch of the line at `line` then denotes a branch per value there. One finding per
    number of values, with the cases that take that many."""
    if len(values) < 2:
        return []
    counts: dict[Case, int] = {}
    for f in values:
        for c in solver_cases:
            if c.branches or (f.case_values and c.base not in f.bases):
                continue
            counts[c] = counts.get(c, 0) + 1
    out: list[Finding] = []
    for n in sorted({k for k in counts.values() if k > 1}):
        out.append(Finding(Kind.STORE_VALUES, AtLine(line),
                           StoreValuesPayload(
                               b.relation, b, n, cover(
                                   solver, [c for c, k in counts.items()
                                            if k == n], solver_cases))))
    return out


def shown_case_names(found: Sequence[Found]
                     ) -> Callable[[Found], tuple[str, ...]]:
    """The case names a value of `found` prints with: its `case_names`
    where another value of `found` has its relation and columns, and
    none where the relation and columns tell it apart."""
    rows = Counter((f.relation, f.columns) for f in found)
    return lambda f: f.case_names if rows[(f.relation, f.columns)] >= 2 \
        else ()
