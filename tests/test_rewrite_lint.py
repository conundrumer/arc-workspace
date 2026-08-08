"""Rewrite-lint rules: each fires on its corpus before-shape and stays
quiet on the kept idiom next to it."""

from dl.rewrite_lint import lint_rewrites


def cats(src: str, hints: bool = False) -> list[str]:
    return [f[0] for f in lint_rewrites(src, hints)]


def test_dead_relation_fixpoint():
    src = """\
.decl a(x: number)
a(X) :- b(X).
.decl b(x: number)
b(1).
.decl out(x: number)
out(X) :- live(X).
.decl live(x: number)
live(2).
"""
    fs = lint_rewrites(src)
    assert [f[0] for f in fs] == ["dead", "dead"]
    assert {f[2] for f in fs} == {"`a` has no uses", "`b` has no uses"}


def test_alias_pure_rename_fires():
    src = """\
.decl src(x: number, y: number)
src(1, 2).
.decl ali(x: number, y: number)
ali(X, Y) :- src(X, Y).
.decl out(x: number)
out(X) :- ali(X, Y), pos(Y).
"""
    assert "alias-inline" in cats(src)


def test_alias_projection_kept():
    src = """\
.decl src(x: number, y: number)
src(1, 2).
.decl some(x: number)
some(X) :- src(X, _).
.decl out(x: number)
out(X) :- some(X).
"""
    assert "alias-inline" not in cats(src)


def test_negated_use_fires():
    src = """\
.decl ray(a: number, p: number, b: number)
ray(1, 2, 3).
.decl painted(p: number)
painted(P) :- ray(_, P, _).
.decl out(p: number)
out(P) :- grid(P), !painted(P).
"""
    assert "negated-use" in cats(src)


def test_negated_use_needs_all_refs_negated():
    src = """\
.decl ray(a: number, p: number, b: number)
ray(1, 2, 3).
.decl painted(p: number)
painted(P) :- ray(_, P, _).
.decl out(p: number)
out(P) :- painted(P).
out(P) :- grid(P), !painted(P).
"""
    assert "negated-use" not in cats(src)


def test_comp_input_not_inlinable():
    src = """\
.comp Parse {
    .decl node(col: number)
    .decl mark(col: number)
    mark(C) :- cell(C), !node(C).
}
.init parse = Parse
parse.node(C) :- seed(C).
.decl out(c: number)
out(C) :- parse.mark(C).
"""
    assert "negated-use" not in cats(src)


def test_choice_tag_same_section_fires():
    src = """\
.type Choice = A {} | B {}
.decl impl_choice(ch: Choice)
impl_choice($A()). impl_choice($B()).
.decl f(ch: Choice, p: number)
f($A(), P) :- g(P).
f($B(), P) :- g(P).
.decl out(p: number)
out(P) :- f(Ch, P), impl_choice(Ch).
"""
    assert "choice-tag" in cats(src)


def test_choice_tag_no_enumerator_kept():
    src = """\
.type Choice = A {} | B {}
.decl f(ch: Choice, p: number)
f($A(), P) :- g(P).
f($B(), P) :- g(P).
.decl out(p: number)
out(P) :- f(_, P).
"""
    assert "choice-tag" not in cats(src)


def test_choice_tag_across_sections_kept():
    src = """\
.type Choice = A {} | B {}
.decl impl_choice(ch: Choice)
impl_choice($A()). impl_choice($B()).
.decl f(ch: Choice, p: number)
// --- A ---
f($A(), P) :- g(P).
// --- B ---
f($B(), P) :- g(P).
.decl out(p: number)
out(P) :- f(Ch, P), impl_choice(Ch).
"""
    assert "choice-tag" not in cats(src)


def test_subsumed_atom():
    src = """\
.decl out(x: number)
out(X) :- r(X, _), r(X, Y), pos(Y).
"""
    fs = [f for f in lint_rewrites(src) if f[0] == "subsumed-atom"]
    assert len(fs) == 1


def test_named_complement():
    src = """\
.comp Consts {
    .decl bg(c: number) bg(0).
}
.init c = Consts
.decl out(p: number, col: number)
out(P, Col) :- grid(P, Col), Col != BG, c.bg(BG).
"""
    assert "named-complement" in cats(src)


def test_named_complement_needs_singleton():
    src = """\
.comp Consts {
    .decl bg(c: number)
    bg(0). bg(5).
}
.init c = Consts
.decl out(p: number, col: number)
out(P, Col) :- grid(P, Col), Col != BG, c.bg(BG).
"""
    assert "named-complement" not in cats(src)


def test_decl_placement():
    src = """\
.decl helper(x: number)
.decl out(x: number)
// --- CaseA ---
helper(X) :- g(X).
out(X) :- helper(X).
"""
    fs = [f for f in lint_rewrites(src) if f[0] == "decl-placement"]
    assert any("`helper`" in f[2] for f in fs)


def test_long_rule():
    long = "out(P) :- " + ", ".join(f"g{i}(P)" for i in range(20)) + "."
    src = f".decl out(p: number)\n{long}\n"
    assert "long-rule" in cats(src)


def test_parse_error_is_a_finding():
    fs = lint_rewrites("ink(P :- in(P).\n")
    assert fs[0][0] == "parse-error"


def test_single_consumer_count_projection_kept():
    src = """\
.decl palette(col: number)
palette(Col) :- g(_, Col).
.decl out(n: number)
out(N) :- N = count : { palette(_) }.
"""
    assert "single-consumer" not in cats(src, hints=True)


def test_pass_through_recursive_kept():
    src = """\
.decl trace(p: number)
trace(P) :- seed(P).
trace(P2) :- trace(P), step(P, P2).
.decl traced(p: number)
traced(P) :- trace(P).
.decl out(p: number)
out(P) :- traced(P).
"""
    assert "pass-through" not in cats(src, hints=True)


def test_domain_enumerator_inline_binder_kept():
    src = """\
.decl helper(p: number, a: number) inline
helper(P, A) :- g(P, A).
.decl axis_elem(a: number)
axis_elem(0). axis_elem(1).
.decl out(p: number)
out(P) :- axis_elem(A), helper(P, A).
"""
    assert "domain-enumerator" not in cats(src, hints=True)


def test_chain_join_absorbed_partner_fires():
    src = """\
.decl stage(id: number)
stage(X) :- seed(X, _).
.decl lookup(id: number, v: number)
lookup(X, V) :- table(X, V, _).
.decl out(v: number)
out(V) :- stage(X), lookup(X, V).
"""
    assert "chain-join" in cats(src, hints=True)


def test_chain_join_shared_partner_kept():
    src = """\
.decl stage(id: number)
stage(X) :- seed(X, _).
.decl lookup(id: number, v: number)
lookup(X, V) :- table(X, V, _).
.decl other(v: number)
other(V) :- lookup(0, V), keep(V).
.decl out(v: number)
out(V) :- stage(X), lookup(X, V).
"""
    assert "chain-join" not in cats(src, hints=True)


def test_cross_choice_fires():
    src = """\
.type Choice = A {} | B {}
.decl out(p: number)
out(P) :- g(P, Ch), (Ch = $A(), x(P) ; Ch = $B(), y(P)).
"""
    assert "cross-choice" in cats(src)


def test_cross_choice_test_split_kept():
    src = """\
.type Choice = A {} | B {}
.decl out(p: number)
out(P) :- g(P), (t(P) ; !t(P), u(P)).
"""
    assert "cross-choice" not in cats(src)


def test_common_subexpr_same_head_suggests_disjunction():
    src = """\
.decl out(p: number, col: number)
out(P, Col) :- a(P, Q), b(Q, R), c(R, Col), d(Col).
out(P, Col) :- a(P, Q), b(Q, R), c(R, Col), e(Col).
"""
    fs = [f for f in lint_rewrites(src, hints=True) if f[0] == "common-subexpr"]
    assert len(fs) == 1 and "disjunction" in fs[0][2]


def test_common_subexpr_different_heads_no_merge():
    src = """\
.decl p(col: number)
.decl q(col: number)
p(Col) :- a(P, Q), b(Q, R), c(R, Col), d(Col).
q(Col) :- a(P, Q), b(Q, R), c(R, Col), e(Col).
"""
    fs = [f for f in lint_rewrites(src, hints=True) if f[0] == "common-subexpr"]
    assert len(fs) == 1 and "disjunction" not in fs[0][2]


def test_common_subexpr_across_sections_kept():
    src = """\
.decl out(p: number, col: number)
// --- One ---
out(P, Col) :- a(P, Q), b(Q, R), c(R, Col), d(Col).
// --- Two ---
out(P, Col) :- a(P, Q), b(Q, R), c(R, Col), e(Col).
"""
    assert "common-subexpr" not in cats(src, hints=True)


def test_common_subexpr_across_tags_kept():
    src = """\
.type Choice = A {} | B {}
.decl out(ch: Choice, col: number)
out($A(), Col) :- a(P, Q), b(Q, R), c(R, Col), d(Col).
out($B(), Col) :- a(P, Q), b(Q, R), c(R, Col), e(Col).
"""
    assert "common-subexpr" not in cats(src, hints=True)


def test_hints_gated():
    src = """\
.decl stage(x: number)
stage(X) :- g(X), !h(X).
.decl out(x: number)
out(X) :- stage(X).
"""
    assert cats(src) == []
    assert "single-consumer" in cats(src, hints=True)


def test_hint_argmax():
    src = """\
.decl beaten(x: number)
beaten(X) :- score(X, N), score(_, N2), N2 > N.
.decl out(x: number)
out(X) :- score(X, _), !beaten(X).
"""
    assert "argmax" in cats(src, hints=True)
    assert "argmax" not in cats(src)
