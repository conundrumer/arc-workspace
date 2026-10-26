"""A relation of `Determine` has an entry in the column map and an entry in the `determination` of the rows file."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from arclog_convert import OUT_ENV
from parity import rerun

ROOT = Path(__file__).resolve().parents[2]
STEM = "009d5c81"
"""A solver whose `Determine` is added by a run, and whose relation `entry.id` is `&entry.class`."""


@pytest.fixture
def converted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The solver file of `STEM` under `tmp_path`, converted there."""
    programs = tmp_path / "programs"
    (programs / "solvers").mkdir(parents=True)
    for entry in (ROOT / "programs").iterdir():
        if entry.name != "solvers":
            (programs / entry.name).symlink_to(entry)
    file = programs / "solvers" / f"{STEM}.dl"
    file.write_text((ROOT / "programs" / "solvers" / f"{STEM}.dl").read_text())
    subprocess.run([sys.executable, "-m", "arclog_convert.convert", "--no-train-replay", "--no-row-parity",
                    "--out", str(tmp_path / "out"), STEM],
                   cwd=ROOT, check=True, capture_output=True, env={**os.environ, "ARCLOG_SOLVERS": str(programs / "solvers")})
    monkeypatch.setenv(OUT_ENV, str(tmp_path / "out"))
    return file


def test_a_relation_of_determine_is_in_the_column_map_and_the_determination(converted: Path) -> None:
    columns = json.loads((converted.parents[2] / "out" / "columns" / f"{STEM}.json").read_text())
    assert [[(e["label"], e["field"]) for e in column] for column in columns["&entry.class"]] == [[("a", None)], [("Id", None)]]
    got = rerun.case_rows(STEM, converted)
    assert isinstance(got, dict)
    [pair] = got["determination"]["pairs"]
    assert pair["pair"] == "task"
    entry = {r["name"]: r for r in pair["relations"]}["&entry.class"]
    assert entry["columns"] == [["a", None], ["Id", None]] and entry["rows"]
    assert "&entry.class" not in {line["name"] for line in got["not_compared"]}
