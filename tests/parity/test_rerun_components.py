"""The relations the converter adds inside a component of the solver, and those of a frame-read plan, are compared with the rows of the Souffle text the converter writes for them."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from arclog_convert import OUT_ENV
from arclog_convert.parity_text import DETERMINE_INSTANCE
from parity import determination_text_path, names_path, rerun, text_path
from solver.determine import run_program

ROOT = Path(__file__).resolve().parents[2]
STEM = "00576224"
"""A task with train pairs, whose solver here has a `Params`, a `Parse` and a `Determine` that each add relations."""

SOLVER = """// 00576224
// @keywords: tiling

.comp Params {
    .decl bg(c: Color) bg(0).
    .decl divisor(n: number) divisor(1).
    .decl seed(p: Position) seed([0, 3, 0, 3]).
    // a hoisted instance in `Params`
    .decl half(p_tile: Position)
    half(P_tile) :- seed(P), divisor(N), divide_2d(P, N, 0, P_tile, _).
    .decl arr_dim(a: Axis, n: number)
    arr_dim(AXIS_V, 3). arr_dim(AXIS_H, 3).
    .decl tile_dim(k: number) tile_dim(2).
    .decl gap(g: number) gap(0).
    // a read of `helpers.tile_pos` over extents that parameters give
    .decl tile_decompose(p: Position, p_outer: Position, p_inner: Position)
    tile_decompose(P_grid, P_tile, P_intile) :-
        arr_dim(AXIS_V, Av), arr_dim(AXIS_H, Ah), tile_dim(K), gap(G),
        helpers.tile_pos([Av, Ah], [K, K], [G, G], P_grid, P_tile, P_intile).
    .init helpers = ParamsHelpers
}
.init params = Params

.comp Parse<Key> {
    .decl cell(key: Key, p: Position, col: Color)  // @input
    .decl tile(key: Key, p_tile: Position, p_in: Position, col: Color)
    // a hoisted instance in `Parse`, which reads a relation of `Parse`
    tile(Ky, P_tile, P_in, C) :-
        cell(Ky, P, C), params.divisor(N), divide_2d(P, N, 0, P_tile, P_in).
}
.init parse = Parse<Unit>
parse.cell($U(), P, C) :- in(P, C).

.decl out(p: Position, col: Color)
out(P_grid, C) :-
    parse.tile($U(), P_t, P_in, C), params.half(P_t), params.tile_decompose(P_grid, _, P_in).

.comp Determine {
    .decl mark(e: Example, p: Position, col: Color)
    mark(E, P, Col) :- ex_in(E, P, Col), !params.bg(Col).
    // the shape of an offset-invariance instance adds relations to `Determine`
    .init si = OffsetInvariance<Example, Color>
    si.cell(E, Q, Col) :- mark(E, Q, Col).
    .decl broken(k: number)
    broken(K) :- si.mismatch(_, A, K), axis_elem(A).
    .init unbroken = Extremes<Unit>
    unbroken.cand($U(), K) :- si.pair(_, A, K, _, _), axis_elem(A), !broken(K).
    .decl period(n: number)
    period(N) :- unbroken.low($U(), N).
}
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
    subprocess.run([sys.executable, "-m", "arclog_convert.convert", "--no-train-replay", "--no-row-parity",
                    "--out", str(tmp_path / "out"), STEM],
                   cwd=ROOT, check=True, capture_output=True, env={**os.environ, "ARCLOG_SOLVERS": str(programs / "solvers")})
    return file


@pytest.fixture(autouse=True)
def out(converted: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(OUT_ENV, str(converted.parents[2] / "out"))


@pytest.fixture
def rows(converted: Path) -> dict:
    got = rerun.case_rows(STEM, converted)
    assert isinstance(got, dict)
    return got


def concept(rows: dict, pair: int = 0) -> dict:
    """The entries of the concept case's pair `pair`, by arclog name."""
    [case, *_] = rows["cases"]
    return {r["name"]: r for r in case["pairs"][pair]["relations"]}


def determination(rows: dict) -> dict:
    """The entries of the determination's pair `task`, by arclog name."""
    [pair] = rows["determination"]["pairs"]
    assert pair["pair"] == "task"
    return {r["name"]: r for r in pair["relations"]}


def test_a_hoisted_instance_in_parse_reads_the_relation_of_parse_through_the_instance(rows: dict) -> None:
    assert "parity_tile_division.cell($U(), P) :- parse.cell(_, P, _)." in text_path(STEM).read_text()
    tile = concept(rows)["&tile_division.tile"]
    assert len(tile["rows"]) == 4   # one tile of the 2 by 2 input of the first pair
    assert "&tile_division.tile" not in {line["name"] for line in rows["not_compared"]}


def test_a_hoisted_instance_in_params_is_compared_with_the_rows_of_the_text(rows: dict) -> None:
    half = concept(rows)["&half_division.tile"]
    assert half["rows"] == [[[1], [0, 3, 0, 3], [0, 0, 0, 0], [0, 3, 0, 3]]]   # the seed, divided by 1 into the one tile
    assert "&half_division.tile" not in {line["name"] for line in rows["not_compared"]}


def test_a_frame_of_the_plan_of_a_tile_read_has_the_cells_of_its_extents(rows: dict) -> None:
    got = concept(rows)
    assert len(got["&tile_decompose_outer.cell"]["rows"]) == 3 * 3
    assert len(got["&tile_decompose_inner.cell"]["rows"]) == 2 * 2
    assert {"&tile_decompose_outer.cell", "&tile_decompose_inner.cell"}.isdisjoint(line["name"] for line in rows["not_compared"])


def test_a_relation_of_determine_is_compared_with_the_rows_of_the_determination_text(rows: dict) -> None:
    names = json.loads(names_path(STEM).read_text())
    [source] = names["relations"]["&si_mismatch_full"]
    assert source["component"] == ["Determine"] and source["path"] == "parity_si_mismatch_full"
    assert ".init determine = Determine" in determination_text_path(STEM).read_text()
    assert "parity_si_mismatch_full" not in text_path(STEM).read_text()
    mismatch = determination(rows)["&si_mismatch_full"]
    assert mismatch["columns"] == [["V0", None], ["V1", None], ["V2", None]]   # the position is existential in a determination
    assert mismatch["rows"]
    assert "&si_mismatch_full" not in {line["name"] for line in rows["not_compared"]}


def test_the_determination_text_names_the_instance_of_determine_that_a_run_adds(converted: Path) -> None:
    loaded = rerun.load_once(STEM, converted)
    assert isinstance(loaded, rerun.Loaded)
    run = run_program(loaded.solver)
    assert run.determine is not None and run.determine.name == DETERMINE_INSTANCE
