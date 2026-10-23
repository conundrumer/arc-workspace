"""A solver declares no relation that the lib declares: Souffle refuses
the program as a redefinition."""

import re
from pathlib import Path

PROGRAMS = Path(__file__).resolve().parents[2] / "programs"
DECL = re.compile(r"^\.decl\s+(\w+)", re.MULTILINE)


def _names(path: Path) -> set[str]:
    return set(DECL.findall(path.read_text()))


def test_no_solver_declares_a_name_the_lib_declares():
    lib = set().union(*(_names(p) for p in (PROGRAMS / "lib").glob("*.dl")))
    clashes = [f"{p.name} {n}" for p in sorted((PROGRAMS / "solvers").glob("*.dl"))
               for n in sorted(_names(p) & lib)]
    assert not clashes, clashes
