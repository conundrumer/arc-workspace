"""What a pair over the CPU budget reports: the line map back to the solver,
and the rule a Souffle profile names."""

from pathlib import Path

from dl.paths import REPO_ROOT
from dl.souffle import _rule_site, slowest_rule
from dl.source import expand_macros, macro_line_map
from tests.test_rigid import SOLVER


def _line_of(text: str, needle: str) -> int:
    """1-based line holding `needle`, which must appear once."""
    lines = [i for i, line in enumerate(text.splitlines(), 1) if needle in line]
    assert len(lines) == 1, f"{needle!r} on {lines}"
    return lines[0]


def _mapped(source: str, needle: str) -> int:
    """The source line the expansion's `needle` line maps back to."""
    expanded = expand_macros(source)
    return macro_line_map(source)[_line_of(expanded, needle) - 1]


def test_a_rule_below_the_macros_maps_back():
    """The GRID call expands to more lines than it occupied, so a rule after
    it sits lower in the expansion than in the solver."""
    expanded = expand_macros(SOLVER)
    rule = "out(P, C) :- params.marker_glyph"
    assert _line_of(expanded, rule) > _line_of(SOLVER, rule)
    assert _mapped(SOLVER, rule) == _line_of(SOLVER, rule)


def test_every_line_of_the_expansion_maps():
    line_map = macro_line_map(SOLVER)
    assert len(line_map) == len(expand_macros(SOLVER).splitlines())
    assert line_map == sorted(line_map)
    assert line_map[0] == 1
    assert max(line_map) <= len(SOLVER.splitlines())


def test_a_generated_rule_maps_to_the_call_it_came_from():
    """A RIGID block's closure rule is written nowhere, so it stands at the
    call site that generated it."""
    assert _mapped(SOLVER, "marker_glyph(D4, A0) :-") == _line_of(
        SOLVER, "RIGID(marker,")


def _rule(locator: str, start: int, end: int, tuples: int) -> dict:
    return {
        "source-locator": locator,
        "runtime": {"start": start, "end": end},
        "num-tuples": tuples,
    }


PROFILE = {
    "root": {"program": {"relation": {
        "cheap": {
            "source-locator": "/w/programs/lib.dl [10:1-10:9]",
            "runtime": {"start": 0, "end": 40},
            "num-tuples": 900,
            "non-recursive-rule": {
                "cheap(X) :- a(X).": _rule("/w/programs/lib.dl [11:1-11:9]",
                                           0, 40, 900),
            },
        },
        "dear": {
            "non-recursive-rule": {
                "dear(X) :- b(X).": _rule("/w/programs/solvers/.tmpq1.dl "
                                          "[57:1-58:20]", 100, 2_600_100, 41),
            },
            "recursive-rule": {
                "dear(X) :- dear(Y), c(Y, X).": {
                    "1": _rule("/w/programs/solvers/.tmpq1.dl [60:1-60:9]",
                               0, 300_000, 7),
                    "2": _rule("/w/programs/solvers/.tmpq1.dl [60:1-60:9]",
                               0, 300_000, 5),
                },
            },
        },
    }}}
}


def test_the_slowest_rule_is_the_one_named():
    assert slowest_rule(PROFILE) == (
        "/w/programs/solvers/.tmpq1.dl", 57, 2.6, 41)


def test_a_recursive_rule_counts_its_iterations_together():
    recursive = PROFILE["root"]["program"]["relation"]["dear"]["recursive-rule"]
    profile = {"root": {"program": {"relation": {
        "dear": {"recursive-rule": recursive},
    }}}}
    assert slowest_rule(profile) == (
        "/w/programs/solvers/.tmpq1.dl", 60, 0.6, 12)


def test_a_profile_naming_no_rule_is_no_answer():
    assert slowest_rule({}) is None
    assert slowest_rule({"root": {"program": {"relation": {
        "cheap": {"source-locator": "/w/programs/lib.dl [10:1-10:9]"},
    }}}}) is None


def test_a_site_outside_the_tempfile_stands_as_it_is():
    run_path = REPO_ROOT / "programs/solvers/.tmpq1.dl"
    lib = REPO_ROOT / "programs/lib.dl"
    assert _rule_site(str(lib), 268, run_path, Path("x.dl")) == "programs/lib.dl:268"
    assert _rule_site("/elsewhere/other.dl", 4, run_path,
                      Path("x.dl")) == "/elsewhere/other.dl:4"


def test_a_site_in_the_tempfile_lands_in_the_solver(tmp_path: Path):
    solver = tmp_path / "abcd1234.dl"
    solver.write_text(SOLVER)
    run_path = REPO_ROOT / "programs/solvers/.tmpq1.dl"
    rule = "out(P, C) :- params.marker_glyph"
    line = _line_of(expand_macros(SOLVER), rule)
    assert _rule_site(str(run_path), line, run_path, solver) == (
        f"abcd1234.dl:{_line_of(SOLVER, rule)}")
