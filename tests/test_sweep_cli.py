"""`sweep --open` and `sweep --mark`: the cache they read, and the line the
marking writes once."""

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


def test_a_parameter_already_marked_takes_no_second_line(tree, capsys):
    header = HEADER + "// review sweep: bg — the pairs leave its value open\n"
    path = tree("aaa11111", OPEN_SWEEP, header=header)
    before = path.read_text()
    cli.cmd_sweep_mark(["aaa11111"], cached=True)
    assert read(capsys)["solvers"] == [
        {"task_id": "aaa11111", "lines": [], "lint_ok": True}]
    assert path.read_text() == before


