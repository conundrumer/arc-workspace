"""The operations that return a new program: fix a relation's value,
remove a part, add an instance."""

from dataclasses import replace

from engine.engine import (
    AnchorOffStamp,
    CellOffForm,
    GridMisfit,
    GridValue,
    Occurrence,
    RelationValue,
    RemovalTarget,
    RemoveAtom,
    RemoveColumn,
    RemoveDisjunct,
    RemoveFact,
    RemoveUnit,
    SizeOffLayout,
)
from engine.program import (
    Aggregate,
    Atom,
    AtomLiteral,
    BodyLiteral,
    BoolLiteral,
    Component,
    DeclId,
    Disjunction,
    GridCall,
    GridCell,
    GridForm,
    GridLayout,
    MemberCell,
    Instance,
    NumberTerm,
    Program,
    RelationDecl,
    RelationName,
    RigidCall,
    Row,
    Scope,
    Term,
    Unit,
    UnitId,
    literal_aggregates,
    term_of,
    with_literal_terms,
    with_subterms,
    grid_size,
)
from engine.memo import ByIdentity
from souffle.expand import expand, grid_facts
from souffle.index import Tree, held_index, hold, index_of, tree_of
from souffle.layout import next_decl, next_unit
from souffle.text import text as code_text
from souffle.values import NotConstant, constant

# remove


def remove(program: Program, target: RemovalTarget) -> Program:
    """`program` without `target` (`engine.Engine.remove`). An emptied
    conjunction holds `true`."""
    match target:
        case RemoveUnit(unit):
            return _remove_unit(program, unit)
        case RemoveAtom(unit, path):
            return _edit_body(program, unit, path, disjunct=False)
        case RemoveDisjunct(unit, path):
            return _edit_body(program, unit, path, disjunct=True)
        case RemoveColumn(relation, column):
            return _remove_column(program, relation, column)
        case RemoveFact(relation, row):
            return _remove_fact(program, relation, row)
    raise TypeError(f"not a removal target: {target!r}")


def _in_rigid_bodies(program: Program, gone: UnitId,
                     instead: tuple[UnitId, ...] = ()) -> Program:
    """`program` with each RIGID call whose body holds `gone` holding
    `instead` in its place."""
    macros = tuple(
        replace(m, body=tuple(k for b in m.body for k in (instead if b == gone else (b,))))
        if isinstance(m, RigidCall) and gone in m.body else m
        for m in program.macros)
    return replace(program, macros=macros)


def _remove_unit(program: Program, unit: UnitId) -> Program:
    gone = [u for u in program.units if u.id == unit]
    if gone:
        out = _in_rigid_bodies(
            replace(program, units=tuple(u for u in program.units if u.id != unit)), unit)
        # The index is kept where the removal changes no declaration
        # and no RIGID call's body.
        index = held_index(program)
        if index is not None and not program.in_rigid_body(unit):
            hold(out, index.changed((gone, ()), ((), ())))
        return out
    macro = next((m for m in program.macros if m.id == unit), None)
    if macro is None:
        raise ValueError(f"no unit {unit.index}")
    gone = {unit}
    relations = program.relations
    if isinstance(macro, RigidCall):
        gone |= set(macro.body)
        relations = tuple(r for r in relations if not macro.binds(r))
    return _in_rigid_bodies(replace(
        program, relations=relations,
        units=tuple(u for u in program.units if u.id not in gone),
        macros=tuple(m for m in program.macros if m.id not in gone)), unit)


def _edit_body(program: Program, unit: UnitId, path: tuple[int, ...],
               disjunct: bool) -> Program:
    old = next((u for u in program.units if u.id == unit), None)
    if old is None or old.body is None:
        raise ValueError(f"no rule {unit.index}")
    body = _without(old.body, path, disjunct)
    subsumptive = old.subsumptive and not (path[0] == 0 and not disjunct)
    new = replace(old, body=body, subsumptive=subsumptive)
    return replace(program, units=tuple(new if u.id == unit else u for u in program.units))


def _without(body: tuple[BodyLiteral, ...], path: tuple[int, ...],
             disjunct: bool) -> tuple[BodyLiteral, ...]:
    """`body` less the literal `path` leads to, or less the branch of the
    disjunction it leads to; an emptied conjunction holds `true`. After the
    index of a literal, a disjunction's step is (branch, literal) and any
    other literal's is (aggregate, literal): the aggregate by its place
    among the literal's aggregates, left to right, and the literal of its
    body."""
    if not path or path[0] >= len(body):
        raise ValueError(f"no literal at {path}")
    i = path[0]
    if len(path) == 1:
        if disjunct:
            raise ValueError(f"no branch at {path}")
        return body[:i] + body[i + 1:] or (BoolLiteral(True),)
    lit, k = body[i], path[1]
    if isinstance(lit, Disjunction):
        if k >= len(lit.branches):
            raise ValueError(f"no branch at {path}")
        if len(path) == 2:
            if not disjunct:
                raise ValueError(f"no literal at {path}")
            branches = lit.branches[:k] + lit.branches[k + 1:]
        else:
            branches = tuple(_without(br, path[2:], disjunct) if j == k else br
                             for j, br in enumerate(lit.branches))
        return body[:i] + (replace(lit, branches=branches),) + body[i + 1:]
    aggregates = literal_aggregates(lit)
    if k >= len(aggregates) or len(path) == 2:
        raise ValueError(f"no aggregate literal at {path}")
    agg = aggregates[k]
    inner = replace(agg, body=_without(agg.body, path[2:], disjunct))
    return body[:i] + (_with_aggregate(lit, k, inner),) + body[i + 1:]


def _with_aggregate(lit: BodyLiteral, k: int, new: Aggregate) -> BodyLiteral:
    """`lit` with its `k`th aggregate (`literal_aggregates`) as `new`."""
    seen = [0]

    def swap(t: Term) -> Term:
        if isinstance(t, Aggregate):
            seen[0] += 1
            return new if seen[0] - 1 == k else t
        return with_subterms(t, swap)

    return with_literal_terms(lit, swap)


def map_atoms(body: tuple[BodyLiteral, ...], fn) -> tuple[BodyLiteral, ...]:
    """`body` with `fn` applied to every atom, through disjunctions and
    aggregates."""
    out: list[BodyLiteral] = []
    for lit in body:
        match lit:
            case AtomLiteral(atom, negated):
                a = fn(atom)
                out.append(AtomLiteral(replace(a, args=tuple(
                    _map_term(t, fn) for t in a.args)), negated))
            case Disjunction(branches, line):
                out.append(Disjunction(tuple(map_atoms(b, fn) for b in branches), line))
            case _:
                out.append(with_literal_terms(lit, lambda t: _map_term(t, fn)))
    return tuple(out)


def _map_term(t: Term, fn) -> Term:
    """`t` with `fn` applied to every atom of the aggregate bodies it
    holds."""
    if isinstance(t, Aggregate):
        return replace(t, expr=None if t.expr is None else _map_term(t.expr, fn),
                       body=map_atoms(t.body, fn))
    return with_subterms(t, lambda x: _map_term(x, fn))


def _remove_column(program: Program, relation: DeclId, column: int) -> Program:
    tree = tree_of(program)
    decl = program.relation(relation)
    if decl is None or column >= len(decl.columns):
        raise ValueError(f"no column {column} of declaration {relation.index}")

    def resolves(atom: Atom, scope: Scope) -> bool:
        return tree.denotes(atom.relation, scope, relation)

    def cut(atom: Atom, scope: Scope) -> Atom:
        if not resolves(atom, scope):
            return atom
        return replace(atom, args=atom.args[:column] + atom.args[column + 1:])

    units = []
    for u in program.units:
        head = cut(u.head, u.scope)
        body = None if u.body is None else map_atoms(u.body, lambda a, s=u.scope: cut(a, s))
        units.append(u if (head, body) == (u.head, u.body) else replace(u, head=head, body=body))
    macros = []
    for m in program.macros:
        if isinstance(m, GridCall) and resolves(Atom(m.relation, (), 0), m.scope):
            if column >= len(m.keys):
                raise ValueError(f"column {column} of {code_text(m.layout)} is a cell column")
            m = replace(m, keys=m.keys[:column] + m.keys[column + 1:])
        macros.append(m)
    decls = tuple(replace(r, columns=r.columns[:column] + r.columns[column + 1:])
                  if r.id == relation else r for r in program.relations)
    return replace(program, relations=decls, units=tuple(units), macros=tuple(macros))


def _row_of(atom: Atom, program: Program) -> Row | None:
    defines = {d.name: d for d in program.defines}
    try:
        return tuple(constant(a, defines) for a in atom.args)
    except NotConstant:
        return None


def _remove_fact(program: Program, relation: RelationName, row: Row) -> Program:
    tree = tree_of(program)
    target = tree.resolve(relation, Scope(()))
    if target is None:
        raise ValueError(f"no relation {relation.text}")

    def same(atom: Atom, scope: Scope) -> bool:
        return tree.denotes(atom.relation, scope, target.decl.id)

    for u in program.units:
        if u.body is None and same(u.head, u.scope) and _row_of(u.head, program) == row:
            return _in_rigid_bodies(
                replace(program, units=tuple(x for x in program.units if x.id != u.id)), u.id)
    for m in program.macros:
        if isinstance(m, GridCall) and same(Atom(m.relation, (), 0), m.scope):
            heads = [h for _, h in grid_facts(m)]
            if any(_row_of(h, program) == row for h in heads):
                n = next_unit(program)
                units: list[Unit] = []
                for h in heads:
                    if _row_of(h, program) == row and not any(
                            _row_of(x.head, program) == row for x in units):
                        continue
                    units.append(Unit(UnitId(n), m.scope, h, None, None, m.span))
                    n += 1
                return _in_rigid_bodies(
                    replace(program, units=(*program.units, *units),
                            macros=tuple(x for x in program.macros if x.id != m.id)),
                    m.id, tuple(u.id for u in units))
    raise ValueError(f"no fact {row} of {relation.text}")


# instantiate


def instantiate(program: Program, component: str, name: str) -> Program:
    """`program` with a top-level instance `name` of `component`
    (`engine.Engine.instantiate`)."""
    if not any(c.name == component and not c.scope.components for c in program.components):
        raise ValueError(f"no component {component}")
    inst = Instance(DeclId(next_decl(program)), name, Scope(()), component, (), None)
    return replace(program, instances=(*program.instances, inst))


# fix_relation


_FIXED: ByIdentity[Program, dict[tuple[RelationName, RelationValue], Program]] \
    = ByIdentity()
"""`fix_relation`'s programs, for each program they rewrite while it
lives: a group's run fixes the same value on many inputs, and the one
program it gives keeps the text and the reading its runs share."""


def fix_relation(program: Program, relation: RelationName, value: RelationValue) -> Program:
    """`program` with `relation`, named from the top level, holding exactly
    `value`, as facts or as one GRID call of the form the relation's calls
    had, fed by none of its units (`engine.Engine.fix_relation`). Where a component that feeds it is held
    by another instance too, the instance on the path reads a copy. Computed once per program, relation and value while the program
    lives."""
    return _FIXED.keyed(program, (relation, value),
                        lambda: _fix_relation(program, relation, value))


def _fix_relation(program: Program, relation: RelationName,
                  value: RelationValue) -> Program:
    """`fix_relation`, computed."""
    index = index_of(program)
    tree = index.tree
    hit = tree.resolve(relation, Scope(()))
    if hit is None:
        raise ValueError(f"no relation {relation.text}")
    grid_call: GridCall | None = None
    if program.rigid_bound(hit.decl) or hit.decl.chart_of is not None:
        # The expansion writes a GRID call as plain units, so the call
        # that places a grid value is taken before it.
        fed = {o.unit for o in index.feeding(hit.decl.id)}
        grid_call = next((m for m in program.macros
                          if isinstance(m, GridCall) and m.id in fed), None)
        program = expand(program)
        index = index_of(program)
        tree = index.tree
        hit = tree.resolve(relation, Scope(()))
        assert hit is not None
    scope_of = {u.id: u.scope.components for u in (*program.units, *program.macros)}
    feeding = [o for o in index.feeding(hit.decl.id)
               if _feeds_instance(tree, scope_of[o.unit], o, relation)]
    feeders = {o.unit for o in feeding}
    layout = next((m for m in program.macros
                   if isinstance(m, GridCall) and m.id in feeders), grid_call)
    scopes = {scope_of[o.unit] for o in feeding}
    shared = [s for s in scopes if s and _uses(tree, program, s) != 1]
    if shared:
        program = _clone_for(program, tree, relation, hit.decl, feeders)
        # A top-level clause whose head names the instance relation is in
        # no copied text, so it goes here.
        top = {u for u in feeders if not scope_of[u]}
        program = replace(program,
                          units=tuple(u for u in program.units if u.id not in top),
                          macros=tuple(m for m in program.macros if m.id not in top))
        return _add_value(program, relation, value, layout)
    kept = replace(program,
                   units=tuple(u for u in program.units if u.id not in feeders),
                   macros=tuple(m for m in program.macros if m.id not in feeders))
    out = _add_value(kept, relation, value, layout)
    # The index is kept: the rewrite changes no declaration, so the
    # result's index is this one without the feeders and with the value's
    # units or call.
    hold(out, index.changed(
        ([u for u in program.units if u.id in feeders],
         [m for m in program.macros if m.id in feeders]),
        (out.units[len(kept.units):], out.macros[len(kept.macros):])))
    return out


def _feeds_instance(tree: Tree, scope: tuple[str, ...], occurrence: Occurrence,
                    relation: RelationName) -> bool:
    """Whether a unit in the text of `scope` that feeds the relation's
    declaration feeds it at `relation`'s instance path. A head with no
    instance names the relation of the text it stands in, which every
    instance of that text holds. A head `a.b.r` feeds the path whose last
    instances are `a.b` and whose earlier ones lead to the unit's text: a
    top-level clause `rise_ray.dir(...)` feeds `rise_ray.dir` and no other
    instance's `dir`."""
    head = occurrence.atom.relation.instances
    if not head:
        return True
    path = relation.instances
    if len(head) > len(path) or path[len(path) - len(head):] != head:
        return False
    holder = _instance_text(tree, path[:len(path) - len(head)])
    if holder is None:
        return False
    return scope == holder or scope in tree.chain(holder)


def _instance_walk(tree: Tree, instances: tuple[str, ...]
                   ) -> tuple[list[Instance], tuple[str, ...]] | str:
    """The instance each part of the instance path `instances`, named from
    the top level, names, outermost first, and the path of the component
    text the path stands for, `()` for the top level; the first part that
    names no instance where one does not."""
    inits: list[Instance] = []
    scope: tuple[str, ...] = ()
    for part in instances:
        init = next((i for texts in tree.levels(scope) for p in texts
                     if (i := tree.inits.get(p, {}).get(part)) is not None), None)
        if init is None:
            return part
        got = tree.comp(init.component, init.scope.components)
        if got is None:
            return part
        inits.append(init)
        scope = got
    return inits, scope


def _instance_text(tree: Tree, instances: tuple[str, ...]) -> tuple[str, ...] | None:
    """The path of the component text the instance path `instances`,
    named from the top level, stands for; `()` for the top level, None
    where a part names no instance."""
    got = _instance_walk(tree, instances)
    return None if isinstance(got, str) else got[1]


def _uses(tree: Tree, program: Program, path: tuple[str, ...], depth: int = 0) -> int:
    """How many instances hold the text of the component at `path`: each
    instance of it, or of a component that extends it, counted once per
    instance of the text that holds the instance."""
    if not path:
        return 1
    if depth > 32:
        return 2
    total = 0
    for inst in program.instances:
        if tree.comp(inst.component, inst.scope.components) == path:
            total += _uses(tree, program, inst.scope.components, depth + 1)
    for comp_path, comp in tree.comps.items():
        if comp.base and tree.comp(comp.base, comp_path[:-1]) == path:
            total += _uses(tree, program, comp_path, depth + 1)
    return total


def place_grid(layout: GridLayout, mark: tuple[int, int] | None,
               value: GridValue) -> GridValue | GridMisfit:
    """`value` as the value of a relation one GRID call of `layout` stores,
    the call's cell marked `@` at `mark` (`engine.Engine.place_grid`)."""
    grid, anchor = value.grid, value.anchor
    if anchor is not None and not layout.stamp:
        return AnchorOffStamp()
    if not layout.valued:
        off = next(((r, c, v) for r, row in enumerate(grid)
                    for c, v in enumerate(row)
                    if MemberCell.of_value(v) is None), None)
        if off is not None:
            return CellOffForm((off[0], off[1]), off[2])
    if anchor is not None or not layout.stamp:
        return value
    if mark is None:
        raise ValueError(f"{code_text(layout)} with no cell marked `@`")
    given = grid_size(grid)
    if given != (layout.height, layout.width):
        return SizeOffLayout(given)
    return GridValue(value.keys, grid, mark)


def _add_value(program: Program, relation: RelationName, value: RelationValue,
               layout: GridCall | None) -> Program:
    """`program` with `value` added as facts of `relation`, or a grid as one
    GRID call of `layout`'s form at the grid's own size, placed as
    `place_grid` places it, and a dense call where no GRID call is
    `layout`: a stamp anchored at the placed anchor, a form that takes
    members alone taking each cell as its `MemberCell`, and a
    valued form taking every cell as a value. Raises `ValueError` for a
    grid `place_grid` does not place."""
    n = next_unit(program)
    if isinstance(value, GridValue):
        if layout is not None:
            placed = place_grid(layout.layout, layout.anchor, value)
            if not isinstance(placed, GridValue):
                raise ValueError(f"{relation.text}: {code_text(layout.layout)} "
                                 f"does not place the grid ({placed})")
            value = placed
        elif value.anchor is not None:
            raise ValueError(f"{relation.text}: a grid with an anchor and no "
                             "GRID call")
        grid, anchor = value.grid, value.anchor
        h, w = grid_size(grid)
        form = GridLayout(GridForm.DENSE if layout is None
                          else layout.layout.form, anchor is not None, h, w)
        member_only = not form.valued

        def cell(r: int, c: int, v: int) -> GridCell:
            m = MemberCell.of_value(v) if member_only else None
            term = NumberTerm(v) if m is None else m.term
            return GridCell(term, (r, c) == anchor)

        call = GridCall(UnitId(n), Scope(()), form, relation, tuple(term_of(k) for k in value.keys),
                        tuple(tuple(cell(r, c, v) for c, v in enumerate(row))
                              for r, row in enumerate(grid)), None)
        return replace(program, macros=(*program.macros, call))
    units = tuple(Unit(UnitId(n + i), Scope(()),
                       Atom(relation, tuple(term_of(v) for v in row), 0), None, None, None)
                  for i, row in enumerate(value))
    return replace(program, units=(*program.units, *units))


def _clone_for(program: Program, tree: Tree, relation: RelationName, decl: RelationDecl,
               feeders: set[UnitId]) -> Program:
    """`program` with the instances on `relation`'s path reading copies of
    their components, the copies without the units in `feeders`, so that no
    other instance loses them."""
    walked = _instance_walk(tree, relation.instances)
    if isinstance(walked, str):
        raise ValueError(f"no instance {walked}")
    inits = walked[0]
    state = _Cloner(program, tree, feeders)
    # From the innermost instance outward: each copy's instance is written
    # in the text that holds it, which is copied in turn when shared.
    target: str | None = None
    for k in range(len(inits) - 1, -1, -1):
        init = inits[k]
        path = tree.comp(init.component, init.scope.components)
        assert path is not None
        if target is None:
            target = state.copy_chain(path, None)
        holder = init.scope.components
        new_init = replace(init, component=target)
        if not holder or _uses(tree, program, holder) == 1:
            state.replace_instance(init, new_init)
            break
        target = state.copy_chain(holder, (init, new_init))
    return state.program


class _Cloner:
    def __init__(self, program: Program, tree: Tree, feeders: set[UnitId]):
        self.program = program
        self.tree = tree
        self.feeders = feeders
        self.unit_n = next_unit(program)
        self.decl_n = next_decl(program)
        self.copies = 0

    def uid(self) -> UnitId:
        self.unit_n += 1
        return UnitId(self.unit_n - 1)

    def did(self) -> DeclId:
        self.decl_n += 1
        return DeclId(self.decl_n - 1)

    def replace_instance(self, old: Instance, new: Instance) -> None:
        self.program = replace(self.program, instances=tuple(
            new if i.id == old.id else i for i in self.program.instances))

    def copy_chain(self, path: tuple[str, ...],
                   swap: tuple[Instance, Instance] | None) -> str:
        """A copy of the component at `path` and of each it extends, under
        new names at the top level, less the units in `feeders`, with the
        instance `swap[0]` written as `swap[1]`; the copy's name."""
        chain = self.tree.chain(path)
        names: list[str] = []
        for p in chain:
            self.copies += 1
            names.append(f"_fixed{self.copies}_{p[-1]}")
        p = self.program
        comps, units, macros, rels, types, insts = [], [], [], [], [], []
        for k, cpath in enumerate(chain):
            comp = self.tree.comps[cpath]
            if any(c.scope.components[:len(cpath)] == cpath for c in p.components):
                raise ValueError(f"component {comp.name} declares a component")
            inner = Scope((names[k],))
            base = names[k + 1] if k + 1 < len(chain) else comp.base
            comps.append(Component(self.did(), names[k], Scope(()), comp.type_params,
                                   base, comp.base_type_args, None))
            for u in p.units:
                if u.scope.components == cpath and u.id not in self.feeders:
                    units.append(replace(u, id=self.uid(), scope=inner))
            for m in p.macros:
                if m.scope.components == cpath and m.id not in self.feeders:
                    if isinstance(m, RigidCall):
                        raise ValueError(f"component {comp.name} holds a RIGID call")
                    macros.append(replace(m, id=self.uid(), scope=inner))
            for r in p.relations:
                if r.scope.components == cpath:
                    rels.append(replace(r, id=self.did(), scope=inner))
            for t in p.types:
                if t.scope.components == cpath:
                    types.append(replace(t, id=self.did(), scope=inner))
            for i in p.instances:
                if i.scope.components == cpath:
                    if swap is not None and i.id == swap[0].id:
                        i = swap[1]
                    insts.append(replace(i, id=self.did(), scope=inner))
        self.program = replace(
            p, components=(*p.components, *comps), units=(*p.units, *units),
            macros=(*p.macros, *macros), relations=(*p.relations, *rels),
            types=(*p.types, *types), instances=(*p.instances, *insts))
        return names[0]
