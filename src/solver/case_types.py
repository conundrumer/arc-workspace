"""Where a solver's program holds a case value: the types whose values
hold a case, the places of a unit's terms of those types, and whether a
base's value can stand there, as `solver.dependence` reads them."""

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass, replace

from engine import AdtValue, Program, RecordValue, UnitId, Value
from engine.memo import ByIdentity
from engine.program import (
    Aggregate,
    Atom,
    AtomLiteral,
    BodyLiteral,
    Comparison,
    ComparisonOperator,
    ConstructorTerm,
    Disjunction,
    RecordTerm,
    RecordType,
    Term,
    TypeName,
    Unit,
    Variable,
    Wildcard,
    own,
    term_of,
    term_value,
    with_literal_terms,
    with_subterms,
)
from solver.graph import Graph, InstancePath, Placed
from solver.model import (
    Base,
    Choice,
    ChoicePoint,
    points_of_type,
    value_at,
    with_value_at,
)
from solver.aggregate import Solver
from solver.vocabulary import CHOICE, IMPL


type CasePlace = tuple[int, tuple[int, ...], str]
"""A case-typed place of an atom's terms (`CasePlaces`): its column, the
record fields that lead to it in that column, and its type."""


@dataclass(frozen=True)
class CaseTypes:
    """The types whose values hold a case (`CasePlaces`): `Choice`, each
    type that stands in it, and each record type of the solver's own text
    with a field of such a type; with each record type's field types, and
    the type of each choice point as the model resolves it, by its path.
    A record type a component declares stands once for each instance path
    that holds it, by its key there, its fields read through that
    instance's type arguments (`Graph.key_at`)."""

    types: frozenset[str]
    records: Mapping[str, tuple[str, ...]]
    points: Mapping[tuple[str, ...], str]

    def at(self, choice: Choice, type: str) -> list[ChoicePoint]:
        """The points of `choice` of `type`, as the model resolves it."""
        return [p for p in choice.points if self.points[p.path] == type]

    def fields(self, type: str) -> tuple[str, ...] | None:
        """The types of the fields a value of `type` opens into: those of
        `term_fields`, but none for `Choice`, which a value is compared
        with whole, as the base."""
        return None if type == CHOICE else self.term_fields(type)

    def term_fields(self, type: str) -> tuple[str, ...] | None:
        """The types of the fields a term of `type` in the program opens
        into; None where it is no record. A record `Choice` opens, since a
        term builds the base field by field."""
        return self.records.get(type)

    def leaves(self, type: str, value: Value) -> list[tuple[str, Value]]:
        """The values at the case-typed places of a value of `type`, each
        with its type: a record of a case type opened by its fields'
        types (`fields`)."""
        if type not in self.types:
            return []
        fields = self.fields(type)
        if fields is None \
                or not isinstance(value, RecordValue) \
                or len(fields) != len(value.fields):
            return [(type, value)]
        return [x for f, v in zip(fields, value.fields, strict=True)
                for x in self.leaves(f, v)]

    def whole(self, type: str) -> bool:
        """Whether every place of a value of `type` holds the case:
        `Choice`, a type that stands in it, or a record type whose fields
        are each of such a type."""
        if type not in self.types:
            return False
        fields = self.fields(type)
        return fields is None or all(self.whole(f) for f in fields)

    def kept(self, type: str) -> tuple[int, ...] | None:
        """For a record type with a field of a case type and a field of
        another (`whole`), the places of the fields that are not wholly of
        the case, in order; None for any other type."""
        fields = self.fields(type)
        if type not in self.types or fields is None or self.whole(type):
            return None
        return tuple(i for i, f in enumerate(fields) if not self.whole(f))


def case_types(solver: Solver) -> CaseTypes:
    """The solver's case types, as `dependence` reads them, the types
    named as `column_types` resolves them; computed once per program and
    `Choice` while the program lives."""
    program, choice = solver.program, solver.choice

    def make() -> CaseTypes:
        return CasePlaces(Graph(program, solver.engine), choice).types

    return _CASE_TYPES.guarded(program, choice, make)


_CASE_TYPES: ByIdentity[Program, tuple[Choice | None, CaseTypes]] \
    = ByIdentity()


def substituted(t: Term, terms: dict[str, Term]) -> Term:
    """`t` with each variable of `terms` replaced by its term."""
    match t:
        case Variable(name=name):
            return terms.get(name, t)
        case Aggregate(expr=expr, body=body):
            return replace(t, expr=None if expr is None
                           else substituted(expr, terms),
                           body=tuple(substituted_literal(x, terms)
                                      for x in body))
    return with_subterms(t, lambda x: substituted(x, terms))


def substituted_atom(a: Atom, terms: dict[str, Term]) -> Atom:
    """`a` with each variable of `terms` replaced by its term."""
    return replace(a, args=tuple(substituted(x, terms) for x in a.args))


def substituted_literal(lit: BodyLiteral, terms: dict[str, Term]
                        ) -> BodyLiteral:
    """`lit` with each variable of `terms` replaced by its term."""
    if isinstance(lit, Disjunction):
        return replace(lit, branches=tuple(
            tuple(substituted_literal(x, terms) for x in b)
            for b in lit.branches))
    return with_literal_terms(lit, lambda x: substituted(x, terms))


def _wild(x: object) -> bool:
    """Whether a term, or a tuple of terms, holds a wildcard."""
    if isinstance(x, Wildcard):
        return True
    if isinstance(x, tuple):
        return any(_wild(y) for y in x)
    if is_dataclass(x) and not isinstance(x, type):
        return any(_wild(getattr(x, f.name)) for f in fields(x))
    return False


def _variables(x: object) -> set[str]:
    """The names of the variables a term, or a tuple of terms, holds."""
    if isinstance(x, Variable):
        return {x.name}
    if isinstance(x, tuple):
        return set().union(*(_variables(y) for y in x))
    if is_dataclass(x) and not isinstance(x, type):
        return set().union(*(_variables(getattr(x, f.name))
                             for f in fields(x)))
    return set()


def _holds_case(term: Term) -> bool:
    """Whether a term holds a constructor or a record, which a case value
    it is compared with must match."""
    return isinstance(term, (ConstructorTerm, RecordTerm))


def compared(unit: Unit, op: ComparisonOperator
             ) -> Iterator[tuple[str, Term]]:
    """Each variable a comparison `op` of a unit's body compares with a
    term, from either side, with that term, in body order."""
    for lit in unit.body or ():
        if isinstance(lit, Comparison) and lit.op is op:
            for var, term in ((lit.lhs, lit.rhs), (lit.rhs, lit.lhs)):
                if isinstance(var, Variable):
                    yield var.name, term


class CasePlaces:
    """Where a unit's rows hold a case value, and whether a base's value
    can stand there (`dependence`).

    A case value stands in a column of a case type: `Choice`, a type that
    stands in `Choice`, or a record type of the solver's own text with a
    field of a case type, the value then standing in that field. A term
    there admits a base where the base's value can stand in it. A variable
    takes the term an equality of the body sets it to. A variable that a
    `!=` of the body holds apart from a constant admits no base whose value
    there is that constant, as `An != $AnchorMinority()` shuts out the
    bases that take `$AnchorMinority`. Else, for each
    positive atom of the body that reads it in a column, or in a field of
    a record there, the variable holds one of the terms the rows of that
    column can hold there, read in the unit that heads them: the terms one
    clause of the relation heads at every place the atom reads the
    variable, together. A relation of an instance of a lib component is
    read through the component's clauses at that instance, as any other
    relation is. So `cut_choice(S)` with facts `cut_choice($Separator())`
    and `cut_choice($Mirror())` admits only the bases whose value there
    is one of the two, and so does a read of `cut.tile_of(S, _, _)` where
    the component's clauses take the key of `tile_of` from `cell` and
    `cut.cell(S, P) :- cut_choice(S)` feeds `cut.cell`. An atom of a
    relation that no unit heads, a unit an operation wrote included,
    holds no row, so it admits no base. An atom where some clause holds
    no term there, or whose relation only units an operation wrote head,
    sets no bound. The record types
    that hold a case are those of the solver's own text, so a column of a
    record type that a lib component declares holds none, though the
    component holds its key in a field of it.

    One clause also ties the places of an atom to one another: where the
    atom holds a variable filled by the base's value (`bounded`) at some
    places, and each clause of the relation that the atom joins heads, at
    another case-typed place, only variables that its head's terms at the
    filled places hold, or that an equality of its body sets from those,
    the atom's variable at that other place is filled too. So, where each clause of `crowded` heads
    `crowded(A, Id, [A, Kind, U, $Threshold()])`, a read
    `crowded(A, Id, Ch)` in a unit whose head fills `Ch` fills `A`, and
    a read `parse.object($U(), A, Id, P)` beside it reaches only the
    clauses of `parse.object` whose head can hold the base's value in the
    column of `A`."""

    def __init__(self, graph: Graph, choice: Choice | None) -> None:
        self.graph = graph
        self.choice = choice
        points = {} if choice is None else {
            p.path: graph.type_at(TypeName((), p.type), (), ())
            for p in choice.points}
        records: dict[str, tuple[str, ...]] = {
            key: tuple(graph.type_at(f.type, t.scope.components, at)
                       for f in t.fields)
            for key, (t, at) in graph.type_decls.items()
            if isinstance(t, RecordType) and own(t.span) and at is not None}
        carrying = {CHOICE, *points.values()}
        grown = True
        while grown:
            more = {n for n, fields in records.items()
                    if n not in carrying
                    and any(f in carrying for f in fields)}
            carrying |= more
            grown = bool(more)
        self.types = CaseTypes(frozenset(carrying), records, points)
        self._eq: dict[UnitId, dict[str, Term]] = {}
        self._ne: dict[UnitId, dict[str, list[Term]]] = {}
        self._cycles = 0
        """How many reads of a place being read already have been met; a
        result that met none, or holds, is final."""
        self._alts: dict[tuple[UnitId, InstancePath, str], list[list[list[
            tuple[Placed, Term, tuple[int, ...]]]]]] = {}
        self._filled: dict[tuple[UnitId, InstancePath], frozenset[str]] = {}
        self._admits: dict[tuple[UnitId, InstancePath, str, tuple[int, ...],
                                 str, Base], bool] = {}
        self._fixed: dict[tuple[UnitId, InstancePath, int], tuple[
            tuple[tuple[str, ...] | None, Base], ...]] = {}
        self._bounded: dict[tuple[UnitId, InstancePath, int],
                            tuple[CasePlace, ...] | None] = {}
        self._demanded: dict[tuple[tuple[UnitId, InstancePath, int], int],
                             tuple[Base, Base]] = {}
        """`demand`'s result by read and by the identity of the base,
        which the entry holds alive, so that equal requests give one
        object."""

    def checks(self, unit: Unit, at: InstancePath
               ) -> tuple[dict[int, tuple[str, Term]], list[Term]]:
        """Each term where the unit holds a case value: each term of its
        head in a column of a case type, by the column, with its type, and
        each term of an `impl_choice` atom of its body, of type `Choice`."""
        columns = {i: (t, term)
                   for i, (t, term) in enumerate(self._typed(at, unit.head))
                   if t in self.types.types}
        impl = [lit.atom.args[0] for lit in unit.body or ()
                if isinstance(lit, AtomLiteral) and not lit.negated
                and lit.atom.relation == IMPL and len(lit.atom.args) == 1]
        return columns, impl

    def bounded(self, placed: Placed, atom: Atom
                ) -> tuple[CasePlace, ...] | None:
        """The case-typed places at which the base's value bounds the units
        a body atom of the placed unit reads, where the atom reads its
        relation at every value at some other place; None where it reads
        it at every value at none (`dependence`). The atom reads at every
        value at a case-typed place of its terms that holds a wildcard, or
        a variable that no case variable of the unit's head fills, a
        variable an equality sets to a term with a filled variable, and a
        variable a body atom ties to filled ones (`CasePlaces`), being filled
        too."""
        key = (placed[0].id, placed[1], id(atom))
        if key in self._bounded:
            return self._bounded[key]
        at = placed[1]
        filled = self._fills(placed)
        places = [((i, path, t), isinstance(leaf, ConstructorTerm) or (
                      isinstance(leaf, Variable) and leaf.name in filled))
                  for i, (column, term) in enumerate(self._typed(at, atom))
                  for path, t, leaf in self._case_leaves(term, column, ())]
        got = None if all(bounds for _place, bounds in places) \
            else tuple(place for place, bounds in places if bounds)
        self._bounded[key] = got
        return got

    def _fills(self, placed: Placed) -> frozenset[str]:
        """The variables of the placed unit that a case variable of its
        head fills (`bounded`): those of its head's case-typed terms, and
        those the equalities of its body (`_through_equalities`) and its
        positive atoms (`_tied`) give from filled ones."""
        unit, at = placed
        key = (unit.id, at)
        if key in self._filled:
            return self._filled[key]
        filled: set[str] = set()
        for _t, term in self.checks(unit, at)[0].values():
            filled |= _variables(term)
        atoms = [lit.atom for lit in unit.body or ()
                 if isinstance(lit, AtomLiteral) and not lit.negated]
        grown = True
        while grown:
            size = len(filled)
            filled = self._through_equalities(unit, filled)
            for atom in atoms:
                filled |= self._tied(at, atom, filled)
            grown = len(filled) > size
        self._filled[key] = frozenset(filled)
        return self._filled[key]

    def _through_equalities(self, unit: Unit, filled: set[str]
                            ) -> set[str]:
        """`filled` with each variable of the unit that an equality of its
        body sets to a term with no wildcard whose variables all stand in
        it, and each variable of a term an equality sets a variable of it
        to, to a fixpoint."""
        filled = set(filled)
        eq = self._equalities(unit)
        grown = True
        while grown:
            grown = False
            for v, term in eq.items():
                if v in filled:
                    more = _variables(term) - filled
                elif _variables(term) <= filled and not _wild(term):
                    more = {v}
                else:
                    more = set()
                if more:
                    filled |= more
                    grown = True
        return filled

    def _tied(self, at: InstancePath, atom: Atom, filled: set[str]
              ) -> set[str]:
        """The variables at the case-typed places of a positive body atom,
        read at `at`, that the atom ties to the variables of `filled` it
        holds (`CasePlaces`): those where each clause of its relation that the
        atom joins (`_joined_heads`) heads a term whose case-typed places
        hold only variables of the head's terms at the atom's places of
        `filled`, or variables an equality of the clause's body sets from
        them (`_through_equalities`). A relation that no clause heads ties
        none."""
        node = self.graph.node(at, atom.relation)
        heads = [] if node is None else self.graph.read_heads(node)
        if not heads:
            return set()
        leaves = [(i, path, t, leaf)
                  for i, (column, term) in enumerate(self._typed(at, atom))
                  for path, t, leaf in self._case_leaves(term, column, ())
                  if isinstance(leaf, Variable)]
        given = [(i, path) for i, path, _t, leaf in leaves
                 if leaf.name in filled]
        open_ = {leaf.name for _i, _path, _t, leaf in leaves
                 if leaf.name not in filled}
        if not given or not open_:
            return set()
        for h, typed in self._joined_heads(heads, atom):
            fixes: set[str] = set()
            for i, path in given:
                got = self._head_at(typed, i, path)
                if got is not None and not got[2]:
                    fixes |= {x.name for _p, _t, x in self._case_leaves(
                        got[1], got[0], ()) if isinstance(x, Variable)}
            fixes = self._through_equalities(h[0], fixes)
            open_ = {v for v in open_
                     if any(self._fixed_at(typed, i, path, fixes)
                            for i, path, _t, leaf in leaves
                            if leaf.name == v)}
        return open_

    def _head_at(self, typed: Sequence[tuple[str, Term]], column: int,
                 path: tuple[int, ...]
                 ) -> tuple[str, Term, tuple[int, ...]] | None:
        """The term a clause's head, `typed` as `_joined_heads` gives it,
        holds at the record fields `path` of a column, with its type and
        the part of `path` that leads on into it where it holds no record
        there; None where the head holds no term of that column."""
        if column >= len(typed):
            return None
        type, term = typed[column]
        while path and isinstance(term, RecordTerm):
            fields = self.types.term_fields(type)
            if fields is None or len(fields) != len(term.args) \
                    or path[0] >= len(fields):
                return None
            type, term, path = fields[path[0]], term.args[path[0]], path[1:]
        return type, term, path

    def _fixed_at(self, typed: Sequence[tuple[str, Term]], column: int,
                  path: tuple[int, ...], fixes: set[str]) -> bool:
        """Whether a clause's head, `typed` as `_joined_heads` gives it,
        holds at the record fields `path` of a column a term each of whose
        case-typed places holds a variable of `fixes`."""
        got = self._head_at(typed, column, path)
        if got is None:
            return False
        type, term, rest = got
        if rest:
            return isinstance(term, Variable) and term.name in fixes
        leaves = self._case_leaves(term, type, ())
        return bool(leaves) and all(
            isinstance(x, Variable) and x.name in fixes
            for _p, _t, x in leaves)

    def _case_leaves(self, term: Term, type: str, path: tuple[int, ...]
                     ) -> list[tuple[tuple[int, ...], str, Term]]:
        """The terms at the case-typed places of a term of `type` that
        stands at `path`, each with its own path and type, records opened
        by their fields' types (`CaseTypes.term_fields`)."""
        if type not in self.types.types:
            return []
        fields = self.types.term_fields(type)
        if isinstance(term, RecordTerm) and fields is not None \
                and len(fields) == len(term.args):
            return [x for j, (a, f) in enumerate(
                        zip(term.args, fields, strict=True))
                    for x in self._case_leaves(a, f, (*path, j))]
        return [(path, type, term)]

    def _typed(self, at: InstancePath, atom: Atom
               ) -> list[tuple[str, Term]]:
        """Each term of an atom a unit at `at` holds, with its column's
        type, read through the type arguments in force there; none where
        no declaration gives the relation."""
        types = self.graph.column_types(at, atom.relation)
        if types is None:
            return []
        return list(zip(types, atom.args, strict=False))

    def demand(self, placed: Placed, atom: Atom, base: Base | None
               ) -> Base | None:
        """What a read asks for, for a unit reached for `base`: `base` with
        the value of each constant term of the atom that stands in a
        column of a point's type, where one point has that type, set at
        that point, and a constant `Choice` value in place of the base."""
        choice = self.choice
        if choice is None or base is None:
            return base
        key = (placed[0].id, placed[1], id(atom))
        fixed = self._fixed.get(key)
        if fixed is None:
            fixed = self._fixed[key] = self._fixes(placed[1], atom, choice)
        if not fixed:
            return base
        memo = (key, id(base))
        if memo in self._demanded:
            return self._demanded[memo][1]
        out = base
        for path, value in fixed:
            if path is None:
                out = value
                continue
            got = with_value_at(choice, out, path, value)
            if got is not None:
                out = got
        if out == base:
            out = base
        self._demanded[memo] = (base, out)
        return out

    def _fixes(self, at: InstancePath, atom: Atom, choice: Choice
               ) -> tuple[tuple[tuple[str, ...] | None, Base], ...]:
        """The values a read fixes (`demand`): each constant term of the
        atom in a column of a point's type, where one point has that type,
        with the point's path, and a constant `Choice` value with None."""
        out: list[tuple[tuple[str, ...] | None, Base]] = []
        for t, term in self._typed(at, atom):
            if not isinstance(term, ConstructorTerm | RecordTerm):
                continue
            value = _constant(term)
            if not isinstance(value, AdtValue | RecordValue):
                continue
            if t == CHOICE:
                out.append((None, value))
                continue
            points = points_of_type(choice, t)
            if len(points) == 1 and isinstance(value, AdtValue):
                out.append((points[0].path, value))
        return tuple(out)

    def admits(self, placed: Placed, type: str, term: Term,
               path: tuple[int, ...], base: Base | None) -> bool:
        """Whether `base`'s value can stand at the place of type `type`
        that the record fields `path` lead to in `term`, the variables of
        `term` read in the placed unit."""
        return self._admits_in(placed, type, term, path, base, frozenset())

    def _admits_in(self, placed: Placed, type: str, term: Term,
                   path: tuple[int, ...], base: Base | None,
                   open_: frozenset[tuple[UnitId, InstancePath, str,
                                          tuple[int, ...]]]
                   ) -> bool:
        """`admits` for the part of `term` at `path`, the record fields to
        it, where the places of `open_` are being read already. A value
        reaches such a place again only through another route, so a read
        of it on this path admits nothing, as a recursive clause adds no
        value its other clauses do not give. A term of a point's type is
        admitted where the base's value at some point of that type matches
        it, or where the base has no value at some point of that type: a
        unit can give a constructor a fixed value at a point under another
        branch, as `markers_of($OnePiece(), $SingleDots())` does where
        `markers` stands under `LargestPiece`."""
        choice = self.choice
        if choice is None or base is None or type not in self.types.types:
            return True
        while path and isinstance(term, RecordTerm):
            if path[0] >= len(term.args):
                return True
            term, path = term.args[path[0]], path[1:]
        unit, at = placed
        if isinstance(term, Variable):
            term = self._equalities(unit).get(term.name, term)
            if not isinstance(term, Variable):
                return self._admits_in(placed, type, term, path, base, open_)
            if not path and any(self._is_value(type, c, base)
                                for c in self._exclusions(unit, term.name)):
                return False
            key = (unit.id, at, term.name, path)
            if key in open_:
                self._cycles += 1
                return False
            memo = (unit.id, at, term.name, path, type, base)
            if memo not in self._admits:
                inner = open_ | {key}
                cycles = self._cycles
                got = all(
                    any(all(self._admits_in(h, type, alt, (*to, *path), base,
                                            inner)
                            for h, alt, to in clause)
                        for clause in alts)
                    for alts in self._alternatives(placed, term.name))
                if got or cycles == self._cycles:
                    self._admits[memo] = got
                return got
            return self._admits[memo]
        if path:
            return True
        fields = self.types.term_fields(type)
        if fields is not None:
            if isinstance(term, RecordTerm) and len(term.args) == len(fields):
                return all(self._admits_in(placed, f, a, (), base, open_)
                           for f, a in zip(fields, term.args, strict=True))
            return True
        return any(v is None or _matches(term, v)
                   for v in self._leaf_values(type, base))

    def _leaf_values(self, type: str, base: Base) -> list[Value | None]:
        """The values `base` can hold at a case-typed place of `type` that
        is no record: the base itself in a `Choice` column, else its value
        at each point of that type, None where it does not reach it."""
        choice = self.choice
        assert choice is not None, "a case-typed place has a choice"
        if type == CHOICE:
            return [base]
        points = points_of_type(choice, type)
        if not points:
            raise ValueError(f"no choice point has the type `{type}`")
        return [value_at(choice, base, p.path) for p in points]

    def _is_value(self, type: str, term: Term, base: Base) -> bool:
        """Whether `term`, a constant that a `!=` of the unit's body
        compares a variable with, is the value `base` holds at a
        case-typed place of `type` that is no record: at each point of
        that type, where several have it, so that the comparison shuts the
        base out there."""
        if self.types.term_fields(type) is not None:
            return False
        value = _constant(term)
        if not isinstance(value, AdtValue | RecordValue):
            return False
        return all(v == value for v in self._leaf_values(type, base))

    def _equalities(self, unit: Unit) -> dict[str, Term]:
        """The terms the equalities of a unit's body set its variables
        to, where the term holds a constructor or a record."""
        if unit.id not in self._eq:
            self._eq[unit.id] = {
                v: t for v, t in compared(unit, ComparisonOperator.EQ)
                if _holds_case(t)}
        return self._eq[unit.id]

    def _exclusions(self, unit: Unit, var: str) -> list[Term]:
        """The terms the `!=` comparisons of a unit's body hold a variable
        apart from, where the term holds a constructor or a record."""
        if unit.id not in self._ne:
            ne: dict[str, list[Term]] = {}
            for v, term in compared(unit, ComparisonOperator.NE):
                if _holds_case(term):
                    ne.setdefault(v, []).append(term)
            self._ne[unit.id] = ne
        return self._ne[unit.id].get(var, [])

    def _alternatives(self, placed: Placed, var: str
                      ) -> list[list[list[tuple[Placed, Term,
                                                tuple[int, ...]]]]]:
        """For each positive atom of a unit's body that reads `var`, the
        alternatives its rows give `var` (`CasePlaces`): one per clause of
        its relation, with the term the clause heads at each place the atom
        reads `var`. Each term stands with the unit that heads it and the
        place of `var` in its column."""
        unit, at = placed
        key = (unit.id, at, var)
        if key not in self._alts:
            out: list[list[list[tuple[Placed, Term, tuple[int, ...]]]]] = []
            for lit in unit.body or ():
                if not isinstance(lit, AtomLiteral) or lit.negated:
                    continue
                node = self.graph.node(at, lit.atom.relation)
                if node is None:
                    continue
                places = [(i, path) for i, arg in enumerate(lit.atom.args)
                          for path in _paths(arg, var)]
                if not places:
                    continue
                if not self.graph.heading(node):
                    out.append([])
                    continue
                heads = self.graph.read_heads(node)
                if not heads:
                    continue
                clauses = self._joined_heads(heads, lit.atom)
                if all(i < len(typed) for _h, typed in clauses
                       for i, _path in places):
                    out.append([[(h, typed[i][1], path)
                                 for i, path in places]
                                for h, typed in clauses])
            self._alts[key] = out
        return self._alts[key]

    def _joined_heads(self, heads: Sequence[Placed], read: Atom
                      ) -> list[tuple[Placed, list[tuple[str, Term]]]]:
        """The clauses `heads` of a relation that a read joins
        (`joined`), each with the terms of its head and their columns'
        types as it types them: a value the read fixes wholly in a column
        sets the variable the clause's head holds there, and a clause
        whose head holds another value there gives the read no row."""
        row = _row(read)
        out: list[tuple[Placed, list[tuple[str, Term]]]] = []
        for h in heads:
            held = joined(h[0].head.args, row, _no_name)
            if held is None:
                continue
            terms = {v: term_of(x) for v, x in held.items() if fixed(x)}
            out.append((h, [(t, substituted(term, terms))
                            for t, term in self._typed(h[1], h[0].head)]))
        return out


def _no_name(_name: str) -> Value | None:
    """The value `CasePlaces` reads a defined name as: none."""
    return None


def _row(read: Atom) -> "Pattern":
    """What a read's terms fix of the rows it reads (`_known`)."""
    return tuple(_known(t) for t in read.args)


def _known(term: Term) -> Value | None:
    """What a read's term fixes of its value (`known`), a defined name
    read as fixing none."""
    return known(term, {}, _no_name)


def _constant(term: Term) -> Value | None:
    """The value a term states with no variable, call or defined name in
    it (`term_value`); None for any other term."""
    return term_value(term, _no_name)


type Pattern = tuple[Value | None, ...]
"""What is known of a row of a relation, per column: the value that a
read's term, or a case, fixes there; None where nothing does."""


UNFIXED: Value = AdtValue("", ())
"""A part of a record or constructor value in a `Pattern` that nothing
fixes, where some other part of it is fixed."""


def compatible(a: Value, b: Value) -> bool:
    """Whether two values of a `Pattern` may be one value: equal where
    both fix a part (`UNFIXED`)."""
    if a == UNFIXED or b == UNFIXED:
        return True
    if isinstance(a, AdtValue) and isinstance(b, AdtValue):
        return a.constructor == b.constructor \
            and len(a.args) == len(b.args) \
            and all(compatible(x, y)
                    for x, y in zip(a.args, b.args, strict=True))
    if isinstance(a, RecordValue) and isinstance(b, RecordValue):
        return len(a.fields) == len(b.fields) \
            and all(compatible(x, y)
                    for x, y in zip(a.fields, b.fields, strict=True))
    return a == b


def _meet(a: Value, b: Value) -> Value:
    """What two `compatible` values of a `Pattern` fix together."""
    if a == UNFIXED:
        return b
    if isinstance(a, AdtValue) and isinstance(b, AdtValue):
        return AdtValue(a.constructor, tuple(
            _meet(x, y) for x, y in zip(a.args, b.args, strict=True)))
    if isinstance(a, RecordValue) and isinstance(b, RecordValue):
        return RecordValue(tuple(
            _meet(x, y) for x, y in zip(a.fields, b.fields, strict=True)))
    return a


def fixed(v: Value) -> bool:
    """Whether a value of a `Pattern` fixes every part (`UNFIXED`)."""
    if v == UNFIXED:
        return False
    if isinstance(v, AdtValue):
        return all(fixed(x) for x in v.args)
    if isinstance(v, RecordValue):
        return all(fixed(x) for x in v.fields)
    return True


def known(term: Term, env: Mapping[str, Value],
          defined: Callable[[str], Value | None]) -> Value | None:
    """What a read's term fixes of the value it stands for, a variable's
    value read in `env` and a defined name's through `defined`: None where
    it fixes none of it, and a record or constructor value with `UNFIXED`
    at each part it does not fix."""
    match term:
        case Variable(name=name):
            return env.get(name)
        case ConstructorTerm(name=name, args=args):
            vals = [known(a, env, defined) for a in args]
            return AdtValue(name, tuple(UNFIXED if v is None else v
                                        for v in vals))
        case RecordTerm(args=args):
            vals = [known(a, env, defined) for a in args]
            return None if all(v is None for v in vals) else RecordValue(
                tuple(UNFIXED if v is None else v for v in vals))
    return term_value(term, defined)


def joined(head: Sequence[Term], row: Pattern,
           defined: Callable[[str], Value | None]
           ) -> dict[str, Value] | None:
    """The value a read fixes (`row`) of each variable of a clause's head,
    column by column, a variable met twice taking what both fix; None
    where the read and the head fix different values in one place, so
    that no row of the clause meets the read. A defined name of the head
    reads through `defined`. Raises `ValueError` where the head and the
    row differ in length."""
    if len(head) != len(row):
        raise ValueError(f"a head of {len(head)} terms read with "
                         f"{len(row)}")
    env: dict[str, Value] = {}

    def join(term: Term, value: Value | None) -> bool:
        if value is None or value == UNFIXED:
            return True
        match term:
            case Variable(name=name):
                if name in env:
                    if not compatible(env[name], value):
                        return False
                    value = _meet(env[name], value)
                env[name] = value
                return True
            case ConstructorTerm(name=name, args=args):
                return isinstance(value, AdtValue) \
                    and value.constructor == name \
                    and len(value.args) == len(args) and all(
                        join(t, v)
                        for t, v in zip(args, value.args, strict=True))
            case RecordTerm(args=args):
                return isinstance(value, RecordValue) \
                    and len(value.fields) == len(args) and all(
                        join(t, v)
                        for t, v in zip(args, value.fields, strict=True))
        mine = term_value(term, defined)
        return mine is None or compatible(mine, value)

    ok = all(join(t, v) for t, v in zip(head, row, strict=True))
    return env if ok else None


def _paths(term: Term, var: str, at: tuple[int, ...] = ()
           ) -> Iterator[tuple[int, ...]]:
    """Each place `var` stands in a term, as the record fields to it."""
    if isinstance(term, Variable) and term.name == var:
        yield at
    elif isinstance(term, RecordTerm):
        for j, a in enumerate(term.args):
            yield from _paths(a, var, (*at, j))


def _matches(term: Term, value: Value) -> bool:
    """Whether a value can stand where a term stands: each constructor
    and record of the term matches the value's, and any other term matches
    any value."""
    match term:
        case ConstructorTerm(name=name, args=args):
            return isinstance(value, AdtValue) and value.constructor == name \
                and len(args) == len(value.args) \
                and all(_matches(a, v)
                        for a, v in zip(args, value.args, strict=True))
        case RecordTerm(args=args):
            return isinstance(value, RecordValue) \
                and len(args) == len(value.fields) \
                and all(_matches(a, v)
                        for a, v in zip(args, value.fields, strict=True))
        case _:
            return True
