"""The parsed view of the solver corpus: each file with its AST and index."""

from collections.abc import Iterator
from pathlib import Path

from dl.dlparse import Index, Program, parse
from dl.paths import SOLVERS_DIR, all_stems


def each_solver() -> Iterator[tuple[Path, Program, Index]]:
    """Every solver, parsed and indexed, in stem order."""
    for stem in all_stems():
        path = SOLVERS_DIR / f"{stem}.dl"
        program = parse(path.read_text())
        yield path, program, Index(program)
