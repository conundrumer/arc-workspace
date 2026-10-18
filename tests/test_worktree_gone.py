"""A read of the operator's state races a merge that removes a change
worktree the read listed: `operate_loop.read_again` reads once more and
gives the second read, and a worktree git still lists with its directory
gone ends the read with `FileNotFoundError`; the reads of `tree_reads` on
a change worktree give, for a removed one, what a worktree with no diff
gives."""

import shutil
import subprocess
from pathlib import Path

import pytest

from engine import checkout
from handbook.paths import scripts_importable
from tests.conftest import script

ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def repo_with_worktree(tmp_path: Path) -> tuple[Path, Path]:
    main, tree = tmp_path / "main", tmp_path / "change"
    main.mkdir(parents=True)
    for argv in (["init", "-q", "-b", "master"], ["commit", "-q", "--allow-empty", "-m", "c"],
                 ["worktree", "add", "-q", "-b", "change", str(tree)]):
        subprocess.run(["git", *argv], cwd=main, env=ENV, check=True, capture_output=True)
    return main, tree


def heads_read(main: Path, between: list[Path]):
    """A read that lists the worktrees and then reads each one's `HEAD`;
    before its first read of a tree, the worktree `between` gives is
    removed, as a merge removes one."""
    def read(_deadline: float) -> list[str]:
        trees = [w.path for w in checkout.worktree_list(main)]
        while between:
            checkout.git_out(main, "worktree", "remove", str(between.pop()))
        return [checkout.git_out(t, "rev-parse", "HEAD") for t in trees]
    return read


def test_a_read_that_races_a_worktree_removal_is_read_again(tmp_path: Path) -> None:
    scripts_importable()
    loop = script("operate_loop")
    main, tree = repo_with_worktree(tmp_path)
    with pytest.raises(FileNotFoundError):
        heads_read(main, [tree])(0.0)
    main, tree = repo_with_worktree(tmp_path / "again")
    assert len(loop.read_again(heads_read(main, [tree]))(0.0)) == 1


def test_a_listed_worktree_whose_directory_is_gone_ends_the_read(tmp_path: Path) -> None:
    scripts_importable()
    loop = script("operate_loop")
    main, tree = repo_with_worktree(tmp_path)
    shutil.rmtree(tree)
    with pytest.raises(FileNotFoundError):
        loop.read_again(heads_read(main, []))(0.0)


def test_the_reads_of_a_removed_worktree_give_what_a_tree_with_no_diff_gives(tmp_path: Path) -> None:
    scripts_importable()
    reads = script("tree_reads")
    main, tree = repo_with_worktree(tmp_path)
    checkout.git_out(main, "worktree", "remove", str(tree))
    assert reads.merge_base(tree) is None
    assert reads.fragments(tree) == ()
    assert reads.gate_outputs(tree) == ()


def test_a_read_raced_by_a_worktree_removal_gives_what_a_removed_worktree_gives(
        tmp_path: Path) -> None:
    scripts_importable()
    reads = script("tree_reads")
    main, tree = repo_with_worktree(tmp_path)

    def read() -> str:
        checkout.git_out(main, "worktree", "remove", str(tree))
        return checkout.git_out(tree, "rev-parse", "HEAD")
    assert reads.standing(tree, read, None) is None
