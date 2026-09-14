"""`sweep --open` and `sweep --mark`: the JSON they print, and what the
marking writes into a solver header."""

import json
from pathlib import Path

import pytest

from dl import cli, solve

HEADER = ("// {stem}\n"
          "// keywords: tiles\n"
          "// input: One grid.\n"
          "// output: The same grid.\n")
BODY = "\n.decl out(p: Position, col: Color)\nout(p, c) :- in(p, c).\n"

OPEN_SWEEP = ("bg: 6 values\n"
              "bg: stored (0); train also admits [(8)]; test refutes [(8)] — "
              "a determination from train alone could pick it\n"
              "budget 180s; elapsed 3s\n")
SETTLED_SWEEP = "bg: 6 values\nbg: unique = (0) ✓\nbudget 180s; elapsed 3s\n"
OPEN_LINE = ("// review sweep: bg — only the test pairs refute the other "
             "values train admits, so a determination from train alone could "
             "pick it")


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A solvers directory and a sweep cache of their own, with the console's
    reads pointed at the same solvers."""
    solvers = tmp_path / "solvers"
    solvers.mkdir()
    cache = tmp_path / "sweep"
    monkeypatch.setattr(solve, "SOLVERS_DIR", solvers)
    monkeypatch.setattr(cli, "SWEEP_CACHE", cache)
    monkeypatch.setattr(cli._console_solvers().config, "SOLVERS", solvers)

    def put(stem: str, sweep: str | None = None, header: str = HEADER,
            body: str = BODY, sha: bool = True) -> Path:
        path = solvers / f"{stem}.dl"
        path.write_text(header.format(stem=stem) + body)
        if sweep is not None:
            cache.mkdir(parents=True, exist_ok=True)
            (cache / f"{stem}.txt").write_text(sweep)
            if sha:
                (cache / f"{stem}.sha").write_text(cli._code_hash(stem))
        return path

    return put


def read(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


def test_the_open_parameters_of_each_stem(tree, capsys):
    tree("aaa11111", OPEN_SWEEP)
    tree("bbb22222", SETTLED_SWEEP)
    assert cli.cmd_sweep_open(["aaa11111", "bbb22222"], cached=True) == 0
    out = read(capsys)
    assert out["skipped"] == []
    assert [s["stem"] for s in out["sweeps"]] == ["aaa11111", "bbb22222"]
    assert out["sweeps"][1]["params"] == []
    [param] = out["sweeps"][0]["params"]
    assert param["param"] == "bg"
    assert param["reported"] == OPEN_SWEEP.splitlines()[1]
    assert param["line"] == OPEN_LINE


def test_a_stem_with_no_solver_is_skipped(tree, capsys):
    cli.cmd_sweep_open(["aaa11111"], cached=True)
    out = read(capsys)
    assert out["sweeps"] == []
    [skipped] = out["skipped"]
    assert skipped["stem"] == "aaa11111"
    assert skipped["reason"].startswith("no solver at ")
    assert skipped["reason"].endswith("/aaa11111.dl")


def test_an_unswept_stem_is_skipped_rather_than_swept(tree, capsys):
    """`--cached` is what a check runs under: no stem sweeps for minutes."""
    tree("aaa11111")
    cli.cmd_sweep_open(["aaa11111"], cached=True)
    out = read(capsys)
    assert out["sweeps"] == []
    assert out["skipped"][0]["reason"].startswith("no cached sweep")


OTHER_BODY = "\n.decl out(p: Position, col: Color)\nout(p, 3) :- in(p, _).\n"


@pytest.fixture
def stub_sweep(monkeypatch: pytest.MonkeyPatch):
    """Stand in for the sweep run, and record the stems it was asked for."""
    ran: list[str] = []

    def fake(stem: str) -> str:
        ran.append(stem)
        return OPEN_SWEEP

    monkeypatch.setattr(cli, "_sweep_output", fake)
    return ran


def test_a_cache_older_than_the_solver_code_sweeps_again(tree, stub_sweep,
                                                         capsys):
    """The solver's code changed after the cache was made, so the cache no
    longer describes it and the sweep runs."""
    tree("aaa11111", SETTLED_SWEEP)
    tree("aaa11111", body=OTHER_BODY)
    assert cli.cmd_sweep_open(["aaa11111"]) == 0
    assert stub_sweep == ["aaa11111"]
    out = read(capsys)
    assert out["skipped"] == []
    assert [p["param"] for p in out["sweeps"][0]["params"]] == ["bg"]
    assert cli.cmd_sweep_open(["aaa11111"], cached=True) == 0
    assert stub_sweep == ["aaa11111"]
    assert read(capsys)["skipped"] == []


def test_a_stale_cache_is_skipped_under_cached(tree, capsys):
    tree("aaa11111", SETTLED_SWEEP)
    tree("aaa11111", body=OTHER_BODY)
    assert cli.cmd_sweep_open(["aaa11111"], cached=True) == 0
    out = read(capsys)
    assert out["sweeps"] == []
    [skipped] = out["skipped"]
    assert skipped["stem"] == "aaa11111"
    assert "stale" in skipped["reason"]


def test_a_cache_with_no_hash_is_stale(tree, capsys):
    """The caches written before the hash carry none, so they are stale."""
    tree("aaa11111", OPEN_SWEEP, sha=False)
    cli.cmd_sweep_open(["aaa11111"], cached=True)
    out = read(capsys)
    assert out["sweeps"] == []
    assert "stale" in out["skipped"][0]["reason"]


def test_a_comment_line_leaves_the_cache_valid(tree, stub_sweep, capsys):
    """`sweep --mark` writes a review line into the header right after
    `sweep --open`, and that line must not invalidate the cache."""
    tree("aaa11111", OPEN_SWEEP)
    tree("aaa11111", header=HEADER + OPEN_LINE + "\n")
    assert cli.cmd_sweep_open(["aaa11111"], cached=True) == 0
    assert stub_sweep == []
    out = read(capsys)
    assert out["skipped"] == []
    assert [p["param"] for p in out["sweeps"][0]["params"]] == ["bg"]


def test_the_marking_writes_one_line_per_open_parameter(tree, capsys):
    path = tree("aaa11111", OPEN_SWEEP)
    assert cli.cmd_sweep_mark(["aaa11111"], cached=True) == 0
    assert read(capsys)["solvers"] == [
        {"task_id": "aaa11111", "lines": [OPEN_LINE], "lint_ok": True}]
    assert path.read_text().splitlines()[4] == OPEN_LINE


def test_a_parameter_already_marked_takes_no_second_line(tree, capsys):
    header = HEADER + "// review sweep: bg — the pairs leave its value open\n"
    path = tree("aaa11111", OPEN_SWEEP, header=header)
    before = path.read_text()
    cli.cmd_sweep_mark(["aaa11111"], cached=True)
    assert read(capsys)["solvers"] == [
        {"task_id": "aaa11111", "lines": [], "lint_ok": True}]
    assert path.read_text() == before


def test_a_stem_with_nothing_open_still_reports(tree, capsys):
    tree("bbb22222", SETTLED_SWEEP)
    cli.cmd_sweep_mark(["bbb22222"], cached=True)
    assert read(capsys)["solvers"] == [
        {"task_id": "bbb22222", "lines": [], "lint_ok": True}]


def test_a_header_the_lint_rejects_reports_as_such(tree, capsys):
    """The header carries no `output:`, which the lint's header category
    reports, and the marking says so rather than hiding it."""
    tree("aaa11111", OPEN_SWEEP, header="// {stem}\n// keywords: tiles\n")
    cli.cmd_sweep_mark(["aaa11111"], cached=True)
    assert read(capsys)["solvers"][0]["lint_ok"] is False
