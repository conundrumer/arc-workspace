"""A relation written with other columns under one ALT than at the top level has an entry in the column map for each writing."""

import json
from pathlib import Path

from tests.conftest import PAINT_STEM


def labels(entry: list[list[dict]]) -> list[list[str]]:
    return [[site["label"] for site in column] for column in entry]


def test_a_relation_written_with_two_columns_in_one_alt_and_one_in_the_other_has_two_entries(paint: Path) -> None:
    columns = json.loads((paint.parents[2] / "out" / "columns" / f"{PAINT_STEM}.json").read_text())
    [entry] = columns["&paint_of"].values()
    assert {tuple(w["constructors"]): labels(w["columns"]) for w in entry["writings"]} == {
        (): [[], ["F"], ["F"]], ("StoredPaint",): [[], ["F"], ["Col"]]}
    [other] = columns["&field"].values()
    assert labels(other) == [["F"]]
