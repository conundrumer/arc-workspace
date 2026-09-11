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



def _kept(rel: str):
    """A profile stub the stored value of `rel` alone reproduces."""
    def profile(source, examples):
        stored = re.search(rf"\b{rel}\(1\)", source)
        return ["ref"] if stored else None
    return profile


def _shared_stub(tmp_path: Path, monkeypatch, domain: list[int]):
    """A solver with one shared parameter and one under a case marker."""
    (tmp_path / f"{STEM}.dl").write_text(
        ".comp Params {\n"
        "    // --- shared ---\n"
        "    .decl n(k: number) n(1).\n\n"
        "    // --- A ---\n"
        "    .decl m(k: number) m(1).\n"
        "}\n"
    )
    monkeypatch.setattr(sweep, "SOLVERS_DIR", tmp_path)
    monkeypatch.setattr(sweep, "load_task",
                        lambda task_id: SimpleNamespace(train=[], test=[]))
    monkeypatch.setattr(sweep, "_lib_defines", lambda: {})
    monkeypatch.setattr(sweep, "_number_domain", lambda task: domain)


def test_a_case_admitting_the_whole_domain_reads_no_shared_param(
        tmp_path: Path, monkeypatch):
    _shared_stub(tmp_path, monkeypatch, [0, 1, 2])
    asked = []

    def run_profile(source, examples):
        asked.append(source)
        stored = _values(source) == frozenset({1})
        # $A holds the stored value alone; $B passes under every value.
        return (["ref"] if stored else None,
                [frozenset({"$A", "$B"} if stored else {"$B"})])

    monkeypatch.setattr(sweep, "_profile_cases", run_profile)
    monkeypatch.setattr(sweep, "_profile", _kept("m"))

    results = sweep.sweep_report(STEM)
    assert [(p, s) for p, s, _ in results] == [
        ("n", "swept"), ("n", "cases"), ("m", "swept"),
    ]
    per_case, _types, domain = results[1][2]
    assert per_case == {"$A": frozenset({(1,)}),
                        "$B": frozenset({(0,), (1,), (2,)})}
    assert domain == frozenset({(0,), (1,), (2,)})
    assert sweep.render_sweep([results[1]]) == [
        "n: the cases admit different values; $A admits [(1)]; "
        "$B admits the whole domain [(0), (1), (2)], so $B never reads n — "
        "it belongs under that case's marker"
    ]
    # The parameter under a case marker asks for no per-case run.
    assert len(asked) == 4


def test_cases_that_agree_report_nothing(tmp_path: Path, monkeypatch):
    _shared_stub(tmp_path, monkeypatch, [0, 1])

    def run_profile(source, examples):
        stored = _values(source) == frozenset({1})
        return (["ref"] if stored else None,
                [frozenset({"$A", "$B"}) if stored else frozenset()])

    monkeypatch.setattr(sweep, "_profile_cases", run_profile)
    monkeypatch.setattr(sweep, "_profile", _kept("m"))

    assert [(p, s) for p, s, _ in sweep.sweep_report(STEM)] == [
        ("n", "swept"), ("m", "swept"),
    ]
