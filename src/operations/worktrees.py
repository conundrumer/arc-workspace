"""The worktree of a change: the one its ticket's log gives, and
`fingerprint`, the state of that worktree."""

import hashlib
import re
from pathlib import Path

from engine import checkout

from operations.state import State, Ticket
from ticketing.vocabulary import Note

BASE = "master"
"""The branch a change's worktree branches from and merges into."""

WORKTREES = ".claude/worktrees"
"""The directory, under the main tree, of the worktrees of changes."""

WORKTREE = re.compile(rf"(/\S+/{re.escape(WORKTREES)}/[^\s,;:)]+)")


def logged_worktree(t: Ticket) -> Path | None:
    """The worktree the latest line of `t`'s log that gives one gives,
    past each line whose note opens with `rerun`. A line whose note opens
    with `rerun` and stands after the worktree's line leaves none."""
    for line in reversed(t.log):
        if line.note.startswith(Note.RERUN):
            return None
        m = WORKTREE.search(line.note)
        if m is not None:
            return Path(m[1])
    return None


def fingerprint(w: Path) -> str:
    """What `scripts/change_worktree.py --fingerprint w` prints, as its
    `--help` gives it."""
    digest = hashlib.sha256(checkout.git_out(w, "diff", "--merge-base", BASE,
                                             "--binary").encode())
    for rel in sorted(checkout.untracked(w)):
        digest.update(rel.encode() + b"\0")
        digest.update((w / rel).read_bytes() + b"\0")
    return digest.hexdigest()


def worktree(t: Ticket, state: State) -> Path | None:
    """`logged_worktree` of `t`, where it stands."""
    return worktree_in(t, state.git.worktrees)


def worktree_in(t: Ticket, worktrees: frozenset[Path]) -> Path | None:
    """`logged_worktree` of `t`, where it is among `worktrees`."""
    path = logged_worktree(t)
    return path if path in worktrees else None
