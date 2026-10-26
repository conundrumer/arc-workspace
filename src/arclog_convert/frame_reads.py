"""The plan of a parameter table that a solver derives by a read of
`helpers.frame_pos` or `helpers.tile_pos` over extents that parameters
give, from the table's clauses, and the Souffle clauses of the instances
the plan makes (`FieldPlan.souffle`): a Frame for each extent, and, for a
tiled frame, a Tiling over the outer and the inner frame."""

from dataclasses import dataclass, replace

from engine.program import (
    Atom,
    AtomLiteral,
    ConstructorTerm,
    DeclId,
    DefinedName,
    Instance,
    NumberTerm,
    RecordTerm,
    RelationName,
    Scope,
    Term,
    TypeName,
    Unit,
    UnitId,
    Variable,
    Wildcard,
)

from arclog_convert.literals import collect_vars
from arclog_convert.terms import subst

PARAMS = ("Params",)
"""The scope of the instances a plan makes."""
FRAME_SUFFIX = "_frame"
"""What follows the table's name in the name of the Frame of a read of `helpers.frame_pos`."""
OUTER_SUFFIX = "_outer"
"""What follows the table's name in the name of the outer Frame of a read of `helpers.tile_pos`."""
INNER_SUFFIX = "_inner"
"""What follows the table's name in the name of the inner Frame of a read of `helpers.tile_pos`."""
TILING_SUFFIX = "_tiling"
"""What follows the table's name in the name of the Tiling of a read of `helpers.tile_pos`."""
FRAME = "Frame"
"""The component of a Frame, in the signature."""
TILING = "Tiling"
"""The component of a Tiling, in the signature."""


@dataclass(frozen=True)
class SquareExtent:
    """The atoms of a clause, each of a parameter, over `label`, a frame's
    extent on both axes."""

    atoms: tuple[AtomLiteral, ...]
    label: str


@dataclass(frozen=True)
class AxisExtent:
    """The atoms of one parameter of an axis and an extent, at `AXIS_V` and
    at `AXIS_H`, that give a frame's extent on each axis."""

    atoms: tuple[AtomLiteral, AtomLiteral]


@dataclass(frozen=True)
class SingleAxisExtent:
    """The atoms of a clause, each of a parameter, over `label`, a frame's
    extent on the axis that `axis`, the atom of a parameter of one axis,
    gives; the frame's extent on the other axis is 1. `axis` is the atom
    at `AXIS_V`."""

    axis: AtomLiteral
    atoms: tuple[AtomLiteral, ...]
    label: str


type Extent = SquareExtent | AxisExtent | SingleAxisExtent


@dataclass(frozen=True)
class FrameRead:
    """A read of `helpers.frame_pos`: the frame's extent, and the term of
    its cell."""

    extent: Extent
    cell: Variable | Wildcard


@dataclass(frozen=True)
class TilingRead:
    """A read of `helpers.tile_pos`: the extents of the outer and the inner
    frame, the gap (None for a gap of 0), and the terms of the cell, its
    outer position and its inner position."""

    outer: Extent
    inner: Extent
    gap: Extent | None
    cells: tuple[Variable | Wildcard, Variable | Wildcard, Variable | Wildcard]


@dataclass(frozen=True)
class FieldPlan:
    """A table's clause, whose one read of `helpers` gives a frame or a
    tiled frame of extents that parameters give, and the clause's other
    literals."""

    unit: Unit
    read: FrameRead | TilingRead
    rest: tuple

    def souffle(self, table: str) -> tuple[list[Instance], list[Unit]]:
        """The instances in `Params` that the plan makes for the table
        `table`, named by `table` and a suffix, each keyed by `$U()`, with the
        Souffle clauses that give their inputs from the extents' parameters:
        the clauses of `extent`, and for a gap `gap`, of a Frame, and of
        `outer`, `inner` and `gap` of a Tiling, in scope `Params`."""
        instances: list[Instance] = []
        units: list[Unit] = []

        def instance(suffix: str, component: str) -> str:
            name = table + suffix
            instances.append(Instance(DeclId(-1 - len(instances)), name, Scope(PARAMS), component,
                                      (TypeName((), "Unit"),), None))
            return name

        def unit(head: RelationName, args: tuple[Term, ...], body: tuple[AtomLiteral, ...]) -> None:
            units.append(Unit(UnitId(-1 - len(units)), Scope(PARAMS), Atom(head, (_KEY, *args), 0), body, None, None))

        def frame(suffix: str, extent: Extent) -> str:
            name = instance(suffix, FRAME)
            for axis, number, body in _extent_rows(extent, "N", 1):
                unit(RelationName((name,), "extent"), (axis, number), body)
            return name

        if isinstance(self.read, FrameRead):
            frame(FRAME_SUFFIX, self.read.extent)
            return instances, units
        outer, inner = frame(OUTER_SUFFIX, self.read.outer), frame(INNER_SUFFIX, self.read.inner)
        tiling = instance(TILING_SUFFIX, TILING)
        for part, frame_name in (("outer", outer), ("inner", inner)):
            unit(RelationName((tiling,), part), (Variable("P"),),
                 (AtomLiteral(Atom(RelationName((frame_name,), "cell"), (_KEY, Variable("P")), 0), False),))
        if self.read.gap is not None:
            for axis, number, body in _extent_rows(self.read.gap, "G", None):
                unit(RelationName((tiling,), "gap"), (axis, number), body)
        return instances, units


_KEY = ConstructorTerm("U", ())


def _extent_rows(extent: Extent, value: str, other: int | None) -> list[tuple[Term, Term, tuple[AtomLiteral, ...]]]:
    """The clauses that give the rows `(axis, number)` of `extent`, an axis
    and its value on that axis, with the variable `value` for the number:
    each with the row's two terms and the body. A single axis's extent gives
    as well the number `other` on the perpendicular axis, where `other` is not None."""
    axis, perp = Variable("A"), Variable("A2")

    def literal(relation: str | RelationName, *args: Term) -> AtomLiteral:
        name = relation if isinstance(relation, RelationName) else RelationName((), relation)
        return AtomLiteral(Atom(name, args, 0), False)

    match extent:
        case SquareExtent(atoms=atoms, label=label):
            return [(axis, Variable(value), (literal("axis_elem", axis), *subst(atoms, {label: value})))]
        case SingleAxisExtent(axis=held, atoms=atoms, label=label):
            on = literal(held.atom.relation, axis)
            rows = [(axis, Variable(value), (on, *subst(atoms, {label: value})))]
            return rows if other is None else [*rows, (perp, NumberTerm(other), (on, literal("perp", axis, perp)))]
        case AxisExtent(atoms=(held, _)):
            return [(axis, Variable(value), (literal(held.atom.relation, axis, Variable(value)),))]


def helpers_read(u: Unit) -> int | None:
    """The index of `u`'s one body atom of `helpers`; None where it has
    none or several."""
    hs = [i for i, l in enumerate(u.body or ()) if isinstance(l, AtomLiteral)
          and l.atom.relation.instances == ("helpers",)]
    return hs[0] if len(hs) == 1 else None


def vars_of(lits) -> set[str]:
    out: set[str] = set()
    collect_vars(list(lits), out)
    return out


def of_param(l, params: set[str]) -> bool:
    """Whether `l` is a positive atom of one of the parameters `params`."""
    return isinstance(l, AtomLiteral) and not l.negated and not l.atom.relation.instances \
        and l.atom.relation.name in params


def unlined(l):
    """`l` with the line of its atom dropped, so that two clauses' equal
    literals compare equal."""
    return replace(l, atom=replace(l.atom, line=0)) if isinstance(l, AtomLiteral) else l


def position(t) -> Variable | Wildcard | None:
    return t if isinstance(t, (Variable, Wildcard)) else None


def planned(u: Unit, read: FrameRead | TilingRead, used: tuple, others: list) -> FieldPlan:
    """The plan of `u` with `read`, where `used` are the atoms of its
    extents among `others`, the literals beside the read. An atom of an
    extent stays among the other literals where a label of it is read
    elsewhere in the clause."""
    rest = [l for l in others if not any(l is x for x in used)]
    elsewhere = vars_of(rest) | vars_of([AtomLiteral(u.head, False)])
    kept = [l for l in others if any(l is x for x in used) and vars_of([l]) & elsewhere]
    return FieldPlan(u, read, tuple(kept + rest))


def field_plan(us: list[Unit], params: set[str]) -> FieldPlan | None:
    """The plan of a table whose one clause reads one `helpers.frame_pos` or
    `helpers.tile_pos`, with each extent an `Extent` over the parameters
    `params`, or whose two clauses are those `single_axis_plan` takes;
    None otherwise."""
    if len(us) == 2:
        return single_axis_plan(us, params)
    if len(us) != 1:
        return None
    u = us[0]
    body = list(u.body or ())
    h = helpers_read(u)
    if h is None or body[h].negated:
        return None
    a = body[h].atom
    others = [l for j, l in enumerate(body) if j != h]

    def extent(d) -> Extent | None:
        if not isinstance(d, RecordTerm) or len(d.args) != 2:
            return None
        x, y = d.args
        if isinstance(x, Variable) and x == y:
            bs = tuple(l for l in others if of_param(l, params) and vars_of([l]) == {x.name})
            return SquareExtent(bs, x.name) if bs else None
        if not (isinstance(x, Variable) and isinstance(y, Variable)):
            return None

        def at(axis: str, v: Variable) -> AtomLiteral | None:
            got = [l for l in others if of_param(l, params) and l.atom.args == (DefinedName(axis), v)]
            return got[0] if len(got) == 1 else None
        av, ah = at("AXIS_V", x), at("AXIS_H", y)
        if av is None or ah is None or av.atom.relation != ah.atom.relation:
            return None
        return AxisExtent((av, ah))

    def zero(d) -> bool:
        return isinstance(d, RecordTerm) and all(isinstance(t, NumberTerm) and t.value == 0 for t in d.args)

    read: FrameRead | TilingRead
    if a.relation.name == "frame_pos" and len(a.args) == 2:
        e, p = extent(a.args[0]), position(a.args[1])
        if e is None or p is None:
            return None
        read, used = FrameRead(e, p), e.atoms
    elif a.relation.name == "tile_pos" and len(a.args) == 6:
        outer, inner = extent(a.args[0]), extent(a.args[1])
        gap = None if zero(a.args[2]) else extent(a.args[2])
        p, po, pi = (position(t) for t in a.args[3:])
        if outer is None or inner is None or (gap is None and not zero(a.args[2])) \
                or p is None or po is None or pi is None:
            return None
        read = TilingRead(outer, inner, gap, (p, po, pi))
        used = outer.atoms + inner.atoms + (gap.atoms if gap else ())
    else:
        return None
    return planned(u, read, used, others)


def single_axis_plan(us: list[Unit], params: set[str]) -> FieldPlan | None:
    """The plan of a table of two clauses, each reading one
    `helpers.frame_pos` whose extent is `[N, 1]` in one clause and `[1, N]`
    in the other, with N a variable: beside that read, the clauses are equal
    except for one atom of a parameter of `params`, of one relation in both,
    whose one argument is `AXIS_V` in the clause of `[N, 1]` and `AXIS_H` in
    the other; N has at least one atom of a parameter whose labels are N
    alone. The plan is of the clause of `[N, 1]`. None otherwise."""
    by_axis: dict[str, tuple[Unit, int, str]] = {}
    for u in us:
        h = helpers_read(u)
        if h is None or u.body[h].negated:
            return None
        a = u.body[h].atom
        if a.relation.name != "frame_pos" or len(a.args) != 2 or not isinstance(a.args[0], RecordTerm) \
                or len(a.args[0].args) != 2:
            return None
        x, y = a.args[0].args
        one = NumberTerm(1)
        if isinstance(x, Variable) and y == one:
            axis, n = "AXIS_V", x.name
        elif isinstance(y, Variable) and x == one:
            axis, n = "AXIS_H", y.name
        else:
            return None
        if axis in by_axis:
            return None
        by_axis[axis] = (u, h, n)
    if by_axis.keys() != {"AXIS_V", "AXIS_H"}:
        return None
    parts = {}
    for axis, (u, h, n) in by_axis.items():
        others = [l for j, l in enumerate(u.body) if j != h]
        axes = [l for l in others if of_param(l, params) and l.atom.args == (DefinedName(axis),)]
        ns = tuple(l for l in others if of_param(l, params) and vars_of([l]) == {n})
        if len(axes) != 1 or not ns:
            return None
        rest = [unlined(l) for l in others if l is not axes[0] and not any(l is x for x in ns)]
        parts[axis] = (u, others, axes[0], ns, n, rest, position(u.body[h].atom.args[1]))
    (uv, others, av, ns, n, rest_v, p), (uh, _, ah, nh, n_h, rest_h, p_h) = parts["AXIS_V"], parts["AXIS_H"]
    if av.atom.relation != ah.atom.relation or n != n_h or p is None or p != p_h \
            or [unlined(l) for l in ns] != [unlined(l) for l in nh] or rest_v != rest_h \
            or replace(uv.head, line=0) != replace(uh.head, line=0):
        return None
    return planned(uv, FrameRead(SingleAxisExtent(av, ns, n), p), (av, *ns), others)
