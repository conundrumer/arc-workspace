"""Rewrite-lint rules: each fires on its corpus before-shape and stays
quiet on the kept idiom next to it."""

from dl.rewrite_lint import _elem_tables, lint_rewrites


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


def test_negated_use_keeps_record_projection():
    src = """\
.decl clash(k: number)
clash([1, 2]).
.decl broken(d: number)
broken(D) :- clash([D, _]).
.decl out(d: number)
out(D) :- cand(D), !broken(D).
"""
    assert "negated-use" not in cats(src)


def test_comp_idiom_clash_fires():
    src = """\
.decl interior(id: number, p: number, col: number)
interior(1, 2, 3).
.decl mixed(id: number)
mixed(Id) :- interior(Id, _, C1), interior(Id, _, C2), C1 != C2.
.decl out(id: number)
out(Id) :- mixed(Id).
"""
    fs = [f for f in lint_rewrites(src, hints=True) if f[0] == "comp-idiom"]
    assert len(fs) == 1
    assert "docs/wf-solver/proposals/multi_cell.md" in fs[0][2]


def test_comp_idiom_pair_relation_kept():
    src = """\
.decl tile(t: number, p: number, col: number)
tile(1, 2, 3).
.decl differs(t: number, t2: number)
differs(T, T2) :- tile(T, P, C1), tile(T2, P, C2), C1 != C2, T != T2.
.decl out(t: number)
out(T) :- differs(T, _).
"""
    assert "comp-idiom" not in cats(src, hints=True)


def test_comp_idiom_pairing_map_kept():
    src = """\
.decl band(a: number, l1: number, l2: number)
band(1, 2, 3).
.decl cs(a: number, l: number, col: number)
cs(1, 2, 3).
.decl broken(a: number)
broken(A) :- band(A, L1, L2), cs(A, L1, C1), cs(A, L2, C2), C1 != C2.
.decl out(a: number)
out(A) :- broken(A).
"""
    assert "comp-idiom" not in cats(src, hints=True)


def test_comp_idiom_lib_pair_relation_kept():
    # `same_line` stays undeclared so it resolves to lib: a lib relation
    # reading both compared values relates the pair as a local one does.
    src = """\
.decl mark(c: number, p: number)
mark(1, 2).
.decl aligned(c: number)
aligned(C) :- mark(C, P), mark(C, Q), P != Q, axis_elem(A), same_line(A, P, Q).
.decl out(c: number)
out(C) :- aligned(C).
"""
    assert "comp-idiom" not in cats(src, hints=True)


def test_lib_idiom_in_params_fires():
    src = """\
.comp Params {
    .decl beside(p: Position, q: Position)
    beside(P, Q) :- dir_elem(D), step_offset(D, S), compose(P, S, Q).
}
.init params = Params
.decl out(p: Position)
out(P) :- params.beside(P, _).
"""
    assert "lib-idiom" in cats(src)


def test_comp_idiom_primitive_kept():
    src = """\
.decl line(a: number)
line(A) :- mark(P1), mark(P2), split(P1, A, _, Ac), split(P2, A, _, Ac), P1 != P2.
.decl out(a: number)
out(A) :- line(A).
"""
    assert "comp-idiom" not in cats(src, hints=True)


def test_comp_idiom_count_kept():
    src = """\
.decl mark(ln: number, p: number)
mark(1, 2).
.decl tripled(ln: number)
tripled(L) :- mark(L, P1), mark(L, P2), mark(L, P3), P1 != P2, P1 != P3, P2 != P3.
.decl out(ln: number)
out(L) :- tripled(L).
"""
    assert "comp-idiom" not in cats(src, hints=True)


def test_comp_idiom_d4_image_fires():
    src = """\
.decl clean(p: number, col: number)
clean(1, 2).
.decl mismatch(d: number)
mismatch(D) :- d4_elem(D), clean(P, Col), apply(D, P, P2), clean(P2, C2), Col != C2.
.decl out(d: number)
out(D) :- d4_elem(D), !mismatch(D).
"""
    fs = [f for f in lint_rewrites(src, hints=True) if f[0] == "comp-idiom"]
    assert len(fs) == 1 and "D4Map.conflict" in fs[0][2]


def test_comp_idiom_shift_image_fires():
    src = """\
.decl cell(p: number, col: number)
cell(1, 2).
.decl broken(delta: number)
broken(Delta) :- cand(Delta), cell(P, Col), compose(P, Delta, P2), cell(P2, C2), Col != C2.
.decl out(delta: number)
out(Delta) :- cand(Delta), !broken(Delta).
"""
    fs = [f for f in lint_rewrites(src, hints=True) if f[0] == "comp-idiom"]
    assert len(fs) == 1 and "OffsetInvariance.mismatch" in fs[0][2]


def test_comp_idiom_is_a_hint():
    src = """\
.decl interior(id: number, p: number, col: number)
interior(1, 2, 3).
.decl mixed(id: number)
mixed(Id) :- interior(Id, _, C1), interior(Id, _, C2), C1 != C2.
.decl out(id: number)
out(Id) :- mixed(Id).
"""
    assert "comp-idiom" not in cats(src)


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
.comp Params {
    .decl bg(c: number) bg(0).
}
.init params = Params
.decl out(p: number, col: number)
out(P, Col) :- grid(P, Col), Col != BG, params.bg(BG).
"""
    assert "named-complement" in cats(src)


def test_named_complement_needs_singleton():
    src = """\
.comp Params {
    .decl bg(c: number)
    bg(0). bg(5).
}
.init params = Params
.decl out(p: number, col: number)
out(P, Col) :- grid(P, Col), Col != BG, params.bg(BG).
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


def test_long_rule_under_a_plan():
    """A `.plan` sits in the rule's span after the terminating period, and
    the body it names is still on one line."""
    long = "out(P) :- " + ", ".join(f"g{i}(P)" for i in range(20)) + "."
    assert "long-rule" in cats(f".decl out(p: number)\n{long}\n.plan 0:(2, 1)\n")
    assert "long-rule" in cats(f".decl out(p: number)\n{long} .plan 0:(2, 1)\n")


def test_long_rule_already_wrapped_stays_quiet():
    """A body that runs on to a later line is wrapped, however long its
    first line is."""
    head = "out(P) :- " + ", ".join(f"g{i}(P)" for i in range(20)) + ","
    src = f".decl out(p: number)\n{head}\n    g20(P).\n"
    assert len(head) > 100
    assert "long-rule" not in cats(src)


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


def test_domain_enumerator_same_type_column_fires():
    src = """\
.decl beside(p: number, d: Dir, q: number)
beside(P, D, Q) :- g(P, D, Q).
.decl out(p: number)
out(P) :- dir_elem(D), beside(P, D, _).
"""
    assert "domain-enumerator" in cats(src, hints=True)


def test_elem_tables_close_wider_through_subtypes_and_unions():
    lib = """\
.type A <: number
.type B <: A
.type C <: number
.type AC = A | C
.type Rec = [x: number]
.decl a_elem(x: A)
.decl b_elem(x: B)
.decl pair(x: A, y: A)
"""
    elem_type, wider = _elem_tables(lib)
    assert elem_type == {"a_elem": "A", "b_elem": "B"}
    assert wider["A"] == {"AC"}          # union member; `number` is no domain
    assert wider["C"] == {"AC"}
    assert wider["B"] == {"A", "AC"}     # subtype, closed through A
    assert "Rec" not in wider


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


def test_common_subexpr_negated_head_kept():
    src = """\
.decl bad(p: number)
.decl out(p: number)
bad(P) :- a(P, Q), b(Q, R), c(R, Col), d(Col).
out(P) :- a(P, Q), b(Q, R), c(R, Col), !bad(P).
"""
    assert "common-subexpr" not in cats(src, hints=True)


def test_single_consumer_impl_choice_kept():
    src = """\
.decl impl_choice(ch: number)
impl_choice(X) :- g(X), !h(X).
.decl out(x: number)
out(X) :- impl_choice(X).
"""
    assert "single-consumer" not in cats(src, hints=True)


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


def test_argmax_pairwise_head_kept():
    src = """\
.decl beaten(x: number, y: number)
beaten(X, Y) :- score(X, N), score(Y, N2), N2 > N.
.decl out(x: number)
out(X) :- score(X, _), !beaten(X, _).
"""
    assert "argmax" not in cats(src, hints=True)


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


def test_raw_aggregate_local_comp_kept():
    src = """\
.comp Helper {
    .decl item(x: number)
    .decl size(n: number)
    size(N) :- N = count : { item(X) }.
}
.init h = Helper
h.item(1).
.decl out(n: number)
out(N) :- h.size(N).
"""
    assert "raw-aggregate" not in cats(src)


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


def test_const_join_lookup_kept():
    src = PARAMS + """\
.decl out(p: number)
out(P) :- in(P, M), params.template(P, M), params.marker(M).
"""
    assert "const-join" not in cats(src, hints=True)


def test_const_join_named_constant_kept():
    src = PARAMS + """\
.decl marks(p: number)
marks(P) :- params.template(P, M), params.marker(M).
.decl out(p: number)
out(P) :- in(P, _), marks(P).
"""
    assert "const-join" not in cats(src, hints=True)


def test_const_join_constant_instance_kept():
    src = PARAMS + """\
.init tview = Reframe<number>
tview.cell(P, M) :- params.template(P, M).
tview.outer(P) :- tview.cell(P, M), params.marker(M).
.decl out(p: number)
out(P) :- in(P, _), tview.outer(P).
"""
    assert "const-join" not in cats(src, hints=True)


def test_const_join_in_disjunction_fires():
    src = PARAMS + """\
.decl out(p: number)
out(P) :- in(P, _), ( params.template(P, M), params.marker(M) ; params.template(P, 0) ).
"""
    assert "const-join" in cats(src, hints=True)


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


def test_typed_order_inequality_kept():
    src = """\
.decl out(p: Position, c: Color)
out(P, C) :- in(P, C), in(_, C2), C != C2.
"""
    assert "typed-order" not in cats(src)


def test_typed_order_ident_comparison_fires():
    src = """\
.decl piece(i: Ident, p: Position)
piece(I, P) :- in(P, _), conn8(P, I).
.decl out(p: Position, c: Color)
out(P, C) :- in(P, C), piece(I, P), piece(I2, _), I < I2.
"""
    assert "typed-order" in cats(src)


def test_typed_order_record_field_fires():
    src = """\
.type Pair = [c: Color, k: number]
.decl pr(x: Pair)
pr([C, K]) :- in(P, C), dir_elem(D), dist(P, D, K).
.decl out(p: Position, c: Color)
out(P, C) :- in(P, C), pr([C1, _]), pr([C2, _]), C1 < C2.
"""
    assert "typed-order" in cats(src)


def test_typed_order_min_over_color_fires():
    src = """\
.decl out(p: Position, c: Color)
out(P, C) :- in(P, _), C = min C2 : { in(_, C2) }.
"""
    assert "typed-order" in cats(src)


def test_typed_order_ordinal_over_color_fires():
    src = """\
.init rank = Ordinal<Unit>
rank.idx_set($U(), C) :- in(_, C).
.decl out(p: Position, c: Color)
out(P, C) :- in(P, C), rank.rank($U(), C, _).
"""
    fs = [f for f in lint_rewrites(src) if f[0] == "typed-order"]
    assert len(fs) == 1 and "`Ordinal` ranks" in fs[0][2]


def test_typed_order_ordinal_over_distance_kept():
    src = """\
.init rank = Ordinal<Unit>
rank.idx_set($U(), K) :- in(P, _), dir_elem(D), dist(P, D, K).
.decl out(p: Position, c: Color)
out(P, C) :- in(P, C), rank.rank($U(), _, _).
"""
    assert "typed-order" not in cats(src)


def test_typed_order_order_before_fed_by_comparison_fires():
    src = """\
.init seq = Order<Unit, Color>
seq.elem($U(), C) :- in(_, C).
seq.before($U(), C, C2) :- in(_, C), in(_, C2), C < C2.
.decl out(p: Position, c: Color)
out(P, C) :- in(P, C), seq.rank($U(), C, _).
"""
    assert "typed-order" in cats(src)


def test_typed_order_stored_order_kept():
    src = """\
.comp Params { .decl ahead(a: Color, b: Color) }
.init params = Params
.init seq = Order<Unit, Color>
seq.elem($U(), C) :- in(_, C).
seq.before($U(), C, C2) :- params.ahead(C, C2).
.decl out(p: Position, c: Color)
out(P, C) :- in(P, C), seq.rank($U(), C, _).
"""
    assert "typed-order" not in cats(src)


def test_typed_order_proposal_comp_kept():
    src = """\
.comp Ladder<Key> {
    .decl c(key: Key, c: Color)
    .decl low(key: Key, c: Color)
    low(K, C) :- c(K, C), c(K, C2), C < C2.
}
.init ladder = Ladder<Unit>
ladder.c($U(), C) :- in(_, C).
.decl out(p: Position, c: Color)
out(P, C) :- in(P, C), ladder.low($U(), C).
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
    // --- shared ---
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
    assert f[1] == 4   # the `bg` declaration's line
    assert f[2].startswith("`bg` is shared, and `$B()` never reads it")


def test_shared_read_every_case_kept():
    src = SHARED_HEAD + """\
out(P, C, $A()) :- in(P, C), params.bg(C), params.mark(C).
out(P, C, $B()) :- in(P, C), params.bg(C).
"""
    assert "shared-read" not in cats(src)


def test_shared_read_through_a_stage_kept():
    src = SHARED_HEAD + """\
.decl ink(p: Position, col: Color)
ink(P, C) :- in(P, C), !params.bg(C).
out(P, C, $A()) :- ink(P, C), params.mark(C).
out(P, C, $B()) :- ink(P, C).
"""
    assert "shared-read" not in cats(src)


def test_shared_read_through_a_lib_instance_kept():
    src = SHARED_HEAD + """\
.decl impl(ch: Choice)
impl($A()). impl($B()).
.init parts = Objects<Choice>
parts.cell(Ch, P) :- in(P, C), !params.bg(C), impl(Ch).
out(P, C, Ch) :- parts.piece(Ch, P, _), in(P, C), params.mark(C).
"""
    assert "shared-read" not in cats(src)


def test_shared_read_takes_the_case_a_stage_serves():
    """An untagged rule that reads a relation only one case states serves
    that case alone, so the parameters it reads reach that case alone."""
    src = SHARED_HEAD + """\
.decl impl(ch: Choice)
impl($A()).
out(P, C, Ch) :- impl(Ch), in(P, C), params.bg(C), params.mark(C).
out(P, C, $B()) :- in(P, C).
"""
    fs = [f for f in lint_rewrites(src) if f[0] == "shared-read"]
    assert [f[1] for f in fs] == [4]
    assert "`$B()` never reads it" in fs[0][2]


def test_shared_read_record_choice_reads_each_component():
    src = """\
.type Step = Rot {} | Look {}
.type Paint = Keep {} | Cover {}
.type Choice = [s: Step, p: Paint]
.comp Params {
    // --- shared ---
    .decl bg(col: Color) bg(0).
}
.init params = Params
.decl step_choice(s: Step)
step_choice($Rot()). step_choice($Look()).
.decl out(p: Position, col: Color, ch: Choice)
out(P, C, [S, $Keep()]) :- in(P, C), params.bg(C), step_choice(S).
out(P, C, [S, $Cover()]) :- in(P, C), step_choice(S).
"""
    fs = [f for f in lint_rewrites(src) if f[0] == "shared-read"]
    assert [f[2] for f in fs] == [
        "`bg` is shared, and `$Cover()` never reads it; a parameter one "
        "case never reads belongs under that case's marker",
    ]


def test_negated_value_fires_on_off_edge_test():
    src = """\
.decl out(p: Position)
out(P) :- in(P, _), params.d(D), dist(P, D, K), K != 0.
"""
    fs = lint_rewrites(src)
    assert [f[0] for f in fs] == ["negated-value"]
    assert fs[0][2] == "`dist(P, D, K), K != 0` ⇒ `!dist(P, D, 0)`"


def test_negated_value_keeps_a_read_value():
    src = """\
.decl out(p: Position, k: number)
out(P, K) :- in(P, _), params.d(D), dist(P, D, K), K != 0.
"""
    assert "negated-value" not in cats(src)


def test_negated_value_skips_a_primitive_that_introduces_variables():
    src = """\
.decl out(p: Position)
out(P) :- in(P, _), params.d(D), dist_pair(P, D, K, _), K != 0.
"""
    assert "negated-value" not in cats(src)


def test_negated_use_rewrites_a_wrapper_over_a_bound_primitive():
    src = """\
.decl key(p: Position, d: Dir)
key(P, D) :- dist(P, D, 0).
.decl out(p: Position)
out(P) :- in(P, _), params.d(D), !key(P, D).
"""
    assert "negated-use" in cats(src)


def test_negated_use_keeps_a_wrapper_that_drops_a_primitive_column():
    src = """\
.decl key(p: Position)
key(P) :- crop(P, _, _).
.decl out(p: Position)
out(P) :- in(P, _), !key(P).
"""
    assert "negated-use" not in cats(src)
