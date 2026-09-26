"""The cases a named `@ignore: derive` or `@ignore: store` line excludes.

A wrong match drops cases from the runner, and no run shows a case that is
missing."""

from itertools import combinations

from dl.annotations import DERIVE, STORE, Branch
from dl.models import CaseId, HeldCase, Space

P = Branch(DERIVE, "p", "Dom", 10)
Q = Branch(DERIVE, "q", "Rare", 20)
R = Branch(STORE, "r", "stored", 30)


def space() -> tuple[Space, dict[CaseId, HeldCase]]:
    """`Choice = A | B { s: Sub } | C` with `Sub = X | Y`, and every held
    `Choice` case with every non-empty set of the three branches."""
    s = Space(False, ["Choice"], {"Choice": {"A": [], "B": ["Sub"], "C": []},
                                  "Sub": {"X": [], "Y": []}})
    s.lines = [P, Q, R]
    runner: dict[CaseId, HeldCase] = {}
    for base in map(CaseId, ["A", "B(X)", "B(Y)", "C"]):
        for k in (1, 2, 3):
            for bs in combinations([P, Q, R], k):
                runner[s.case_id(base, bs)] = HeldCase(base, bs)
    return s, runner


def matched(name: str) -> set[tuple[str, frozenset[str]]] | None:
    s, runner = space()
    found = s.matching(name, runner)
    if found is None:
        return None
    return {(runner[c].base, frozenset(b.name for b in runner[c].branches))
            for c in found}


def test_one_branch() -> None:
    got = matched("q=Rare")
    assert got is not None and len(got) == 4 * 4
    assert all("q=Rare" in bs for _b, bs in got)


def test_two_branches_of_both_kinds() -> None:
    got = matched("r=stored & p=Dom")
    assert got == {(b, frozenset(bs)) for b in ["A", "B(X)", "B(Y)", "C"]
                   for bs in [{"p=Dom", "r=stored"},
                              {"p=Dom", "q=Rare", "r=stored"}]}


def test_constructors() -> None:
    got = matched("B & p=Dom")
    assert got is not None and {b for b, _ in got} == {"B(X)", "B(Y)"}
    assert len(got) == 2 * 4
    got = matched("Y & p=Dom")
    assert got is not None and {b for b, _ in got} == {"B(Y)"}
    got = matched("concept & p=Dom")
    assert got is not None and {b for b, _ in got} == {"A"}


def test_full_case() -> None:
    assert matched("C & p=Dom & q=Rare & r=stored") == {
        ("C", frozenset({"p=Dom", "q=Rare", "r=stored"}))}


def test_own_branch_named_again() -> None:
    """A line's `<name>` may list the line's own branch, which the line
    joins to it again."""
    assert matched("B & r=stored & r=stored") == matched("B & r=stored")
    assert matched("Y & q=Rare & p=Dom & q=Rare") == matched("Y & p=Dom & q=Rare")


def test_no_case() -> None:
    assert matched("Z & p=Dom") is None
    assert matched("p=Other") is None


def test_stored_value() -> None:
    """`<param>=stored` lists the stored value at a `@derive` line's point:
    the cases that take no branch there."""
    assert matched("p=stored & q=Rare") == {
        (b, frozenset(bs)) for b in ["A", "B(X)", "B(Y)", "C"]
        for bs in [{"q=Rare"}, {"q=Rare", "r=stored"}]}
    assert matched("B & r=stored & q=stored & p=stored") == {
        (b, frozenset({"r=stored"})) for b in ["B(X)", "B(Y)"]}
    assert matched("p=stored & p=Dom") is None
    assert matched("s=stored & q=Rare") is None
    s, _runner = space()
    assert s.denoted("p=stored & q=Rare") == "q=Rare"
    assert s.denoted("C & p=stored") == "C"
