"""The lint names a positive read of an input of a lib component's instance that no clause of the solver writes."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOLVER = ROOT / "tests" / "gate" / "solvers" / "99306f82.dl"
BEFORE = """marks.before($U(), P, Q) :-
    mark(P, _), mark(Q, _), params.corner(D), nearer(D, P, Q).
"""
READ = """.decl unordered(p: Position)
unordered(P) :- marks.before($U(), P, _).
"""


def lint(path: Path) -> str:
    return subprocess.run([sys.executable, "scripts/run_dl.py", "lint", str(path)], cwd=ROOT,
                          capture_output=True, text=True).stdout


def test_a_read_of_an_input_no_clause_writes_is_named(tmp_path: Path):
    text = SOLVER.read_text()
    assert BEFORE in text
    path = tmp_path / SOLVER.name
    path.write_text(text.replace(BEFORE, READ))
    line = text.replace(BEFORE, READ).split("\n").index("unordered(P) :- marks.before($U(), P, _).") + 1
    assert f"{SOLVER.name}:{line}: unfilled-input: `marks.before` is read" in lint(path)


def test_a_read_of_an_input_a_clause_writes_gives_no_such_finding(tmp_path: Path):
    path = tmp_path / SOLVER.name
    path.write_text(SOLVER.read_text())
    assert "unfilled-input" not in lint(path)
