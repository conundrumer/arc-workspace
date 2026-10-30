"""The Souffle text that derives the rows of the relations the converter adds.

The lib rewrite (`libmap.rewrite`) gives some relations of the converted
program that the solver's program holds no relation of: each relation of an
instance it hoists or expands, and each relation of an expansion's shape that
holds no relation of the solver, such as `<read>_full`; and the frame-read
plan (`frame_reads.FieldPlan`) gives the Frame and Tiling instances of a
parameter table. `parity_text` gives the clauses that the rewrite writes for
them, in its ground form (`Converter.ground_prog`), and those of the plan
(`Converter.plan_units`), as a text to add to the solver's program, so that a
Souffle run derives the rows of each such relation from the solver's own:

- A relation, an instance or a type of the rewrite's program is held where the
  solver declares the same in the same scope (`Converter.source`), and, for
  an instance, its component declares each relation the rewrite's clauses name
  through it. A clause of the text reads a held relation as the solver declares
  it.
- The text holds, under a fresh name (`PREFIX` and the name), each relation,
  instance and type of a component of the solver that is not held and that a
  root, an arclog relation without a Souffle relation, or a clause of the text,
  reads or heads, with the clauses that head it. So does it for each such
  relation and instance of the top level.
- An instance stands in the component of the lib that declares each relation
  the clauses name through it, or else in the form of its component, `Sig`
  and its name, from `lib-forms.dl` (`forms`), or in the lib component
  `libmap.COMP` renames to its name. A clause reads a relation of the
  signature that the lib holds no relation of, such as `gap`, under the form
  of `lib-forms.dl` that `RELATION_PREFIX` leads (`top_forms`).
- The relations, instances and types of the text stand at the top level. A
  node of a component of the solver (`Parse`, `Params`, `Determine`) stands
  there too, and a clause of it reads each relation or instance of its
  component through the instance of that component in the program the text
  joins (a `Home`): the instance that a `.init` of the solver at the top level
  gives, such as `parse` and `params`, and each held instance inside a
  component, such as the `parse` of `Determine`. A type parameter of the
  component is the argument of its instance.
- The determination runs the component `Determine` over the task's examples,
  in a program that the cases do not run (`ParityText.determination`). A
  root that stands in `Determine`, or in a component that `Determine`
  instantiates, has its place in that text, which also declares the instance
  of `Determine` where the solver has none (`DETERMINE_INSTANCE`); the other
  roots have theirs in `ParityText.text`.
- A root has no place where no instance of the program holds the component it
  stands in, where a clause of it reads an instance of no component of the text
  or a relation that the text's program does not declare (a relation of the
  signature that `FORMS` gives no form of), or where it needs a type that is an
  `ADT` of a component or a relation that a pick chooses: a `CHOOSE` relation,
  which no clause of the rewrite's ground program heads, or a relation whose
  clauses end in `ONE` marks. A root that is such a relation needs it itself.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, fields, is_dataclass, replace
from enum import StrEnum
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from engine.program import (
    AdtType,
    Atom,
    Instance,
    RelationDecl,
    RelationName,
    Scope,
    TypeDecl,
    TypeName,
    Unit,
    body_atoms,
)
from souffle import printer
from souffle.parser import parse
from solver.vocabulary import DETERMINE
from arclog_convert import libmap, paths
from arclog_convert.libmap.box import mapped
from arclog_convert.libmap.instances import LIB_PATH

if TYPE_CHECKING:
    from arclog_convert.leaves import Converter

FORMS = Path(__file__).with_name("lib-forms.dl")
"""The components of the signature that the lib holds no form of."""
FORM_PREFIX = "Sig"
"""What leads the name of a component of `FORMS`."""
RELATION_PREFIX = "sig_"
"""What leads the name of a relation of `FORMS` at the top level."""
PREFIX = "parity_"
"""What leads the name of each relation, instance and type of the text."""
DETERMINE_INSTANCE = "determine"
"""The name of the instance of `Determine` that a run adds where the solver has none
(`solver.determine.run_program`), and that the determination's text declares."""

NESTED_COMPONENT = "ParityNested"
"""The component of the text that holds each instance of the text that belongs to
a home inside a home (`_Lift.nested`)."""
NESTED_INSTANCE = "parity_nested"
"""The instance of `NESTED_COMPONENT`."""

type InstancePath = tuple[str, ...]
"""The instances from the top level of the program the text joins."""


class Kind(StrEnum):
    RELATION = "relation"
    INSTANCE = "instance"
    TYPE = "type"


@dataclass(frozen=True)
class Node:
    """A relation, an instance or a type of the program, by the scope it is
    declared in and its name there."""

    kind: Kind
    name: str
    scope: tuple[str, ...] = ()


@dataclass(frozen=True)
class At:
    """A node as the text's program holds it: the instances that lead to the
    component it stands in, none for the top level."""

    node: Node
    path: InstancePath = ()


@dataclass(frozen=True)
class Home:
    """The instance of a component of the solver that the text's program
    holds, where the nodes of that component stand."""

    scope: tuple[str, ...]
    path: InstancePath
    args: tuple[tuple[str, TypeName], ...]
    """The argument of each type parameter of the component, as the instance
    that holds the home writes it, in the home at `parent`."""
    parent: InstancePath
    determined: bool
    """The home stands in the instance of `Determine` or below it."""


@dataclass(frozen=True)
class Place:
    """Where the rows of an arclog relation stand in the text: `path` from the
    top level of the text's program, and the relation the converter holds for
    it, `relation` in `scope`, as `Converter.resolve` takes them, with its
    number of columns in the text."""

    path: str
    scope: tuple[str, ...]
    relation: RelationName
    width: int
    determined: bool
    """The place stands in `ParityText.determination`, not in `ParityText.text`."""


@dataclass(frozen=True)
class ParityText:
    """The text, and the place of each arclog relation whose rows it derives."""

    text: str
    places: Mapping[str, Place]
    determination: str = ""
    """The text that the determination run adds to the solver's program, with the places
    that are `determined`; empty where no place is."""


@cache
def _forms_program():
    """`FORMS` parsed after the lib."""
    prog = parse(f'#include "lib.dl"\n#line 1\n{FORMS.read_text()}', paths.ROOT / "programs")
    assert hasattr(prog, "components"), prog
    return prog


@cache
def forms() -> dict[str, dict[str, int]]:
    """The public relations of each component of `FORMS`, with the number of
    columns of each; a relation a base declares is the component's."""
    prog = _forms_program()
    own = {c.name: c for c in prog.components if c.span is not None and c.span.file is None}

    def public(name: str) -> dict[str, int]:
        c = own[name]
        base = public(c.base) if c.base else {}
        return base | {r.name: len(r.columns) for r in prog.relations
                       if r.scope.components == (name,) and not r.name.startswith("_")}
    return {name: public(name) for name in own}


@cache
def top_forms() -> frozenset[str]:
    """The name, with no `RELATION_PREFIX`, of each relation of `FORMS` at the top level."""
    return frozenset(r.name.removeprefix(RELATION_PREFIX) for r in _forms_program().relations
                     if r.span is not None and r.span.file is None and not r.scope.components)


def _types_in(x: Any) -> Iterator[TypeName]:
    """Each type name inside `x`, a declaration, a unit or a tuple of them."""
    if isinstance(x, TypeName):
        yield x
    elif isinstance(x, tuple):
        for y in x:
            yield from _types_in(y)
    elif is_dataclass(x) and not isinstance(x, type):
        for f in fields(x):
            yield from _types_in(getattr(x, f.name))


def _retyped(x: Any, to: Callable[[TypeName], TypeName]) -> Any:
    """`x` with each type name inside it replaced by `to` of it."""
    if isinstance(x, TypeName):
        return to(x)
    if isinstance(x, tuple):
        return tuple(_retyped(y, to) for y in x)
    if is_dataclass(x) and not isinstance(x, type):
        return replace(x, **{f.name: _retyped(getattr(x, f.name), to) for f in fields(x)})
    return x


@dataclass(frozen=True)
class Index:
    """A program's own parts."""

    decls: dict[Node, RelationDecl | Instance | TypeDecl]
    """The relations, the instances and the types, in program order."""
    units: dict[Node, list[Unit]]
    """The units that head each relation or instance, in program order."""
    accessed: dict[Node, set[str]]
    """The relations of each instance that a unit names through it."""

    @staticmethod
    def of(prog) -> "Index":
        def own(x) -> bool:
            return x.span is None or x.span.file is None
        index = Index({}, {}, {})
        for kind, decls in ((Kind.RELATION, prog.relations), (Kind.INSTANCE, prog.instances), (Kind.TYPE, prog.types)):
            for d in decls:
                if own(d):
                    index.decls[Node(kind, d.name, d.scope.components)] = d
        for u in prog.units:
            if not own(u):
                continue
            head = u.head.relation
            scope = u.scope.components
            node = index.find(Kind.INSTANCE, scope, head.instances[0]) if head.instances \
                else index.find(Kind.RELATION, scope, head.name)
            if node is not None:
                index.units.setdefault(node, []).append(u)
            for a in [u.head, *(a for a, _ in body_atoms(u.body or ()))]:
                if (inst := index.instance_of(scope, a.relation.instances)) is not None:
                    index.accessed.setdefault(inst, set()).add(a.relation.name)
        return index

    def find(self, kind: Kind, scope: tuple[str, ...], name: str, outer: bool = True) -> Node | None:
        """The node `name` that a unit of `scope` reads: the scope's own, else the top level's."""
        for s in dict.fromkeys((scope, ()) if outer else (scope,)):
            if (node := Node(kind, name, s)) in self.decls:
                return node
        return None

    def instance_of(self, scope: tuple[str, ...], chain: tuple[str, ...]) -> Node | None:
        """The last instance of `chain`, read in a unit of `scope`, each after
        the first inside the component of the one before; None for no instance."""
        node = None
        for i, name in enumerate(chain):
            node = self.find(Kind.INSTANCE, scope, name, outer=i == 0)
            if node is None:
                return None
            scope = (self.decls[node].component,)
        return node


def _present(c: Converter, comp: str) -> frozenset[str] | None:
    """The relations `comp` declares in `programs/lib.dl`; None for a
    component that file does not hold."""
    if comp not in c.lib.comps or c.lib.comps[comp] is c.sig.comps.get(comp):
        return None
    return frozenset(r.name for r in c.lib.present(comp)[1]) - c.lib.extension.get(comp, set())


def _component(c: Converter, comp: str, accessed: set[str]) -> str | None:
    """The component of the text for an instance of `comp` whose clauses name
    the relations `accessed`: the lib's, or the form of `comp`, or the lib
    component `libmap.COMP` renames to `comp`; None where none declares each."""
    forms_of = forms()
    renamed = next((was for was, r in libmap.COMP.items() if r.name == comp), None)
    for name in (comp, f"{FORM_PREFIX}{comp}", renamed):
        if name is None:
            continue
        declared = forms_of[name].keys() if name in forms_of else _present(c, name)
        if declared is not None and accessed <= declared:
            return name
    return None


def _width(c: Converter, comp: str, relation: str) -> int:
    """The number of columns of `relation` in the component `comp` of the text."""
    if comp in forms():
        return forms()[comp][relation]
    return len(next(r for r in c.lib.present(comp)[1] if r.name == relation).cols)


@dataclass(frozen=True)
class Root:
    """What an arclog relation stands for in the rewrite's program: the
    relation, or the instance and the `relation` of it, at `at`, by the name
    `key` (scope and name) that the converter gives it."""

    at: At
    relation: str | None
    key: tuple[tuple[str, ...], str]


class _Lift:
    """The rewrite's program and the solver's, with the homes of the components
    of the solver in the program the text joins: the reading, the naming and the
    writing of the nodes the text holds."""

    def __init__(self, c: Converter) -> None:
        program = replace(c.ground_prog, instances=(*c.ground_prog.instances, *c.plan_instances.values()),
                          units=(*c.ground_prog.units, *c.plan_units))
        self.c = c
        self.ground, self.solver = Index.of(program), Index.of(c.source)
        self.order = {node: i for i, node in enumerate(self.ground.decls)}
        self.comps = {k.name: k for k in c.source.components}
        self.homes, self.declares_determine = self._homes()
        self.taken = {n.name for n in (*self.solver.decls, *self.ground.decls) if not n.scope} \
            | {*c.lib.top, *c.sig.top, NESTED_COMPONENT, NESTED_INSTANCE}
        """The names of the top level that a fresh name does not take."""
        self.fresh: dict[At, str] = {}
        self.aliases: dict[TypeName, str] = {}
        self._component_of: dict[Node, str | None] = {}

    def _homes(self) -> tuple[dict[InstancePath, Home], bool]:
        """The home of each instance of a component of the solver that the
        solver's program holds, with the instance that the determination's
        text declares (`DETERMINE_INSTANCE`) where the solver instantiates
        `Determine` nowhere, and whether it does."""
        homes = {(): Home((), (), (), (), False)}
        queue: list[InstancePath] = [()]
        added = False
        while queue:
            at = queue.pop(0)
            home = homes[at]
            for node, decl in self.solver.decls.items():
                if node.kind is Kind.INSTANCE and node.scope == home.scope and decl.component in self.comps:
                    path = (*at, node.name)
                    homes[path] = Home((decl.component,), path, tuple(zip(self.comps[decl.component].type_params,
                                                                          decl.type_args)),
                                       at, home.determined or decl.component == DETERMINE)
                    queue.append(path)
            if not queue and not added and DETERMINE in self.comps \
                    and not any(h.scope == (DETERMINE,) for h in homes.values()):
                added = True
                path = (DETERMINE_INSTANCE,)
                homes[path] = Home((DETERMINE,), path, (), (), True)
                queue.append(path)
        return homes, added

    def home_of(self, scope: tuple[str, ...]) -> Home | None:
        """The one home of the component `scope`, in a run that the scope belongs to; None where there are several or none."""
        found = [h for h in self.homes.values() if h.scope == scope and (h.determined == (scope == (DETERMINE,)))]
        return found[0] if len(found) == 1 else None

    # ---- reading

    def held(self, at: At) -> bool:
        """The solver declares the same node in the same scope; for an instance, its component declares each relation named through it."""
        node = at.node
        ours, theirs = self.ground.decls[node], self.solver.decls.get(node)
        if theirs is None or printer.declaration(ours) != printer.declaration(theirs):
            return False
        if node.kind is not Kind.INSTANCE:
            return True
        present = _present(self.c, ours.component)
        return present is None or self.ground.accessed.get(node, set()) <= present

    def reached(self, name: RelationName, scope: tuple[str, ...], path: InstancePath) -> tuple[At, tuple[str, ...]] | None:
        """The node that `name` names, read in a unit of `scope` whose component stands at `path`, and the instances
        it names inside that node; None for a relation of the lib. A name that ends at a held instance of a
        component of the solver reaches the relation `name.name` of that component where the rewrite's program
        declares it, so a relation the rewrite adds there is a node the text does not hold."""
        if not name.instances:
            node = self.ground.find(Kind.RELATION, scope, name.name)
            return None if node is None else (At(node, path if node.scope == scope else ()), ())
        first, *rest = name.instances
        node = self.ground.find(Kind.INSTANCE, scope, first)
        if node is None:
            return None
        at = At(node, path if node.scope == scope else ())
        while rest and self.held(at) and self.ground.decls[at.node].component in self.comps:
            inside = self.ground.find(Kind.INSTANCE, (self.ground.decls[at.node].component,), rest[0], outer=False)
            if inside is None:
                return None
            at, rest = At(inside, (*at.path, at.node.name)), rest[1:]
        if not rest and self.held(at) and (component := self.ground.decls[at.node].component) in self.comps:
            relation = Node(Kind.RELATION, name.name, (component,))
            if relation in self.ground.decls:
                return At(relation, (*at.path, at.node.name)), ()
        return at, tuple(rest)

    def type_at(self, t: TypeName, path: InstancePath) -> At | None:
        """The type of a component of the solver that `t` names, read in the
        component at `path`; None for a type of the top level or a primitive."""
        home = self.homes.get(path)
        if home is None or t.instances or home.scope == ():
            return None
        node = Node(Kind.TYPE, t.name, home.scope)
        return At(node, path) if node in self.ground.decls else None

    def component(self, at: At) -> str | None:
        """The component of the text for the instance `at`; None where none declares each relation named through it."""
        if at.node not in self._component_of:
            self._component_of[at.node] = _component(self.c, self.ground.decls[at.node].component,
                                                     self.ground.accessed.get(at.node, set()))
        return self._component_of[at.node]

    def reads(self, at: At) -> list[At] | None:
        """Each node that the declaration of `at` and the clauses that head it
        read, other than those of the lib; None where a clause reads what the text's program does not declare."""
        out: list[At] = [got for t in _types_in(self.ground.decls[at.node])
                         if (got := self.type_at(t, at.path)) is not None]
        for u in self.ground.units.get(at.node, []):
            out += [got for t in _types_in(u) if (got := self.type_at(t, at.path)) is not None]
            for a, _ in body_atoms(u.body or ()):
                if (hit := self.reached(a.relation, u.scope.components, at.path)) is not None:
                    out.append(hit[0])
                elif not self.declared(a.relation):
                    return None
        return out

    def declared(self, name: RelationName) -> bool:
        """The text's program declares the relation `name` of the lib, at the top level or in the forms of `FORMS`."""
        return name.instances in ((), (LIB_PATH,)) and (name.name in self.c.lib.top or name.name in top_forms())

    def chosen(self, node: Node) -> bool:
        """The node is a relation that a pick chooses: no clause of the ground program heads it (a `CHOOSE`), or the converter folds its `ONE` marks into its clauses."""
        return node.kind is Kind.RELATION and (not self.ground.units.get(node)
                                               or (node.scope, node.name) in self.c.one_marks)

    def closure(self, root: At) -> set[At] | None:
        """Each node the root needs that the solver does not hold; None where one has no place in the text."""
        seen: set[At] = set()
        todo = [root]
        while todo:
            at = todo.pop()
            if at in seen or self.held(at):
                continue
            decl = self.ground.decls[at.node]
            if at.node.kind is Kind.INSTANCE and self.component(at) is None or isinstance(decl, AdtType) \
                    or self.chosen(at.node):
                return None
            seen.add(at)
            if (got := self.reads(at)) is None:
                return None
            todo += got
        return seen

    # ---- locating

    def locate(self, renamed: Callable[[str], str], roots: set[str]) -> dict[str, Root]:
        """The relation, or the relation of an instance, of the rewrite's
        program that each of `roots` is the arclog name of, by the names
        `Converter.names` gives; a root with none is left out."""
        c = self.c
        out: dict[str, Root] = {}
        for key, base in c.names.items():
            at = self.site(key)
            if at is None:
                continue
            decl = self.ground.decls[at.node]
            if at.node.kind is Kind.RELATION:
                out[renamed(f"&{base}")] = Root(at, None, key)
            elif decl.component in c.lib.comps:
                for r in c.lib.relations(decl.component)[1]:
                    out[renamed(f"&{base}.{r.name}")] = Root(at, r.name, key)
        return {arc: root for arc, root in out.items() if arc in roots}

    def site(self, key: tuple[tuple[str, ...], str]) -> At | None:
        """The relation or instance of the rewrite's program that the name `key` of `Converter.names` stands for, as the text's program holds it."""
        scope, name = key
        c = self.c
        if key in c.det_copy_via:   # a copy of a node of the parse, which the instance of the parse in the copy's scope holds
            home = self.home_of(scope)
            scope, name = c.det_copies[key][0], c.det_copies[key][1]
            path = None if home is None else (*home.path, c.det_copy_via[key])
        else:
            home = self.home_of(scope)
            path = None if home is None else home.path
        if path is None or path not in self.homes or self.homes[path].scope != scope:
            return None
        for kind in (Kind.RELATION, Kind.INSTANCE):
            if (node := Node(kind, name, scope)) in self.ground.decls:
                return At(node, path)
        return None

    # ---- writing

    @staticmethod
    def nested(at: At) -> bool:
        """Whether the instance `at` stands in `NESTED_COMPONENT`: it belongs to a home two
        instances inside the top level or deeper. A type argument of an instance names a type
        through the instances of that home, and `solver.graph.Graph` reads the type
        arguments of the instances of each level in turn, so the instance stands one level
        in, where the home's instances are known."""
        return at.node.kind is Kind.INSTANCE and len(at.path) >= 2

    def prefix(self, at: At) -> tuple[str, ...]:
        """The instances that lead from the top level of the text to `at`, when it is lifted."""
        return (NESTED_INSTANCE,) if self.nested(at) else ()

    def fresh_name(self, name: str) -> str:
        """A name of the top level that is not taken, led by `PREFIX`."""
        cand = PREFIX + name
        while cand in self.taken:
            cand += "_"
        self.taken.add(cand)
        return cand

    def name_all(self, included: Iterable[At]) -> None:
        """Give each node of `included` a fresh name, in the order of the program."""
        for at in sorted(included, key=lambda at: (at.path, self.order[at.node])):
            if at not in self.fresh:
                self.fresh[at] = self.fresh_name(at.node.name)

    def argument(self, t: TypeName) -> tuple[TypeName, str | None]:
        """The type argument of an instance for the type `t` as the text reads it: `t`, or, where
        it names a type through an instance, which a type argument cannot, an alias of
        it, with the declaration of that alias."""
        if not t.instances:
            return t, None
        if t not in self.aliases:
            self.aliases[t] = self.fresh_name(t.name)
        return TypeName((), self.aliases[t]), f".type {self.aliases[t]} = {t.text}"

    def retype(self, x: Any, path: InstancePath) -> Any:
        """`x`, a declaration or a unit that stands in the component at `path`, with each type
        name written as the top level of the text reads it."""
        home = self.homes[path]
        args = dict(home.args)

        def to(t: TypeName) -> TypeName:
            if t.instances:
                return TypeName((*path, *t.instances), t.name)
            if t.name in args:
                return self.retype(args[t.name], home.parent)
            if (at := self.type_at(t, path)) is not None:
                return TypeName(path, t.name) if self.held(at) else TypeName((), self.fresh[at])
            return t
        return _retyped(x, to)

    def rename(self, atom: Atom, scope: tuple[str, ...], path: InstancePath) -> Atom:
        """`atom`, read in a unit of `scope` whose component stands at `path`,
        as the top level of the text reads it."""
        r = atom.relation
        if r.instances == (LIB_PATH,):
            return replace(atom, relation=RelationName((), RELATION_PREFIX + r.name if r.name in top_forms() else r.name))
        got = self.reached(r, scope, path)
        if got is None:
            if not r.instances and r.name in top_forms():
                return replace(atom, relation=RelationName((), RELATION_PREFIX + r.name))
            return atom
        at, rest = got
        if at.node.kind is Kind.RELATION:
            to = RelationName(at.path, r.name) if self.held(at) else RelationName((), self.fresh[at])
        else:
            to = RelationName((*at.path, at.node.name, *rest), r.name) if self.held(at) \
                else RelationName((*self.prefix(at), self.fresh[at], *rest), r.name)
        return replace(atom, relation=to)

    def lines(self, included: Iterable[At]) -> list[str]:
        """The declarations of `included` and the clauses that head each, in the order of the program,
        with the instances that stand in `NESTED_COMPONENT` last."""
        out: list[str] = []
        nested: list[str] = []
        for at in sorted(included, key=lambda at: (at.path, self.order[at.node])):
            decl = replace(self.retype(self.ground.decls[at.node], at.path), name=self.fresh[at], scope=Scope(()))
            if at.node.kind is Kind.INSTANCE:
                args = [self.argument(t) for t in decl.type_args]
                out += [line for _, line in args if line is not None and line not in out]
                decl = replace(decl, component=self.component(at), type_args=tuple(t for t, _ in args))
            (nested if self.nested(at) else out).append(printer.declaration(decl))
            out += [printer.unit(mapped(self.retype(u, at.path), lambda a, u=u, at=at: self.rename(a, u.scope.components, at.path)))
                    for u in self.ground.units.get(at.node, [])]
        if nested:
            out += [f".comp {NESTED_COMPONENT} {{", *nested, "}", f".init {NESTED_INSTANCE} = {NESTED_COMPONENT}"]
        return out


def parity_text(c: Converter, renamed: Callable[[str], str], roots: Iterable[str]) -> ParityText:
    """The text for the arclog relations `roots`, each without a Souffle
    relation of the solver's program; `renamed` gives the final arclog name
    of a name `Converter.names` makes. A root with no place in the program of
    the rewrite, or that reads what no component of the text declares, has none."""
    if c.ground_prog is None:
        return ParityText("", {})
    lift = _Lift(c)
    ground, solver = lift.ground, lift.solver
    clash = [n for n, t in ground.decls.items() if n.kind is Kind.TYPE and not n.scope and solver.decls.get(n) is not None
             and printer.declaration(t) != printer.declaration(solver.decls[n])]
    if clash:
        raise ValueError(f"the rewrite's type {clash[0].name} clashes with the solver's")
    found: dict[str, tuple[Root, set[At]]] = {}
    for arc, root in lift.locate(renamed, set(roots)).items():
        needed = lift.closure(root.at)
        if needed is None or (root.at not in needed and not root.at.path):   # a node of the top level that the solver holds has its own relation
            continue
        if root.relation is not None:
            comp = lift.component(root.at) if root.at in needed else ground.decls[root.at.node].component
            if comp is None or root.relation not in (forms()[comp] if comp in forms() else _present(c, comp) or ()):
                continue
        found[arc] = (root, needed)
    if not found:
        return ParityText("", {})
    lift.name_all({at for _, needed in found.values() for at in needed})
    determined = {arc for arc, (root, _) in found.items() if lift.homes[root.at.path].determined}
    lines = [printer.declaration(t) for n, t in ground.decls.items() if n.kind is Kind.TYPE and not n.scope and n not in solver.decls]
    cases = lift.lines({at for arc, (_, needed) in found.items() if arc not in determined for at in needed})
    det = lift.lines({at for arc, (_, needed) in found.items() if arc in determined for at in needed})
    out: dict[str, Place] = {}
    for arc, (root, _) in found.items():
        out[arc] = _place(lift, root, arc in determined)
    return ParityText("\n".join(lines + cases) + "\n" if cases else "", out,
                      "\n".join([*lines, *([f".init {DETERMINE_INSTANCE} = {DETERMINE}"] if lift.declares_determine else []), *det]) + "\n"
                      if det or determined else "")


def _place(lift: _Lift, root: Root, determined: bool) -> Place:
    """The place of `root` in the text."""
    at, scope = root.at, root.key[0]
    node = at.node
    held = lift.held(at)
    if root.relation is None:
        path = ".".join((*at.path, node.name)) if held else lift.fresh[at]
        return Place(path, scope, RelationName((), root.key[1]), len(lift.ground.decls[node].columns), determined)
    comp = lift.ground.decls[node].component if held else lift.component(at)
    assert comp is not None
    path = ".".join((*at.path, node.name, root.relation)) if held else ".".join((*lift.prefix(at), lift.fresh[at], root.relation))
    return Place(path, scope, RelationName((root.key[1],), root.relation), _width(lift.c, comp, root.relation), determined)
