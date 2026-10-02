"""The checkout's root and the directories under it, which every package
reads. Each directory is computed from `ROOT` when asked, so a checkout
that sets `ROOT` moves every one of them."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
"""The root of the checkout the tool runs in."""


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
    """`programs/solvers/`, the directory `solver.model.load` reads."""
    return programs() / "solvers"


def witnesses() -> Path:
    """`programs/witnesses/`, where each task's witness file stands."""
    return programs() / "witnesses"


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
    """`.scratch/cache/`: the run cache, a directory per kind of result."""
    return scratch() / "cache"


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
