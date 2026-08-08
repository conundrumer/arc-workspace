"""Simplify-lint rules: each fires on its corpus before-shape and stays
quiet on the kept idiom next to it."""

from dl.simplify_lint import lint_simplify


def cats(src: str, advisory: bool = False) -> list[str]:
    return [f[0] for f in lint_simplify(src, advisory)]


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
    fs = lint_simplify(src)
    assert [f[0] for f in fs] == ["dead", "dead"]
    assert {f[2] for f in fs} == {"a", "b"}


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
.decl f(ch: Choice, p: number)
f($A(), P) :- g(P).
f($B(), P) :- g(P).
.decl out(p: number)
out(P) :- f(_, P).
"""
    assert "choice-tag" in cats(src)


def test_choice_tag_across_sections_kept():
    src = """\
.type Choice = A {} | B {}
.decl f(ch: Choice, p: number)
// --- A ---
f($A(), P) :- g(P).
// --- B ---
f($B(), P) :- g(P).
.decl out(p: number)
out(P) :- f(_, P).
"""
    assert "choice-tag" not in cats(src)


def test_subsumed_atom():
    src = """\
.decl out(x: number)
out(X) :- r(X, _), r(X, Y), pos(Y).
"""
    fs = [f for f in lint_simplify(src) if f[0] == "subsumed-atom"]
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
    fs = [f for f in lint_simplify(src) if f[0] == "decl-placement"]
    assert any(f[2].startswith("helper") for f in fs)


def test_long_rule():
    long = "out(P) :- " + ", ".join(f"g{i}(P)" for i in range(20)) + "."
    src = f".decl out(p: number)\n{long}\n"
    assert "long-rule" in cats(src)


def test_parse_error_is_a_finding():
    fs = lint_simplify("ink(P :- in(P).\n")
    assert fs[0][0] == "parse-error"


def test_advisory_gated():
    src = """\
.decl stage(x: number)
stage(X) :- g(X), !h(X).
.decl out(x: number)
out(X) :- stage(X).
"""
    assert cats(src) == []
    assert "single-consumer" in cats(src, advisory=True)


def test_advisory_argmax():
    src = """\
.decl beaten(x: number)
beaten(X) :- score(X, N), score(_, N2), N2 > N.
.decl out(x: number)
out(X) :- score(X, _), !beaten(X).
"""
    assert "argmax" in cats(src, advisory=True)
    assert "argmax" not in cats(src)
