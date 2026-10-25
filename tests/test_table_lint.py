"""The lint's verdict on a relation, from the rows files and the arclog text
of a solver written in the test."""

import json
from pathlib import Path

import pytest

from study.table_lint import read_counts, solver_lines

SOLVER = "t0000000"


def lint(
    tmp_path: Path,
    arclog: str,
    counts: dict[str, str],
    rows: dict[str, tuple[list[str], list[list]]] | None = None,
    fault: str | None = None,
) -> dict[str, str]:
    """The line of each relation of `counts` (the counts of its `train/0`
    input), by relation; `rows` has the column types and rows of the
    relations whose rows `row-counts` wrote."""
    (tmp_path / f"{SOLVER}.arclog").write_text(arclog)
    for relation, (types, body) in (rows or {}).items():
        path = tmp_path / "rows" / SOLVER / "train-0" / f"{relation}.0.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        columns = [{"name": f"c{i}", "type": ty} for i, ty in enumerate(types)]
        path.write_text(json.dumps({"solver": SOLVER, "input": "train/0", "relation": relation, "model": 0, "columns": columns, "rows": body}))
    relations, faults = read_counts("".join(f"{SOLVER} train/0 {name} {count}\n" for name, count in counts.items()))
    assert faults == []
    lines = solver_lines(tmp_path, tmp_path / "rows", SOLVER, relations, fault)
    return {line.split()[1]: line.split(" ", 2)[2] for line in lines}


def box(i: int) -> list[int]:
    return [i, 0, i, 0]


def test_a_relation_equal_to_another_written_relation_is_a_restatement(tmp_path: Path):
    rows = (["Int", "Int"], [[i, i % 7] for i in range(30)])
    got = lint(tmp_path, "(RULE &a (&x *P) (&y P *Q))\n(RULE &b (&z *P) (&w P *Q))", {"&a": "30", "&b": "30"}, {"&a": rows, "&b": rows})
    assert got["&a"].startswith("30 restatement ")
    assert got["&b"].startswith("30 restatement ")


def test_a_relation_that_is_the_projection_of_another_is_a_restatement(tmp_path: Path):
    wide = (["Int", "Int", "Int"], [[i, i % 7, i % 5] for i in range(40)])
    narrow = (["Int", "Int"], [[i, i % 5] for i in range(40)])
    got = lint(tmp_path, "(RULE &w (&x *P) (&y P *Q))\n(RULE &n (&z *P) (&u P *Q))", {"&w": "40", "&n": "40"}, {"&w": wide, "&n": narrow})
    assert got["&n"].split()[1] == "restatement"
    assert got["&w"].split()[1] != "restatement"


@pytest.mark.parametrize(
    ("arclog", "relation"),
    [
        ("(RULE &p (&x *A) (&y *B))", "&p"),
        ("(INIT &m Ray (node (P) (&origin D) (input *P)))", "&m.node"),
    ],
)
def test_a_product_body_or_a_guard_with_no_head_variable_is_a_product(tmp_path: Path, arclog: str, relation: str):
    got = lint(tmp_path, arclog, {relation: "stopped:rows:5"})
    assert got[relation].startswith("stopped:rows:5 product ")


def test_a_full_cross_product_of_rows_is_a_product(tmp_path: Path):
    rows = (["Int", "Int"], [[a, b] for a in range(6) for b in range(7)])
    got = lint(tmp_path, "(RULE &p (OR ((&x *A)) ((&y *A))) (&z *B))", {"&p": "42"}, {"&p": rows})
    assert got["&p"].startswith("42 product ")


def test_the_pairs_of_an_order_are_an_order(tmp_path: Path):
    chain = (["Box", "Box"], [[box(i), box(j)] for i in range(8) for j in range(i + 1, 8)])
    got = lint(tmp_path, "(RULE &o (&x *P))", {"&o": "28"}, {"&o": chain})
    assert got["&o"].startswith("28 order or class as pairs ")


def test_an_edge_that_orders_two_of_its_columns_is_an_order(tmp_path: Path):
    arclog = "(INIT &w Propagation (edge ((:a N) (:b N2)) (&node (:N *N)) (&node (:N *N2)) (< N2 N)))"
    got = lint(tmp_path, arclog, {"&w.edge": "stopped:rows:5"})
    assert got["&w.edge"].startswith("stopped:rows:5 order or class as pairs ")


def test_pairs_of_cells_that_a_lib_relation_reads_are_a_lib_relation(tmp_path: Path):
    near = (["Box", "Box"], [[box(i), box(i + step)] for i in range(30) for step in ([1], [2, 3], [1, 5])[i % 3]])
    got = lint(tmp_path, "(RULE &s (&cell *P) (neighbor P *Q) (&cell Q))", {"&s": "50"}, {"&s": near})
    assert got["&s"].startswith("50 lib relation per pair ")


def test_the_output_and_a_relation_the_decode_gives_no_table_are_not_flagged():
    text = "".join(
        f"{SOLVER} train/0 {name} 5000\n"
        for name in ["&output", "&big", "&c.node"]
    ) + f"{SOLVER} train/0 &c.node no table\n"
    relations, faults = read_counts(text)
    assert faults == []
    assert [r.name for r in relations if r.flagged] == ["&big"]
