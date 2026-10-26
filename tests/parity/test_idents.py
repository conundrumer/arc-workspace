"""The source of each `Ident` leaf of a program's relations
(`parity.idents.ident_sources`), and the text of a minted id."""

import pytest

from engine import RecordValue, RelationName
from engine.program import Program
from parity.idents import At, IdentSources, Minted, NoMembers, Stored, Unresolved, Writer, ident_paths, ident_sources
from solver.aggregate import parse_with_lib
from souffle.engine import SouffleEngine

PROGRAM = """
.type Pc = [e: Example, id: Ident]
.decl node(e: Example, p: Position)
.init comps = Components<Example>
comps.node(E, P) :- node(E, P).

.decl kept(e: Example, p: Position, id: Ident)
kept(E, P, Id) :- comps.label(E, P, Id).

.decl dropped(p: Position, id: Ident)
dropped(P, Id) :- comps.label(_, P, Id).

.decl fixed(id: Ident, col: Color)
fixed(0, 3).

.decl piece(pc: Pc)
piece([E, Id]) :- kept(E, _, Id).

.decl same(a: Pc, b: Pc)
same(A, B) :- piece(A), piece(B).

.init classes = Canon<Pc>
classes.equiv(A, B) :- same(A, B).

.decl class_of(pc: Pc, id: Ident)
class_of(A, Id) :- classes.id(A, Id).
"""


@pytest.fixture(scope="module")
def sources() -> IdentSources:
    engine = SouffleEngine(cache_dir=None)
    program = parse_with_lib(engine, PROGRAM)
    assert isinstance(program, Program), program
    return ident_sources(engine, program)


def test_a_relation_that_keeps_the_key_of_the_minting_relation_is_minted_at_it(sources: IdentSources):
    got = sources.of(RelationName((), "kept"), 2, ())
    assert got == Minted(RelationName(("comps",), "label"), 2, (0,), (1,), (At(0, ()),))


def test_a_relation_that_drops_the_key_is_unresolved(sources: IdentSources):
    got = sources.of(RelationName((), "dropped"), 1, ())
    assert got == Unresolved("the row leaves out the key of comps.label")


def test_a_number_a_fact_writes_is_stored(sources: IdentSources):
    assert sources.of(RelationName((), "fixed"), 0, ()) == Stored()


def test_a_lib_relation_reads_the_source_of_the_columns_of_its_type_parameter(sources: IdentSources):
    members = sources.of(RelationName(("classes",), "id"), 0, (1,))
    assert members == Minted(RelationName(("comps",), "label"), 2, (0,), (1,), (At(0, (0,)),))
    minted = sources.of(RelationName((), "class_of"), 1, ())
    assert minted == Minted(RelationName(("classes",), "id"), 1, (), (0,), ())


def test_a_column_that_holds_no_ident_has_no_source(sources: IdentSources):
    assert sources.of(RelationName((), "fixed"), 1, ()) is None


def test_the_ident_leaves_of_a_record_column_are_found_by_their_path(sources: IdentSources):
    info = sources.info(RelationName((), "piece"))
    assert info is not None
    assert list(ident_paths(info.shapes[0])) == [(1,)]


def test_a_minted_id_is_the_text_of_the_set_of_its_members(sources: IdentSources):
    label, classes = RelationName(("comps",), "label"), RelationName(("classes",), "id")

    def cell(r: int, c: int) -> RecordValue:
        return RecordValue((r, r, c, c))

    rows = {
        label: ((4, cell(1, 2), 7), (4, cell(1, 3), 7), (4, cell(2, 2), 8), (5, cell(1, 2), 7)),
        classes: ((RecordValue((4, 7)), 9), (RecordValue((4, 8)), 9)),
    }
    writer = Writer(sources, rows)
    minted = sources.of(RelationName((), "kept"), 2, ())
    assert isinstance(minted, Minted)
    assert writer.text(minted, 7, (4, cell(1, 2), 7)) == "{[1,1,2,2],[1,1,3,3]}"
    assert writer.text(minted, 7, (5, cell(1, 2), 7)) == "{[1,1,2,2]}"
    with pytest.raises(NoMembers):
        writer.text(minted, 8, (5, cell(1, 2), 8))
    classed = sources.of(RelationName((), "class_of"), 1, ())
    assert isinstance(classed, Minted)
    assert writer.text(classed, 9, (RecordValue((4, 7)), 9)) == "{[{[1,1,2,2],[1,1,3,3]}],[{[2,2,2,2]}]}"
