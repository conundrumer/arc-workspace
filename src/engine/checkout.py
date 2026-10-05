"""The checkout's root and the directories under it, which every package
reads. Each directory is computed from `ROOT` when asked, so a checkout
that sets `ROOT` moves every one of them. The run cache, the solver files
and the witness files each move to the directory an environment variable
names, where it is set. Git runs in a tree through `git`, and
`changed_paths` lists what a tree changes against a commit."""

import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
"""The root of the checkout the tool runs in."""

CACHE_ENV = "ARC_CACHE_DIR"
"""The environment variable that names the run cache in place of
`.scratch/cache/`."""

SOLVER_FILES_ENV = "ARC_SOLVER_FILES_DIR"
"""The environment variable that names the directory `solvers` returns in
place of `programs/solvers/`."""

WITNESSES_ENV = "ARC_WITNESSES_DIR"
"""The environment variable that names the directory of the witness files
in place of `programs/witnesses/`."""


def from_env(var: str, default: Path) -> Path:
    """The directory the environment variable `var` names, or `default`
    where `var` is unset. An empty value is a fault."""
    value = os.environ.get(var)
    if value is None:
        return default
    if not value:
        raise ValueError(f"{var} is set but empty")
    return Path(value)


class GitFailed(RuntimeError):
    """A git command that exited with an error: its arguments, the tree it
    ran in, and what git wrote on stderr."""

    def __init__(self, tree: Path, argv: Sequence[str], stderr: str) -> None:
        super().__init__(f"git {' '.join(argv)} failed in {tree}: {stderr.strip()}")
        self.tree = tree
        self.argv = tuple(argv)
        self.stderr = stderr


def git(tree: Path, *argv: str, stdin: str | None = None,
        env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """One git command in `tree`, with `stdin` on its standard input and
    `env` as its environment where they are given: what it did, whatever
    its exit status."""
    return subprocess.run(["git", *argv], cwd=tree, input=stdin, env=env,
                          capture_output=True, text=True)


def git_out(tree: Path, *argv: str, env: Mapping[str, str] | None = None) -> str:
    """The stdout of a git command in `tree`, which must succeed: a failure
    is `GitFailed`."""
    done = git(tree, *argv, env=env)
    if done.returncode != 0:
        raise GitFailed(tree, argv, done.stderr)
    return done.stdout


class Change(StrEnum):
    """How a path's content in a tree differs from a commit: git's status
    letter, or `UNTRACKED` for a file git neither tracks nor ignores."""

    ADDED = "A"
    DELETED = "D"
    MODIFIED = "M"
    TYPE_CHANGED = "T"
    UNTRACKED = "?"

    @property
    def added(self) -> bool:
        """Whether the path has no content at the commit."""
        return self in (Change.ADDED, Change.UNTRACKED)


@dataclass(frozen=True)
class Changed:
    """A path whose content in a tree differs from a commit, from the
    tree's root, and how it differs."""

    path: str
    change: Change


def changed_paths(tree: Path, base: str, *pathspec: str) -> list[Changed]:
    """Each path that `pathspec` matches whose content in `tree` differs
    from the commit `base`: first the tracked ones, each side of a rename
    and each submodule whose checkout differs from its commit or holds
    changes among them, then the untracked ones git does not ignore, each
    in git's order. A submodule whose only difference from its commit is
    untracked files inside it is no changed path. With no `pathspec`,
    every path."""
    spec = ["--", *pathspec] if pathspec else []
    named = git_out(tree, "diff", "--name-status", "--no-renames",
                    "--ignore-submodules=untracked", "-z", base, *spec).split("\0")
    out = [Changed(path, Change(status))
           for status, path in zip(named[0:-1:2], named[1::2], strict=True)]
    untracked = git_out(tree, "ls-files", "--others", "--exclude-standard", "-z",
                        *spec).split("\0")
    return out + [Changed(p, Change.UNTRACKED) for p in untracked if p]


def git_common_dir(tree: Path) -> Path:
    """The common git directory of the repository `tree` is a worktree of,
    which every worktree of that repository shares. A `tree` that is no
    git worktree is a fault (`GitFailed`)."""
    return (tree / git_out(tree, "rev-parse", "--git-common-dir").strip()).resolve()


def main_worktree(tree: Path) -> Path:
    """The main worktree of the repository `tree` is a worktree of: the
    directory that holds the common git directory."""
    return git_common_dir(tree).parent


def shown(path: Path, root: Path = ROOT) -> Path:
    """`path` as a line prints it: from `root`, the checkout's root where
    none is given, where it stands under it, else resolved."""
    for p, r in ((path.absolute(), root), (path.resolve(), root.resolve())):
        if p.is_relative_to(r):
            return p.relative_to(r)
    return path.resolve()


def programs() -> Path:
    """`programs/`: the lib, the proposers, the functor library, the
    solvers and their witness files."""
    return ROOT / "programs"


def solvers() -> Path:
    """`programs/solvers/`, where each solver's file stands, unless
    `SOLVER_FILES_ENV` names another directory."""
    return from_env(SOLVER_FILES_ENV, programs() / "solvers")


def witnesses() -> Path:
    """`programs/witnesses/`, where each task's witness file stands, unless
    `WITNESSES_ENV` names another directory."""
    return from_env(WITNESSES_ENV, programs() / "witnesses")


def docs() -> Path:
    """`docs/`: the handbook and the proposals."""
    return ROOT / "docs"


def handbook() -> Path:
    """`docs/handbook/`: the documents a solver session reads, which a
    `quotes` call names."""
    return docs() / "handbook"


def proposal_entry(comp: str) -> Path:
    """Where the entry of the proposal comp `comp` stands."""
    return docs() / "wf-solver" / "proposals" / f"{comp}.md"


def prompts() -> Path:
    """`prompts/`: the prose the commands print and the roles read."""
    return ROOT / "prompts"


def scratch() -> Path:
    """`.scratch/`: the run cache and what the tools write for a session."""
    return ROOT / ".scratch"


def cache() -> Path:
    """`.scratch/cache/`: the run cache, a directory per kind of result,
    unless `CACHE_ENV` names another directory."""
    return from_env(CACHE_ENV, scratch() / "cache")


def claude() -> Path:
    """`.claude/`: the agents, skills and workflows Claude Code reads."""
    return ROOT / ".claude"


def agents() -> Path:
    """`.claude/agents/`, where the agent definitions are written."""
    return claude() / "agents"


def workflows() -> Path:
    """`.claude/workflows/`: a script per workflow."""
    return claude() / "workflows"


def skills() -> Path:
    """`.claude/skills/`: a directory per skill."""
    return claude() / "skills"


def tools() -> Path:
    """`tools/`: the solver console and the editor extension."""
    return ROOT / "tools"


def console() -> Path:
    """`tools/console/`: the solver console, whose modules stand in
    `solver_console/` under it."""
    return tools() / "console"


def scripts() -> Path:
    """`scripts/`: the commands a session or the user runs."""
    return ROOT / "scripts"
