"""The cases the row parity check runs take each ALT of the solver, and the relations it leaves out are `skip` or `uncompared` by the rule of `parity.rerun`."""

from dataclasses import replace
from pathlib import Path

import pytest

from parity import NameMap, case_name, rerun

SOLVER = """// aaaaaaaa
// @keywords: test
// input: a grid
// output: the grid

.type DecChoice = Table {} | Count {}
.type Body = Lookup {} | And {}
.type Choice = [d: DecChoice, b: Body]

.decl out(p: Position, col: Color, c: Choice)
out(P, C, [$Table(), $Lookup()]) :- in(P, C).

.decl seed(k: number)
seed(1).

.decl marked(k: number)
marked(K) :- seed(K), in(_, _).

.init bbox = Bbox<number>
bbox.cell(K, P) :- seed(K), in(P, _).
"""


@pytest.fixture
def loaded(tmp_path: Path) -> rerun.Loaded:
    file = tmp_path / "aaaaaaaa.dl"
    file.write_text(SOLVER)
    got = rerun.load_once("aaaaaaaa", file)
    assert isinstance(got, rerun.Loaded)
    return got


def test_the_cases_take_each_alt_of_two_groups(loaded: rerun.Loaded) -> None:
    names = [case_name(loaded.solver, c, loaded.names) for c in rerun.cases_to_run(loaded)]
    assert names[0] == "concept"
    taken = {c for case in rerun.cases_to_run(loaded) for c in rerun.constructors(case.base)}
    assert taken == {"Table", "Count", "Lookup", "And"}
    assert len(names) == 3


def test_a_relation_is_skipped_or_uncompared_by_its_kind(loaded: rerun.Loaded) -> None:
    mapped, left = rerun.classify(loaded, {}, [])
    assert mapped == []
    verdicts = {entry["name"]: (entry["verdict"], rerun.Reason(entry["reason"])) for entry in left}
    assert verdicts["souffle:in"] == ("skip", rerun.Reason.INPUT)
    assert verdicts["souffle:dir_elem"] == ("skip", rerun.Reason.LIB)
    assert verdicts["souffle:bbox.box"] == ("skip", rerun.Reason.LIB)
    assert verdicts["souffle:seed"] == ("skip", rerun.Reason.FACTS)
    assert verdicts["souffle:marked"] == ("uncompared", rerun.Reason.NO_ENTRY)
    assert verdicts["souffle:bbox.cell"] == ("uncompared", rerun.Reason.NO_ENTRY)


def test_an_arclog_relation_that_no_relation_of_the_run_stands_for_is_uncompared(loaded: rerun.Loaded) -> None:
    _, left = rerun.classify(loaded, {}, ["&ghost"])
    assert {"name": "&ghost", "verdict": "uncompared", "reason": rerun.Reason.NO_RELATION.value} in left


def test_a_folded_relation_is_paired_with_the_entry_of_its_check_relation(loaded: rerun.Loaded) -> None:
    names = NameMap.of({"relations": {"&check_marked": [{"component": [], "relation": "marked", "path": "marked"}]},
                        "constructors": {}, "unmapped": []})
    columns = {"&check_marked": {"marked": [[{"leaf": [], "label": "K", "field": None, "example": False}]]}}
    mapped, left = rerun.classify(replace(loaded, names=names), columns, [])
    assert [(at.relation.text, at.name, at.key) for at in mapped] == [("marked", "&check_marked", "marked")]
    assert "souffle:marked" not in {entry["name"] for entry in left}


def test_a_folded_relation_with_no_check_relation_is_uncompared_for_the_converters_reason(loaded: rerun.Loaded) -> None:
    names = NameMap.of({"relations": {}, "constructors": {}, "unmapped": [], "untranslated": {"marked": "the converter wrote no clause of the relation"}})
    _, left = rerun.classify(replace(loaded, names=names), {}, [])
    assert {"name": "souffle:marked", "verdict": "uncompared", "reason": "the converter wrote no clause of the relation"} in left
