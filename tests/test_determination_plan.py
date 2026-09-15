"""The determination plan's joint enumeration."""

import re
from pathlib import Path
from types import SimpleNamespace

from dl import determination_plan, solve, sweep
from dl.determination_plan import render_determination_plan

STEM = "abcd1234"


def plan(results):
    return render_determination_plan((results, [], set()))


def _stub_solver(tmp_path: Path, monkeypatch, domain: list[int]):
    """A two-parameter solver over a small number domain, with the task and
    the lib defines stubbed out."""
    (tmp_path / f"{STEM}.dl").write_text(
        ".comp Params {\n"
        "    .decl a(k: number) a(1).\n"
        "    .decl b(k: number) b(1).\n"
        "}\n"
    )
    monkeypatch.setattr(solve, "SOLVERS_DIR", tmp_path)
    monkeypatch.setattr(determination_plan, "load_task",
                        lambda task_id: SimpleNamespace(train=[], test=[]))
    monkeypatch.setattr(determination_plan, "_lib_defines", lambda: {})
    monkeypatch.setattr(sweep, "_number_domain", lambda task: domain)


def _report():
    return ([("a", {"domain": "enumerable(2)"}),
             ("b", {"domain": "enumerable(2)"})], [], set())


def _assignment(source: str) -> tuple[int, int]:
    return (int(re.search(r"\ba\((-?\d+)\)", source).group(1)),
            int(re.search(r"\bb\((-?\d+)\)", source).group(1)))


def _survivors(tmp_path: Path, monkeypatch, fits) -> tuple:
    _stub_solver(tmp_path, monkeypatch, [0, 1])
    monkeypatch.setattr(
        determination_plan, "_profile",
        lambda source, examples: "ref" if fits(_assignment(source)) else None)
    return determination_plan.settle_survivors(STEM, _report())


def test_one_surviving_assignment_reads_as_exact(tmp_path: Path, monkeypatch):
    survivors = _survivors(tmp_path, monkeypatch, lambda v: v == (1, 1))
    assert survivors == (4, 1, {"a": ["(1)"], "b": ["(1)"]})
    lines = render_determination_plan(_report(), survivors)
    assert "  a (domain enumerable(2), pairs-exact: (1))" in lines
    assert "1 of 4 joint assignments of the enumerated parameters " \
           "reproduce every train pair" in lines


def test_several_surviving_assignments_read_as_ambiguous(
        tmp_path: Path, monkeypatch):
    """Two assignments reproduce the train pairs, so each parameter holds
    two surviving values and neither is determinable."""
    survivors = _survivors(tmp_path, monkeypatch, lambda v: v[0] == v[1])
    assert survivors == (4, 2, {"a": ["(0)", "(1)"], "b": ["(0)", "(1)"]})
    lines = render_determination_plan(_report(), survivors)
    assert "  a (domain enumerable(2), pairs-ambiguous(2): (0), (1))" in lines
    assert "2 of 4 joint assignments of the enumerated parameters " \
           "reproduce every train pair" in lines
    # An ambiguous parameter is an action, so the plan does not read as idle.
    assert "no actions" not in lines


