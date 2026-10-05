"""The retro's worktree merge into a tree that refuses its patch: the tree
keeps its files, and the worktree, which holds the only copy of the change,
stays."""

import subprocess
from pathlib import Path

import pytest

from tests.conftest import script


@pytest.fixture(scope="module")
def retro_merge():
    return script("retro_merge")


def git(cwd: Path, *argv: str) -> str:
    done = subprocess.run(["git", *argv], cwd=cwd, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout


def repo_at(root: Path) -> Path:
    """A repo with one commit: a tracked file under `src/` and one under `tests/`."""
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "src" / "a.py").write_text("a = 1\n")
    (root / "tests" / "test_a.py").write_text("def test_a():\n    assert True\n")
    (root / ".gitignore").write_text(".venv/\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "init")
    return root


def worktree_of(repo: Path, path: Path) -> Path:
    """A worktree of `repo` at HEAD, with a tracked edit, a new file, and a
    diff file of its own."""
    git(repo, "worktree", "add", "-q", str(path), "HEAD")
    (path / "src" / "a.py").write_text("a = 2\n")
    (path / "tests" / "test_b.py").write_text("def test_b():\n    assert True\n")
    (path / ".scratch" / "retro" / "diffs").mkdir(parents=True)
    (path / ".scratch" / "retro" / "diffs" / "src__a.py.diff").write_text("the diff\n")
    (path / ".scratch" / "loose.txt").write_text("scratch\n")
    return path


@pytest.fixture
def pair(tmp_path: Path) -> tuple[Path, Path]:
    """A repo and a worktree of it that holds a change."""
    repo = repo_at(tmp_path / "repo")
    return repo, worktree_of(repo, tmp_path / "wt")


def test_a_tree_that_refuses_the_patch_keeps_its_files_and_the_worktree(
        retro_merge, tmp_path: Path, pair):
    _, wt = pair
    into = repo_at(tmp_path / "into")
    (into / "src" / "a.py").write_text("a = 99\n")
    result = retro_merge.merge(wt, into)
    assert result["applied"] is False
    assert result["conflict"]
    assert (into / "src" / "a.py").read_text() == "a = 99\n"
    assert not (into / "tests" / "test_b.py").exists()
    assert wt.is_dir()
