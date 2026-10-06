"""Which of a solver's bases have a derivation of `out` that depends on
each part of the solver's own text, by a walk over the program's rules
(`solver.graph.Graph.read`)."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from engine import Engine, Program, RelationName, UnitId
from engine.memo import Once, Recent
from engine.program import Atom, Term
from solver.case_types import CasePlace, CasePlaces
from solver.graph import (
    Graph,
    InstancePath,
    Node,
    NodeKind,
    Placed,
    walked,
)
from solver.annotations import CaseMarker
from solver.model import Base, UnderMarker
from solver.aggregate import Solver, marker_listing, section_at
from solver.vocabulary import CHOICE, PARAMS, PARAMS_SCOPE



@dataclass(frozen=True)
class Dependence:
    """Which of a list of bases have a derivation of `out` that depends on
    each part of the solver's own text, each in the list's order
    (`dependence`). The units stand in the program's order, the relations
    of `Params` in the order `Params` declares them, and the other
    relations in the order of their names' text."""

    units: Mapping[UnitId, tuple[Base | None, ...]]
    """Each unit a base's derivation of `out` depends on."""
    parameters: Mapping[str, tuple[Base | None, ...]]
    """Each relation of `Params` by name: a parameter, or a relation that
    clauses feed."""
    relations: Mapping[RelationName, tuple[Base | None, ...]]
    """Each relation that a unit the derivation depends on reads or
    feeds, by the name a top-level clause reads it by: `in`,
    `params.<p>`, `<instance>.<relation>`."""
    stranded: Mapping[tuple[UnitId, "Node"], tuple[Base | None, ...]] = field(
        default_factory=dict[tuple[UnitId, "Node"], tuple[Base | None, ...]])
    """Each unit a base's walk reads that stands under a marker that does
    not list the base, with the relation the unit feeds: as a top-level
    clause names it, or the instance of a lib component by its path.
    `checker` gives the marker of each a hint of the case-section
    category, which fails no command."""

    def reads_parameter(self, base: Base | None, name: str) -> bool:
        """Whether `base` has a derivation of `out` that depends on the
        relation of `Params` `name` (`parameters`); a name absent there is
        one no base reads."""
        return base in self.parameters.get(name, ())


def dependent_bases(rd: Dependence, units: Iterable[UnitId]
                    ) -> frozenset[Base | None]:
    """The bases whose derivation of `out` depends on any of `units`
    (`Dependence.units`)."""
    return frozenset(b for u in units for b in rd.units.get(u, ()))


DEPENDENCE_HELD = 32
"""The most results of `dependence` one process holds."""


_DEPENDENCE: Recent[tuple[tuple[int, ...], tuple[Base | None, ...]],
                    tuple[tuple[object, ...], Dependence]] \
    = Recent(DEPENDENCE_HELD)
"""`dependence`'s results by the identities of the parts it reads, each
with those parts, which it keeps alive while it holds the result."""


_DEPENDENCE_ONCE: Once[tuple[tuple[int, ...], tuple[Base | None, ...]],
                      tuple[tuple[object, ...], Dependence]] \
    = Once(_DEPENDENCE)


def dependence(engine: Engine, solver: Solver, bases: Sequence[Base | None]
               ) -> Dependence:
    """Which of `bases` have a derivation of `out` that depends on each
    unit, parameter and relation of the solver's own text
    (solver-file.md, under "Cases", "Params" and "Program").

    The result is a function of the solver's model, its case markers
    among its annotations, the program's declarations, its GRID and RIGID
    calls and the units of the solver's own text and of the lib, whose rows
    are the rows the walk reads; a unit an operation wrote (`own`) is none
    of them. So
    it is computed once for each distinct such input, by the identity of
    those parts: a variation that fixes a parameter's value removes the
    same own units whatever the value, and a deletion removes its own.

    The walk reads the program as it runs, its GRID and RIGID calls
    expanded (`Engine.expand`), so that a unit in a RIGID block is read
    through the rules that place its chart; the units, parameters and
    stranded units it reports are those of the solver's program.

    A unit of a component runs at each instance of the component, and a
    relation of a component is one relation per instance (`Graph`). The walk
    reads the units of the lib as it reads those of the solver's own text,
    at each instance path they run at, the instances inside the lib's
    components included (`Graph.read`). A base's
    model reads its grids from `out` at its case, so its derivation depends on
    each unit that heads `out` and admits it, and, from each unit it depends
    on, on each unit that heads a relation that unit reads and admits it. A
    unit whose head has a case column, a column of `Choice` (the case column
    `ch`, solver-file.md, under "Cases"), of a type that stands in `Choice`, or
    of a record type with a field of such a type, admits a base when the base's
    value can stand in each term the head holds there, whatever carries the
    value there (`CasePlaces`). A unit whose head has none admits every base,
    whatever section it stands in, since the program runs it for every case.
    Either unit admits only the bases whose value can stand in the term of an
    `impl_choice` atom of its body. A read asks for the rows its terms fix:
    where a read holds a constant constructor in a column of a type that stands
    at one choice point, or a constant `Choice` value, it asks for the rows
    that hold that value there, whatever the base holds, and the units it
    reaches are read for the base with that value at that point
    (`CasePlaces.demand`); so `near_arm($Clear(), P, D) :- near_arm($Any(), P, D)`
    reads the `$Any()` clauses for a base that takes `$Clear`. A read is at
    every value at each case-typed place where it holds a wildcard, or a
    variable that no case variable of the unit's head fills: there, a unit
    that heads its relation admits the base whatever term it holds. At the
    read's other case-typed places, the base's value still bounds which units
    the read reaches (`CasePlaces.bounded`), so `crowded(A, Id, Ch)` in a clause
    whose head fills `Ch` and not `A` reaches only the clauses whose head can
    hold the base's value in the column of `Ch`. So a read of a relation of
    an instance of a lib component reaches, through the component's rules at
    the instance's type arguments, only the units that feed the instance at
    the case values the read can take: where `layout` is an instance of
    `Unanimous<EmptyPanel, Layout>`, `layout.value(E, L)` in a clause whose
    head fills `E` reaches only the clauses of `layout.item` whose head can
    hold the base's value in the key column. A record type a lib component
    declares is no case type (`CasePlaces`), so a read is at every value past
    a place where the component passes its key into such a record. A base's derivation depends on a parameter where it depends on a
    unit that reads it, and on a relation where it depends on a unit that reads
    it or a unit that feeds it. A unit the walk reads for a base that stands
    under a marker that does not list the base (`section_at`, solver-file.md,
    under "Cases") is reported with the base (`Dependence.stranded`)."""
    program = solver.program
    held: tuple[object, ...] = (
        solver.stem, solver.task_id, solver.annotations.markers, solver.choice,
        solver.branches, solver.params, solver.witness_file, solver.task,
        solver.lib, solver.problems, program.types, program.relations,
        program.components, program.instances, program.functors,
        program.comments, program.includes, program.defines,
        program.macros, *filter(walked, program.units))
    key = (tuple(map(id, held)), tuple(bases))

    def make() -> tuple[tuple[object, ...], Dependence]:
        got = (held, _dependence(engine, engine.expand(program), solver,
                                 bases))
        _DEPENDENCE.put(key, got)
        return got

    return _DEPENDENCE_ONCE.get(key, make)[1]


type _Wanted = tuple[Base | None, tuple[CasePlace, ...] | None]
"""What a read asks for in `dependence`'s walk: the base whose value the
reached units hold, and the case-typed places of the read at which that
value bounds them, where the read is at every value at some other place
(`CasePlaces.bounded`); None where it is at every value at none."""


def _dependence(engine: Engine, expanded: Program, solver: Solver,
                bases: Sequence[Base | None]) -> Dependence:
    """`dependence`, computed over `expanded`, the solver's program with
    its GRID and RIGID calls expanded."""
    from solver.names import marker_lists

    graph = Graph(expanded, engine)
    cases = CasePlaces(graph, solver.choice)
    listing = marker_listing(solver)
    marker_of: dict[UnitId, CaseMarker | None] = {}
    checked: dict[tuple[UnitId, InstancePath],
                  tuple[dict[int, tuple[str, Term]], list[Term]]] = {}
    for u in graph.units:
        assert u.span is not None, "a unit of the solver's own text"
        section = section_at(solver, u.scope, u.span.first)
        marker_of[u.id] = section.marker if isinstance(
            section, UnderMarker) and listing[section.marker.line] else None
    markers = sorted({m.line: m for m in marker_of.values()
                      if m is not None}.values(), key=lambda m: m.line)
    by_unit: dict[UnitId, list[Base | None]] = {}
    by_param: dict[str, list[Base | None]] = {}
    by_relation: dict[RelationName, list[Base | None]] = {}
    by_stranded: dict[tuple[UnitId, Node], list[Base | None]] = {}
    held: dict[tuple[int, tuple[CasePlace, ...] | None], _Wanted] = {}

    def wanted(base: Base | None, bounded: tuple[CasePlace, ...] | None
               ) -> _Wanted:
        """What a read asks for, one object per base and bounded places,
        as `Graph.read` keys a request by its identity."""
        got = held.get((id(base), bounded))
        if got is None or got[0] is not base:
            got = held[(id(base), bounded)] = (base, bounded)
        return got

    def demand(placed: Placed, atom: Atom, asked: _Wanted) -> _Wanted:
        return wanted(cases.demand(placed, atom, asked[0]),
                      cases.bounded(placed, atom))

    for base in bases:
        listed = {m.line: marker_lists(solver, m, base) for m in markers}

        def admits(placed: Placed, wanted: _Wanted) -> bool:
            base, bounded = wanted
            key = (placed[0].id, placed[1])
            got = checked.get(key)
            if got is None:
                got = checked[key] = cases.checks(*placed)
            columns, impl = got
            return all(cases.admits(placed, CHOICE, term, (), base)
                       for term in impl) and (
                all(cases.admits(placed, t, term, (), base)
                    for t, term in columns.values())
                if bounded is None else
                all(cases.admits(placed, t, columns[i][1], path, base)
                    for i, path, t in bounded))

        def unlisted(placed: Placed,
                     listed: Mapping[int, bool] = listed) -> bool:
            m = marker_of.get(placed[0].id)
            return m is not None and not listed[m.line]

        units, nodes, names, stranded = graph.read(
            admits, wanted(base, None), demand, unlisted)
        for key in stranded:
            by_stranded.setdefault(key, []).append(base)
        for uid in units:
            by_unit.setdefault(uid, []).append(base)
        for n in nodes:
            if n.kind is NodeKind.RELATION \
                    and graph.component_at(n.path) == PARAMS:
                by_param.setdefault(n.name, []).append(base)
        for rel in names:
            by_relation.setdefault(rel, []).append(base)
    params = [r.name for r in solver.program.relations
              if r.scope == PARAMS_SCOPE]
    written = frozenset(u.id for u in solver.program.units)
    return Dependence(
        {u.id: tuple(by_unit[u.id]) for u in graph.units
         if u.id in by_unit and u.id in written},
        {p: tuple(by_param[p]) for p in params if p in by_param},
        {r: tuple(by_relation[r])
         for r in sorted(by_relation, key=lambda r: (r.instances, r.name))},
        {k: tuple(by_stranded[k]) for k in sorted(
            by_stranded, key=lambda k: (k[0].index, k[1].path, k[1].name))
         if k[0] in written})
