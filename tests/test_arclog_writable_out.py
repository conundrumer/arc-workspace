import subprocess
from pathlib import Path

import pytest

from arclog_convert import OUT_ENV, out, writable_out


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def trees(tmp_path: Path) -> tuple[Path, Path]:
    main = tmp_path / "main"
    main.mkdir()
    git(main, "init", "-q")
    git(main, "commit", "-q", "--allow-empty", "-m", "x")
    linked = tmp_path / "linked"
    git(main, "worktree", "add", "-q", "--detach", str(linked))
    return main, linked


def test_linked_worktree_without_out_refuses(trees: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    main, linked = trees
    monkeypatch.delenv(OUT_ENV, raising=False)
    with pytest.raises(SystemExit, match="--out"):
        writable_out(linked)
    assert writable_out(main) == out()


def test_linked_worktree_with_out_env_writes_there(trees: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _, linked = trees
    monkeypatch.setenv(OUT_ENV, str(tmp_path / "o"))
    assert writable_out(linked) == tmp_path / "o"
