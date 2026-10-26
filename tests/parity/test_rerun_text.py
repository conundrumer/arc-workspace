"""The relations the converter adds, which no relation of the solver's file holds, are compared with the rows of the Souffle text the converter writes for them."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from arclog_convert import OUT_ENV
from parity import names_path, rerun, text_path

ROOT = Path(__file__).resolve().parents[2]
STEM = "00576224"
"""A task with train pairs, whose solver here tiles each cell of the input at two positions."""

SOLVER = """// 00576224
// @keywords: tiling
// output: the input tiled

.decl tile(p: Position)
tile([0, 1, 0, 1]).
tile([1, 0, 0, 1]).

.init ray = Ray<Unit>
ray.mark($U(), P) :- in(P, 1).
ray.dir($U(), D) :- dir8_elem(D).
ray.cell($U(), P) :- in(P, _).

.decl out(p: Position, col: Color)
out(P, C) :- in(P0, C), tile(T), concat_2d(T, P0, 0, P).
out(P, 5) :- ray.stop($U(), P, _, _, _), in(P, _).
"""


@pytest.fixture(scope="module")
def converted(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The solver file `SOLVER` under a temporary checkout, converted there."""
    tmp_path = tmp_path_factory.mktemp("converted")
    programs = tmp_path / "programs"
    (programs / "solvers").mkdir(parents=True)
    for entry in (ROOT / "programs").iterdir():
        if entry.name != "solvers":
            (programs / entry.name).symlink_to(entry)
    file = programs / "solvers" / f"{STEM}.dl"
    file.write_text(SOLVER)
    subprocess.run([sys.executable, "-m", "arclog_convert.convert", 
                    "--out", str(tmp_path / "out"), STEM],
                   cwd=ROOT, check=True, capture_output=True, env={**os.environ, "ARCLOG_SOLVERS": str(programs / "solvers")})
    return file


@pytest.fixture
def rows(converted: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setenv(OUT_ENV, str(converted.parents[2] / "out"))
    got = rerun.case_rows(STEM, converted)
    assert isinstance(got, dict)
    return got


def entries(rows: dict) -> dict:
    """The entries of the concept case's first pair, by arclog name."""
    [case, *_] = rows["cases"]
    return {r["name"]: r for r in case["pairs"][0]["relations"]}


@pytest.mark.usefixtures("rows")
def test_the_text_holds_the_clauses_of_a_hoisted_instance_under_fresh_names() -> None:
    text = text_path(STEM).read_text()
    assert ".init parity_output_tiling = SigTiling<Unit>" in text
    assert "parity_output_tiling.outer($U(), T) :- tile(T)." in text


def test_a_hoisted_instances_output_is_compared_with_the_rows_of_the_text(converted: Path, rows: dict) -> None:
    names = json.loads(names_path(STEM).read_text())
    assert names["relations"]["&output_tiling.cell"] == [{"component": [], "path": "parity_output_tiling.cell", "relation": "parity_output_tiling.cell"}]
    cell = entries(rows)["&output_tiling.cell"]
    assert len(cell["rows"]) == 2 * 4   # two tiles of the 2 by 2 input of the first pair
    assert "&output_tiling.cell" not in {line["name"] for line in rows["not_compared"]}


def test_a_shapes_relation_is_compared_with_the_rows_of_the_text(rows: dict) -> None:
    assert "&ray.end" in entries(rows)
    assert "&ray.end" not in {line["name"] for line in rows["not_compared"]}


def test_a_relation_of_the_text_no_arclog_relation_stands_for_is_skipped(rows: dict) -> None:
    left = {line["name"]: (line["verdict"], line["reason"]) for line in rows["not_compared"]}
    assert left["souffle:parity_output_tiling.outer"] == ("skip", rerun.Reason.TEXT.value)
