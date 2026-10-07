"""Whether a value the `store` survey finds is stored already, or is
stored parameters' value read back, and whether the concept case reads
it."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from itertools import combinations, permutations

from checker.lint.view import literal_vars, term_vars
from checker.runs import Runs
from checker.store.relations import declaration, feeding
from checker.store.survey import Found, keyed_too
from engine import (
    DeclId,
    Index,
    RelationName,
    Row,
    Scope,
    Value,
)
from engine.program import (
    Atom,
    AtomLiteral,
    BodyLiteral,
    Disjunction,
    Qualifier,
    RelationDecl,
    Term,
    Unit,
    own,
)
from engine.quotes import quotes
from solver.aggregate import TOP, Solver, lists_case
from solver.case_columns import holds_at
from solver.case_types import (
    Pattern,
    case_types,
    joined,
    known,
)
from solver.dependence import Dependence, dependent_bases
from solver.graph import Graph, InstancePath
from solver.model import Base, choice_values
from solver.names import marker_lists
from solver.readers import marker_at
from solver.run_parts import (
    case_reading,
    parameter_reading,
    per_case,
    row_key,
    rows_at,
)
from solver.vocabulary import PARAMS_SCOPE


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
        d = declaration(self.index, rel, scope)
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
                 if not keyed_too(held, types[i])} if values else {}
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
    concept case's among them."""
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
