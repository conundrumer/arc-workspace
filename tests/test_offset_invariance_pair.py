"""The conversion reads a `cand` and a negated `mismatch` of one `OffsetInvariance` conjunction as the `period` with its offset."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def convert(out: Path, stem: str) -> str:
    subprocess.run([sys.executable, "-m", "arclog_convert.convert", "--out", str(out), stem],
                   cwd=ROOT, check=True, capture_output=True)
    return (out / "gen" / f"{stem}.arclog").read_text()


def test_the_pair_in_one_clause_derives_no_relation_over_the_cells(tmp_path):
    text = convert(tmp_path, "c3f564a4")
    assert "_cand" not in text and "_mismatch" not in text
    assert "jump_offset D K (:V *Delta)" in text


def test_a_pair_over_an_example_key_keeps_its_derived_relations(tmp_path):
    text = convert(tmp_path, "332efdb3")
    assert "_cand" in text or "_mismatch" in text
