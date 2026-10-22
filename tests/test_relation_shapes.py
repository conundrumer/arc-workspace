import json
from pathlib import Path

import pytest

from study.relation_shapes import read_rows_file


def write(path: Path, rows: list, columns: list) -> Path:
    path.write_text(json.dumps({"solver": "s", "input": "train/0", "relation": "&r", "model": 0, "columns": columns, "rows": rows}))
    return path


def test_rows_file_with_a_repeated_row_is_refused(tmp_path: Path) -> None:
    path = write(tmp_path / "r.json", [[1], [1]], [{"name": "c0", "type": "Number"}])
    with pytest.raises(ValueError):
        read_rows_file(path)


def test_rows_file_with_a_short_row_is_refused(tmp_path: Path) -> None:
    path = write(tmp_path / "r.json", [[1]], [{"name": "c0", "type": "Number"}, {"name": "c1", "type": "Number"}])
    with pytest.raises(ValueError):
        read_rows_file(path)
