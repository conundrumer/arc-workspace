"""Body-lint checks: each fires on the shape it names and stays quiet next
to the legal form."""

from dl.lint import lint_body


def cats(src: str) -> list[str]:
    return [f[0] for f in lint_body(src)]


def test_reserved_decl_name_fires():
    src = """\
.decl count(n: number)
count(0).
"""
    fs = [f for f in lint_body(src) if f[0] == "reserved name"]
    assert len(fs) == 1
    assert fs[0][1] == 1
    assert "`count` is a Souffle reserved word" in fs[0][2]
    assert "rename it" in fs[0][2]


def test_reserved_init_name_fires():
    src = """\
.comp Tally<Key> {
    .decl n(key: Key, c: number)
}
.init count = Tally<Color>
"""
    fs = [f for f in lint_body(src) if f[0] == "reserved name"]
    assert [f[1] for f in fs] == [4]


def test_reserved_name_inside_comp_fires():
    src = """\
.comp Parse<Key> {
    .decl band(key: Key, p: Position)
}
"""
    fs = [f for f in lint_body(src) if f[0] == "reserved name"]
    assert [f[1] for f in fs] == [2]
    assert "`band`" in fs[0][2]


def test_reserved_type_and_comp_names_fire():
    src = """\
.type max <: number
.comp output {
    .decl v(x: number)
}
"""
    fs = [f for f in lint_body(src) if f[0] == "reserved name"]
    assert [f[1] for f in fs] == [1, 2]


def test_reserved_name_in_unparsable_source_fires():
    src = """\
.decl count(n: number)
count(0) :-
"""
    assert cats(src) == ["reserved name"]


def test_free_names_stay_quiet():
    # `tally` and `band_cell` are the renames; `type`, `plan`, and `init`
    # are reserved only with their leading dot.
    src = """\
.decl tally(n: number)
.decl band_cell(p: Position)
.decl type(x: number)
.decl plan(x: number)
.init init = Consts
"""
    assert "reserved name" not in cats(src)


def test_reserved_word_in_a_comment_stays_quiet():
    src = """\
// .decl count(n: number)
.decl tally(n: number)
"""
    assert "reserved name" not in cats(src)


def test_qualified_member_named_for_a_keyword_stays_quiet():
    # The check reads declared names, not uses, so a member access that
    # merely ends in a keyword is not a collision.
    src = """\
.decl v(x: number)
v(N) :- c.max(N).
"""
    assert "reserved name" not in cats(src)


def test_shadowed_type_argument_fires():
    src = """\
.comp Parse<Key> {
    .type KP = [key: Key, p_part: Position]
    .decl cell(key: Key, p: Position)
    .init box = BoxFrame<KP>
    box.cell([Ky, Q], P) :- cell(Ky, P), cell(Ky, Q).
}
.init parse = Parse<Unit>
"""
    fs = [f for f in lint_body(src) if f[0] == "shadowed type"]
    assert [f[1] for f in fs] == [4]
    assert "`KP` also names a type inside `BoxFrame`" in fs[0][2]
    assert "rename it" in fs[0][2]


def test_shadowed_type_reaches_through_a_nested_instance():
    src = """\
.comp Wrap<K> {
    .init b = BoxFrame<K>
    .decl cell(key: K, p: Position)
    b.cell(K, P) :- cell(K, P).
}
.type KP = [key: Unit, p_part: Position]
.init w = Wrap<KP>
"""
    fs = [f for f in lint_body(src) if f[0] == "shadowed type"]
    assert [f[1] for f in fs] == [7]
    assert "`Wrap`" in fs[0][2]


def test_free_type_argument_stays_quiet():
    # `KD` collides with nothing inside `BoxFrame`, type-parameter field
    # and all.
    src = """\
.comp Parse<Key> {
    .type KD = [key: Key, p_part: Position]
    .decl cell(key: Key, p: Position)
    .init box = BoxFrame<KD>
    box.cell([Ky, Q], P) :- cell(Ky, P), cell(Ky, Q).
}
.init parse = Parse<Unit>
"""
    assert "shadowed type" not in cats(src)


def test_type_argument_to_a_typeless_comp_stays_quiet():
    src = """\
.type KP = [key: Unit, p_part: Position]
.init tally = Mode<KP>
"""
    assert "shadowed type" not in cats(src)
