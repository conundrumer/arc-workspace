"""The reads of git and of the main worktree that the operator's procedures
take their state from: the worktrees, the commits of `master`, the code
review tags, the task claims, the accepted gate outputs a change writes,
and the session's scratchpad directory."""

import os
from pathlib import Path

from engine import checkout
from operating.state import Commit

COMMITS = 300
"""The commits of `master` read for After a batch, newest first."""

CODE_DIRS = ("src/", "scripts/", "tests/")
ACCEPTED = "tests/gate/accepted"


def main_tree() -> Path:
    return checkout.main_worktree(checkout.ROOT)


def git(main: Path, *argv: str) -> str:
    return checkout.git_out(main, *argv)


def worktrees(main: Path) -> dict[Path, str | None]:
    """Each worktree, with its branch, or None where it stands on none."""
    out: dict[Path, str | None] = {}
    tree: Path | None = None
    for line in git(main, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            tree = Path(line.split(" ", 1)[1])
            out[tree] = None
        elif line.startswith("branch refs/heads/") and tree is not None:
            out[tree] = line.removeprefix("branch refs/heads/")
    return out


def commits(main: Path) -> tuple[Commit, ...]:
    out: list[Commit] = []
    for chunk in git(main, "log", "master", f"-n{COMMITS}", "--format=%x00%H %ct %s",
                     "--name-only").split("\0")[1:]:
        head, _, names = chunk.partition("\n")
        sha, ct, subject = (head.split(" ", 2) + [""])[:3]
        out.append(Commit(sha, float(ct), any(n.startswith(CODE_DIRS) for n in names.split()),
                          subject))
    return tuple(out)


def code_review(main: Path) -> int | None:
    tags = [int(t.rsplit("/", 1)[1]) for t in git(main, "tag", "-l", "code-review/*").split()
            if t.rsplit("/", 1)[1].isdigit()]
    return max(tags) if tags else None


def claims(main: Path) -> dict[str, str]:
    return {p.parent.name: p.read_text().strip()
            for p in (main / "work" / "task").glob("*/claim")}


def gate_outputs(tree: Path) -> tuple[str, ...]:
    """The accepted gate outputs the change in the worktree `tree` writes,
    against `master`."""
    changed = git(tree, "diff", "--name-only", "master", "--", ACCEPTED).split()
    added = git(tree, "ls-files", "--others", "--exclude-standard", "--", ACCEPTED).split()
    return tuple(sorted({*changed, *added}))


def scratch(session: str) -> Path:
    """The session's scratchpad directory, as the section `Launching` of
    `prompts/agents/notes/launching.md` gives it, for a session that
    started in the main worktree, as the coordinator's does."""
    started = str(main_tree())
    return (Path(f"/private/tmp/claude-{os.getuid()}") / started.replace("/", "-") / session
            / "scratchpad")
