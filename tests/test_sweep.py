"""Parameter value sweep: what its report tells the reader."""

import re
from pathlib import Path
from types import SimpleNamespace

from dl import solve, sweep

STEM = "abcd1234"


def _stub(tmp_path: Path, monkeypatch, facts: str, domain: list[int],
          decl: str = "n(k: number)"):
    """A one-parameter solver over a small number domain, with the task and
    the lib defines stubbed out."""
    (tmp_path / f"{STEM}.dl").write_text(
        f".comp Params {{\n    .decl {decl} {facts}\n}}\n")
    monkeypatch.setattr(solve, "SOLVERS_DIR", tmp_path)
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

    [(param, status, detail)] = sweep.sweep_report(STEM, max_candidates=9)
    assert (param, status) == ("n", "swept-near")
    # The scope tuple is the swept count and the whole candidate count.
    assert detail[4] == (9, 25)
    # One column moves with the other held; both at once stay out.
    assert (3, 2) in tried and (1, 3) in tried and (3, 3) not in tried
    # A coordinate sweep names its scope in place of the tick.
    assert sweep.render_sweep([(param, status, detail)]) == [
        "n: unique = (1, 2) (swept single-column changes; 9 of 25 values)"
    ]


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


def _two_param_stub(tmp_path: Path, monkeypatch, domain: list[int]):
    """A solver with two one-column parameters, each stored at 1."""
    (tmp_path / f"{STEM}.dl").write_text(
        ".comp Params {\n"
        "    .decl n(k: number) n(1).\n\n"
        "    .decl m(k: number) m(1).\n"
        "}\n"
    )
    monkeypatch.setattr(solve, "SOLVERS_DIR", tmp_path)
    monkeypatch.setattr(sweep, "load_task",
                        lambda task_id: SimpleNamespace(train=[], test=[]))
    monkeypatch.setattr(sweep, "_lib_defines", lambda: {})
    monkeypatch.setattr(sweep, "_number_domain", lambda task: domain)
    monkeypatch.setattr(sweep, "_pool_workers", lambda: 2)

    def profile(source, examples):
        return "ref" if re.search(r"\bn\(1\)", source) and \
            re.search(r"\bm\(1\)", source) else None

    monkeypatch.setattr(sweep, "_profile", profile)


def test_a_spent_time_limit_cuts_one_param_and_leaves_the_rest_unswept(
        tmp_path: Path, monkeypatch):
    """The parameter in flight reports the runs it made; the parameter
    behind it reports the time limit as its reason."""
    _two_param_stub(tmp_path, monkeypatch, [0, 1, 2, 3])

    results = sweep.sweep_report(STEM, time_limit=0)
    assert [(p, s) for p, s, _ in results] == [
        ("n", "swept-cut"), ("m", "skip"),
    ]
    assert results[0][2][4] == (2, 4)
    assert sweep.render_sweep(results) == [
        "n: unique = (1) (cut by the time limit; 2 of 4 values)",
        "m: not swept — time limit",
    ]


def test_a_determined_param_says_its_determination_picks_the_stored_value(
        monkeypatch):
    """A refuted extra is already picked from train when the parameter's
    determination reproduces the stored value; without one, the line keeps
    the open clause."""
    monkeypatch.setattr(sweep, "_lib_defines", lambda: {})
    result = ("n", "swept", ([(1,), (2,)], [(1,)], ["number"], {(2,): False}))
    head = "n: stored (1); train also admits [(2)]; test refutes [(2)] — "
    assert sweep.render_sweep([result], {"n"}) == [
        head + "the determination picks the stored value"
    ]
    assert sweep.render_sweep([result]) == [
        head + "a determination from train alone could pick it"
    ]
