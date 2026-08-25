"""Parser and index over the solver dialect."""

from pathlib import Path

import pytest

from dl.dlparse import (
    EXTERN,
    TOP,
    Agg,
    Atom,
    Bool,
    Cmp,
    Ctor,
    Disj,
    Index,
    MacroConst,
    Neg,
    ParseError,
    Rule,
    Wild,
    parse,
)

SOLVERS = Path(__file__).parent.parent / "programs" / "solvers"
LIB = Path(__file__).parent.parent / "programs" / "lib.dl"


def test_corpus_parses():
    solvers = [f for f in sorted(SOLVERS.glob("*.dl")) if not f.name.startswith(".")]
    for f in solvers + [LIB]:
        Index(parse(f.read_text()))


def test_rule_and_fact():
    p = parse("ink(P) :- in(P, C), !c.bg(C).\nseed(3).\n")
    rule, fact = p.items
    assert isinstance(rule, Rule) and rule.body is not None
    assert isinstance(rule.body[1], Neg)
    assert rule.body[1].atom.qual == "c"
    assert isinstance(fact, Rule) and fact.body is None


def test_qualified_chain_and_bool():
    p = parse(
        "x(P) :- c.frame.pos(P).\n"
        "compose(A, B) :- true.\n"
    )
    assert p.items[0].body[0].qual == "c.frame"
    assert p.items[1].body == [Bool(True)]


def test_aggregate_and_macro_const():
    p = parse("big(N) :- N = max K : { size(K), K > 1 }, dir(DIR_T).\n")
    cmp_, atom = p.items[0].body
    assert isinstance(cmp_, Cmp)
    assert isinstance(cmp_.rhs, Agg) and cmp_.rhs.op == "max"
    assert atom.args == (MacroConst("DIR_T"),)


def test_grid_fact_takes_no_period():
    p = parse(".decl g(p: number)\nGRID_1x2(g, 1, 2)\nafter(P) :- g(P).\n")
    grid = p.items[1]
    assert grid.grid and grid.head.name == "GRID_1x2"


def test_decl_line_fact():
    p = parse(".comp Consts {\n    .decl bg(c: Color) bg(0).\n}\n")
    decl, fact = p.items[0].items
    assert decl.name == "bg" and fact.head.name == "bg"


def test_ctor_record_wildcard():
    p = parse("m(K) :- box.cell($U(), [T, B], _), f(K).\n")
    args = p.items[0].body[0].args
    assert isinstance(args[0], Ctor) and args[0].name == "U"
    assert isinstance(args[2], Wild)


def test_disjunction():
    p = parse(
        "out(P, Col) :- in(P, _),\n"
        "    ( tile(P, Col)\n"
        "    ; !tile(P, _), c.bg(Col)\n"
        "    ).\n"
    )
    disj = p.items[0].body[1]
    assert isinstance(disj, Disj) and len(disj.branches) == 2
    assert isinstance(disj.branches[1][0], Neg)


def test_disjunction_index_roles():
    src = """\
.decl tile(p: number, c: number)
tile(1, 2).
.decl out(p: number, c: number)
out(P, Col) :- g(P), (tile(P, Col) ; !tile(P, _), bg(Col)).
"""
    ix = Index(parse(src))
    roles = [r.role for r in ix.refs_of((TOP, "tile"))]
    assert roles == ["head", "pos", "neg"]


def test_paren_expr_is_not_a_disjunction():
    p = parse("out(X) :- (X + Y) != Z, g(X, Y, Z).\n")
    assert isinstance(p.items[0].body[0], Cmp)


def test_single_branch_group():
    p = parse("out(P, Col) :- ( tile(P, Col), P = Col ), g(P).\n")
    group = p.items[0].body[0]
    assert isinstance(group, Disj) and len(group.branches) == 1
    assert isinstance(group.branches[0][1], Cmp)


def test_paren_call_before_comparison_is_not_a_group():
    p = parse("out(X) :- (max Y : { g(Y) }) > X, g(X).\n")
    assert isinstance(p.items[0].body[0], Cmp)


def test_subsumptive_clause():
    p = parse("high(K, S) <= high(K, S2) :- S < S2.\n")
    rule = p.items[0]
    assert isinstance(rule, Rule) and rule.sub
    assert rule.head.name == "high"
    assert isinstance(rule.body[0], Atom) and rule.body[0].name == "high"
    assert isinstance(rule.body[1], Cmp)


def test_comp_inheritance():
    src = """\
.comp Base<K> {
    .decl node(k: K)
    .decl out(k: K)
    out(X) :- node(X).
}
.comp Derived<K> : Base<K> {
    .decl extra(k: K)
    extra(X) :- node(X).
}
.init d = Derived<number>
top(X) :- d.out(X), d.extra(X).
"""
    p = parse(src)
    comp = p.comps()["Derived"]
    assert comp.base == "Base" and comp.base_targs == ["K"]
    ix = Index(p)
    assert ix.resolve("Derived", None, "node") == ("Base", "node")
    assert ix.resolve(TOP, None, "out") == (EXTERN, "out")
    assert ix.resolve(TOP, "d", "out") == ("Base", "out")
    assert ix.resolve(TOP, "d", "extra") == ("Derived", "extra")


def test_comments_kept():
    p = parse("// header\nink(P) :- in(P, C).  // trailing\n")
    own = [c for c in p.comments if c.own_line]
    assert len(p.comments) == 2 and len(own) == 1


def test_parse_error_positions():
    with pytest.raises(ParseError) as e:
        parse("ink(P :- in(P).\n")
    assert e.value.line == 1


def test_index_resolution_and_roles():
    src = """\
.comp Consts {
    .decl bg(c: Color) bg(0).
}
.init c = Consts
.decl ink(p: Position)
ink(P) :- in(P, C), !c.bg(C).
.decl n(k: number)
n(K) :- K = count : { ink(P) }.
"""
    ix = Index(parse(src))
    assert [r.role for r in ix.refs_of(("Consts", "bg"))] == ["head", "neg"]
    roles = [r.role for r in ix.refs_of((TOP, "ink"))]
    assert roles == ["head", "agg"]
    assert ix.resolve(TOP, None, "in") == (EXTERN, "in")


def test_index_sections():
    src = """\
// --- CaseA --- with trailing prose
.decl a(x: number)
a(X) :- g(X).
"""
    ix = Index(parse(src))
    assert ix.rules[0].section == "CaseA"


def test_choice_domain():
    src = """\
.decl seat(b: number, pc: number) choice-domain b, pc
seat(B, P) :- cand(B, P).
.decl one(x: number, y: number, z: number) choice-domain (x, y), z
.decl plain(x: number)
"""
    from dl.dlparse import Decl

    decls = {d.name: d for d in parse(src).items if isinstance(d, Decl)}
    assert decls["seat"].choice_domain == ["b", "pc"]
    assert decls["one"].choice_domain == ["(x, y)", "z"]
    assert decls["plain"].choice_domain == []
