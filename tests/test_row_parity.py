"""A task's row parity record is fresh where its files are equal; a change to its column map or to its Souffle solver file makes it stale."""
import json
from pathlib import Path

from arclog_convert import row_parity, train_replay

SOURCES = "sources-digest"
BINARY = "binary-digest"
STEM = "aaaa0001"


def setup(tmp_path: Path):
    gen, tasks, solvers = tmp_path / "gen", tmp_path / "tasks", tmp_path / "solvers"
    for directory in (gen, tasks, solvers, tmp_path / "names", tmp_path / "columns", tmp_path / "row_parity"):
        directory.mkdir()
    (gen / f"{STEM}.arclog").write_text("log")
    (gen / f"{STEM}.arcdata").write_text("data")
    (tasks / f"{STEM}.json").write_text("{}")
    (tmp_path / "names" / f"{STEM}.json").write_text("{}")
    (tmp_path / "columns" / f"{STEM}.json").write_text("{}")
    (solvers / f"{STEM}.dl").write_text("solver")
    record = {"files": row_parity.files_digest(STEM, gen, tasks, solvers), "sources": SOURCES, "binary": BINARY, "lines": []}
    (tmp_path / "row_parity" / f"{STEM}.json").write_text(json.dumps(record))


def stale(tmp_path: Path) -> list[str]:
    gen, tasks, solvers = tmp_path / "gen", tmp_path / "tasks", tmp_path / "solvers"
    return train_replay.stale_tasks([STEM], lambda stem: row_parity.files_digest(stem, gen, tasks, solvers),
                                    tmp_path / "row_parity", SOURCES, lambda: BINARY)


def test_a_task_whose_files_are_unchanged_is_fresh(tmp_path):
    setup(tmp_path)
    assert stale(tmp_path) == []


def test_a_change_to_its_column_map_makes_it_stale(tmp_path):
    setup(tmp_path)
    (tmp_path / "columns" / f"{STEM}.json").write_text('{"&x": []}')
    assert stale(tmp_path) == [STEM]


def test_a_change_to_its_souffle_solver_file_makes_it_stale(tmp_path):
    setup(tmp_path)
    (tmp_path / "solvers" / f"{STEM}.dl").write_text("changed")
    assert stale(tmp_path) == [STEM]
