"""A negated defect relation converts to an `ALL` only where the reading clause gives the `ALL`'s domain a member."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEM = "7837ac64"
ORIGINAL = "gapped_line(L) :- in(P, Col), params.bg(Col), axis_elem(A), split(P, A, L, _)."
TRIAL = ("gapped_line(L) :- in(P, Col), params.bg(Col), dir_elem(D), neighbor(P, D, Q), !in(Q, Col), "
         "axis_of(D, A2), perp(A2, A), split(P, A, L, _).")


def converted(tmp_path: Path) -> str:
    """The conversion of the solver `STEM` whose `gapped_line` clause is `TRIAL`."""
    source = (ROOT / "programs" / "solvers" / f"{STEM}.dl").read_text()
    assert ORIGINAL in source
    programs = tmp_path / "programs"
    (programs / "solvers").mkdir(parents=True)
    for entry in (ROOT / "programs").iterdir():
        if entry.name != "solvers":
            (programs / entry.name).symlink_to(entry)
    (programs / "solvers" / f"{STEM}.dl").write_text(source.replace(ORIGINAL, TRIAL))
    subprocess.run([sys.executable, "-m", "arclog_convert.convert", "--no-train-replay", "--no-row-parity", "--out", str(tmp_path / "out"), STEM],
                   cwd=ROOT, check=True, capture_output=True, env={**os.environ, "ARCLOG_SOLVERS": str(programs / "solvers")})
    return (tmp_path / "out" / "gen" / f"{STEM}.arclog").read_text()


def rule(text: str, name: str) -> str:
    return text[text.index(f"(RULE &{name}"):].split("\n\n")[0]


def test_a_negation_whose_domain_can_be_empty_is_a_not_over_a_rule(tmp_path: Path):
    text = converted(tmp_path)
    assert "(NOT (&gapped_line L))" in rule(text, "on_line")
    assert "(RULE &gapped_line" in text
    assert "(ALL " not in rule(text, "on_line")
