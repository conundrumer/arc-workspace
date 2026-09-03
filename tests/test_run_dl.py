"""Runner: hand-written grids, and reporting a compile failure once."""

import io
from pathlib import Path

import pytest

from dl import cli
from dl.facts import parse_grid
from dl.render import render_stem_failures
from dl.solve import PairResult, TaskResult, VariantResult

STEM = "abcd1234"


@pytest.fixture
def solvers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A solvers directory holding one stem, with Souffle stubbed out."""
    (tmp_path / f"{STEM}.dl").write_text("// stub\n")
    monkeypatch.setattr(cli, "SOLVERS_DIR", tmp_path)
    monkeypatch.setattr(cli, "build_functors", lambda: None)
    monkeypatch.setattr(cli, "compile_error", lambda stem: None)
    return tmp_path


def test_digit_rows():
    assert parse_grid("030\n333\n") == [[0, 3, 0], [3, 3, 3]]


def test_dots_and_spaces_are_the_same_grid():
    assert parse_grid(". 3 .\n3 3 3\n") == parse_grid("030\n333")


def test_comments_and_blank_lines_are_skipped():
    assert parse_grid("# a figure\n\n1 1\n. 1\n") == [[1, 1], [0, 1]]


def test_json_grid_passes_through():
    assert parse_grid(" [[0, 3], [3, 3]] ") == [[0, 3], [3, 3]]


def test_ragged_rows_raise():
    with pytest.raises(ValueError, match="differ in width"):
        parse_grid("03\n333")


def test_empty_text_raises():
    with pytest.raises(ValueError, match="empty grid"):
        parse_grid("\n\n")


def test_json_cell_out_of_range_raises():
    with pytest.raises(ValueError, match="out of range"):
        parse_grid("[[0, 12]]")


def _emit(cases):
    """A run_dl stand-in emitting (variant, grid) pairs, no defects."""
    return lambda task_id, rows, stem=None: [(v, g, [], []) for v, g in cases]


def test_grid_prints_a_case_per_choice(solvers, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_dl", _emit([
        ("$Complete", [[2, 1], [1, 1]]),
        ("$Copy", [[2, 1], [1, 2]]),
    ]))
    path = solvers / "grid.txt"
    path.write_text(". 1\n1 1\n")

    assert cli.cmd_grid(STEM, str(path)) == 0
    out = capsys.readouterr().out
    assert "input:\n  . 1\n  1 1\n" in out
    assert "$Complete:\n  2 1\n  1 1\n" in out
    assert "$Copy:\n  2 1\n  1 2\n" in out
    assert "2 cases, 2 distinct grid(s)" in out


def test_grid_reads_stdin_when_no_file(solvers, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_dl", _emit([("", [[1]])]))
    monkeypatch.setattr("sys.stdin", io.StringIO("1\n"))

    assert cli.cmd_grid(STEM) == 0
    out = capsys.readouterr().out
    assert "(out):\n  1\n" in out
    assert "cases," not in out  # no Choice column, nothing to compare


def test_grid_reports_defective_cells(solvers, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_dl",
                        lambda t, r, stem=None: [("", [[1]], [(0, 0)], [(0, 1)])])
    monkeypatch.setattr("sys.stdin", io.StringIO("1\n"))

    assert cli.cmd_grid(STEM) == 0
    out = capsys.readouterr().out
    assert "conflicts at: [(0, 0)]" in out
    assert "missing cells at: [(0, 1)]" in out


def test_grid_rejects_a_malformed_grid(solvers, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("03\n333\n"))

    assert cli.cmd_grid(STEM) == 2
    assert "bad grid" in capsys.readouterr().err


def test_grid_on_a_missing_solver(solvers, capsys):
    assert cli.cmd_grid("nosuch") == 2
    assert "no solver at" in capsys.readouterr().err


def _explode(*args, **kwargs):
    raise AssertionError("ran the solver on a source that does not compile")


def test_grid_reports_a_compile_error_once(solvers, monkeypatch, capsys):
    monkeypatch.setattr(cli, "compile_error", lambda stem: "souffle exited 1:\nError: x")
    monkeypatch.setattr(cli, "run_dl", _explode)
    monkeypatch.setattr("sys.stdin", io.StringIO("1\n"))

    assert cli.cmd_grid(STEM) == 1
    out = capsys.readouterr().out
    assert out == f"{STEM}.dl: souffle exited 1:\nError: x\n"


SHADOWED = (".type KP = [key: Unit, p_part: Position]\n"
            ".init occ = Occurrences<KP, Color>\n")


def test_run_names_a_shadowed_type_beside_souffle(solvers, monkeypatch, capsys):
    (solvers / f"{STEM}.dl").write_text(SHADOWED)
    monkeypatch.setattr(cli, "compile_error",
                        lambda stem: "souffle exited 1:\nError: Unable to deduce type")
    monkeypatch.setattr(cli, "run_task", _explode)
    monkeypatch.setattr(cli, "run_fit", _explode)

    assert cli.cmd_one(STEM) == 1
    out = capsys.readouterr().out
    assert "Error: Unable to deduce type" in out
    assert f"{STEM}.dl:2: shadowed type: " in out
    assert "also names a type inside `Occurrences`" in out


def test_a_collision_finding_alone_does_not_hold_back_the_run(solvers, monkeypatch):
    """Souffle decides. The collision checks read component structure the
    compiler resolves differently, so one can name a program it accepts."""
    (solvers / f"{STEM}.dl").write_text(SHADOWED)
    ran = []
    monkeypatch.setattr(cli, "res_out_stem", lambda stem: True)
    monkeypatch.setattr(cli, "run_task",
                        lambda stem: ran.append(stem) or TaskResult(stem=stem))
    monkeypatch.setattr(cli, "run_fit", lambda stem: None)

    assert cli.cmd_one(STEM) == 0
    assert ran == [STEM]


def test_run_reports_a_compile_error_ahead_of_the_pairs(solvers, monkeypatch, capsys):
    monkeypatch.setattr(cli, "compile_error", lambda stem: "souffle exited 1:\nError: x")
    monkeypatch.setattr(cli, "run_task", _explode)
    monkeypatch.setattr(cli, "run_fit", _explode)

    assert cli.cmd_one(STEM) == 1
    assert capsys.readouterr().out.count("Error: x") == 1


def test_a_compile_error_still_carries_the_lint(solvers, monkeypatch, capsys):
    """Lint needs no Souffle, so a source that will not compile still gets
    the findings its author is about to work from."""
    (solvers / f"{STEM}.dl").write_text(
        ".decl v(n: number)\nv(N) :- src(N), N != 3, ok(N).\n")
    monkeypatch.setattr(cli, "compile_error", lambda stem: "souffle exited 1:\nError: x")
    monkeypatch.setattr(cli, "run_task", _explode)
    monkeypatch.setattr(cli, "run_fit", _explode)

    assert cli.cmd_one(STEM) == 1
    out = capsys.readouterr().out
    assert "Error: x" in out
    assert f"{STEM}.dl:2: nonzero literal: `3`" in out


def _failed(idx: int, error: str) -> PairResult:
    return PairResult(kind="train", idx=idx, ok=False, error=error)


def _souffle_error(temp: str) -> str:
    return (f"souffle exited 1:\nError: Undefined relation q in file {temp} "
            "at line 47")


def test_one_error_shared_by_every_pair_renders_once():
    """Every pair runs from a tempfile of its own, so the same error reads
    differently until the solver is put back in the tempfile's place."""
    lines = render_stem_failures(STEM, [_failed(0, _souffle_error(".tmpab12cd.dl")),
                                        _failed(1, _souffle_error(".tmpzz98yy.dl"))])
    assert lines == ["train[0], train[1]: FAIL",
                     f"  {_souffle_error(f'{STEM}.dl')}"]


def test_pairs_failing_differently_each_render():
    lines = render_stem_failures(STEM, [_failed(0, "boom"), _failed(1, "bang")])
    assert lines == ["train[0]: FAIL", "  boom", "train[1]: FAIL", "  bang"]


def test_a_cpu_limit_names_the_solver_it_ran():
    limit = "souffle exceeded the 5s CPU limit on {}"
    lines = render_stem_failures(STEM, [_failed(0, limit.format(".tmpab12cd.dl")),
                                        _failed(1, limit.format(".tmpzz98yy.dl"))])
    assert lines[1] == f"  {limit.format(f'{STEM}.dl')}"


def test_a_wrong_grid_still_renders_its_diff():
    pair = PairResult(
        kind="test", idx=0, ok=False, expected=[[1]],
        variants=[VariantResult(name="", ok=False, actual=[[2]])],
    )
    lines = render_stem_failures(STEM, [pair])
    assert lines[0] == "test[0]: FAIL"
    assert "    expected:" in lines
