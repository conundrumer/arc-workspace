"""A variable that the atoms of two inputs of a hoisted site share is a key column, so a `Tiling` grounded per example pairs one example's positions."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_a_tiling_over_two_per_example_inputs_is_keyed_by_the_example(tmp_path):
    subprocess.run([sys.executable, "-m", "arclog_convert.convert", "--out", str(tmp_path),
                    "c3e719e8"], cwd=ROOT, check=True, capture_output=True)
    text = (tmp_path / "gen" / "c3e719e8.arclog").read_text()
    found = re.search(r"\(INIT &background_tiling Tiling.*?\n\n", text, re.S)
    assert found
    form = found.group(0)
    assert "(key (" in form and "^E" in form
