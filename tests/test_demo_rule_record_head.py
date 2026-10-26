"""The conversion writes the `&prediction` clause of a `DemonstrationConsistency` whose head site is a record of variables under the labels of the record's fields."""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEM = "20a9e565"
HEAD = "catalog.prediction(D, $Stretch(E), [I0, I], P_h, Col) :-"


def stretch_rule(tmp_path: Path, renamed: bool) -> str:
    """The `DEMO_RULE $Stretch` of the converted solver `STEM`, with the variables `I0` and `I` of its `Stretch` prediction clause renamed `Lo` and `Hi` where `renamed`."""
    source = (ROOT / "programs" / "solvers" / f"{STEM}.dl").read_text()
    head, found, rest = source.partition(HEAD)
    assert found
    clause, blank, tail = rest.partition("\n\n")
    if renamed:
        head_names = re.sub(r"\bI0\b", "Lo", re.sub(r"\bI\b", "Hi", HEAD))
        clause = re.sub(r"\bI0\b", "Lo", re.sub(r"\bI\b", "Hi", clause))
    else:
        head_names = HEAD
    programs = tmp_path / "programs"
    (programs / "solvers").mkdir(parents=True)
    for entry in (ROOT / "programs").iterdir():
        if entry.name != "solvers":
            (programs / entry.name).symlink_to(entry)
    (programs / "solvers" / f"{STEM}.dl").write_text(head + head_names + clause + blank + tail)
    subprocess.run([sys.executable, "-m", "arclog_convert.convert", "--out", str(tmp_path / "out"), STEM],
                   cwd=ROOT, check=True, capture_output=True, env={**os.environ, "ARCLOG_SOLVERS": str(programs / "solvers")})
    text = (tmp_path / "out" / "gen" / f"{STEM}.arclog").read_text()
    return text[text.index("(DEMO_RULE ($Stretch"):].split("\n    (DEMO_RULE")[0]


def test_a_record_of_variables_at_a_head_site_is_written_under_the_labels_of_its_fields(tmp_path: Path):
    rule = stretch_rule(tmp_path / "named", renamed=False)
    assert "TODO" not in rule
    assert "(&stretch *D (:E1 D) *I0 *I *P *K)" in rule
    assert stretch_rule(tmp_path / "renamed", renamed=True) == rule
