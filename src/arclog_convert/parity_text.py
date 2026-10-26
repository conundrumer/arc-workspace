"""The Souffle text that derives the rows of the relations the converter adds.

The lib rewrite (`libmap.rewrite`) gives some relations of the converted
program that the solver's program holds no relation of: each relation of an
instance it hoists or expands, and each relation of an expansion's shape that
holds no relation of the solver, such as `<read>_full`. `parity_text` gives
the clauses that the rewrite writes for them, in its ground form
(`Converter.ground_prog`), as a text to add to the solver's program, so that
a Souffle run derives the rows of each such relation from the solver's own:

- A relation or an instance of the rewrite's program is held where the
  solver declares the same (`Converter.source`), and, for an instance,
  its component declares each relation the rewrite's clauses name through it.
  A clause of the text reads a held relation as the solver declares it.
- The text holds, under a fresh name (`PREFIX` and the name), each relation
  and instance that is not held and that a root, an arclog relation without a
  Souffle relation, or a clause of the text, reads or heads, with the clauses
  that head it.
- An instance stands in the component of the lib that declares each relation
  the clauses name through it, or else in the form of its component, `Sig`
  and its name, from `lib-forms.dl` (`forms`), or in the lib component
  `libmap.COMP` renames to its name. A clause reads a relation of the
  signature that the lib holds no relation of, such as `gap`, under the form
  of `lib-forms.dl` that `RELATION_PREFIX` leads (`top_forms`).
- The relations and instances of the text stand at the top level. A root that
  reads an instance of no such component, or that stands in a component of the
  solver, has no place.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from engine.program import Atom, Instance, RelationDecl, RelationName, TypeDecl, Unit, body_atoms
from souffle import printer
from souffle.parser import parse
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
"""What leads the name of each relation and instance of the text."""


class Kind(StrEnum):
    RELATION = "relation"
    INSTANCE = "instance"


@dataclass(frozen=True)
class Node:
    """A relation or an instance of the program, by its name at the top level."""

    kind: Kind
    name: str


@dataclass(frozen=True)
class Place:
    """Where the rows of an arclog relation stand in the text: `path` from the
    top level of the text, and the relation the rewrite's program holds for
    it, from the top level of the program, with its number of columns in the
    text."""

    path: str
    relation: RelationName
    width: int


@dataclass(frozen=True)
class ParityText:
    """The text, and the place of each arclog relation whose rows it derives."""

    text: str
    places: Mapping[str, Place]


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


@dataclass(frozen=True)
class Index:
    """A program's own top-level parts."""

    relations: dict[str, RelationDecl]
    instances: dict[str, Instance]
    types: dict[str, TypeDecl]
    units: dict[Node, list[Unit]]
    """The units that head each relation or instance, in program order."""
    accessed: dict[str, set[str]]
    """The relations of each instance that a unit names through it."""

    @staticmethod
    def of(prog) -> "Index":
        def own(x) -> bool:
            return (x.span is None or x.span.file is None) and not x.scope.components
        index = Index({r.name: r for r in prog.relations if own(r)}, {i.name: i for i in prog.instances if own(i)},
                      {t.name: t for t in prog.types if own(t)}, {}, {})
        for u in prog.units:
            if not own(u):
                continue
            head = u.head.relation
            index.units.setdefault(Node(Kind.INSTANCE, head.instances[0]) if head.instances
                                   else Node(Kind.RELATION, head.name), []).append(u)
            for a in [u.head, *(a for a, _ in body_atoms(u.body or ()))]:
                if len(a.relation.instances) == 1:
                    index.accessed.setdefault(a.relation.instances[0], set()).add(a.relation.name)
        return index

    def node_of(self, atom: Atom) -> Node | None:
        """The relation or instance the atom reads; None for a relation of the lib."""
        r = atom.relation
        if r.instances:
            return Node(Kind.INSTANCE, r.instances[0]) if r.instances[0] in self.instances else None
        return Node(Kind.RELATION, r.name) if r.name in self.relations else None

    def declaration(self, node: Node) -> str:
        decl = self.relations[node.name] if node.kind is Kind.RELATION else self.instances[node.name]
        return printer.declaration(decl)


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


def parity_text(c: Converter, renamed: Callable[[str], str], roots: Iterable[str]) -> ParityText:
    """The text for the arclog relations `roots`, each without a Souffle
    relation of the solver's program; `renamed` gives the final arclog name
    of a name `Converter.names` makes. A root with no place in the program of
    the rewrite, or that reads what no component of the text declares, has none."""
    if c.ground_prog is None:
        return ParityText("", {})
    ground, solver = Index.of(c.ground_prog), Index.of(c.source)
    clash = [t for t in ground.types if t in solver.types and
             printer.declaration(ground.types[t]) != printer.declaration(solver.types[t])]
    if clash:
        raise ValueError(f"the rewrite's type {clash[0]} clashes with the solver's")

    def held(node: Node) -> bool:
        """The solver declares the same relation or instance; an instance's component declares each relation named through it."""
        if node.kind is Kind.RELATION:
            return node.name in solver.relations and solver.declaration(node) == ground.declaration(node)
        inst = ground.instances[node.name]
        if node.name not in solver.instances or solver.declaration(node) != ground.declaration(node):
            return False
        present = _present(c, inst.component)
        return present is None or ground.accessed.get(node.name, set()) <= present

    places = _locate(c, renamed, ground, set(roots))
    chosen: dict[str, str | None] = {}

    def component(inst: str) -> str | None:
        if inst not in chosen:
            chosen[inst] = _component(c, ground.instances[inst].component, ground.accessed.get(inst, set()))
        return chosen[inst]

    def closure(root: Node) -> set[Node] | None:
        """Each node the root needs that the solver does not hold; None where one has no component."""
        seen: set[Node] = set()
        todo = [root]
        while todo:
            node = todo.pop()
            if node in seen or held(node):
                continue
            if node.kind is Kind.INSTANCE and component(node.name) is None:
                return None
            seen.add(node)
            todo += [n for u in ground.units.get(node, []) for a, _ in body_atoms(u.body or ())
                     if (n := ground.node_of(a)) is not None]
        return seen

    included: set[Node] = set()
    found: dict[str, tuple[Node, str | None]] = {}
    for arc, (node, relation) in places.items():
        needed = closure(node)
        if needed is None or node not in needed:
            continue
        if relation is not None:
            comp = component(node.name)
            assert comp is not None
            if relation not in (forms()[comp] if comp in forms() else _present(c, comp) or ()):
                continue
        included |= needed
        found[arc] = (node, relation)
    if not found:
        return ParityText("", {})
    taken = {*solver.relations, *solver.instances, *c.lib.top, *c.sig.top, *ground.relations, *ground.instances}
    fresh: dict[Node, str] = {}
    for kind, table in ((Kind.RELATION, ground.relations), (Kind.INSTANCE, ground.instances)):
        for name in table:
            if Node(kind, name) in included:
                cand = PREFIX + name
                while cand in taken:
                    cand += "_"
                taken.add(cand)
                fresh[Node(kind, name)] = cand

    def rename(atom: Atom) -> Atom:
        r = atom.relation
        if r.instances == (LIB_PATH,):
            return replace(atom, relation=RelationName((), RELATION_PREFIX + r.name if r.name in top_forms() else r.name))
        if not r.instances and r.name in top_forms() and r.name not in ground.relations:
            return replace(atom, relation=RelationName((), RELATION_PREFIX + r.name))
        if r.instances:
            to = fresh.get(Node(Kind.INSTANCE, r.instances[0]))
            return atom if to is None else replace(atom, relation=RelationName((to, *r.instances[1:]), r.name))
        to = fresh.get(Node(Kind.RELATION, r.name))
        return atom if to is None else replace(atom, relation=RelationName((), to))

    lines = [printer.declaration(t) for n, t in ground.types.items() if n not in solver.types]
    for node, name in fresh.items():
        if node.kind is Kind.RELATION:
            lines.append(printer.declaration(replace(ground.relations[node.name], name=name)))
        else:
            inst = ground.instances[node.name]
            comp = component(node.name)
            assert comp is not None
            lines.append(printer.declaration(replace(inst, name=name, component=comp)))
        lines += [printer.unit(mapped(u, rename)) for u in ground.units.get(node, [])]
    out: dict[str, Place] = {}
    for arc, (node, relation) in found.items():
        if relation is None:
            out[arc] = Place(fresh[node], RelationName((), node.name), len(ground.relations[node.name].columns))
        else:
            comp = component(node.name)
            assert comp is not None
            out[arc] = Place(f"{fresh[node]}.{relation}", RelationName((node.name,), relation),
                             _width(c, comp, relation))
    return ParityText("\n".join(lines) + "\n", out)


def _locate(c: Converter, renamed: Callable[[str], str], ground: Index, roots: set[str]
            ) -> dict[str, tuple[Node, str | None]]:
    """The relation, or the relation of an instance, of the rewrite's program
    that each of `roots` is the arclog name of, by the names `Converter.names`
    gives; a root with none is left out."""
    out: dict[str, tuple[Node, str | None]] = {}
    for name in ground.relations:
        if ((), name) in c.names:
            out[renamed(f"&{c.names[(), name]}")] = (Node(Kind.RELATION, name), None)
    for name, inst in ground.instances.items():
        if ((), name) in c.names and inst.component in c.lib.comps:
            for r in c.lib.relations(inst.component)[1]:
                out[renamed(f"&{c.names[(), name]}.{r.name}")] = (Node(Kind.INSTANCE, name), r.name)
    return {arc: at for arc, at in out.items() if arc in roots}
