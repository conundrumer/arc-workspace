"""The box-algebra expansions, as passes over a parsed Souffle solver.

- `typed`: an `edge_inset` or `edge_outset` atom whose direction is a
  DiagDir becomes `corner_inset` or `corner_outset`. The direction's type is
  the type of a constant, or the column type of each other atom of the
  clause, its head included, that the direction's variable fills, read from
  the present lib and the solver's declarations.
- `idioms`: a `crop`, `box_edge` or `box_corner` atom becomes the two tests
  it composes: `inside` with `relative`, `same_dist` or `corner_anchor`.
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass, replace
from typing import Any

from engine.program import (AliasType, Atom, AtomLiteral, DefinedName, Disjunction, RelationName,
                            SubtypeType, Unit, Variable, Wildcard)

CORNER = {"edge_inset": "corner_inset", "edge_outset": "corner_outset"}


def atoms(x):
    """Each atom inside x, in order."""
    if isinstance(x, Atom):
        yield x
    elif isinstance(x, tuple):
        for y in x:
            yield from atoms(y)
    elif is_dataclass(x) and not isinstance(x, type):
        for f in fields(x):
            yield from atoms(getattr(x, f.name))


def mapped(x: Any, fn) -> Any:
    """x with each atom a inside it replaced by fn(a)."""
    if isinstance(x, Atom):
        return fn(x)
    if isinstance(x, tuple):
        return tuple(mapped(y, fn) for y in x)
    if is_dataclass(x) and not isinstance(x, type):
        changes = {f.name: mapped(getattr(x, f.name), fn) for f in fields(x)}
        return replace(x, **changes) if any(changes[k] is not getattr(x, k) for k in changes) else x
    return x


class Types:
    """Column types of the atoms a solver's clauses hold."""

    def __init__(self, prog, lib) -> None:
        self.lib = lib
        self.rels = {(r.scope.components, r.name): r for r in prog.relations}
        self.insts = {(i.scope.components, i.name): i for i in prog.instances}
        self.types = {(t.scope.components, t.name): t for t in prog.types}

    def base(self, name: str, scope: tuple[str, ...]) -> str:
        """The lib type a solver type name stands for."""
        for _ in range(16):
            t = next((self.types[(scope[:i], name)] for i in range(len(scope), -1, -1)
                      if (scope[:i], name) in self.types), None)
            if isinstance(t, AliasType):
                name = t.target.name
            elif isinstance(t, SubtypeType):
                name = t.base.name
            else:
                return name
        return name

    def column(self, a: Atom, i: int, scope: tuple[str, ...]) -> str | None:
        rn = a.relation
        if not rn.instances:
            r = next((self.rels[(scope[:k], rn.name)] for k in range(len(scope), -1, -1)
                      if (scope[:k], rn.name) in self.rels), None)
            if r is not None:
                return self.base(r.columns[i].type.name, scope) if i < len(r.columns) else None
            cols = self.lib.top.get(rn.name)
            return cols[i][1] if cols and i < len(cols) else None
        if rn.instances == ("params",):
            r = self.rels.get((("Params",), rn.name))
            return self.base(r.columns[i].type.name, ("Params",)) if r and i < len(r.columns) else None
        if len(rn.instances) != 1:
            return None
        inst = next((self.insts[(scope[:k], rn.instances[0])] for k in range(len(scope), -1, -1)
                     if (scope[:k], rn.instances[0]) in self.insts), None)
        if inst is None or inst.component not in self.lib.comps:
            return None
        tparams, rels = self.lib.relations(inst.component)
        lr = next((r for r in rels if r.name == rn.name), None)
        if lr is None or i >= len(lr.cols):
            return None
        t = lr.cols[i].type
        sub = {p: ta.name for p, ta in zip(tparams, inst.type_args)}
        return self.base(sub.get(t, t), inst.scope.components)


def typed(prog, lib) -> tuple[object, dict[Atom, str]]:
    """The program with each corner site of `edge_inset` and `edge_outset`
    renamed, and each site whose direction's type is neither Dir nor
    DiagDir, with the reason."""
    types = Types(prog, lib)
    judgment: dict[Atom, str] = {}

    def unit(u: Unit) -> Unit:
        sites = [a for a in atoms(u.body or ()) if not a.relation.instances and a.relation.name in CORNER]
        if not sites:
            return u
        corner: set[Atom] = set()
        for a in sites:
            d = a.args[0] if a.args else None
            found: set[str] = set()
            if isinstance(d, DefinedName):
                found.add("DiagDir" if d.name.startswith("DIAG_") else "Dir" if d.name.startswith("DIR_") else "")
            elif isinstance(d, Variable):
                for b in [u.head, *atoms(u.body or ())]:
                    if b is a:
                        continue
                    for i, t in enumerate(b.args):
                        if isinstance(t, Variable) and t.name == d.name:
                            ty = types.column(b, i, u.scope.components)
                            if ty is not None:
                                found.add(ty)
            if found & {"Dir", "DiagDir"} == {"DiagDir"}:
                corner.add(a)
            elif found & {"Dir", "DiagDir"} != {"Dir"}:
                judgment[a] = f"{a.relation.name}: the direction's type is {' or '.join(sorted(found)) or 'unknown'}"
        if not corner:
            return u
        return mapped(u, lambda a: replace(a, relation=RelationName((), CORNER[a.relation.name]))
                      if a in corner else a)

    return replace(prog, units=tuple(unit(u) for u in prog.units)), judgment


IDIOMS = {"crop", "box_edge", "box_corner"}


def lib_atom(name: str, args: tuple, line: int) -> Atom:
    return Atom(RelationName((), name), args, line)


def idiom_tests(a: Atom) -> list[Atom]:
    """The two tests an idiom atom composes, the `inside` test first; the
    second is absent at a `crop` whose relative cell is not read."""
    p, b, x = a.args
    out = [lib_atom("inside", (p, b), a.line)]
    if a.relation.name == "crop":
        if not isinstance(x, Wildcard):
            out.append(lib_atom("relative", (b, p, x), a.line))
    else:
        out.append(lib_atom("same_dist" if a.relation.name == "box_edge" else "corner_anchor", (x, p, b), a.line))
    return out


def idioms(prog, ground: bool = False) -> tuple[object, dict[Atom, str]]:
    """The program with each `crop`, `box_edge` and `box_corner` atom
    replaced by its tests, and each site left in place, with the reason.

    A positive site adds its tests, less an `inside` test its list already
    holds. A negated site, every argument a variable or a constant, is the
    negated second test where its list holds the `inside` test, and else
    the union of the two negated tests. With `ground`, a `same_dist`
    direction that is a wildcard is a fresh variable, and each `same_dist`
    direction is grounded by `dir_elem`, which the Souffle engine needs."""
    judgment: dict[Atom, str] = {}
    fresh = iter(range(1 << 30))

    def site(a: Atom) -> bool:
        return not a.relation.instances and a.relation.name in IDIOMS and len(a.args) == 3

    def grounded(tests: list[Atom]) -> list[AtomLiteral]:
        out = []
        for t in tests:
            if ground and t.relation.name == "same_dist":
                d = t.args[0]
                if isinstance(d, Wildcard):
                    d = Variable(f"D_idiom{next(fresh)}")
                    t = Atom(t.relation, (d, *t.args[1:]), t.line)
                out.append(AtomLiteral(lib_atom("dir_elem", (d,), t.line), False))
            out.append(AtomLiteral(t, False))
        return out

    def body(lits: tuple) -> tuple:
        held = {l.atom for l in lits if isinstance(l, AtomLiteral) and not l.negated
                and l.atom.relation == RelationName((), "inside")}
        held = {(a.args, ) for a in held}
        out: list = []
        for lit in lits:
            if isinstance(lit, Disjunction):
                out.append(Disjunction(tuple(body(br) for br in lit.branches), lit.line))
                continue
            if not (isinstance(lit, AtomLiteral) and site(lit.atom)):
                out.append(lit)
                continue
            a = lit.atom
            tests = idiom_tests(a)
            key = (tests[0].args, )
            if not lit.negated:
                if key in held:
                    tests = tests[1:]
                held.add(key)
                out += grounded(tests)
            elif any(isinstance(x, Wildcard) for x in a.args):
                judgment[a] = f"{a.relation.name}: a negated site with an unread column"
                out.append(lit)
            elif key in held or len(tests) == 1:
                out += [AtomLiteral(l.atom, True) if l.atom is tests[-1] else l for l in grounded(tests[-1:])]
            else:
                out.append(Disjunction(tuple(
                    tuple(AtomLiteral(l.atom, True) if l.atom is t else l for l in grounded([t]))
                    for t in tests), a.line))
        return tuple(out)

    def unit(u: Unit) -> Unit:
        if not u.body or not any(site(a) for a in atoms(u.body)):
            return u
        return replace(u, body=body(u.body))

    return replace(prog, units=tuple(unit(u) for u in prog.units)), judgment
