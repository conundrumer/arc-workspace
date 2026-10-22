"""The worktree that tests of a change share."""

import shutil
import subprocess
from pathlib import Path


def git(cwd: Path, *argv: str) -> None:
    subprocess.run([shutil.which("git") or "git", "-C", str(cwd), *argv], check=True,
                   capture_output=True, env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                                             "GIT_COMMITTER_NAME": "t",
                                             "GIT_COMMITTER_EMAIL": "t@t"})


def worktree(tmp_path: Path) -> Path:
    main = tmp_path / "main"
    main.mkdir()
    git(main, "init", "-q", "-b", "master")
    (main / "a.txt").write_text("a\n")
    git(main, "add", "a.txt")
    git(main, "commit", "-q", "-m", "a")
    w = main / ".claude" / "worktrees" / "change-9-1"
    git(main, "worktree", "add", "-q", "-b", "change-9-1", str(w))
    return w
