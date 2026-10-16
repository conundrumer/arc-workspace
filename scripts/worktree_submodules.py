"""The git submodules of a worktree that `merge_change.py`, `materialize.py`
and `patch_stub.py` set up: the submodules a tree's `.gitmodules` lists,
the main tree's copy of each one's repository, whether one is checked out,
and the setup of a worktree's submodules from those copies with no
network."""

import fcntl
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout

UPSTREAM_LOCK = "arc-upstream.lock"
"""The lock file, in the repository's common git directory, that one
submodule setup at a time holds."""


@dataclass(frozen=True)
class Submodule:
    """A submodule `.gitmodules` lists: its name, and its path in the tree."""

    name: str
    path: str


def submodules(tree: Path) -> list[Submodule]:
    """The submodules the `.gitmodules` of `tree` lists, in its order."""
    listed = checkout.git_out(tree, "config", "-f", ".gitmodules", "-z",
                     "--get-regexp", r"^submodule\..*\.path$")
    found: list[Submodule] = []
    for entry in filter(None, listed.split("\0")):
        key, path = entry.split("\n", 1)
        found.append(Submodule(key.removeprefix("submodule.").removesuffix(".path"), path))
    return found


def main_gitdir(main: Path, sub: Submodule) -> str:
    """The git directory of submodule `sub` in the main tree, which holds
    the main tree's copy of its repository."""
    return checkout.git_out(main, "rev-parse", "--path-format=absolute",
                   "--git-path", f"modules/{sub.name}").strip()


def update(worktree: Path, main: Path) -> None:
    """Run `git submodule update --init` in the worktree, with each
    submodule's URL set to the main tree's copy of its repository, and every
    transport but the local one refused."""
    overrides: list[str] = []
    for sub in submodules(worktree):
        overrides += ["-c", f"submodule.{sub.name}.url={main_gitdir(main, sub)}"]
    checkout.git_out(worktree, *overrides, "submodule", "update", "--init",
            env={**os.environ, "GIT_ALLOW_PROTOCOL": "file"})


def checked_out(tree: Path, sub: Submodule) -> bool:
    """Whether submodule `sub` is checked out in `tree`: its path is the top
    directory of a repository of its own."""
    path = tree / sub.path
    return path.is_dir() and Path(checkout.git_out(
        path, "rev-parse", "--show-toplevel").strip()) == path


class SetupFailed(RuntimeError):
    """A setup by `locked_update` that failed, with its cause."""


SETUP_FAILED = mctx("setting up the submodules of {tree} from {main} failed: {cause}")


def locked_update(tree: Path, main: Path) -> None:
    """Run `update` on `tree` from `main`, one setup at a time across the
    repository's worktrees."""
    with open(checkout.git_common_dir(tree) / UPSTREAM_LOCK, "a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            update(tree, main)
        except checkout.GitFailed as exc:
            raise SetupFailed(SETUP_FAILED.format(tree=tree, main=main, cause=exc)) from exc


def set_up(tree: Path) -> None:
    """Set up the submodules of `tree` by `locked_update`, from the main
    tree's copies, where one is not checked out."""
    if all(checked_out(tree, sub) for sub in submodules(tree)):
        return
    locked_update(tree, checkout.main_worktree(tree))


def set_up_in_script(tree: Path) -> bool:
    """Run `set_up` on `tree` for a script, and print its failure on
    stderr. Whether the submodules stand checked out."""
    try:
        set_up(tree)
    except SetupFailed as exc:
        print(exc, file=sys.stderr)
        return False
    return True
