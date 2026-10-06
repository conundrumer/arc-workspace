"""The annotation reader over a comment list: a line off its form is a
problem, never a line read as something else. A reader that takes the
wrong input passes silently in use."""

from engine import DeclId
from solver import annotations
from solver.annotations import (
    ClaimKind,
    IgnoreForm,
    NamedVerdict,
    Plausibility,
    VerdictWord,
)
from solver.category import Category
from solver.problems import InSolver, ProblemKind
from tests.solver.fake import adt, comment, program, relation

BAND = DeclId(9)


def test_forms_and_their_places() -> None:
    parsed = program(
        types=[adt(1, "Choice", 7, [("Cut", 7), ("Lattice", 11)])],
        relations=[relation(9, "band", 20)],
        comments=[
            comment(1, "// 0000aaaa"),
            comment(2, "// @keywords: lines panels"),
            comment(3, "// the panels, read off the lines"),
            comment(4, "// @rule cut: panels are cut by the lines"),
            comment(5, "//     @approximated: an even lattice"),
            comment(6, "//     @witness uneven: variant other"),
            comment(8, "// @scene even: the lines stand evenly"),
            comment(9, "// @witness unequal: ordinary Lattice & Cut"),
            comment(10, "//     @relaxed even"),
            comment(16, "// @ignore: single-consumer — kept for reading"),
            comment(17, "// @store: variant stored", BAND),
            comment(18, "// @ignore: dead — no reason", BAND),
            comment(19, "// @ignore: derive p=Q — named", BAND),
            comment(21, "// @invariant: retired"),
            comment(22, "// @frob x"),
            comment(23, "// @ignore: no such category — x"),
            comment(24, "// @relaxed even"),
            comment(25, "// --- Cut, Lattice(a=B): the two ---"),
        ])
    got, problems = annotations.read(parsed)
    assert [(f.word, f.value) for f in got.header] == [
        ("keywords", "lines panels")]
    assert [c.line for c in got.header_prose] == [3]
    rule, scene = got.claims
    assert (rule.kind, rule.slug, rule.constructor) == (
        ClaimKind.RULE, "cut", None)
    assert [w.id for w in rule.approximated[0].witnesses] == ["uneven"]
    assert (scene.kind, scene.constructor) == (ClaimKind.SCENE, "Lattice")
    uneven, unequal = got.witnesses
    assert (uneven.approximates, uneven.verdict) == ("cut", VerdictWord.OTHER)
    assert (unequal.plausibility, unequal.verdict, unequal.relaxed,
            unequal.constructor) == (
        Plausibility.ORDINARY, NamedVerdict("Lattice & Cut"), ("even",),
        "Lattice")
    (store,) = got.stores
    assert (store.relation, store.above, store.verdict) == (
        None, BAND, VerdictWord.STORED)
    single, dead, derive = got.ignores
    # The lint form stands on its declaration only directly above it.
    assert (single.category, single.above) == (Category.SINGLE_CONSUMER, None)
    assert (dead.category, dead.above) == (Category.DEAD, None)
    assert (derive.form, derive.name, derive.above) == (
        IgnoreForm.DERIVE, "p=Q", BAND)
    (marker,) = got.markers
    assert [p.name for p in marker.parts] == ["Cut", "Lattice(a=B)"]
    assert marker.gloss == "the two"
    assert [(p.kind, p.place) for p in problems] == [
        (ProblemKind.RETIRED_FORM, InSolver(21)),
        (ProblemKind.UNKNOWN_FORM, InSolver(22)),
        (ProblemKind.UNKNOWN_IGNORE_CATEGORY, InSolver(23)),
        (ProblemKind.OFF_FORM, InSolver(24)),
    ]
