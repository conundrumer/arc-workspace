"""The trees of commits kept under `checkout.cache()` for the reads of
`reader_diffs`, each a detached git worktree of the repository, with the
locks that make each once and keep it while a process reads it, and the
sweep that removes those unused for `UNUSED_SECONDS`."""

from __future__ import annotations

import fcntl
import os
import shutil
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO

from engine import checkout
from handbook.paths import REPO_ROOT


TREES = "reader-trees"
"""The directory under `checkout.cache()` that holds the kept trees
(`tree_at`)."""

UNUSED_SECONDS = 30 * 60
"""How long a kept tree stays after its last use (`tree_at`)."""


@contextmanager
def flocked(path: Path, op: int) -> Iterator[IO[str]]:
    """The lock file at `path`, held through `flock` with `op`. A file that
    a holder removed while this one waited for it is opened again, so that
    each hold is on the file that stands at `path`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        with path.open("a+") as f:
            fcntl.flock(f, op)
            try:
                standing = os.stat(path).st_ino == os.fstat(f.fileno()).st_ino
            except FileNotFoundError:
                standing = False
            if standing:
                yield f
                return


def remove_tree(tree: Path) -> None:
    """Removes `tree` and its entry in `git worktree list`, where either
    stands."""
    try:
        checkout.git_out(REPO_ROOT, "worktree", "remove", "--force", str(tree))
    except checkout.GitFailed:
        shutil.rmtree(tree, ignore_errors=True)


def sweep(trees: Path) -> None:
    """Removes each kept tree under `trees` that no block has used for
    `UNUSED_SECONDS` and whose locks are free at once (`tree_at`)."""
    for use in sorted(trees.glob("*.use")):
        make = use.with_suffix(".make")
        try:
            if time.time() - use.stat().st_mtime < UNUSED_SECONDS:
                continue
            with (flocked(make, fcntl.LOCK_EX | fcntl.LOCK_NB),
                  flocked(use, fcntl.LOCK_EX | fcntl.LOCK_NB)):
                if time.time() - use.stat().st_mtime < UNUSED_SECONDS:
                    continue
                use.with_suffix(".whole").unlink(missing_ok=True)
                remove_tree(use.with_suffix(""))
                use.unlink()
                make.unlink(missing_ok=True)
        except (BlockingIOError, FileNotFoundError):
            continue


@contextmanager
def tree_at(commit: str) -> Iterator[Path]:
    """The tree of `commit`, a detached git worktree of the repository kept
    under `checkout.cache()`, one per commit, so that the checkout stays as
    it is, the commit's own code finds the main worktree as in any other
    checkout, and the tree of the old commit of one merge is made once,
    by the merge (`keep_tree`) or by the first update after it.

    A tree is whole only once `git worktree add` has succeeded, so a tree
    with no whole mark is made again. Each make prunes the entries of
    `git worktree list` whose directory is gone, such as those of the
    trees of a run cache that was deleted, which no sweep reads again. A
    block holds the tree's lock shared while it reads the tree, so that no
    process removes a tree in use (`sweep`). A commit git does not know is
    a fault."""
    try:
        full = checkout.git_out(REPO_ROOT, "rev-parse", "--verify", "--end-of-options",
                                f"{commit}^{{commit}}").strip()
    except checkout.GitFailed as e:
        raise SystemExit(e.stderr.strip())
    trees = checkout.cache() / TREES
    tree = trees / full
    use, make, whole = (tree.with_suffix(s) for s in (".use", ".make", ".whole"))
    try:
        while True:
            with flocked(use, fcntl.LOCK_SH):
                if whole.exists():
                    os.utime(use)
                    yield tree
                    return
            with flocked(make, fcntl.LOCK_EX):
                if whole.exists():
                    continue
                with flocked(use, fcntl.LOCK_EX):
                    os.utime(use)
                    remove_tree(tree)
                    checkout.git_out(REPO_ROOT, "worktree", "prune")
                    try:
                        checkout.git_out(REPO_ROOT, "worktree", "add", "--force",
                                         "--detach", str(tree), full)
                    except checkout.GitFailed as e:
                        raise SystemExit(e.stderr.strip())
                    whole.touch()
    finally:
        sweep(trees)


def keep_tree(commit: str) -> None:
    """Makes the kept tree of `commit` (`tree_at`) where none stands, so
    that the blocks that need it later enter it whole."""
    with tree_at(commit):
        pass
