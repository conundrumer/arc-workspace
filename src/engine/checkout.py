"""The checkout's root and the directories under it, which every package
reads. Each directory is computed from `ROOT` when asked, so a checkout
that sets `ROOT` moves every one of them. The run cache, the solver files
and the witness files each move to the directory an environment variable
names, where it is set."""

import os
import subprocess
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


def _from_env(var: str, default: Path) -> Path:
    """The directory the environment variable `var` names, or `default`
    where `var` is unset. An empty value is a fault."""
    value = os.environ.get(var)
    if value is None:
        return default
    if not value:
        raise ValueError(f"{var} is set but empty")
    return Path(value)


def git_common_dir(tree: Path) -> Path:
    """The common git directory of the repository `tree` is a worktree of,
    which every worktree of that repository shares. A `tree` that is no
    git worktree is a fault."""
    done = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=tree,
                          capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError(f"{tree} is no git worktree: {done.stderr.strip()}")
    return (tree / done.stdout.strip()).resolve()


def main_worktree(tree: Path) -> Path:
    """The main worktree of the repository `tree` is a worktree of: the
    directory that holds the common git directory."""
    return git_common_dir(tree).parent


def shown(path: Path) -> Path:
    """`path` as a line prints it: from the checkout's root where it
    stands under it, else resolved."""
    for p, root in ((path.absolute(), ROOT), (path.resolve(), ROOT.resolve())):
        if p.is_relative_to(root):
            return p.relative_to(root)
    return path.resolve()


def programs() -> Path:
    """`programs/`: the lib, the proposers, the functor library, the
    solvers and their witness files."""
    return ROOT / "programs"


def solvers() -> Path:
    """`programs/solvers/`, where each solver's file stands, unless
    `SOLVER_FILES_ENV` names another directory."""
    return _from_env(SOLVER_FILES_ENV, programs() / "solvers")


def witnesses() -> Path:
    """`programs/witnesses/`, where each task's witness file stands, unless
    `WITNESSES_ENV` names another directory."""
    return _from_env(WITNESSES_ENV, programs() / "witnesses")


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
    return _from_env(CACHE_ENV, scratch() / "cache")


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
