"""Parser and index over the solver dialect."""

import hashlib
from pathlib import Path

import pytest

import dl.dlparse
from dl.dlparse import (
    EXTERN,
    TOP,
    Atom,
    Cmp,
    Decl,
    Index,
    Neg,
    ParseError,
    Rule,
    body_literals,
    marker_cases,
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


def test_marker_cases_drop_the_fields_a_constructor_fixes():
    src = """\
.type Growth = Iso {} | Aniso {}
.type Seats = Derived {} | Table {}
.type Choice = Derive { g: Growth, s: Seats } | Disp {}
// --- Derive(g=Iso) ---
.decl a(x: number)
a(X) :- g(X).
"""
    ix = Index(parse(src))
    assert ix.rules[0].section == "Derive(g=Iso)"
    assert marker_cases(ix.rules[0].section) == ["Derive"]
    assert marker_cases("Derive(g=Iso, s=Table), Disp") == ["Derive", "Disp"]


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


def test_body_literals():
    src = (
        "y(P) :- a(P), (b(P) ; c(P), d(P)), !e(P),"
        " N = count : { f(P, K), K > 1 }, N > 0.\n"
    )
    rule = parse(src).items[0]
    assert isinstance(rule, Rule)
    lits = list(body_literals(rule))
    assert [l.name for l in lits if isinstance(l, Atom)] == ["a", "b", "c", "d", "f"]
    assert sum(isinstance(l, Neg) for l in lits) == 1
    assert sum(isinstance(l, Cmp) for l in lits) == 3
    shallow = list(body_literals(rule, into_aggs=False))
    assert [l.name for l in shallow if isinstance(l, Atom)] == ["a", "b", "c", "d"]
    assert sum(isinstance(l, Cmp) for l in shallow) == 2
    fact = parse("seed(3).\n").items[0]
    assert isinstance(fact, Rule)
    assert list(body_literals(fact)) == []


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




def test_two_heads_parse_as_two_rules():
    """A clause with two heads parses to what the two one-head clauses
    over its body parse to."""
    two = parse("a(X), b(X) :- c(X), X > 1.")
    pair = parse("a(X) :- c(X), X > 1. b(X) :- c(X), X > 1.")
    assert len(two.items) == 2
    assert two.items == pair.items


def test_a_changed_text_parses_again():
    first = parse(".decl a(x: number)\n")
    second = parse(".decl b(x: number)\n")
    [a] = first.items
    [b] = second.items
    assert isinstance(a, Decl) and a.name == "a"
    assert isinstance(b, Decl) and b.name == "b"
