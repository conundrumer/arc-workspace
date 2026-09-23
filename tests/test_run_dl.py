"""Runner: grids and Souffle output, a compile error's lint, the `since`
window, the temp sources, and the lib include the build adds."""

import os
import subprocess
import time
from pathlib import Path

import pytest

from dl import cli, solve
from dl.facts import Candidate, parse_grid, parse_output
from dl.solve import TaskResult

STEM = "abcd1234"


@pytest.fixture
def solvers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A solvers directory holding one stem, with Souffle stubbed out."""
    (tmp_path / f"{STEM}.dl").write_text("// stub\n")
    monkeypatch.setattr(solve, "SOLVERS_DIR", tmp_path)
    monkeypatch.setattr(cli, "build_functors", lambda: None)
    monkeypatch.setattr(cli, "compile_error", lambda stem: None)
    return tmp_path


def test_ragged_rows_raise():
    with pytest.raises(ValueError, match="differ in width"):
        parse_grid("03\n333")


def test_a_malformed_case_leaves_the_other_cases_grids():
    stdout = ("---------------\n===============\n"
              "[0, -1, 1, 0]\t3\t$Bad\n"
              "[0, 0, 0, 0]\t3\t$Good\n"
              "===============\n")
    bad, good = parse_output(stdout)
    assert bad.case == "$Bad" and bad.grid == [] and bad.error
    assert good == Candidate("$Good", [[3]], [], [])


def _explode(*args, **kwargs):
    raise AssertionError("ran the solver on a source that does not compile")


SHADOWED = (".type _SK = [key: Unit, p_part: Position]\n"
            ".init inv = OffsetInvariance<_SK, Color>\n")


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


# A header the lint accepts, so only hints are left to report.
def _git_run(repo: Path, *args: str, date: str | None = None) -> None:
    """One git call on `repo`, which no ambient git setting reaches: the user's
    config stays out, and so does every inherited `GIT_` variable, a commit
    date among them. `date` is the date the call takes instead."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env |= {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
    if date is not None:
        env |= {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
    subprocess.run(["git", *args], cwd=repo, check=True, env=env)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A git repo whose solvers directory the `since` command reads."""
    solvers = tmp_path / "programs" / "solvers"
    solvers.mkdir(parents=True)
    _git_run(tmp_path, "init", "-q")
    _git_run(tmp_path, "config", "user.email", "t@t")
    _git_run(tmp_path, "config", "user.name", "t")
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(cli, "all_stems",
                        lambda: sorted(p.stem for p in solvers.glob("*.dl")))
    return tmp_path


def _commit(repo: Path, stems: list[str], message: str,
            date: str | None = None) -> None:
    for stem in stems:
        (repo / "programs" / "solvers" / f"{stem}.dl").write_text(f"// {message}\n")
    _git_run(repo, "add", "-A")
    _git_run(repo, "commit", "-q", "-m", message, date=date)


def _rewriting_window(repo: Path) -> None:
    """A base commit before the window, then a window whose commits each
    stay under the share and together reach most of the corpus."""
    _commit(repo, ["aaaa1111", "bbbb2222", "cccc3333", "dddd4444"], "base",
            date="2000-01-01T00:00:00")
    _commit(repo, ["aaaa1111", "bbbb2222"], "a pair")
    _commit(repo, ["cccc3333", "eeee5555"], "another pair")


def test_since_narrows_a_rewriting_window_to_the_solvers_it_adds(repo, capsys):
    _rewriting_window(repo)

    assert cli.cmd_since("2001-01-01") == 0
    out = capsys.readouterr()
    assert out.out == "eeee5555\n"
    assert "the window holds a corpus-wide rewrite" in out.err
    assert "4 solvers of 5" in out.err


def test_since_lists_a_worktree_solver_older_than_the_date(repo, capsys):
    """Uncommitted work stands between commits however long it has sat, so
    the content difference decides, not the modification time."""
    _commit(repo, ["aaaa1111", "bbbb2222", "cccc3333", "dddd4444"], "four")
    stale = repo / "programs" / "solvers" / "eeee5555.dl"
    stale.write_text("// stale\n")
    os.utime(stale, (0, time.time() - 3600))

    assert cli.cmd_since("1 minute ago") == 0
    assert capsys.readouterr().out == "eeee5555\n"


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
