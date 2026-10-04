"""What the forced removal of a merged worktree would lose, which the script
refuses before the commit: files inside its submodules, and submodule
commits that only the worktree's own copies of the submodules' repositories
hold."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

SCRIPT = REPO_ROOT / "scripts" / "merge_change.py"

ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


@pytest.fixture(scope="module")
def merge_change():
    """The script, loaded from its path: `scripts/` is no package."""
    spec = importlib.util.spec_from_file_location("merge_change", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["merge_change"] = module
    spec.loader.exec_module(module)
    return module


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
