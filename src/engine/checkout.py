"""The checkout's root and the directories under it, which every package
reads. Each directory is computed from `ROOT` when asked, so a checkout
that sets `ROOT` moves every one of them."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
"""The root of the checkout the tool runs in."""


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


def prompts() -> Path:
    """`prompts/`: the prose the commands print and the roles read."""
    return ROOT / "prompts"


def scratch() -> Path:
    """`.scratch/`: the run cache and what the tools write for a session."""
    return ROOT / ".scratch"
