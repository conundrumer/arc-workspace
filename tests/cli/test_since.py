"""The scope `since` gives, over a repository of dated commits: the stems
the commits in the window touch, a commit that rewrites over half the
corpus left out, a window whose commits together do kept to the solvers
they add, and the working tree's changes. A wrong scope surveys the wrong
solvers with nothing to show it, and the scope rests on reading git's
output."""

import os
from pathlib import Path

import pytest

from cli import text
from cli.survey import cmd_since
from engine import checkout

SOLVERS = Path("programs") / "solvers"
WINDOW = "2026-01-15T00:00:00"


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty repository the commands take as the checkout."""
    monkeypatch.setattr(checkout, "ROOT", tmp_path)
    monkeypatch.delenv(checkout.SOLVER_FILES_ENV, raising=False)
    checkout.git_out(tmp_path, "init", "-q")
    (tmp_path / SOLVERS).mkdir(parents=True)
    return tmp_path


def write(repo: Path, *stems: str) -> None:
    for stem in stems:
        path = repo / SOLVERS / f"{stem}.dl"
        path.write_text(path.read_text() + "//\n" if path.exists() else f"// {stem}\n")


def commit(repo: Path, date: str, *stems: str) -> None:
    """Write each of `stems` and commit them, dated `date`."""
    write(repo, *stems)
    checkout.git_out(repo, "add", "-A")
    env = {**os.environ, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
    checkout.git_out(repo, "-c", "user.name=t", "-c", "user.email=t@t", "-c",
                     "commit.gpgsign=false", "commit", "-q", "-m", date, env=env)


def scope(capsys: pytest.CaptureFixture[str]) -> list[str]:
    assert cmd_since(WINDOW) == 0
    return capsys.readouterr().out.split()


def test_the_window_holds_its_commits_and_the_working_tree_but_no_rewrite(repo, capsys):
    commit(repo, "2026-01-01T00:00:00", "a", "b", "c", "d", "e", "f")
    commit(repo, "2026-01-10T00:00:00", "d")
    commit(repo, "2026-02-01T00:00:00", "a")
    commit(repo, "2026-02-02T00:00:00", "b", "c", "d", "e")
    write(repo, "f", "g")
    checkout.git_out(repo, "mv", str(SOLVERS / "e.dl"), str(SOLVERS / "h.dl"))
    assert scope(capsys) == ["a", "f", "g", "h"]


def test_a_window_whose_commits_together_rewrite_the_corpus_keeps_what_they_add(
        repo, capsys):
    commit(repo, "2026-01-01T00:00:00", "a", "b", "c", "d", "e", "f")
    commit(repo, "2026-02-01T00:00:00", "a", "b")
    commit(repo, "2026-02-02T00:00:00", "c", "g")
    assert scope(capsys) == ["g"]


def test_a_failing_git_call_exits_1_with_git_s_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(checkout, "ROOT", tmp_path)
    monkeypatch.delenv(checkout.SOLVER_FILES_ENV, raising=False)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    assert cmd_since(WINDOW) == 1
    err = capsys.readouterr().err
    assert err.startswith(text.GIT_FAILED.format(error="")) and "not a git repository" in err
