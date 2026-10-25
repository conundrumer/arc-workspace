"""`tables_export.main` with `--previous` replays a task whose generated program changed, reuses the others, and writes the files of a run with no `--previous`."""
import importlib.util
import filecmp
import os
import shutil
import sys
from pathlib import Path

import pytest

pytest.importorskip("arclog")
pytest.importorskip("pyarrow")
import pandas as pd

ROOT = Path(__file__).parent.parent
GEN = Path(os.environ.get("ARCLOG_GEN", ROOT / "work/arclog/gen"))
sys.path.insert(0, str(ROOT / "engine/arclog-py"))
spec = importlib.util.spec_from_file_location("tables_export", ROOT / "engine/arclog-py/tables_export.py")
assert spec and spec.loader
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)

TASKS = ["00576224", "007bbfb7"]
WHOLE = ["index", "tables", "flows", "assigned", "projections", "projection_rows"]


def rows(path):
    frame = pd.read_parquet(path)
    return frame.reset_index(drop=True).sort_values(list(frame.columns), kind="stable", key=lambda c: c.astype(str)).reset_index(drop=True)


@pytest.mark.skipif(not all((GEN / f"{t}.arclog").exists() for t in TASKS), reason="no generated corpus")
def test_changed_task_replays_and_the_rest_is_reused(tmp_path, capsys, monkeypatch):
    corpus = tmp_path / "gen"
    corpus.mkdir()
    for t in TASKS:
        for ext in ("arclog", "arcdata"):
            shutil.copy(GEN / f"{t}.{ext}", corpus / f"{t}.{ext}")
    monkeypatch.setattr(export, "CORPUS", str(corpus))
    monkeypatch.setenv("ARCLOG_THREADS", "2")
    options = dict(projection_cap=10000, step_cap=10000)
    export.main(str(tmp_path / "first"), TASKS, **options)
    with open(corpus / f"{TASKS[0]}.arclog", "a") as sink:
        sink.write("\n")
    capsys.readouterr()
    export.main(str(tmp_path / "second"), TASKS, previous=str(tmp_path / "first"), **options)
    printed = capsys.readouterr().out.splitlines()
    assert printed[0] == "1 tasks reused, 1 to replay"
    export.main(str(tmp_path / "full"), TASKS, **options)
    assert printed[-1] == capsys.readouterr().out.splitlines()[-1]
    for name in WHOLE:
        pd.testing.assert_frame_equal(rows(tmp_path / "second" / f"{name}.parquet"), rows(tmp_path / "full" / f"{name}.parquet"))
    for name in ("report.txt", "checks.txt"):
        assert (tmp_path / "second" / name).read_text() == (tmp_path / "full" / name).read_text()
    for t in TASKS:
        for f in os.listdir(tmp_path / "full" / "values" / t):
            assert filecmp.cmp(tmp_path / "second" / "values" / t / f, tmp_path / "full" / "values" / t / f, shallow=False)
    reused = TASKS[1]
    for f in os.listdir(tmp_path / "second" / "values" / reused):
        assert os.path.samefile(tmp_path / "second" / "values" / reused / f, tmp_path / "first" / "values" / reused / f)


@pytest.mark.skipif(not all((GEN / f"{t}.arclog").exists() for t in TASKS), reason="no generated corpus")
def test_reuse_keeps_fault_lines_that_have_a_colon_after_the_task(tmp_path, monkeypatch):
    corpus = tmp_path / "gen"
    corpus.mkdir()
    for t in TASKS:
        for ext in ("arclog", "arcdata"):
            shutil.copy(GEN / f"{t}.{ext}", corpus / f"{t}.{ext}")
    monkeypatch.setattr(export, "CORPUS", str(corpus))
    monkeypatch.setenv("ARCLOG_THREADS", "2")
    options = dict(projection_cap=10000, step_cap=10000)
    export.main(str(tmp_path / "first"), TASKS, **options)
    line = f"{TASKS[1]}: the checker refuses the case"
    for tasks in (tmp_path / "first" / "parts").glob("*.tasks.txt"):
        if TASKS[1] in tasks.read_text():
            report = tasks.with_name(tasks.name.replace(".tasks.txt", ".report.txt"))
            report.write_text(report.read_text() + line + "\n")
    export.main(str(tmp_path / "second"), TASKS, previous=str(tmp_path / "first"), **options)
    assert line in (tmp_path / "second" / "report.txt").read_text().splitlines()
