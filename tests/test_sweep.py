"""Parameter value sweep: what a skipped parameter tells the reader."""

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from dl import sweep

STEM = "abcd1234"


def test_a_param_over_the_cap_names_the_rerun(tmp_path: Path, monkeypatch):
    (tmp_path / f"{STEM}.dl").write_text(
        ".comp Params {\n    .decl n(k: number) n(2).\n}\n")
    monkeypatch.setattr(sweep, "SOLVERS_DIR", tmp_path)
    monkeypatch.setattr(sweep, "load_task",
                        lambda task_id: SimpleNamespace(train=[], test=[]))
    monkeypatch.setattr(sweep, "_lib_defines", lambda: {})
    monkeypatch.setattr(sweep, "_number_domain", lambda task: list(range(5)))

    assert sweep.sweep_report(STEM, max_candidates=2) == [
        ("n", "skip",
         f"5 alternative values, cap 2; rerun with run_dl.py sweep {STEM} 5"),
    ]


def _stub(tmp_path: Path, monkeypatch, facts: str, domain: list[int]):
    """A one-parameter solver over a small number domain, with the task and
    the lib defines stubbed out."""
    (tmp_path / f"{STEM}.dl").write_text(
        f".comp Params {{\n    .decl n(k: number) {facts}\n}}\n")
    monkeypatch.setattr(sweep, "SOLVERS_DIR", tmp_path)
    monkeypatch.setattr(sweep, "load_task",
                        lambda task_id: SimpleNamespace(train=[], test=[]))
    monkeypatch.setattr(sweep, "_lib_defines", lambda: {})
    monkeypatch.setattr(sweep, "_number_domain", lambda task: domain)


def _values(source: str) -> frozenset[int]:
    return frozenset(int(m) for m in re.findall(r"\bn\((-?\d+)\)", source))


def test_a_set_over_the_cap_sweeps_single_row_changes(tmp_path: Path, monkeypatch):
    _stub(tmp_path, monkeypatch, "n(1). n(2).", [0, 1, 2, 3])
    tried = []

    def profile(source, examples):
        vals = _values(source)
        tried.append(vals)
        return "ref" if vals in (frozenset({1, 2}), frozenset({1, 3})) else None

    monkeypatch.setattr(sweep, "_profile", profile)

    [(param, status, detail)] = sweep.sweep_report(STEM, max_candidates=4)
    fitting, stored, _types, verdicts = detail
    assert (param, status) == ("n", "swept-set-near")
    assert set(fitting) == {frozenset({(1,), (2,)}), frozenset({(1,), (3,)})}
    assert verdicts == {frozenset({(1,), (3,)}): True}
    # Two changes at once — drop the stored rows and add two others — stays
    # outside the neighborhood.
    assert frozenset({0, 3}) not in tried
    assert sweep.render_sweep([(param, status, detail)])[0].startswith(
        "n: stored {(1), (2)} (swept single-row changes); ")

