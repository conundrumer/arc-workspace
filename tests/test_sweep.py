"""Parameter value sweep: what its report tells the reader."""

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from dl import sweep

STEM = "abcd1234"


def _stub(tmp_path: Path, monkeypatch, facts: str, domain: list[int],
          decl: str = "n(k: number)"):
    """A one-parameter solver over a small number domain, with the task and
    the lib defines stubbed out."""
    (tmp_path / f"{STEM}.dl").write_text(
        f".comp Params {{\n    .decl {decl} {facts}\n}}\n")
    monkeypatch.setattr(sweep, "SOLVERS_DIR", tmp_path)
    monkeypatch.setattr(sweep, "load_task",
                        lambda task_id: SimpleNamespace(train=[], test=[]))
    monkeypatch.setattr(sweep, "_lib_defines", lambda: {})
    monkeypatch.setattr(sweep, "_number_domain", lambda task: domain)


def _values(source: str) -> frozenset[int]:
    return frozenset(int(m) for m in re.findall(r"\bn\((-?\d+)\)", source))


def test_a_param_over_the_cap_sweeps_single_column_changes(
        tmp_path: Path, monkeypatch):
    _stub(tmp_path, monkeypatch, "n(1, 2).", [0, 1, 2, 3, 4],
          decl="n(a: number, b: number)")
    tried = []

    def profile(source, examples):
        a, b = re.findall(r"\bn\((-?\d+), (-?\d+)\)", source)[0]
        tried.append((int(a), int(b)))
        return "ref" if tried[-1] == (1, 2) else None

    monkeypatch.setattr(sweep, "_profile", profile)

    [(param, status, detail)] = sweep.sweep_report(STEM, max_candidates=4)
    assert (param, status) == ("n", "swept-near")
    # The scope tuple is the swept count and the whole candidate count.
    assert detail[4] == (9, 25)
    # One column moves with the other held; both at once stay out.
    assert (3, 2) in tried and (1, 3) in tried and (3, 3) not in tried
    # A coordinate sweep names its scope in place of the tick.
    assert sweep.render_sweep([(param, status, detail)]) == [
        "n: unique = (1, 2) (swept single-column changes; 9 of 25 values)"
    ]


def test_a_one_column_param_over_the_cap_is_swept_whole(
        tmp_path: Path, monkeypatch):
    """One column's coordinate slice is the cross product itself, so that
    sweep is complete and keeps its tick."""
    _stub(tmp_path, monkeypatch, "n(1).", [0, 1, 2, 3, 4])

    monkeypatch.setattr(
        sweep, "_profile",
        lambda source, examples: "ref" if _values(source) == frozenset({1}) else None)

    [(param, status, detail)] = sweep.sweep_report(STEM, max_candidates=4)
    assert (param, status) == ("n", "swept")
    assert sweep.render_sweep([(param, status, detail)]) == ["n: unique = (1) ✓"]


def test_a_zero_is_no_candidate_set_member_where_stored_rows_hold_none(
        tmp_path: Path, monkeypatch):
    _stub(tmp_path, monkeypatch, "n(1). n(2).", [0, 1, 2, 3])
    tried = []

    def profile(source, examples):
        vals = _values(source)
        tried.append(vals)
        return "ref" if vals == frozenset({1, 2}) else None

    monkeypatch.setattr(sweep, "_profile", profile)

    [(param, status, _detail)] = sweep.sweep_report(STEM, max_candidates=4)
    assert (param, status) == ("n", "swept-set-near")
    assert not any(0 in v and len(v) > 1 for v in tried)


def test_each_parameter_prints_its_candidate_count(
        tmp_path: Path, monkeypatch, capsys):
    _stub(tmp_path, monkeypatch, "n(1). n(2).", [0, 1, 2, 3])

    def profile(source, examples):
        return "ref" if _values(source) == frozenset({1, 2}) else None

    monkeypatch.setattr(sweep, "_profile", profile)

    sweep.sweep_report(STEM, max_candidates=4)
    err = capsys.readouterr().err.splitlines()
    # The singleton candidates, then the candidate sets.
    assert err == ["n: 4 values", "n: 6 values"]


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


def test_a_wholly_swept_set_keeps_the_tick(tmp_path: Path, monkeypatch):
    """A set sweep that covers the whole candidate space settles the
    parameter, so its line carries the mark."""
    _stub(tmp_path, monkeypatch, "n(1). n(2).", [0, 1, 2])

    monkeypatch.setattr(
        sweep, "_profile",
        lambda source, examples: "ref" if _values(source) == frozenset({1, 2}) else None)

    [(param, status, detail)] = sweep.sweep_report(STEM, max_candidates=4)
    assert (param, status) == ("n", "swept-set")
    assert sweep.render_sweep([(param, status, detail)]) == [
        "n: unique as a set = {(1), (2)} ✓ (facts fit only together; "
        "swept whole)"
    ]


def test_a_partly_swept_set_drops_the_tick(tmp_path: Path, monkeypatch):
    """A partial set sweep names the part of the candidate space it swept, and
    withholds the mark, as a partial value sweep does."""
    _stub(tmp_path, monkeypatch, "n(1). n(2).", [0, 1, 2, 3])

    monkeypatch.setattr(
        sweep, "_profile",
        lambda source, examples: "ref" if _values(source) == frozenset({1, 2}) else None)

    [(param, status, detail)] = sweep.sweep_report(STEM, max_candidates=4)
    assert (param, status) == ("n", "swept-set-near")
    assert sweep.render_sweep([(param, status, detail)]) == [
        "n: unique as a set = {(1), (2)} (facts fit only together; "
        "swept single-row changes)"
    ]


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
