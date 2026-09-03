"""Fill sweep: what a skipped slot tells the reader."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from dl import sweep

STEM = "abcd1234"


def test_a_slot_over_the_cap_names_the_rerun(tmp_path: Path, monkeypatch):
    (tmp_path / f"{STEM}.dl").write_text(
        ".comp Consts {\n    .decl n(k: number) n(2).\n}\n")
    monkeypatch.setattr(sweep, "SOLVERS_DIR", tmp_path)
    monkeypatch.setattr(sweep, "load_task",
                        lambda task_id: SimpleNamespace(train=[], test=[]))
    monkeypatch.setattr(sweep, "_lib_defines", lambda: {})
    monkeypatch.setattr(sweep, "_number_domain", lambda task: list(range(5)))

    assert sweep.sweep_report(STEM, max_candidates=2) == [
        ("n", "skip",
         f"5 alternative fills, cap 2; rerun with run_dl.py sweep {STEM} 5"),
    ]
