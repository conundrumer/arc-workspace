"""The kept determination plans of `arclog_convert.plans` are shared by every
`--out` directory, are written whole, and are missed once the solver file or
the runner and lib stamp changes."""

from pathlib import Path

import pytest

from arclog_convert import paths, plans
from engine import checkout


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "solvers").mkdir()
    (tmp_path / "solvers" / "s.dl").write_text("o(1).\n")
    monkeypatch.setattr(paths, "SOLVERS", tmp_path / "solvers")
    monkeypatch.setattr(paths, "PLANS", tmp_path / "out1" / "plan")
    monkeypatch.setenv(checkout.CACHE_ENV, str(tmp_path / "cache"))
    monkeypatch.setattr("cli.common.stamp", lambda: "stamp1")
    return tmp_path


def plan_text(stem: str) -> bytes:
    digest = plans.solver_hash(stem)
    return f"undecided\nrunner and lib: stamp1\n{plans.PLAN_HASH}{digest}\n".encode()


def test_a_plan_kept_by_one_out_directory_is_restored_into_another(tree: Path, monkeypatch: pytest.MonkeyPatch):
    paths.PLANS.mkdir(parents=True)
    (paths.PLANS / "s.txt").write_bytes(plan_text("s"))
    assert plans.restore_plans(["s"], plans.current_lib_line()) == []
    monkeypatch.setattr(paths, "PLANS", tree / "out2" / "plan")
    assert plans.restore_plans(["s"], plans.current_lib_line()) == []
    assert (paths.PLANS / "s.txt").read_bytes() == plan_text("s")
    assert [p.name for p in plans.store().iterdir() if p.name.startswith(".")] == []


def test_a_changed_solver_file_or_stamp_misses(tree: Path, monkeypatch: pytest.MonkeyPatch):
    paths.PLANS.mkdir(parents=True)
    (paths.PLANS / "s.txt").write_bytes(plan_text("s"))
    assert plans.restore_plans(["s"], plans.current_lib_line()) == []
    monkeypatch.setattr(paths, "PLANS", tree / "out2" / "plan")
    monkeypatch.setattr("cli.common.stamp", lambda: "stamp2")
    assert plans.restore_plans(["s"], plans.current_lib_line()) == ["s"]
    monkeypatch.setattr("cli.common.stamp", lambda: "stamp1")
    (paths.SOLVERS / "s.dl").write_text("o(2).\n")
    assert plans.restore_plans(["s"], plans.current_lib_line()) == ["s"]
