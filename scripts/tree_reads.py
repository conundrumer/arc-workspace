"""The reads of git and of the main worktree that the operator's procedures
take their state from: the worktrees, the commits of `master`, the code
review tags, the task claims, the accepted gate outputs a change writes,
and the session's scratchpad directory."""

import os
from pathlib import Path

from engine import checkout
from operations.state import Commit
from operations.task_work import CLAIM, tasks_work

COMMITS = 300
"""The commits of `master` read for After a batch, newest first."""

CODE_DIRS = ("src/", "scripts/", "tests/")
PROCESS_DIRS = ("prompts/agents/", "src/operations/")
ACCEPTED = "tests/gate/accepted"


def main_tree() -> Path:
    return checkout.main_worktree(checkout.ROOT)


def git(main: Path, *argv: str) -> str:
    return checkout.git_out(main, *argv)


def worktrees(main: Path) -> dict[Path, str | None]:
    return {w.path: w.branch for w in checkout.worktree_list(main)}


def commits(main: Path) -> tuple[Commit, ...]:
    out: list[Commit] = []
    for chunk in git(main, "log", "master", f"-n{COMMITS}", "--format=%x00%H %ct %s",
                     "--name-only").split("\0")[1:]:
        head, _, names = chunk.partition("\n")
        sha, ct, subject = (head.split(" ", 2) + [""])[:3]
        files = names.split()
        out.append(Commit(sha, float(ct), any(n.startswith(CODE_DIRS) for n in files), subject,
                          any(n.startswith(PROCESS_DIRS) for n in files)))
    return tuple(out)


def code_review(main: Path) -> int | None:
    tags = [int(t.rsplit("/", 1)[1]) for t in git(main, "tag", "-l", "code-review/*").split()
            if t.rsplit("/", 1)[1].isdigit()]
    return max(tags) if tags else None


def claims(main: Path) -> dict[str, str]:
    return {p.parent.name: p.read_text().strip()
            for p in tasks_work(main).glob(f"*/{CLAIM}")}


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
