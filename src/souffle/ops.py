"""The operations that return a new program: fix a relation's value,
remove a part, add an instance."""

from dataclasses import replace

from engine.engine import (
    GridValue,
    Occurrence,
    RelationValue,
    RemovalTarget,
    RemoveAtom,
    RemoveColumn,
    RemoveDisjunct,
    RemoveFact,
    RemoveUnit,
)
from engine.program import (
    Aggregate,
    Atom,
    AtomLiteral,
    BinaryTerm,
    BodyLiteral,
    BoolLiteral,
    Cast,
    Comparison,
    Component,
    ConstructorTerm,
    DeclId,
    Disjunction,
    FunctorCall,
    GridCall,
    GridCell,
    GridForm,
    Instance,
    IntrinsicCall,
    NumberTerm,
    Program,
    RecordTerm,
    RelationDecl,
    RelationName,
    RigidCall,
    Row,
    Scope,
    Term,
    UnaryTerm,
    Unit,
    UnitId,
    Wildcard,
)
from souffle.expand import expand, grid_facts
from souffle.index import Tree, hold, index_of
from souffle.layout import next_decl, next_unit
from souffle.parser import Shape
from souffle.values import NotConstant, constant, term_of

# remove


def remove(program: Program, target: RemovalTarget) -> Program:
    """`program` without `target`. An emptied conjunction holds `true`.
    Raises `ValueError` where the program lacks the target: no such unit,
    literal, branch, column or fact."""
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
    if any(u.id == unit for u in program.units):
        return _in_rigid_bodies(
            replace(program, units=tuple(u for u in program.units if u.id != unit)), unit)
    macro = next((m for m in program.macros if m.id == unit), None)
    if macro is None:
        raise ValueError(f"no unit {unit.index}")
    gone = {unit}
    relations = program.relations
    if isinstance(macro, RigidCall):
        gone |= set(macro.body)
        relations = tuple(r for r in relations
                          if not (r.scope == macro.scope
                                  and (r.chart_of == macro.block or r.name in macro.names)))
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


def _literal_terms(lit: BodyLiteral) -> tuple[Term, ...]:
    match lit:
        case AtomLiteral(atom, _):
            return atom.args
        case Comparison(_, lhs, rhs):
            return (lhs, rhs)
    return ()


def _term_aggregates(t: Term) -> list[Aggregate]:
    match t:
        case Aggregate():
            return [t]
        case ConstructorTerm(_, args) | RecordTerm(args) | IntrinsicCall(_, args) \
                | FunctorCall(_, args):
            return [a for x in args for a in _term_aggregates(x)]
        case UnaryTerm(_, arg) | Cast(arg, _):
            return _term_aggregates(arg)
        case BinaryTerm(_, lhs, rhs):
            return _term_aggregates(lhs) + _term_aggregates(rhs)
    return []


def literal_aggregates(lit: BodyLiteral) -> list[Aggregate]:
    """The aggregates a literal's terms hold, left to right, not those
    inside another aggregate."""
    return [a for t in _literal_terms(lit) for a in _term_aggregates(t)]


def _with_aggregate(lit: BodyLiteral, k: int, new: Aggregate) -> BodyLiteral:
    """`lit` with its `k`th aggregate (`literal_aggregates`) as `new`."""
    seen = [0]

    def swap(t: Term) -> Term:
        match t:
            case Aggregate():
                seen[0] += 1
                return new if seen[0] - 1 == k else t
            case ConstructorTerm(name, args):
                return ConstructorTerm(name, tuple(swap(a) for a in args))
            case RecordTerm(args):
                return RecordTerm(tuple(swap(a) for a in args))
            case IntrinsicCall(f, args):
                return IntrinsicCall(f, tuple(swap(a) for a in args))
            case FunctorCall(name, args):
                return FunctorCall(name, tuple(swap(a) for a in args))
            case UnaryTerm(op, arg):
                return UnaryTerm(op, swap(arg))
            case Cast(arg, type_name):
                return Cast(swap(arg), type_name)
            case BinaryTerm(op, lhs, rhs):
                lhs2 = swap(lhs)
                return BinaryTerm(op, lhs2, swap(rhs))
        return t

    match lit:
        case AtomLiteral(atom, negated):
            return AtomLiteral(replace(atom, args=tuple(swap(a) for a in atom.args)), negated)
        case Comparison(op, lhs, rhs, line):
            lhs2 = swap(lhs)
            return Comparison(op, lhs2, swap(rhs), line)
    return lit


def map_atoms(body: tuple[BodyLiteral, ...], fn) -> tuple[BodyLiteral, ...]:
    """`body` with `fn` applied to every atom, through disjunctions and
    aggregates."""
    out: list[BodyLiteral] = []
    for lit in body:
        match lit:
            case AtomLiteral(atom, negated):
                a = fn(atom)
                out.append(AtomLiteral(replace(a, args=_map_terms(a.args, fn)), negated))
            case Comparison(op, lhs, rhs, line):
                lhs2, rhs2 = _map_terms((lhs, rhs), fn)
                out.append(Comparison(op, lhs2, rhs2, line))
            case Disjunction(branches, line):
                out.append(Disjunction(tuple(map_atoms(b, fn) for b in branches), line))
            case _:
                out.append(lit)
    return tuple(out)


def _map_terms(terms: tuple[Term, ...], fn) -> tuple[Term, ...]:
    out: list[Term] = []
    for t in terms:
        match t:
            case Aggregate(op, expr, body):
                out.append(Aggregate(op, None if expr is None else _map_terms((expr,), fn)[0],
                                     map_atoms(body, fn)))
            case ConstructorTerm(name, args):
                out.append(ConstructorTerm(name, _map_terms(args, fn)))
            case RecordTerm(args):
                out.append(RecordTerm(_map_terms(args, fn)))
            case IntrinsicCall(f, args):
                out.append(IntrinsicCall(f, _map_terms(args, fn)))
            case FunctorCall(name, args):
                out.append(FunctorCall(name, _map_terms(args, fn)))
            case UnaryTerm(op, arg):
                out.append(UnaryTerm(op, _map_terms((arg,), fn)[0]))
            case Cast(arg, type_name):
                out.append(Cast(_map_terms((arg,), fn)[0], type_name))
            case BinaryTerm(op, lhs, rhs):
                a, b = _map_terms((lhs, rhs), fn)
                out.append(BinaryTerm(op, a, b))
            case _:
                out.append(t)
    return tuple(out)


def _remove_column(program: Program, relation: DeclId, column: int) -> Program:
    tree = Tree(program)
    decl = next((r for r in program.relations if r.id == relation), None)
    if decl is None or column >= len(decl.columns):
        raise ValueError(f"no column {column} of declaration {relation.index}")

    def resolves(atom: Atom, scope: Scope) -> bool:
        hit = tree.resolve(atom.relation, scope)
        return hit is not None and hit.decl.id == relation

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
                raise ValueError(f"column {column} of {Shape.of_call(m).name} is a cell column")
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
    tree = Tree(program)
    target = tree.resolve(relation, Scope(()))
    if target is None:
        raise ValueError(f"no relation {relation}")

    def same(atom: Atom, scope: Scope) -> bool:
        hit = tree.resolve(atom.relation, scope)
        return hit is not None and hit.decl.id == target.decl.id

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
    raise ValueError(f"no fact {row} of {relation}")


# instantiate


def instantiate(program: Program, component: str, name: str) -> Program:
    """`program` with a top-level instance `name` of `component`. Raises
    `ValueError` where no top-level component has that name."""
    if not any(c.name == component and not c.scope.components for c in program.components):
        raise ValueError(f"no component {component}")
    inst = Instance(DeclId(next_decl(program)), name, Scope(()), component, (), None)
    return replace(program, instances=(*program.instances, inst))


# fix_relation


def fix_relation(program: Program, relation: RelationName, value: RelationValue) -> Program:
    """`program` with `relation`, named from the top level, holding exactly
    `value`, as facts or as one GRID call of the form the relation's calls
    had, fed by none of its units. Where a component that feeds it is held
    by another instance too, the instance on the path reads a copy. Raises
    `ValueError` where no declaration answers the name, and for a grid on a
    stamp or sparse form."""
    index = index_of(program)
    tree = index.tree
    hit = tree.resolve(relation, Scope(()))
    if hit is None:
        raise ValueError(f"no relation {'.'.join((*relation.instances, relation.name))}")
    if any(isinstance(m, RigidCall) and hit.decl.name in m.names for m in program.macros) \
            or hit.decl.chart_of is not None:
        program = expand(program)
        index = index_of(program)
        tree = index.tree
        hit = tree.resolve(relation, Scope(()))
        assert hit is not None
    scope_of = {u.id: u.scope.components for u in (*program.units, *program.macros)}
    feeding = [o for o in index.feeding(hit.decl.id)
               if _feeds_instance(tree, scope_of.get(o.unit, ()), o, relation)]
    feeders = {o.unit for o in feeding}
    grid_form = next((Shape.of_call(m) for m in program.macros
                      if isinstance(m, GridCall) and m.id in feeders), None)
    scopes = {_scope_of(program, o.unit) for o in feeding}
    shared = [s for s in scopes if s and _uses(tree, program, s) != 1]
    if shared:
        program = _clone_for(program, tree, relation, hit.decl, feeders)
        # A top-level clause whose head names the instance relation is in
        # no copied text, so it goes here.
        top = {u for u in feeders if not scope_of.get(u, ())}
        program = replace(program,
                          units=tuple(u for u in program.units if u.id not in top),
                          macros=tuple(m for m in program.macros if m.id not in top))
        return _add_value(program, relation, value, grid_form)
    kept = replace(program,
                   units=tuple(u for u in program.units if u.id not in feeders),
                   macros=tuple(m for m in program.macros if m.id not in feeders))
    out = _add_value(kept, relation, value, grid_form)
    # The index is carried: the rewrite changes no declaration, so the
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


def _instance_text(tree: Tree, instances: tuple[str, ...]) -> tuple[str, ...] | None:
    """The path of the component text the instance path `instances`,
    named from the top level, stands for; `()` for the top level, None
    where a part names no instance."""
    scope: tuple[str, ...] = ()
    for part in instances:
        init = next((i for texts in tree.levels(scope) for p in texts
                     if (i := tree.inits.get(p, {}).get(part)) is not None), None)
        if init is None:
            return None
        got = tree.comp(init.component, init.scope.components)
        if got is None:
            return None
        scope = got
    return scope


def _scope_of(program: Program, unit: UnitId) -> tuple[str, ...]:
    for u in (*program.units, *program.macros):
        if u.id == unit:
            return u.scope.components
    return ()


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


def _add_value(program: Program, relation: RelationName, value: RelationValue,
               form: Shape | None) -> Program:
    n = next_unit(program)
    if isinstance(value, GridValue):
        grid = value.grid
        policy = form.form if form is not None else GridForm.DENSE
        if form is not None and (form.stamp or form.form is GridForm.SPARSE):
            raise ValueError(f"{form.name} takes no grid of colors")
        if policy is GridForm.MASK and any(c not in (0, 1) for row in grid for c in row):
            raise ValueError(f"{form.name if form else 'GRID'} takes 1 and 0 cells only")
        cell = ((lambda c: GridCell(NumberTerm(1) if c else Wildcard(), False))
                if policy is GridForm.MASK else (lambda c: GridCell(NumberTerm(c), False)))
        call = GridCall(UnitId(n), Scope(()), policy, False, len(grid),
                        len(grid[0]) if grid else 0, relation,
                        tuple(term_of(k) for k in value.keys),
                        tuple(tuple(cell(c) for c in row) for row in grid), None)
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
    inits: list[Instance] = []
    scope: tuple[str, ...] = ()
    for part in relation.instances:
        levels = list(tree.levels(scope))
        init = next((i for texts in levels for p in texts
                     if (i := tree.inits.get(p, {}).get(part)) is not None), None)
        if init is None:
            raise ValueError(f"no instance {part}")
        inits.append(init)
        path = tree.comp(init.component, init.scope.components)
        assert path is not None
        scope = path
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
