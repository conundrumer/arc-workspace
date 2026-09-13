"""Parser and index over the solver dialect."""

import hashlib
from pathlib import Path

import pytest

import dl.dlparse
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
    body_literals,
    parse,
)

SOLVERS = Path(__file__).parent.parent / "programs" / "solvers"
LIB = Path(__file__).parent.parent / "programs" / "lib.dl"


CACHE_KEY = "dlparse/corpus"


def test_corpus_parses(request):
    """Every program in the corpus parses and indexes.

    A file that parsed under the current parser parses again, so the run
    records what it proved and re-parses only what changed. The record is
    keyed by the parser's own source: an edit there re-parses the corpus.
    """
    solvers = [f for f in sorted(SOLVERS.glob("*.dl")) if not f.name.startswith(".")]
    parser = hashlib.sha256(
        Path(dl.dlparse.__file__).read_bytes()).hexdigest()
    store = getattr(request.config, "cache", None)
    cached = store.get(CACHE_KEY, {}) if store else {}
    if cached.get("parser") != parser:
        cached = {"parser": parser, "files": {}}
    proved = cached["files"]
    for f in solvers + [LIB]:
        text = f.read_text()
        digest = hashlib.sha256(text.encode()).hexdigest()
        if proved.get(str(f)) == digest:
            continue
        Index(parse(text))
        proved[str(f)] = digest
    if store:
        store.set(CACHE_KEY, cached)


def test_rule_and_fact():
    p = parse("ink(P) :- in(P, C), !params.bg(C).\nseed(3).\n")
    rule, fact = p.items
    assert isinstance(rule, Rule) and rule.body is not None
    assert isinstance(rule.body[1], Neg)
    assert rule.body[1].atom.qual == "params"
    assert isinstance(fact, Rule) and fact.body is None


def test_qualified_chain_and_bool():
    p = parse(
        "x(P) :- params.frame.pos(P).\n"
        "compose(A, B) :- true.\n"
    )
    assert p.items[0].body[0].qual == "params.frame"
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


def test_grid_fact_takes_macro_cell_tokens():
    """A grid head's arguments are cell tokens, not terms, so the anchor
    prefix and the absent token pass."""
    p = parse("GRID_STAMP_1x3(s, @1, _, 1)\nafter(P) :- s(P).\n")
    grid = p.items[0]
    assert grid.grid and grid.head.name == "GRID_STAMP_1x3"
    assert p.items[1].head.name == "after"


def test_decl_line_fact():
    p = parse(".comp Params {\n    .decl bg(c: Color) bg(0).\n}\n")
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
        "    ; !tile(P, _), params.bg(Col)\n"
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
.comp Params {
    .decl bg(c: Color) bg(0).
}
.init params = Params
.decl ink(p: Position)
ink(P) :- in(P, C), !params.bg(C).
.decl n(k: number)
n(K) :- K = count : { ink(P) }.
"""
    ix = Index(parse(src))
    assert [r.role for r in ix.refs_of(("Params", "bg"))] == ["head", "neg"]
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


def test_index_section_marker_in_comp_stays_in_the_comp():
    src = """\
// --- CaseA ---
.decl a(x: number)
a(X) :- g(X).
.comp P {
    // --- CaseB ---
    .decl b(x: number)
    b(X) :- g(X).
}
.decl c(x: number)
c(X) :- g(X).
"""
    ix = Index(parse(src))
    sections = {r.rule.head.name: r.section for r in ix.rules}
    assert sections == {"a": "CaseA", "b": None, "c": "CaseA"}


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


def test_body_literals():
    src = (
        "y(P) :- a(P), (b(P) ; c(P), d(P)), !e(P),"
        " N = count : { f(P, K), K > 1 }, N > 0.\n"
    )
    rule = parse(src).items[0]
    lits = list(body_literals(rule))
    assert [l.name for l in lits if isinstance(l, Atom)] == ["a", "b", "c", "d", "f"]
    assert sum(isinstance(l, Neg) for l in lits) == 1
    assert sum(isinstance(l, Cmp) for l in lits) == 3
    shallow = list(body_literals(rule, into_aggs=False))
    assert [l.name for l in shallow if isinstance(l, Atom)] == ["a", "b", "c", "d"]
    assert sum(isinstance(l, Cmp) for l in shallow) == 2
    fact = parse("seed(3).\n").items[0]
    assert list(body_literals(fact)) == []


def test_plan_directive():
    src = """\
.decl walk(a: number, b: number)
walk(A, B) :- edge(A, B).
walk(A, B) :- walk(A, C), edge(C, B).
.plan 0:(2, 1)
"""
    base, step = parse(src).items[1:]
    assert base.plan is None
    assert step.plan == [(0, (2, 1))]
    assert step.end_line == 4


def test_plan_on_the_rule_line_and_many_versions():
    src = "p(A, B) :- p(A, C), p(C, B). .plan 0:(1, 2), 1:(2, 1)\n"
    rule = parse(src).items[0]
    assert rule.plan == [(0, (1, 2)), (1, (2, 1))]
    assert rule.end_line == 1
    assert parse("q(A) :- r(A).\n.decl s(a: number)\n").items[0].plan is None


def test_comp_nested_in_comp():
    src = """\
.comp Outer {
    .comp Inner {
        .decl node(k: number)
        node(1).
    }
    .init i = Inner
    .decl seen(k: number)
    seen(X) :- i.node(X).
}
.init o = Outer
top(X) :- o.seen(X), o.i.node(X).
"""
    p = parse(src)
    outer = p.comps()["Outer"]
    inner = next(it for it in outer.items if isinstance(it, dl.dlparse.Comp))
    assert inner.name == "Inner" and "Inner" not in p.comps()
    ix = Index(p)
    assert ix.resolve("Outer", "i", "node") == ("Inner", "node")
    assert ix.resolve(TOP, "o.i", "node") == ("Inner", "node")
    assert [r.role for r in ix.refs_of(("Inner", "node"))] == ["head", "pos", "pos"]


def test_stateful_functor():
    prog = parse(".functor box_dist(p: Box, d: Dir): number stateful\n"
                 ".decl a(x: number)\n")
    f = prog.items[0]
    assert f.name == "box_dist"
    assert f.text.endswith("number stateful")
    assert prog.items[1].name == "a"


def test_a_branch_list_continues_on_a_line_opening_with_a_bar():
    """Each branch takes its own line under its gloss, so a line ends at a
    branch and the next one opens with the bar."""
    src = """\
// which way the tiles turn
.type Choice =
      // mirror across the seam
      Mirror {}
      // a quarter turn
    | Turn {d: number}
      // leave it alone
    | Keep {}
.decl out(c: Choice)
out($Keep()).
"""
    prog = parse(src)
    td = prog.items[0]
    assert td.name == "Choice"
    assert td.branches == ["Mirror", "Turn", "Keep"]
    assert prog.items[1].name == "out"
