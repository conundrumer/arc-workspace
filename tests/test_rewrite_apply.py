"""The rewrite a `negated-use` finding proposes must compile: each use of
the flagged relation, with the negation replaced by the inlined atoms, is
handed to Souffle."""

import shutil

import pytest

from dl.dlparse import Atom, Neg, Var, parse
from dl.rewrite_lint import _atom_str, _lit_str, _term_str, lint_rewrites
from dl.source import build_source
from dl.souffle import compile_check

needs_souffle = pytest.mark.skipif(
    shutil.which("souffle") is None, reason="souffle not installed",
)


def _rewritten_uses(source: str) -> list[str]:
    """Top-level rules that negate a `negated-use` relation, re-rendered
    with the negation inlined."""
    program = parse(source)
    flagged = {
        f[2].split("(", 1)[0].lstrip("`!")
        for f in lint_rewrites(source) if f[0] == "negated-use"
    }
    if not flagged:
        return []
    defs = {
        it.head.name: it
        for it in program.items
        if hasattr(it, "head") and it.body and it.head.name in flagged
    }
    out: list[str] = []
    for it in program.items:
        if not hasattr(it, "head") or not it.body:
            continue
        negs = [
            lit for lit in it.body
            if isinstance(lit, Neg) and lit.atom.qual is None
            and lit.atom.name in defs
        ]
        if not negs:
            continue
        lits = []
        for lit in it.body:
            if lit in negs:
                d = defs[lit.atom.name]
                names = {
                    a.name: _term_str(lit.atom.args[i])
                    for i, a in enumerate(d.head.args) if isinstance(a, Var)
                }
                atom = d.body[0]
                assert isinstance(atom, Atom)
                lits.append(f"!{_atom_str(atom, names)}")
            else:
                lits.append(_lit_str(lit))
        out.append(f"{_atom_str(it.head)} :- {', '.join(lits)}.")
    return out


@needs_souffle
def test_applier_compiles_a_projection_rewrite():
    src = """\
#include "../lib.dl"
.decl ray(a: number, p: Position, b: number)
ray(1, [0, 0, 0, 0], 3).
.decl painted(p: Position)
painted(P) :- ray(_, P, _).
.decl out(p: Position, col: Color)
out(P, 0) :- in(P, _), !painted(P).
"""
    rules = _rewritten_uses(src)
    assert rules == ["out(P, 0) :- in(P, _), !ray(_, P, _)."]
    assert compile_check(build_source(src + "\n".join(rules) + "\n")) is None
