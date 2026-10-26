"""Each case reads the rows of a relation over the columns of the writing it takes."""

from pathlib import Path

from tests.conftest import PAINT_STEM
from parity import rerun


def test_each_case_reads_its_own_columns(paint: Path) -> None:
    got = rerun.case_rows(PAINT_STEM, paint)
    assert isinstance(got, dict)
    by_case = {}
    for case in got["cases"]:
        [first, *_] = case["pairs"]
        by_case[case["case"]] = {r["name"]: r for r in first["relations"]}["&paint_of"]
    concept, stored = by_case["concept"], by_case["$StoredPaint"]
    assert concept["columns"] == [["F", None], ["F", None]]
    assert all(a == b for [a], [b] in concept["rows"])
    assert stored["columns"] == [["F", None], ["Col", None]]
    assert any(a != b for [a], [b] in stored["rows"])
