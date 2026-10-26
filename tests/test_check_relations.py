"""A Souffle relation that the converter folds into other arclog relations gets a check relation in the program the row-parity check reads, and an entry in the name map and the column map; the converted program has none."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEM = "642d658d"
OPEN_STEM = "a2d730bd"


def convert(tmp_path: Path, stem: str = STEM) -> Path:
    """The `--out` directory of the conversion of the solver `stem` from a copy of its file."""
    programs = tmp_path / "programs"
    (programs / "solvers").mkdir(parents=True)
    for entry in (ROOT / "programs").iterdir():
        if entry.name != "solvers":
            (programs / entry.name).symlink_to(entry)
    (programs / "solvers" / f"{stem}.dl").write_text((ROOT / "programs" / "solvers" / f"{stem}.dl").read_text())
    subprocess.run([sys.executable, "-m", "arclog_convert.convert", "--no-train-replay", "--no-row-parity", "--out", str(tmp_path / "out"), stem],
                   cwd=ROOT, check=True, capture_output=True, env={**os.environ, "ARCLOG_SOLVERS": str(programs / "solvers")})
    return tmp_path / "out"


def test_a_relation_written_as_a_quantifier_gets_its_clauses_in_the_check_copy_only(tmp_path: Path):
    out = convert(tmp_path)
    converted = (out / "gen" / f"{STEM}.arclog").read_text()
    copy = (out / "gen_check" / f"{STEM}.arclog").read_text()
    assert "check_mismatch" not in converted
    assert "(RULE &check_mismatch\n  (&arm *P *Col)\n  (dir_elem *D)\n  (NOT (&arm P D Col)))" in copy
    names = json.loads((out / "names" / f"{STEM}.json").read_text())
    assert names["relations"]["&check_mismatch"] == [{"component": [], "path": "mismatch", "relation": "mismatch"}]
    columns = json.loads((out / "columns" / f"{STEM}.json").read_text())
    assert [[(e["label"], e["field"]) for e in column] for column in columns["&check_mismatch"]["mismatch"]] == [[("P", None)], [("Col", None)]]


def test_a_relation_of_a_case_and_an_open_value_gets_its_clauses_under_the_alts_that_write_them(tmp_path: Path):
    out = convert(tmp_path, OPEN_STEM)
    converted = (out / "gen" / f"{OPEN_STEM}.arclog").read_text()
    copy = (out / "gen_check" / f"{OPEN_STEM}.arclog").read_text()
    assert "check_run" not in converted
    assert "    (RULE &check_run\n      (&block_order (:D *C) *A)))" in copy
    assert "\n(RULE &check_run)\n" in copy
    names = json.loads((out / "names" / f"{OPEN_STEM}.json").read_text())
    assert names["relations"]["&check_run"] == [{"component": [], "path": "run", "relation": "run"}]
    assert "run" not in names["untranslated"]
    columns = json.loads((out / "columns" / f"{OPEN_STEM}.json").read_text())
    assert columns["&check_run"]["run"] == [[], []]
