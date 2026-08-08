"""Locations of the Souffle sources and build artifacts the runner works with."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROGRAMS_DIR = REPO_ROOT / "programs"
SOLVERS_DIR = PROGRAMS_DIR / "solvers"
FUNCTORS_SRC = PROGRAMS_DIR / "lib_functors.cpp"
FUNCTORS_LIB = PROGRAMS_DIR / "libfunctors.dylib"
PROPOSERS_SRC = PROGRAMS_DIR / "proposers.dl"


def all_stems() -> list[str]:
    """Solver stems, skipping dotfiles: a concurrent run materializes
    `.tmp*.dl` scratch files into the solvers directory."""
    return sorted(
        p.stem for p in SOLVERS_DIR.glob("*.dl") if not p.name.startswith(".")
    )
