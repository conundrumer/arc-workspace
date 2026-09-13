"""Runner: hand-written grids, and reporting a compile failure once."""

import io
import os
import subprocess
import time
from pathlib import Path

import pytest

from dl import cli
from dl.facts import Candidate, parse_grid, parse_output
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


def test_a_negative_edge_distance_names_the_edge_and_the_row():
    stdout = "---------------\n===============\n[0, -1, 1, 0]\t3\n===============\n"
    (c,) = parse_output(stdout)
    assert "negative edge distance b=-1" in c.error
    assert "[0, -1, 1, 0] 3" in c.error


def test_a_malformed_variant_leaves_the_other_variants_grids():
    stdout = ("---------------\n===============\n"
              "[0, -1, 1, 0]\t3\t$Bad\n"
              "[0, 0, 0, 0]\t3\t$Good\n"
              "===============\n")
    bad, good = parse_output(stdout)
    assert bad.variant == "$Bad" and bad.grid == [] and bad.error
    assert good == Candidate("$Good", [[3]], [], [])


def _emit(cases):
    """A run_dl stand-in emitting (variant, grid) pairs, no defects."""
    return lambda task_id, rows, stem=None: [
        Candidate(v, g, [], []) for v, g in cases
    ]


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


def test_grid_prints_a_malformed_cases_message_and_the_other_cases_grids(
    solvers, monkeypatch, capsys
):
    monkeypatch.setattr(cli, "run_dl", lambda t, r, stem=None: [
        Candidate("$Bad", [], [], [], error="negative edge distance b=-1"),
        Candidate("$Good", [[1]], [], []),
    ])
    monkeypatch.setattr("sys.stdin", io.StringIO("1\n"))

    assert cli.cmd_grid(STEM) == 0
    out = capsys.readouterr().out
    assert "$Bad:\n  negative edge distance b=-1\n" in out
    assert "$Good:\n  1\n" in out
    assert "2 cases, 1 distinct grid(s)" in out


def test_grid_reads_stdin_when_no_file(solvers, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_dl", _emit([("", [[1]])]))
    monkeypatch.setattr("sys.stdin", io.StringIO("1\n"))

    assert cli.cmd_grid(STEM) == 0
    out = capsys.readouterr().out
    assert "(out):\n  1\n" in out
    assert "cases," not in out  # no Choice column, nothing to compare


def test_grid_reports_defective_cells(solvers, monkeypatch, capsys):
    monkeypatch.setattr(
        cli, "run_dl",
        lambda t, r, stem=None: [Candidate("", [[1]], [(0, 0)], [(0, 1)])])
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


MACROS = (".decl shape(p: Position)\n"
          "GRID_MASK_2x2(shape,\n"
          "    1, _,\n"
          "    _, 1)\n"
          "RIGID(piece,\n"
          "    .decl glyph(p: Position)\n"
          "    glyph([0, 0, 0, 0]).\n"
          ")\n")


def test_expand_prints_the_macro_expansion_without_the_run_directives(
        solvers, capsys):
    (solvers / f"{STEM}.dl").write_text(MACROS)

    assert cli.cmd_expand(STEM) == 0
    out = capsys.readouterr().out
    assert "shape([0, 1, 0, 1]).\nshape([1, 0, 1, 0]).\n" in out
    assert ".decl piece_glyph(d4: D4, p: Position)" in out
    assert "_rigid_piece_glyph(B0), d4_elem(D4), apply(D4, B0, A0)" in out
    assert "GRID_" not in out and "RIGID(" not in out
    assert ".input" not in out and ".output" not in out


def _explode(*args, **kwargs):
    raise AssertionError("ran the solver on a source that does not compile")


def test_grid_reports_a_compile_error_once(solvers, monkeypatch, capsys):
    monkeypatch.setattr(cli, "compile_error", lambda stem: "souffle exited 1:\nError: x")
    monkeypatch.setattr(cli, "run_dl", _explode)
    monkeypatch.setattr("sys.stdin", io.StringIO("1\n"))

    assert cli.cmd_grid(STEM) == 1
    out = capsys.readouterr().out
    assert out == f"{STEM}.dl: souffle exited 1:\nError: x\n"


SHADOWED = (".type _SK = [key: Unit, p_part: Position]\n"
            ".init inv = OffsetInvariance<_SK, Color>\n")


def test_run_names_a_shadowed_type_beside_souffle(solvers, monkeypatch, capsys):
    (solvers / f"{STEM}.dl").write_text(SHADOWED)
    monkeypatch.setattr(cli, "compile_error",
                        lambda stem: "souffle exited 1:\nError: Unable to deduce type")
    monkeypatch.setattr(cli, "run_task", _explode)
    monkeypatch.setattr(cli, "run_determine", _explode)

    assert cli.cmd_one(STEM) == 1
    out = capsys.readouterr().out
    assert "Error: Unable to deduce type" in out
    assert f"{STEM}.dl:2: shadowed type: " in out
    assert "also names a type inside `OffsetInvariance`" in out


def test_a_collision_finding_alone_does_not_hold_back_the_run(solvers, monkeypatch):
    """Souffle decides. The collision checks read component structure the
    compiler resolves differently, so one can name a program it accepts."""
    (solvers / f"{STEM}.dl").write_text(SHADOWED)
    ran = []
    monkeypatch.setattr(cli, "res_out_stem", lambda stem: True)
    monkeypatch.setattr(cli, "run_task",
                        lambda stem: ran.append(stem) or TaskResult(stem=stem))
    monkeypatch.setattr(cli, "run_determine", lambda stem: None)

    assert cli.cmd_one(STEM) == 0
    assert ran == [STEM]


def test_run_reports_a_compile_error_ahead_of_the_pairs(solvers, monkeypatch, capsys):
    monkeypatch.setattr(cli, "compile_error", lambda stem: "souffle exited 1:\nError: x")
    monkeypatch.setattr(cli, "run_task", _explode)
    monkeypatch.setattr(cli, "run_determine", _explode)

    assert cli.cmd_one(STEM) == 1
    assert capsys.readouterr().out.count("Error: x") == 1


def test_a_compile_error_still_carries_the_lint(solvers, monkeypatch, capsys):
    """Lint needs no Souffle, so a source that will not compile still gets
    the findings its author is about to work from."""
    (solvers / f"{STEM}.dl").write_text(
        ".decl v(n: number)\nv(N) :- src(N), N != 3, ok(N).\n")
    monkeypatch.setattr(cli, "compile_error", lambda stem: "souffle exited 1:\nError: x")
    monkeypatch.setattr(cli, "run_task", _explode)
    monkeypatch.setattr(cli, "run_determine", _explode)

    assert cli.cmd_one(STEM) == 1
    out = capsys.readouterr().out
    assert "Error: x" in out
    assert f"{STEM}.dl:2: nonzero literal: `3`" in out


# A header the lint accepts, so only the hint tier is left to report.
HEAD = f"// {STEM}\n// keywords: lines\n// output: the staged cells\n"
HINTED = (HEAD + ".decl stage(x: number)\nstage(X) :- g(X), !h(X).\n"
          ".decl out(x: number)\nout(X) :- stage(X).\n")


def test_a_hint_alone_leaves_lint_ok(solvers, capsys):
    """The hint tier is advisory: the corpus both inlines and keeps its
    shapes, so a hint is a call the session makes, not a verdict."""
    (solvers / f"{STEM}.dl").write_text(HINTED)

    assert cli.cmd_lint(STEM, hints=True) == 0
    out = capsys.readouterr().out
    assert "single-consumer" in out
    assert out.endswith("lint: ok, 1 hint\n")


def test_a_lint_finding_fails_lint_beside_a_hint(solvers, capsys):
    (solvers / f"{STEM}.dl").write_text(HINTED.replace("!h(X)", "X != 3, !h(X)"))

    assert cli.cmd_lint(STEM, hints=True) == 1
    out = capsys.readouterr().out
    assert f"{STEM}.dl:5: nonzero literal: `3`" in out
    assert "lint: ok" not in out


def test_a_run_counts_its_hints_beside_lint_ok(solvers, monkeypatch, capsys):
    (solvers / f"{STEM}.dl").write_text(HINTED)
    monkeypatch.setattr(cli, "res_out_stem", lambda stem: True)
    monkeypatch.setattr(cli, "run_task", lambda stem: TaskResult(stem=stem))
    monkeypatch.setattr(cli, "run_determine", lambda stem: None)

    assert cli.cmd_one(STEM, hints=True) == 0
    assert "\nlint: ok, 1 hint\n" in capsys.readouterr().out


def _corpus(solvers, monkeypatch, failing: set[str]) -> None:
    """Two solvers a corpus run sees, with one pair each and Souffle stubbed."""
    for stem in ("aaaa1111", "bbbb2222"):
        (solvers / f"{stem}.dl").write_text("// stub\n")
    monkeypatch.setattr(cli, "res_out_stem", lambda stem: True)
    monkeypatch.setattr(cli, "run_determine", lambda stem: None)
    monkeypatch.setattr(cli, "_pair_work", lambda stem: [(stem,)])
    monkeypatch.setattr(
        cli, "run_pair",
        lambda stem: PairResult(kind="train", idx=0, ok=stem not in failing,
                                error="" if stem not in failing else "boom"),
    )


def test_a_run_over_two_stems_reports_those_two_alone(
        solvers, monkeypatch, capsys):
    _corpus(solvers, monkeypatch, failing={"bbbb2222"})
    monkeypatch.setattr(cli, "all_stems", _explode)

    assert cli.cmd_all(stems=["aaaa1111", "bbbb2222"]) == 1
    out = capsys.readouterr().out
    assert "aaaa1111: 1/1 PASS\n" in out
    assert "bbbb2222: 0/1 FAIL\n" in out
    assert "--- 1 failing solver(s) ---" in out
    assert "boom" in out
    assert out.endswith("summary: 1/2 solvers\n")


def test_a_missing_stem_among_several_is_refused(solvers, monkeypatch, capsys):
    _corpus(solvers, monkeypatch, failing=set())
    monkeypatch.setattr(cli, "build_functors", _explode)

    assert cli.cmd_all(stems=["aaaa1111", "nosuch"]) == 2
    assert "no solver at" in capsys.readouterr().err


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
                     *(f"  {ln}"
                       for ln in _souffle_error(f"{STEM}.dl").splitlines())]


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


def test_a_variant_error_renders_under_its_heading():
    """A variant whose cells describe no grid has no diff to show, so the
    error stands in the diff's place."""
    pair = PairResult(
        kind="test", idx=0, ok=False, expected=[[1]],
        variants=[VariantResult(name="$Copy", ok=False, actual=[],
                                error="negative edge distance -1 at row 0")],
    )
    lines = render_stem_failures(STEM, [pair])
    assert lines[lines.index("  $Copy:") + 1] == (
        "    negative edge distance -1 at row 0")


def test_variants_failing_on_different_errors_each_render():
    """Two variants group into one block when they fail the same way. A
    different error is a different way, so each keeps its own block."""
    def variant(name: str, error: str) -> VariantResult:
        return VariantResult(name=name, ok=False, actual=[], error=error)

    pair = PairResult(
        kind="test", idx=0, ok=False, expected=[[1]],
        variants=[variant("$Copy", "negative edge distance -1 at row 0"),
                  variant("$Complete", "inconsistent bounds")],
    )
    lines = render_stem_failures(STEM, [pair])
    assert "  $Copy:" in lines
    assert "  $Complete:" in lines
    assert "    negative edge distance -1 at row 0" in lines
    assert "    inconsistent bounds" in lines


CHOICE = ".type Choice = Complete {} | Copy {}\n"


def test_grid_names_a_case_that_emits_nothing(solvers, monkeypatch, capsys):
    (solvers / f"{STEM}.dl").write_text(CHOICE)
    monkeypatch.setattr(cli, "run_dl", _emit([("$Complete", [[2, 1], [1, 1]])]))
    monkeypatch.setattr("sys.stdin", io.StringIO(". 1\n1 1\n"))

    assert cli.cmd_grid(STEM) == 0
    assert "$Copy: emits nothing" in capsys.readouterr().out


def test_grid_counts_an_empty_case_in_the_footer(solvers, monkeypatch, capsys):
    (solvers / f"{STEM}.dl").write_text(CHOICE)
    monkeypatch.setattr(cli, "run_dl", _emit([("$Complete", [[2, 1], [1, 1]])]))
    monkeypatch.setattr("sys.stdin", io.StringIO(". 1\n1 1\n"))

    assert cli.cmd_grid(STEM) == 0
    assert "2 cases, 1 distinct grid(s)" in capsys.readouterr().out


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A git repo whose solvers directory the `since` command reads."""
    solvers = tmp_path / "programs" / "solvers"
    solvers.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(cli, "all_stems",
                        lambda: sorted(p.stem for p in solvers.glob("*.dl")))
    return tmp_path


def _commit(repo: Path, stems: list[str], message: str) -> None:
    for stem in stems:
        (repo / "programs" / "solvers" / f"{stem}.dl").write_text(f"// {message}\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo, check=True)


def test_since_lists_the_solvers_its_commits_touch(repo, capsys):
    _commit(repo, ["aaaa1111", "bbbb2222", "cccc3333", "dddd4444"], "four")
    _commit(repo, ["aaaa1111"], "one")

    assert cli.cmd_since("1 minute ago") == 0
    assert capsys.readouterr().out == "aaaa1111\n"


def test_since_skips_a_corpus_wide_rewrite(repo, capsys):
    _commit(repo, ["aaaa1111", "bbbb2222", "cccc3333", "dddd4444"], "four")
    _commit(repo, ["aaaa1111", "bbbb2222", "cccc3333"], "rewrite")

    assert cli.cmd_since("1 minute ago") == 0
    out = capsys.readouterr()
    assert out.out == ""
    assert "3 solvers" in out.err


def test_since_lists_an_uncommitted_solver(repo, capsys):
    _commit(repo, ["aaaa1111", "bbbb2222", "cccc3333", "dddd4444"], "four")
    (repo / "programs" / "solvers" / "bbbb2222.dl").write_text("// edited\n")
    (repo / "programs" / "solvers" / "eeee5555.dl").write_text("// new\n")

    assert cli.cmd_since("1 minute ago") == 0
    assert capsys.readouterr().out == "bbbb2222\neeee5555\n"


def test_since_lists_a_worktree_solver_older_than_the_date(repo, capsys):
    """Uncommitted work stands between commits however long it has sat, so
    the content difference decides, not the modification time."""
    _commit(repo, ["aaaa1111", "bbbb2222", "cccc3333", "dddd4444"], "four")
    stale = repo / "programs" / "solvers" / "eeee5555.dl"
    stale.write_text("// stale\n")
    os.utime(stale, (0, time.time() - 3600))

    assert cli.cmd_since("1 minute ago") == 0
    assert capsys.readouterr().out == "eeee5555\n"


DOC = """# Keywords

## Setup

- `lines` — per-line structure
- `crop` — a subregion

## Prior

- `cast` — content extends

## Shape

- `latent-canvas` — a canvas neither grid shows
"""


@pytest.fixture
def keyworded(solvers: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A solvers directory read against a small keywords.md."""
    doc = solvers / "keywords.md"
    doc.write_text(DOC)
    monkeypatch.setattr(cli, "KEYWORDS_DOC", doc)
    monkeypatch.setattr(cli, "all_stems",
                        lambda: sorted(p.stem for p in solvers.glob("*.dl")))
    return solvers


def _solver(dir: Path, stem: str, *header: str) -> None:
    dir.joinpath(f"{stem}.dl").write_text(
        "".join(f"// {line}\n" for line in header) + ".decl out(x: number)\n")


def test_keywords_counts_the_solvers_carrying_each_keyword(keyworded, capsys):
    _solver(keyworded, "aaaa1111", "keywords: lines cast latent-canvas")
    _solver(keyworded, "bbbb2222", "keywords: lines")

    assert cli.cmd_keywords([]) == 0
    out = capsys.readouterr().out
    assert "     2  lines\n" in out
    assert "     1  cast\n" in out
    assert "     0  crop\n" in out
    assert "     1  latent-canvas\n" in out


def test_keywords_reads_the_one_keywords_line(keyworded, capsys):
    """Every section of the doc is one vocabulary, and a word outside it is
    unknown. A second `keywords:` line is not read."""
    _solver(keyworded, "aaaa1111", "keywords: lines tiling seam",
            "keywords: crop")

    assert cli.cmd_keywords([]) == 0
    out = capsys.readouterr().out
    assert "aaaa1111: tiling is not in keywords.md\n" in out
    assert "aaaa1111: seam is not in keywords.md\n" in out
    assert "     1  lines\n" in out
    assert "     0  crop\n" in out
    assert out.endswith("unknown keywords: 2\n")


def test_keywords_reads_the_retired_concept_and_shape_fields(keyworded, capsys):
    """A header that has not migrated carries `concept:` and `shape:`, and
    the index counts the keywords of both fields."""
    _solver(keyworded, "aaaa1111", "concept: lines cast",
            "shape: latent-canvas")

    assert cli.cmd_keywords([]) == 0
    out = capsys.readouterr().out
    assert "     1  lines\n" in out
    assert "     1  cast\n" in out
    assert "     1  latent-canvas\n" in out


def test_keywords_reads_the_named_stems_alone(keyworded, capsys):
    _solver(keyworded, "aaaa1111", "keywords: lines")
    _solver(keyworded, "bbbb2222", "keywords: crop")

    assert cli.cmd_keywords(["aaaa1111"]) == 0
    out = capsys.readouterr().out
    assert "     1  lines\n" in out
    assert "     0  crop\n" in out


def test_keywords_on_a_missing_solver(keyworded, capsys):
    assert cli.cmd_keywords(["nosuch"]) == 2
    assert "no solver at" in capsys.readouterr().err


def test_a_stale_temp_source_is_swept_and_a_live_one_kept(tmp_path, monkeypatch):
    from dl import souffle
    monkeypatch.setattr(souffle, "SOLVERS_DIR", tmp_path)
    stale = tmp_path / ".tmpstale.dl"
    live = tmp_path / ".tmplive.dl"
    stale.write_text("x")
    live.write_text("x")
    now = live.stat().st_mtime
    import os
    os.utime(stale, (now - 7200, now - 7200))
    assert souffle.sweep_temp_sources(now) == 1
    assert not stale.exists() and live.exists()


def test_explained_restates_a_pattern_over_a_functor_result():
    from dl.souffle import _explained

    stderr = ("variable not grounded: T at .tmpx.dl [108:49-108:50]\n"
              'Assertion failed: ("variable not grounded" && false), '
              "function visit_, file ValueTranslator.cpp, line 48.\n")
    out = _explained(stderr)
    assert out.startswith("a record pattern binds `T` (line 108)")
    assert out.endswith(stderr)
    assert _explained("Error: Ungrounded variable X\n") == "Error: Ungrounded variable X\n"


# ---------- the lib include the build adds ----------

def _line_of(text: str, needle: str) -> int:
    lines = [i for i, line in enumerate(text.splitlines(), 1) if needle in line]
    assert len(lines) == 1, f"{needle!r} on {lines}"
    return lines[0]


def test_the_build_prepends_the_lib_include_and_keeps_one_already_there():
    from dl.source import expand_macros
    from tests.test_rigid import SOLVER

    bare = SOLVER.replace('#include "../lib.dl"\n', "")
    for built in (expand_macros(bare), expand_macros(SOLVER)):
        assert built.splitlines()[0] == '#include "../lib.dl"'
        assert built.count("#include") == 1


def test_the_added_include_shifts_the_line_map_by_one():
    from dl.source import expand_macros, macro_line_map
    from tests.test_rigid import SOLVER

    bare = SOLVER.replace('#include "../lib.dl"\n', "")
    built = expand_macros(bare)
    line_map = macro_line_map(bare)
    assert len(line_map) == len(built.splitlines())
    # the added line maps to the first source line, as the line after it does
    assert line_map[:2] == [1, 1]
    rule = "out(P, C) :- params.marker_glyph"
    assert line_map[_line_of(built, rule) - 1] == _line_of(bare, rule)
