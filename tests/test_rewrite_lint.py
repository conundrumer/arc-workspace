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


def test_comp_idiom_multi_cell_kept():
    # Two reads differing in one column alone state a multi-cell test.
    # No lib relation holds it, so the pair draws no hint.
    src = """\
.decl interior(id: number, p: number, col: number)
interior(1, 2, 3).
.decl mixed(id: number)
mixed(Id) :- interior(Id, _, C1), interior(Id, _, C2), C1 != C2.
.decl out(id: number)
out(Id) :- mixed(Id).
"""
    assert "comp-idiom" not in cats(src, hints=True)


def test_comp_idiom_axis_fires():
    # `A != A2` over Axis states the other axis, which `perp` states.
    src = """\
.decl line_col(p: Position, a: Axis, col: Color)
line_col(1, 2, 3).
.decl crossed(p: Position)
crossed(P) :- line_col(P, A, _), line_col(P, A2, _), A != A2.
.decl out(p: Position)
out(P) :- crossed(P).
"""
    fs = [f for f in lint_rewrites(src, hints=True) if f[0] == "comp-idiom"]
    assert len(fs) == 1
    assert "perp(A, A2)" in fs[0][2]


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


def test_subsumed_atom():
    src = """\
.decl out(x: number)
out(X) :- r(X, _), r(X, Y), pos(Y).
"""
    fs = [f for f in lint_rewrites(src) if f[0] == "subsumed-atom"]
    assert len(fs) == 1


def test_named_complement():
    src = """\
.comp Params {
    .decl bg(c: number) bg(0).
}
.init params = Params
.decl out(p: number, col: number)
out(P, Col) :- grid(P, Col), Col != BG, params.bg(BG).
"""
    assert "named-complement" in cats(src)


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
    assert "long-clause" in cats(src)


def test_parse_error_is_a_finding():
    fs = lint_rewrites("ink(P :- in(P).\n")
    assert fs[0][0] == "parse-error"


def test_domain_enumerator_bound_variable_fires():
    src = """\
.decl axis_elem(a: number)
axis_elem(0). axis_elem(1).
.decl src(p: number, a: number)
src(P, A) :- g(P, A).
.decl out(p: number)
out(P) :- axis_elem(A), src(P, A).
"""
    assert "domain-enumerator" in cats(src, hints=True)


def test_domain_enumerator_wider_column_kept():
    # `dir_elem` holds four of the eight Dir8 elements, so over a Dir8
    # column the atom is a filter.
    src = """\
.decl beside(p: number, d: Dir8, q: number)
beside(P, D, Q) :- g(P, D, Q).
.decl out(p: number)
out(P) :- dir_elem(D), beside(P, D, _).
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


def test_cross_choice_fires():
    src = """\
.type Choice = A {} | B {}
.decl out(p: number)
out(P) :- g(P, Ch), (Ch = $A(), x(P) ; Ch = $B(), y(P)).
"""
    assert "cross-choice" in cats(src)


def test_common_subexpr_same_head_suggests_disjunction():
    src = """\
.decl out(p: number, col: number)
out(P, Col) :- a(P, Q), b(Q, R), c(R, Col), d(Col).
out(P, Col) :- a(P, Q), b(Q, R), c(R, Col), e(Col).
"""
    fs = [f for f in lint_rewrites(src, hints=True) if f[0] == "common-subexpr"]
    assert len(fs) == 1 and "disjunction" in fs[0][2]


def test_ignore_directive_silences_single_consumer():
    rest = """\
.decl stage(x: number)
stage(X) :- g(X), !h(X).
.decl out(x: number)
out(X) :- stage(X).
"""
    ignored = f"// @ignore: single-consumer — the name states the stage\n{rest}"
    assert "single-consumer" not in cats(ignored, hints=True)
    assert "single-consumer" in cats(rest, hints=True)


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


def test_raw_aggregate_fires():
    src = """\
.decl s(x: number, n: number)
s(1, 2).
.decl big(x: number)
big(X) :- s(X, N), N = max M : { s(_, M) }.
.decl out(x: number)
out(X) :- big(X).
"""
    assert "raw-aggregate" in cats(src)


PARAMS = """\
.comp Params {
    .decl template(p: number, col: number)
    template(1, 2).
    .decl marker(col: number)
    marker(2).
}
.init params = Params
"""


def test_hint_const_join_fires():
    src = PARAMS + """\
.decl out(p: number)
out(P) :- in(P, _), params.template(P, M), params.marker(M).
"""
    assert "const-join" in cats(src, hints=True)
    assert "const-join" not in cats(src)


def test_typed_order_color_comparison_fires():
    src = """\
.decl pale(c: Color)
pale(C) :- in(_, C), in(_, C2), C < C2.
.decl out(p: Position, c: Color)
out(P, C) :- in(P, C), pale(C).
"""
    fs = [f for f in lint_rewrites(src) if f[0] == "typed-order"]
    assert [f[1] for f in fs] == [2, 2]
    assert "a `Color`" in fs[0][2]


def test_typed_order_distance_bound_kept():
    src = """\
.comp Params { .decl gap(k: number) }
.init params = Params
.decl out(p: Position, c: Color)
out(P, C) :- in(P, C), dir_elem(D), dist(P, D, K), params.gap(K2), K < K2.
"""
    assert "typed-order" not in cats(src)


def test_choice_domain_fires():
    src = """\
.decl pick(k: number, p: Position) choice-domain k
pick(K, P) :- in(P, _), dir_elem(D), dist(P, D, K).
.decl out(p: Position, c: Color)
out(P, C) :- pick(_, P), in(P, C).
"""
    fs = [f for f in lint_rewrites(src) if f[0] == "choice-domain"]
    assert len(fs) == 1 and fs[0][1] == 1


SHARED_HEAD = """\
.type Choice = A {} | B {}
.comp Params {
    .decl bg(col: Color) bg(0).

    // --- A ---
    .decl mark(col: Color) mark(3).
}
.init params = Params
.decl out(p: Position, col: Color, ch: Choice)
"""


def test_shared_read_case_that_never_reads_fires():
    src = SHARED_HEAD + """\
out(P, C, $A()) :- in(P, C), params.bg(C), params.mark(C).
out(P, C, $B()) :- in(P, C).
"""
    [f] = [f for f in lint_rewrites(src) if f[0] == "shared-read"]
    assert f[1] == 3   # the `bg` declaration's line
    assert f[2].startswith("`bg` is shared, and `$B()` never reads it")


def test_shared_read_every_case_kept():
    src = SHARED_HEAD + """\
out(P, C, $A()) :- in(P, C), params.bg(C), params.mark(C).
out(P, C, $B()) :- in(P, C), params.bg(C).
"""
    assert "shared-read" not in cats(src)


def test_negated_value_fires_on_off_edge_test():
    src = """\
.decl out(p: Position)
out(P) :- in(P, _), params.d(D), dist(P, D, K), K != 0.
"""
    fs = lint_rewrites(src)
    assert [f[0] for f in fs] == ["negated-value"]
    assert fs[0][2] == "`dist(P, D, K), K != 0` ⇒ `!dist(P, D, 0)`"


def test_negated_use_rewrites_a_wrapper_over_a_bound_primitive():
    src = """\
.decl key(p: Position, d: Dir)
key(P, D) :- dist(P, D, 0).
.decl out(p: Position)
out(P) :- in(P, _), params.d(D), !key(P, D).
"""
    assert "negated-use" in cats(src)


