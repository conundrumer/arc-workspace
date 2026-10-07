"""The checkout's root, the directories under it, and the directories of
the main worktree that every worktree of the repository shares, which
every package reads. Each directory is computed from `ROOT` when asked, so
a checkout that sets `ROOT` moves every one of them. The run cache, the
solver files and the witness files each move to the directory an
environment variable names, where it is set. Git runs in a tree through
`git`, `changed_paths` lists what a tree changes against a commit, and a
`uv run` in another tree runs in `tree_env`."""

import functools
import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
"""The root of the checkout the tool runs in."""

CACHE_ENV = "ARC_CACHE_DIR"
"""The environment variable that names the run cache in place of
`.cache/`."""

SOLVER_FILES_ENV = "ARC_SOLVER_FILES_DIR"
"""The environment variable that names the directory `solvers` returns in
place of `programs/solvers/`."""

WITNESSES_ENV = "ARC_WITNESSES_DIR"
"""The environment variable that names the directory of the witness files
in place of `programs/witnesses/`."""


def from_env(var: str, default: Path | Callable[[], Path]) -> Path:
    """The directory the environment variable `var` names, or `default`
    where `var` is unset, called where it is a function, so that it is
    computed only where it is used. An empty value is a fault."""
    value = os.environ.get(var)
    if value is None:
        return default() if callable(default) else default
    if not value:
        raise ValueError(f"{var} is set but empty")
    return Path(value)


def tree_env() -> dict[str, str]:
    """The environment in which a `uv run` command runs in its tree's own
    environment."""
    return {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}


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


def git_out(tree: Path, *argv: str, stdin: str | None = None,
            env: Mapping[str, str] | None = None) -> str:
    """The stdout of a git command in `tree`, with `stdin` on its standard
    input where it is given, which must succeed: a failure is `GitFailed`."""
    return _succeeded(tree, argv, git(tree, *argv, stdin=stdin, env=env))


def _succeeded(tree: Path, argv: Sequence[str],
               done: subprocess.CompletedProcess[str]) -> str:
    """The stdout of the git command `done`, which ran `argv` in `tree`; a
    nonzero exit is `GitFailed`."""
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
    from the commit `base`: first the tracked ones, each side of a rename,
    each submodule whose checkout differs from its commit or holds changes,
    and each path the index of `tree` marks skip-worktree, present in the
    tree or absent from it, among them, in the order of the index, then the
    untracked ones git does not ignore, in git's order. A submodule whose
    only difference from its commit is untracked files inside it is no
    changed path. A skip-worktree mark on a submodule is a fault
    (`ValueError`). With no `pathspec`, every path."""
    spec = ["--", *pathspec] if pathspec else []
    named = git_out(tree, "diff", "--name-status", "--no-renames",
                    "--ignore-submodules=untracked", "-z", base, *spec).split("\0")
    marked = _skip_worktree(tree, spec)
    tracked = {path: Change(status)
               for status, path in zip(named[0:-1:2], named[1::2], strict=True)}
    for path in marked:
        tracked.pop(path, None)
    tracked |= _marked_changes(tree, base, marked)
    untracked = git_out(tree, "ls-files", "--others", "--exclude-standard", "-z",
                        *spec).split("\0")
    return ([Changed(p, tracked[p]) for p in sorted(tracked, key=os.fsencode)]
            + [Changed(p, Change.UNTRACKED) for p in untracked if p])


class Mode(StrEnum):
    """The mode git gives an entry of the index or of a tree."""

    REGULAR = "100644"
    EXECUTABLE = "100755"
    SYMLINK = "120000"
    GITLINK = "160000"
    """An entry that records a submodule's commit."""
    TREE = "040000"
    """A directory, which a tree gives and the index does not."""


@dataclass(frozen=True)
class IndexEntry:
    """An entry of the index: its mode, its object name, which for a
    gitlink is the submodule's commit, and its path."""

    mode: Mode
    object_name: str
    path: str


def index_entry(entry: str) -> IndexEntry:
    """An entry as `git ls-files -s -z` prints it, with no tag before it.
    A mode of no known form is a fault (`ValueError`)."""
    meta, path = entry.split("\t", 1)
    mode, object_name, _stage = meta.split(" ")
    return IndexEntry(Mode(mode), object_name, path)


def _skip_worktree(tree: Path, spec: Sequence[str]) -> list[str]:
    """Each path that `spec` matches and the index of `tree` marks
    skip-worktree, whose content `git diff` reads from the index in place
    of the tree. A mark on a submodule is a fault (`ValueError`)."""
    marked: list[str] = []
    for entry in git_out(tree, "ls-files", "-v", "-s", "-z", *spec).split("\0"):
        if not entry.startswith("S "):
            continue
        found = index_entry(entry.removeprefix("S "))
        if found.mode == Mode.GITLINK:
            raise ValueError(f"the submodule {found.path} in {tree} is marked skip-worktree")
        marked.append(found.path)
    return marked


def _marked_changes(tree: Path, base: str, marked: Sequence[str]) -> dict[str, Change]:
    """How each path of `marked` whose content in `tree` differs from the
    commit `base` differs: its blob, and whether it is a symbolic link, at
    each side."""
    if not marked:
        return {}
    at_base = {path: (Mode(meta.split(" ")[0]) == Mode.SYMLINK, meta.split(" ")[2])
               for entry in git_out(tree, "--literal-pathspecs", "ls-tree", "-z", base,
                                    "--", *marked).split("\0") if entry
               for meta, path in [entry.split("\t", 1)]}
    files = [p for p in marked if (tree / p).is_file() and not (tree / p).is_symlink()]
    blobs = git_out(tree, "hash-object", "--stdin-paths", stdin="\n".join(files))
    in_tree = {p: (False, oid) for p, oid in zip(files, blobs.split(), strict=True)}
    for p in marked:
        if (tree / p).is_symlink():
            in_tree[p] = (True, git_out(tree, "hash-object", "--stdin", "--no-filters",
                                        stdin=os.readlink(tree / p)).strip())
    out: dict[str, Change] = {}
    for path in marked:
        was, now = at_base.get(path), in_tree.get(path)
        if was == now:
            continue
        out[path] = (Change.ADDED if was is None else Change.DELETED if now is None
                     else Change.TYPE_CHANGED if was[0] != now[0] else Change.MODIFIED)
    return out


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


@functools.cache
def _shared(root: Path) -> Path:
    """`main_worktree` of `root`, kept for the process."""
    return main_worktree(root)


def caches() -> Path:
    """`.cache/` in the main worktree, which every worktree of the
    repository shares: the run cache and the gate's records of the
    machine."""
    return _shared(ROOT) / ".cache"


def cache() -> Path:
    """The run cache, a directory per kind of result: `caches()`, unless
    `CACHE_ENV` names another directory."""
    return from_env(CACHE_ENV, caches)


def work() -> Path:
    """`work/` in the main worktree, beside `caches()`: the files the
    sessions share and cite, a directory per `<domain>/<subject>`, and
    the cards."""
    return _shared(ROOT) / "work"


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
