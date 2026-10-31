"""The `tile_size` expansion, as a pass over a parsed Souffle solver.

`tile_size(Ext, N, 0, K)` holds where `K = Ext / N` exactly, with `Ext > 0`.
Where K is also bound by another positive atom of the conjunction, the atom
only tests the three values, and `stride(Ext, K, 0, N, 0)` with `N > 0`
holds exactly where it does: with `K > 0` the stride gives the part
`Ext / K` and the remainder `Ext % K`, so it holds where `Ext = N * K`, and
no `K <= 0` gives a row. The atom becomes those two literals.

A site stays in place, and the converter reports it unresolved, where its
gap is not the literal 0, where K is not bound by another positive atom, or
where `Ext` is not bound or N is not a variable or a positive number.
Arclog has no arithmetic and `divide` has no mode that gives its side, so
the quotient form (K unbound) has no arclog counterpart.
"""
from __future__ import annotations

from dataclasses import replace

from engine.program import (Atom, AtomLiteral, Comparison, ComparisonOperator, Disjunction, NumberTerm,
                            RelationName, Unit, Variable)

from arclog_convert.libmap.division import _lib_inline, _modes
from arclog_convert.libmap.instances import term_vars

RELATION = "tile_size"
IDIOMS = frozenset({RELATION})


def _site(lit) -> bool:
    return isinstance(lit, AtomLiteral) and not lit.negated and lit.atom.relation == RelationName((), RELATION) \
        and len(lit.atom.args) == 4


def _binds(lits, bound: set[str]) -> set[str]:
    """`bound` with each variable that a positive atom of `lits` other than a
    `tile_size` site binds: every variable of an atom of a relation that is
    no lib inline relation, and of a lib inline relation once the variables
    of one of its modes are bound."""
    modes = _modes()
    inline = _lib_inline()
    out = set(bound)
    atoms = [l.atom for l in lits if isinstance(l, AtomLiteral) and not l.negated and not _site(l)]
    changed = True
    while changed:
        changed = False
        for a in atoms:
            vs = set(term_vars(a.args, []))
            if vs <= out:
                continue
            if a.relation.instances or a.relation.name not in inline:
                grounds = True
            else:
                found = modes.get(a.relation.name)
                grounds = found is not None and any(
                    all(i >= len(a.args) or not term_vars(a.args[i], []) or set(term_vars(a.args[i], [])) <= out
                        for i in m) for m in found[0])
            if grounds:
                out |= vs
                changed = True
    return out


def _body(lits: tuple, outer: set[str]) -> tuple:
    bound = _binds(lits, outer)
    out: list = []
    for lit in lits:
        if isinstance(lit, Disjunction):
            out.append(replace(lit, branches=tuple(_body(b, bound) for b in lit.branches)))
        elif _site(lit):
            out.extend(_rewritten(lit, bound))
        else:
            out.append(lit)
    return tuple(out)


def _rewritten(lit: AtomLiteral, bound: set[str]) -> list:
    a = lit.atom
    ext, n, gap, k = a.args
    zero = NumberTerm(0)
    if not (isinstance(gap, NumberTerm) and gap.value == 0):
        return [lit]
    if not (isinstance(k, Variable) and k.name in bound and k.name not in term_vars((ext, n), [])):
        return [lit]
    if not (isinstance(ext, Variable) and ext.name in bound or isinstance(ext, NumberTerm)):
        return [lit]
    if isinstance(n, Variable):
        test = [Comparison(ComparisonOperator.GT, n, zero, a.line)]
    elif isinstance(n, NumberTerm) and n.value > 0:
        test = []
    else:
        return [lit]
    return [AtomLiteral(Atom(RelationName((), "stride"), (ext, k, gap, n, zero), a.line), False), *test]


def expand(prog) -> object:
    """The program with each `tile_size` site that a `stride` test replaces so."""
    def unit(u: Unit) -> Unit:
        if not u.body or not any(_has_site(u.body)):
            return u
        return replace(u, body=_body(u.body, set()))

    return replace(prog, units=tuple(unit(u) for u in prog.units))


def _has_site(lits):
    for l in lits:
        if isinstance(l, Disjunction):
            for b in l.branches:
                yield from _has_site(b)
        elif _site(l):
            yield l
