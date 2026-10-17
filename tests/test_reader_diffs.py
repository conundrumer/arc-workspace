"""The kept trees and the kept run outputs of `handbook.reader_diffs`."""

import os
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

import handbook.reader_diffs as rd
from engine import checkout


def _git(repo: Path, *argv: str) -> str:
    env = {"PATH": os.environ["PATH"], "HOME": str(repo),
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(["git", *argv], cwd=repo, env=env, check=True,
                          capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    """A repository of one commit whose `scripts/context.py` prints its
    arguments and adds a line to `runs` for each run, as the repository
    `reader_diffs` reads, with a run cache of its own."""
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    runs = tmp_path / "runs"
    (root / "scripts" / "context.py").write_text(
        "import sys\n"
        f"open({str(runs)!r}, 'a').write('run\\n')\n"
        "print(' '.join(sys.argv[1:]))\n")
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "c")
    monkeypatch.setattr(rd, "REPO_ROOT", root)
    monkeypatch.setenv(checkout.CACHE_ENV, str(tmp_path / "cache"))
    return root, _git(root, "rev-parse", "HEAD").strip()


def _worktrees(root: Path) -> list[str]:
    return [line for line in _git(root, "worktree", "list", "--porcelain").splitlines()
            if line.startswith("worktree ")]


def test_two_updates_of_one_commit_make_one_tree(repo: tuple[Path, str]) -> None:
    root, commit = repo
    barrier = threading.Barrier(2)
    trees: list[Path] = []

    def update() -> None:
        barrier.wait()
        with rd._tree_at(commit) as tree:
            trees.append(tree)

    threads = [threading.Thread(target=update) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert trees[0] == trees[1]
    assert len(_worktrees(root)) == 2


def test_a_tree_in_use_is_not_removed(repo: tuple[Path, str],
                                      monkeypatch: pytest.MonkeyPatch) -> None:
    root, commit = repo
    monkeypatch.setattr(rd, "UNUSED_SECONDS", -1)
    with rd._tree_at(commit) as tree:
        rd._sweep(tree.parent)
        assert (tree / "scripts" / "context.py").exists()
    assert not tree.exists()
    assert len(_worktrees(root)) == 1


def test_a_kept_render_is_read_in_place_of_a_run(repo: tuple[Path, str],
                                                 tmp_path: Path) -> None:
    _, commit = repo
    with rd._tree_at(commit) as tree:
        first = rd._render_in(tree, commit, "agent", ["x"])
    with rd._tree_at(commit) as tree:
        second = rd._render_in(tree, commit, "agent", ["x"])
    assert first == second == "context agent x\n"
    assert (tmp_path / "runs").read_text() == "run\n"


def test_a_make_prunes_the_trees_of_a_deleted_cache(repo: tuple[Path, str],
                                                    tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    root, commit = repo
    with rd._tree_at(commit) as tree:
        pass
    shutil.rmtree(tree.parent)
    monkeypatch.setenv(checkout.CACHE_ENV, str(tmp_path / "other"))
    with rd._tree_at(commit):
        pass
    assert len(_worktrees(root)) == 2
