"""The conversion joins a variable that a record pattern binds to a record-valued field with each other read of that variable, on each of its fields."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEM = "7b3084d4"
WHOLE = "covers([K, B], P, Col) :- occ.occurrence(K, B), image(K, P_inner, Col), compose(B, P_inner, P)."
PATTERN = "covers([K, B], P, Col) :- placement(_, _, [K, B]), image(K, P_inner, Col), compose(B, P_inner, P)."


def covers_rule(tmp_path: Path, clause: str) -> str:
    """The `&covers` rule of the converted solver `STEM` whose `covers` clause is `clause`."""
    source = (ROOT / "programs" / "solvers" / f"{STEM}.dl").read_text()
    assert WHOLE in source
    programs = tmp_path / "programs"
    (programs / "solvers").mkdir(parents=True)
    for entry in (ROOT / "programs").iterdir():
        if entry.name != "solvers":
            (programs / entry.name).symlink_to(entry)
    (programs / "solvers" / f"{STEM}.dl").write_text(source.replace(WHOLE, clause))
    subprocess.run([sys.executable, "-m", "arclog_convert.convert", "--no-train-replay", "--out", str(tmp_path / "out"), STEM],
                   cwd=ROOT, check=True, capture_output=True, env={**os.environ, "ARCLOG_SOLVERS": str(programs / "solvers")})
    text = (tmp_path / "out" / "gen" / f"{STEM}.arclog").read_text()
    return text[text.index("(RULE &covers"):].split("\n\n")[0]


def test_a_record_pattern_variable_is_joined_on_each_field_at_a_whole_read(tmp_path: Path):
    rule = covers_rule(tmp_path, PATTERN)
    assert "(&placement *O *D *B)" in rule
    assert "(&image O D *P_inner *Col)" in rule
