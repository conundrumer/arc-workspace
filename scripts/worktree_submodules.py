"""The git submodules of a worktree that `merge_change.py` sets up: the
submodules a tree's `.gitmodules` lists, the main tree's copy of each one's
repository, whether one is checked out, and the setup of a worktree's
submodules from those copies with no network."""

import os
from dataclasses import dataclass
from pathlib import Path

from engine import checkout


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
