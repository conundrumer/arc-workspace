"""What the forced removal of a merged worktree would lose, which the script
refuses before the commit and fails on before the removal: files inside
its submodules, and, before the commit alone, submodule
commits that only the worktree's own copies of the submodules' repositories
hold."""

import os
import subprocess
from pathlib import Path

import pytest

from tests.conftest import script

ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


@pytest.fixture(scope="module")
def merge_change():
    return script("merge_change")


def git(cwd: Path, *argv: str) -> str:
    done = subprocess.run(["git", "-c", "protocol.file.allow=always", *argv], cwd=cwd,
                          env=ENV, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout


def commit_file(repo: Path, name: str) -> None:
    (repo / name).write_text(name)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", name)


@pytest.fixture
def trees(tmp_path: Path, merge_change) -> tuple[Path, Path]:
    """A main tree with a submodule `s`, and a worktree on a branch of its
    own whose submodule the script has set up."""
    sub, main, worktree = tmp_path / "sub", tmp_path / "main", tmp_path / "worktree"
    for repo in (sub, main):
        repo.mkdir()
        git(repo, "init", "-q", "-b", "master")
        commit_file(repo, "a")
    git(main, "submodule", "add", "-q", str(sub), "s")
    git(main, "commit", "-q", "-m", "s")
    git(main, "worktree", "add", "-q", str(worktree), "-b", "change")
    main, worktree = main.resolve(), worktree.resolve()
    merge_change.set_up_submodules(worktree, main)
    return main, worktree


def test_untracked_file_in_submodule_is_refused(merge_change, trees):
    _, worktree = trees
    merge_change.refuse_dirty_submodules(worktree)
    (worktree / "s" / "new").write_text("new")
    with pytest.raises(merge_change.Refused, match="s/new"):
        merge_change.refuse_dirty_submodules(worktree)


def test_submodule_commit_the_main_tree_lacks_is_refused(merge_change, trees, tmp_path):
    main, worktree = trees
    commit_file(worktree / "s", "b")
    with pytest.raises(merge_change.Refused, match="lack"):
        merge_change.stage(worktree, main, tmp_path / "index")
    assert git(worktree, "diff", "--cached", "--name-only") == ""


def test_unlisted_gitlink_is_refused(merge_change, trees, tmp_path):
    main, worktree = trees
    nested = worktree / "nested"
    nested.mkdir()
    git(nested, "init", "-q", "-b", "master")
    commit_file(nested, "n")
    with pytest.raises(merge_change.Refused, match="does not list"):
        merge_change.stage(worktree, main, tmp_path / "index")
    assert git(worktree, "diff", "--cached", "--name-only") == ""


def test_change_refused_in_a_stack_reaches_master_through_no_other(
        merge_change, tmp_path, monkeypatch):
    """A change stacked on a refused one merges alone, without the refused
    change's commit beneath it."""
    sub, main = tmp_path / "sub", tmp_path / "main"
    first, second = tmp_path / "first", tmp_path / "second"
    for repo in (sub, main):
        repo.mkdir()
        git(repo, "init", "-q", "-b", "master")
        commit_file(repo, "a")
    git(main, "submodule", "add", "-q", str(sub), "s")
    git(main, "commit", "-q", "-m", "s")
    git(main, "worktree", "add", "-q", str(first), "-b", "first")
    git(main, "worktree", "add", "-q", str(second), "-b", "second")
    main, first, second = main.resolve(), first.resolve(), second.resolve()
    (first / "bad").write_text("bad")
    (second / "good").write_text("good")

    def check(tree: Path, main: Path, touched: set[str]) -> None:
        if (tree / "bad").exists():
            raise merge_change.Refused("bad")

    monkeypatch.setattr(merge_change, "check", check)
    monkeypatch.setattr(merge_change, "run_in",
                        lambda tree, argv: subprocess.CompletedProcess(argv, 0, "", ""))
    for k in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(k, ENV[k])
    assert not merge_change.merge([(first, "first"), (second, "second")])
    assert git(main, "ls-tree", "--name-only", "master").split() == [
        ".gitmodules", "a", "good", "s"]
    assert git(first, "status", "--porcelain").split() == ["??", "bad"]


def test_untracked_file_in_submodule_keeps_the_worktree(merge_change, trees):
    main, worktree = trees
    (worktree / "s" / "new").write_text("new")
    change = merge_change.Change(worktree, "change", frozenset(), "", None, "")
    with pytest.raises(merge_change.Failed, match="s/new"):
        merge_change.remove(main, change)
    assert (worktree / "s" / "new").exists()
