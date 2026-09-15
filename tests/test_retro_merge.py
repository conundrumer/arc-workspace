"""The retro's worktree merge: the patch it takes from a worktree, the tree it
applies that patch to, and the diffs it carries over."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from dl.paths import REPO_ROOT

SCRIPT = REPO_ROOT / "scripts" / "retro_merge.py"


@pytest.fixture(scope="module")
def retro_merge():
    """The script, loaded from its path: `scripts/` is no package."""
    spec = importlib.util.spec_from_file_location("retro_merge", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["retro_merge"] = module
    spec.loader.exec_module(module)
    return module


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


def test_merge_applies_the_change_copies_the_diffs_and_removes_the_worktree(
        retro_merge, tmp_path: Path, pair):
    repo, wt = pair
    into = repo_at(tmp_path / "into")
    result = retro_merge.merge(wt, into)
    assert result == {"applied": True, "files": ["src/a.py", "tests/test_b.py"], "conflict": ""}
    assert (into / "src" / "a.py").read_text() == "a = 2\n"
    assert (into / "tests" / "test_b.py").exists()
    assert (into / ".scratch" / "retro" / "diffs" / "src__a.py.diff").read_text() == "the diff\n"
    assert not (into / ".scratch" / "loose.txt").exists()
    assert not wt.exists()
    assert "wt" not in git(repo, "worktree", "list")


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


