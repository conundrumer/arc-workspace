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
    for f in os.listdir(tmp_path / "second" / "values" / TASKS[0]):
        assert not os.path.samefile(tmp_path / "second" / "values" / TASKS[0] / f, tmp_path / "first" / "values" / TASKS[0] / f)


def linked(second, first):
    """Whether every values file of `second` is a link to the file of `first`."""
    return all(os.path.samefile(second / "values" / t / f, first / "values" / t / f) for t in TASKS for f in os.listdir(second / "values" / t))


def setup(tmp_path, monkeypatch):
    corpus = tmp_path / "gen"
    corpus.mkdir()
    for t in TASKS:
        for ext in ("arclog", "arcdata"):
            shutil.copy(GEN / f"{t}.{ext}", corpus / f"{t}.{ext}")
    monkeypatch.setattr(export, "CORPUS", str(corpus))
    monkeypatch.setenv("ARCLOG_THREADS", "2")
    return dict(projection_cap=10000, step_cap=10000)


@pytest.mark.skipif(not all((GEN / f"{t}.arclog").exists() for t in TASKS), reason="no generated corpus")
def test_changed_checker_checks_again_with_no_replay(tmp_path, monkeypatch):
    options = setup(tmp_path, monkeypatch)
    export.main(str(tmp_path / "first"), TASKS, **options)
    for part in (tmp_path / "first" / "parts").glob("*.checks.txt"):
        part.write_text(part.read_text() + f"{TASKS[0]} 0: stale: a check line of the old checker\n")
    checker = tmp_path / "export_checks.py"
    checker.write_bytes(Path(export.CHECKER).read_bytes() + b"\n")
    monkeypatch.setattr(export, "CHECKER", str(checker))
    export.main(str(tmp_path / "second"), TASKS, previous=str(tmp_path / "first"), **options)
    export.main(str(tmp_path / "full"), TASKS, **options)
    assert linked(tmp_path / "second", tmp_path / "first")
    assert (tmp_path / "second" / "checks.txt").read_text() == (tmp_path / "full" / "checks.txt").read_text()
    assert "stale" not in (tmp_path / "second" / "checks.txt").read_text()


@pytest.mark.skipif(not all((GEN / f"{t}.arclog").exists() for t in TASKS), reason="no generated corpus")
def test_changed_rows_code_replays_every_task(tmp_path, monkeypatch):
    options = setup(tmp_path, monkeypatch)
    export.main(str(tmp_path / "first"), TASKS, **options)
    rows = tmp_path / "export_rows.py"
    rows.write_bytes(Path(export.ROWS).read_bytes() + b"\n")
    monkeypatch.setattr(export, "ROWS", str(rows))
    export.main(str(tmp_path / "second"), TASKS, previous=str(tmp_path / "first"), **options)
    for t in TASKS:
        for f in os.listdir(tmp_path / "second" / "values" / t):
            assert not os.path.samefile(tmp_path / "second" / "values" / t / f, tmp_path / "first" / "values" / t / f)


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
