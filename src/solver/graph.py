"""The relations of a solver's program at each instance the program runs:
the instance tree, the lib's instances and the instances inside them
included; the units at the instance paths they run at, by the relation each
heads; the resolution of a name a unit reads; the column types of a
relation there; and the walk over them that `solver.dependence` reads."""

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, auto

from engine import Engine, Program, RelationName, Scope, UnitId
from engine.program import (
    AliasType,
    Atom,
    Component,
    Instance,
    RecordType,
    RelationDecl,
    SubtypeType,
    TypeDecl,
    TypeName,
    Unit,
    body_atoms,
    dotted,
    enclosing,
    own,
)
from solver.vocabulary import INPUT


def followed(links: Mapping[str, str], name: str) -> list[str]:
    """`name`, then the type each link names in turn, each once: a type
    name followed through aliases (or subtypes) to the end of its chain,
    or to the first name met again."""
    out = [name]
    while name in links and links[name] not in out:
        name = links[name]
        out.append(name)
    return out


def component_chain(components: Mapping[str, Component], name: str | None
                    ) -> list[str | None]:
    """A component and each component it extends, in turn, a base that
    `components` lacks last; `[None]` for the top level."""
    out: list[str | None] = [name]
    while name is not None:
        c = components.get(name)
        name = None if c is None or c.base in out else c.base
        if name is not None:
            out.append(name)
    return out


def by_innermost[D: (Instance, RelationDecl)](decls: Sequence[D]
                                              ) -> dict[str | None, dict[str, D]]:
    """Declarations by the innermost component that declares them, None
    for the top level, then by name."""
    out: dict[str | None, dict[str, D]] = {}
    for d in decls:
        out.setdefault(d.scope.components[-1] if d.scope.components
                       else None, {})[d.name] = d
    return out


def chain_declared[D: (Instance, RelationDecl)](
        declared: Mapping[str | None, Mapping[str, D]],
        components: Mapping[str, Component], comp: str | None, name: str
) -> D | None:
    """The declaration under `name` of a component, or of the first
    component along its chain (`component_chain`) that declares one, from
    the declarations `by_innermost` gives; None where none does."""
    return next((declared[c][name] for c in component_chain(components, comp)
                 if name in declared.get(c, {})), None)


def chain_relation(program: Program, comp: str, name: str
                   ) -> RelationDecl | None:
    """The relation an instance of `comp` holds under `name`
    (`chain_declared`)."""
    return chain_declared(by_innermost(program.relations),
                          {c.name: c for c in program.components}, comp, name)


MAX_DEPTH = 8
"""How many instances deep an instance path the model follows goes."""


def walked(unit: Unit) -> bool:
    """Whether the walk of `Graph.read` reads a unit: each unit of the
    program but one an operation wrote, which stands on no line."""
    return unit.span is not None


class NodeKind(Enum):
    """What a node of `Graph` stands for."""

    RELATION = auto()
    """A relation of the program at the instance path that declares it,
    the relations of the lib's instances among them."""
    INSTANCE = auto()
    """An instance of a lib component, by its instance path, which stands
    for every relation of the instance where a unit of the solver's own
    text heads one (`Graph.resolve`)."""


type InstancePath = tuple[str, ...]
"""The instances a top-level clause names a relation through, outermost
first: `()` for the top level, `("parse", "box")` for `parse.box`."""


@dataclass(frozen=True)
class Node:
    """A relation as `Graph` follows it (`NodeKind`): its instance path,
    and its name, empty for an instance of a lib component."""

    kind: NodeKind
    path: InstancePath
    name: str

    @property
    def text(self) -> str:
        """The relation as a top-level clause names it, or the instance of
        a lib component by its path."""
        return dotted(self.path) if self.kind is NodeKind.INSTANCE \
            else RelationName(self.path, self.name).text

    def __hash__(self) -> int:
        # Held after the first call: the walk of `Graph.read` keys its
        # tables by node.
        h = self.__dict__.get("_hash")
        if h is None:
            h = hash((self.kind, self.path, self.name))
            object.__setattr__(self, "_hash", h)
        return h


type Placed = tuple[Unit, InstancePath]
"""A unit at an instance path it runs at."""


class Graph:
    """The relations of the solver's program as its units read them at
    each instance (`solver.dependence.dependence`, and the store check's
    relations between `in` and `out` and its stored-already test): the
    units of the program at the instance paths they run at, by the
    relation each heads, and the resolution of a relation a unit reads.
    The instance tree holds the instances of the solver's own components,
    of the lib's components, and those inside the lib's components. A unit
    of the top level runs at `()`; a unit of a component, at each instance
    path of the component or of a component that extends it. A name
    resolves at the unit's path, then at each path around it, outermost
    last, as Souffle resolves a name inside an instance. An instance of a
    component that no included file declares resolves to nothing, a path
    deeper than `MAX_DEPTH` is not followed, a base no file declares ends a
    component's chain, and type arguments pair with type parameters as far
    as both go: each is a fault of `load` (`instance_faults`)."""

    def __init__(self, program: Program, engine: Engine) -> None:
        self.program = program
        self.index = engine.index(program)
        self.components = {c.name: c for c in program.components}
        self.relations = by_innermost(program.relations)
        self.instances = by_innermost(program.instances)
        self.tree: dict[InstancePath, str] = {}
        """Every instance path to its component."""
        self.args: dict[InstancePath, dict[str, str]] = {(): {}}
        """The type arguments in force at each instance path by type
        parameter, each as `type_at` reads it in the scope whose text
        writes it, at the instance path the instance stands in."""
        self._at: dict[str, list[InstancePath]] = {}
        """Each component's instance paths, and those of each component
        that extends it, in the order of the instances."""
        for at, path, inst, comp in self._instance_tree():
            self.tree[path] = comp.name
            self.args[path] = self._chain_args(comp, at, {
                p: self._arg(self.args[at], a, inst.scope.components, at)
                for p, a in zip(comp.type_params, inst.type_args,
                                strict=False)})
            for c in self._chain(comp.name):
                if c is not None:
                    self._at.setdefault(c, []).append(path)
        self.type_decls: dict[str, tuple[TypeDecl, InstancePath | None]] = {}
        """Each type the program declares by each key a reading of a type
        names it by (`key_at`), with the instance path its own text is read
        at (`reading`): the top level for a type the top level declares, the
        path that holds it for a type that takes a key per instance
        (`keyed_per_instance`), under its key there, and none for any other
        type a component declares, under its key (`key_of`). Souffle takes
        one declaration of a name in a scope, so a key has one declaration.
        Raises `ValueError` where a key names two declarations."""
        for t in program.types:
            self.type_decls.setdefault(
                self.key_of(t), (t, None if t.scope.components else ()))
        for t in program.types:
            if self.keyed_per_instance(t):
                for q in self._at.get(t.scope.components[-1], []):
                    key = self.key_at(t, q)
                    held = self.type_decls.get(key)
                    if held is not None and held[0] is not t:
                        raise ValueError(f"the type key `{key}` names two "
                                         f"declarations")
                    self.type_decls[key] = (t, q)
        self.units = [u for u in program.units if own(u.span)]
        self._columns: dict[tuple[InstancePath, RelationName],
                            list[str] | None] = {}
        """`column_types`' results by path and name."""
        self._reach: frozenset[RelationName] | None = None
        self._heading: tuple[dict[Node, list[Placed]],
                             dict[Node, list[Placed]]] | None = None
        self._body: dict[tuple[UnitId, InstancePath], list[tuple[
            Atom, Node, RelationName | None]]] = {}
        self._fed: dict[tuple[UnitId, InstancePath], Node] = {}
        """The node each unit of the solver's own text heads at each path
        it runs at (`resolve`)."""
        self.heads: dict[Node, list[Placed]] = {}
        """The units of the solver's own text that head each node, at the
        paths they run at, as `resolve` gives the node: an instance of a
        lib component stands for every relation of it they head."""
        for u in self.units:
            for at in self.paths_of(u):
                node = self.resolve(at, u.head.relation)
                if node is not None:
                    self.heads.setdefault(node, []).append((u, at))
                    self._fed[(u.id, at)] = node

    def component_at(self, path: InstancePath) -> str | None:
        """The component of the instance at `path`, a path of the instance
        tree; None for the top level."""
        return self.tree[path] if path else None

    def _chain(self, comp: str | None) -> list[str | None]:
        """A component and each component it extends, in turn
        (`component_chain`)."""
        return component_chain(self.components, comp)

    def _instance_tree(self) -> Iterator[tuple[InstancePath, InstancePath,
                                               Instance, Component]]:
        """Each instance path, breadth first from the top level, with the
        path it stands in, its instance and the instance's component. A
        path deeper than `MAX_DEPTH` is not followed, and an instance of a
        component no file declares is left out."""
        comps: dict[InstancePath, str] = {}
        front: list[InstancePath] = [()]
        while front:
            at = front.pop(0)
            if len(at) > MAX_DEPTH:
                continue
            here = comps.get(at) if at else None
            for name in self._instance_names(here):
                inst = self._instance(here, name)
                comp = None if inst is None \
                    else self.components.get(inst.component)
                if inst is None or comp is None:
                    continue
                path = (*at, name)
                comps[path] = comp.name
                yield at, path, inst, comp
                front.append(path)

    def _arg(self, held: Mapping[str, str], arg: TypeName,
             scope: tuple[str, ...], at: InstancePath) -> str:
        """A type argument written in the text of `scope`, read at the
        instance path `at`, where `held` gives the arguments in force by
        type parameter: the argument in force where it names a type
        parameter, else the type it names (`type_at`)."""
        got = arg.argument(held)
        return self.type_at(arg, scope, at) if got is None else got

    def _locate(self, at: InstancePath, instances: tuple[str, ...],
                stop_at_lib: bool
                ) -> tuple[InstancePath, Instance | None] | None:
        """The instance path the qualifiers `instances` of a name lead to
        from `at`, each qualifier resolving at the path around it,
        innermost first; where `stop_at_lib` holds, they stop at the first
        instance of a lib component, which is given. None where a
        qualifier names no instance."""
        for name in instances:
            found = self._innermost(
                at, lambda c: self._instance(c, name) is not None)
            if found is None:
                return None
            at = (*found, name)
            if at not in self.tree:
                return None
            if stop_at_lib and not own(self.components[self.tree[at]].span):
                return at, self._instance(self.component_at(found), name)
        return at, None

    def _declaring(self, path: InstancePath, name: str
                   ) -> InstancePath | None:
        """The innermost path at or around `path` whose component declares
        the relation `name`."""
        return self._innermost(
            path, lambda c: self._relation(c, name) is not None)

    def _innermost(self, path: InstancePath,
                   holds: Callable[[str | None], bool]
                   ) -> InstancePath | None:
        """The innermost path at or around `path` whose component, None
        for the top level, `holds` accepts: where a name read at `path`
        resolves."""
        return next((q for q in enclosing(path)
                     if holds(self.component_at(q))), None)

    def _chain_args(self, comp: Component, at: InstancePath,
                    args: dict[str, str]) -> dict[str, str]:
        """The type arguments of an instance of `comp` that stands in the
        instance path `at` by type parameter, those of each component it
        extends included, each base's read in the scope that declares the
        component that names it, at `at` (`_arg`)."""
        out = dict(args)
        seen = {comp.name}
        while comp.base is not None and comp.base not in seen:
            base = self.components.get(comp.base)
            if base is None:
                break
            out |= {p: self._arg(out, a, comp.scope.components, at)
                    for p, a in zip(base.type_params, comp.base_type_args,
                                    strict=False)}
            comp = base
            seen.add(comp.name)
        return out

    def _instance_names(self, comp: str | None) -> list[str]:
        return [n for c in self._chain(comp)
                for n in self.instances.get(c, {})]

    def _instance(self, comp: str | None, name: str) -> Instance | None:
        return chain_declared(self.instances, self.components, comp, name)

    def _relation(self, comp: str | None, name: str) -> RelationDecl | None:
        return chain_declared(self.relations, self.components, comp, name)

    def paths_of(self, unit: Unit) -> list[InstancePath]:
        """The instance paths a unit runs at, in the order of the
        instances."""
        if not unit.scope.components:
            return [()]
        return self._at.get(unit.scope.components[-1], [])

    def resolve(self, at: InstancePath, rel: RelationName) -> Node | None:
        """The node a unit of the solver's own text at `at` reads or heads
        by the name `rel`, a relation of an instance of a lib component
        read as the instance; None where no declaration gives it."""
        got = self._locate(at, rel.instances, True)
        if got is None:
            return None
        path, lib = got
        if lib is not None:
            return Node(NodeKind.INSTANCE, path, "")
        q = self._declaring(path, rel.name)
        return None if q is None else Node(NodeKind.RELATION, q, rel.name)

    def node(self, at: InstancePath, rel: RelationName) -> Node | None:
        """The relation a unit at `at` reads or heads by the name `rel`
        (`place`), as a node; None where no declaration gives it."""
        q = self.place(at, rel)
        return None if q is None \
            else Node(NodeKind.RELATION, q.instances, q.name)

    def decl(self, at: InstancePath, rel: RelationName
             ) -> tuple[RelationDecl, Mapping[str, str]] | None:
        """The declaration of the relation a unit at `at` names by `rel`
        (`place`), with the type arguments in force there by type
        parameter; None where it is no declaration the solver can read."""
        q = self.place(at, rel)
        if q is None:
            return None
        d = self._relation(self.component_at(q.instances), q.name)
        return None if d is None else (d, self.args[q.instances])

    def column_types(self, at: InstancePath, rel: RelationName
                     ) -> list[str] | None:
        """The type of each column of the relation a unit at `at` names by
        `rel`, read in the scope that declares the relation at the instance
        path that declares it (`place`, `type_at`); None where it is no
        declaration the solver can read. Computed once per path and
        name."""
        key = (at, rel)
        if key not in self._columns:
            q = self.place(at, rel)
            d = None if q is None \
                else self._relation(self.component_at(q.instances), q.name)
            self._columns[key] = None if q is None or d is None else [
                self.type_at(c.type, d.scope.components, q.instances)
                for c in d.columns]
        return self._columns[key]

    def key_of(self, t: TypeDecl) -> str:
        """A type declaration's key: for a type of the solver's own text,
        the components of the scope that declares it and its name joined
        by dots, so that two components that declare one name name two
        types; for a lib type, its name."""
        return dotted((*t.scope.components, t.name)) if own(t.span) \
            else t.name

    def resolve_type(self, name: TypeName, scope: tuple[str, ...]) -> str:
        """The type `name` denotes when read in `scope` at no instance
        (`reading`): a type parameter reads as its own name, and a type a
        component declares by its key (`key_of`)."""
        return self.reading(name, scope, None)

    def type_at(self, name: TypeName, scope: tuple[str, ...], at: InstancePath
                ) -> str:
        """The type `name` denotes when read in the text of `scope` at
        the instance path `at`, a path that text runs at (`reading`): a
        type parameter reads as the argument in force at `at` (`args`), and
        a type a component declares is read at the instance path that holds
        it (`holder`). The one reading of a type that a comparison of types
        reads."""
        return self.reading(name, scope, at)

    def reading(self, name: TypeName, scope: tuple[str, ...],
                at: InstancePath | None) -> str:
        """The type `name` denotes when read in the text of `scope`, at
        the instance path `at` where it is not None, then each alias
        followed to the type it names, its target read in the scope that
        declares the alias, at the path that holds it, to the end of the
        chain or to the last alias before one met again. Every type the
        model reads, a component's record among them, resolves through the
        engine's index of the program in the scope that reads it
        (`Index.type_decl`), never by its bare name; a name that denotes no
        declaration and no type argument in force, as a primitive type
        does, reads as its text. The type is named by its key at the path
        that holds it (`key_at`)."""
        last: str | None = None
        seen: set[tuple[str, InstancePath | None]] = set()
        while True:
            t = self.index.type_decl(name, Scope(scope))
            if t is None:
                got = None if at is None else name.argument(self.args[at])
                return name.text if got is None else got
            path = None if at is None else self.holder(t, name, at)
            if not isinstance(t, AliasType):
                return self.key_at(t, path)
            mark = (self.key_of(t), path)
            if mark in seen and last is not None:
                return last
            seen.add(mark)
            last = self.key_of(t)
            name, scope, at = t.target, t.scope.components, path

    def key_at(self, t: TypeDecl, path: InstancePath | None) -> str:
        """The key of the type declaration `t` read at the instance path
        `path` that holds it, or at no instance where `path` is None
        (`reading`): its key (`key_of`), but for a type that takes a key per
        instance (`keyed_per_instance`), read at an instance path, the path
        and its name joined by dots, as Souffle names it at that
        instance."""
        if path is not None and self.keyed_per_instance(t):
            return dotted((*path, t.name))
        return self.key_of(t)

    @staticmethod
    def keyed_per_instance(t: TypeDecl) -> bool:
        """Whether `t` is a record type of the solver's own text that a
        component declares. Its fields read through the type arguments of
        the instance that holds it, so it takes one key per instance."""
        return bool(t.scope.components) and own(t.span) \
            and isinstance(t, RecordType)

    def holder(self, t: TypeDecl, name: TypeName, at: InstancePath
               ) -> InstancePath:
        """The instance path that holds the type declaration `t`, which
        `name` denotes when read at `at`: the top level for a type the top
        level declares; else the innermost path at or around `at`, or
        around the instance path the qualifiers of `name` lead to from
        `at`, whose component, or a component it extends, declares it.
        Raises `ValueError` where no path of the instance tree does."""
        if not t.scope.components:
            return ()
        if name.instances:
            got = self._locate(at, name.instances, False)
            if got is None:
                raise ValueError(f"`{name.text}` names no instance at "
                                 f"`{dotted(at)}`")
            at = got[0]
        comp = t.scope.components[-1]
        found = self._innermost(at, lambda c: comp in self._chain(c))
        if found is None:
            raise ValueError(f"no instance at or around `{dotted(at)}` "
                             f"holds `{name.text}`")
        return found


    def link(self, t: AliasType | SubtypeType) -> str:
        """The type key an alias's target or a subtype's base names, read
        in the scope that declares the alias or subtype (`scoped_key`)."""
        target = t.target if isinstance(t, AliasType) else t.base
        return self.scoped_key(target, t.scope.components)

    def scoped_key(self, name: TypeName, scope: tuple[str, ...]) -> str:
        """The key (`key_of`) of the type declaration `name` denotes when
        read in the text of `scope` (`Index.type_decl`); the name's text
        where it denotes none, as for a primitive type or a component's
        type parameter."""
        t = self.index.type_decl(name, Scope(scope))
        return name.text if t is None else self.key_of(t)

    def heading(self, node: Node) -> list[Placed]:
        """The units that head the relation of a node `node` gives, each
        at the instance path it runs at: the units of the solver's own text
        and of the lib alike, and the units an operation wrote."""
        return self._headings()[0].get(node, [])

    def read_heads(self, node: Node) -> list[Placed]:
        """The units of `heading` that the walk of `read` reads: all but
        those an operation wrote."""
        return self._headings()[1].get(node, [])

    def _headings(self) -> tuple[dict[Node, list[Placed]],
                                 dict[Node, list[Placed]]]:
        """`heading` and `read_heads` for every node, computed once."""
        if self._heading is None:
            every: dict[Node, list[Placed]] = {}
            read: dict[Node, list[Placed]] = {}
            for u in self.program.units:
                for at in self.paths_of(u):
                    n = self.node(at, u.head.relation)
                    if n is None:
                        continue
                    every.setdefault(n, []).append((u, at))
                    if walked(u):
                        read.setdefault(n, []).append((u, at))
            self._heading = (every, read)
        return self._heading

    def body(self, placed: Placed
             ) -> list[tuple[Atom, Node, RelationName | None]]:
        """Each atom a unit's body reads (`body_atoms`), in order, with the
        relation it reads at the path the unit runs at (`node`), and, for a
        unit of the solver's own text, the name a top-level clause reads
        that relation by (`resolve`, `top_name`); an atom that no
        declaration gives is left out."""
        unit, at = placed
        key = (unit.id, at)
        got = self._body.get(key)
        if got is None:
            got = self._body[key] = []
            for atom, _negated in body_atoms(unit.body or ()):
                n = self.node(at, atom.relation)
                if n is None:
                    continue
                read = self.resolve(at, atom.relation) if own(unit.span) \
                    else None
                got.append((atom, n, None if read is None
                            else self.top_name(read, atom.relation.name)))
        return got

    def read[D](self, root: Node, admits: Callable[[Placed, D], bool],
                start: D, demand: Callable[[Placed, Atom, D], D],
                unlisted: Callable[[Placed], bool] | None = None
                ) -> tuple[list[UnitId], list[Node], set[RelationName],
                           list[tuple[UnitId, Node]]]:
        """What one base's derivation of the relation `root` depends on
        (`solver.dependence`): the units, the relations as
        nodes, and the relations a unit of the solver's own text reads or
        heads by the names a top-level clause reads them by. The walk reads
        every unit of the program but those an operation wrote, the lib's
        among them, each at the instance paths it runs at. A read asks for
        rows of what it demands, `start` at `root`: `demand` gives what a
        unit's read of an atom asks for, from what the unit was reached
        for, and `admits` tells the placed units whose head can hold such a
        row. Last, each admitted unit that `unlisted` names, with the node
        it feeds as `resolve` gives it: the relation as a top-level clause
        names it, or an instance of a lib component by its path."""
        units: dict[UnitId, None] = {}
        placed: set[tuple[UnitId, InstancePath, int]] = set()
        nodes: dict[Node, None] = {}
        names: set[RelationName] = set()
        front: list[tuple[Unit, InstancePath, D]] = []
        asked: set[tuple[Node, int]] = set()
        stranded: dict[tuple[UnitId, Node], None] = {}
        # What a read asks for is keyed by identity: `demand` gives one
        # object per distinct result of a read, and the values are
        # records whose hash walks every field.

        def reach(node: Node, wanted: D) -> None:
            if (node, id(wanted)) in asked:
                return
            asked.add((node, id(wanted)))
            nodes[node] = None
            for u, at in self.read_heads(node):
                if (u.id, at, id(wanted)) not in placed:
                    if not admits((u, at), wanted):
                        continue
                    placed.add((u.id, at, id(wanted)))
                    units[u.id] = None
                    front.append((u, at, wanted))
                    fed = self._fed.get((u.id, at))
                    if fed is not None:
                        names.add(self.top_name(fed, u.head.relation.name))
                if unlisted is not None and unlisted((u, at)):
                    stranded[(u.id, self._fed[(u.id, at)])] = None

        reach(root, start)
        while front:
            u, at, wanted = front.pop()
            for atom, node, name in self.body((u, at)):
                reach(node, demand((u, at), atom, wanted))
                if name is not None:
                    names.add(name)
        return list(units), list(nodes), names, list(stranded)

    def placed(self) -> list[Placed]:
        """Every unit of the solver's own text at each instance path it
        runs at."""
        return [(u, at) for u in self.units for at in self.paths_of(u)]

    def reading_input(self) -> frozenset[RelationName]:
        """The relations whose rows depend on `in` by dataflow
        (`depending`)."""
        if self._reach is None:
            self._reach = self.depending(RelationName((), INPUT.name),
                                         lambda _atom: True)
        return self._reach

    def depending(self, start: RelationName, counts: Callable[[Atom], bool]
                  ) -> frozenset[RelationName]:
        """The relations whose rows depend on the relation at `start` by
        dataflow, `start` among them, each by its instance path and its
        name: a relation read by a unit that reads `start` by an atom
        `counts` admits, or that reads such a relation, at the instance
        path the unit runs at. The units of the lib's components count as
        the solver's own do, so each relation of a lib instance stands on
        its own: a relation of it that its units feed from constants or
        from stored parameters alone does not depend on `start` although
        another relation of the instance does. A relation stands at the
        innermost path around the reading unit's whose component declares
        it."""
        readers: dict[RelationName, list[tuple[Unit, InstancePath]]] = {}
        for u in self.program.units:
            for at in self.paths_of(u):
                for atom, _negated in body_atoms(u.body or ()):
                    got = self.place(at, atom.relation)
                    if got is not None and counts(atom):
                        readers.setdefault(got, []).append((u, at))
        seen = {start}
        work = [start]
        while work:
            for u, at in readers.get(work.pop(), ()):
                head = self.place(at, u.head.relation)
                if head is not None and head not in seen:
                    seen.add(head)
                    work.append(head)
        return frozenset(seen)

    def reads_input(self, rel: RelationName) -> bool:
        """Whether the relation a top-level clause names by `rel` depends
        on `in` (`reading_input`)."""
        got = self.place((), rel)
        return got is not None and got in self.reading_input()

    def extends(self, comp: str, base: str) -> bool:
        """Whether `comp` is `base` or extends it."""
        return base in self._chain(comp)

    def relation_decl(self, node: Node) -> RelationDecl | None:
        """The declaration of a relation node; None for an instance of a
        lib component, whose relations the node stands for together."""
        if node.kind is not NodeKind.RELATION:
            return None
        return self._relation(self.component_at(node.path), node.name)

    def place(self, at: InstancePath, rel: RelationName
              ) -> RelationName | None:
        """The relation a unit at `at` names by `rel`, by the instance
        path that declares it in the instance tree and its name; None
        where no declaration gives it."""
        got = self._locate(at, rel.instances, False)
        if got is None:
            return None
        q = self._declaring(got[0], rel.name)
        return None if q is None else RelationName(q, rel.name)

    def feeding(self, place: RelationName
                ) -> list[tuple[Unit, InstancePath]]:
        """The clauses that put rows into the relation at `place`
        (`place`), each at the instance path it runs at: the units of the
        solver's own text and of the lib alike (`heading`), a subsumptive
        clause left out, as it puts no row in."""
        return [p for p in self.heading(
                    Node(NodeKind.RELATION, place.instances, place.name))
                if not p[0].subsumptive]

    def top_name(self, node: Node, name: str) -> RelationName:
        """The name a top-level clause reads a node's relation by, where
        a unit read it by `name`."""
        return RelationName(node.path, node.name
                            if node.kind is NodeKind.RELATION else name)
