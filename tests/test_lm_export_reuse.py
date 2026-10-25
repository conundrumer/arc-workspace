"""`lm/export.py --previous` streams the tasks whose key differs, reuses the others, and writes the files of a run with no `--previous`."""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("arclog")
ROOT = Path(__file__).parent.parent
TASKS = ["00576224", "007bbfb7"]


def run(out, *args):
    r = subprocess.run([sys.executable, str(ROOT / "lm/export.py"), "--out", str(out), "--heldout", TASKS[0], *args, *TASKS],
                       cwd=ROOT, capture_output=True, text=True, timeout=240)
    assert r.returncode == 0, r.stderr
    return r.stdout


needs_corpus = pytest.mark.skipif(not all((ROOT / f"work/arclog/gen/{t}.arclog").exists() for t in TASKS), reason="no generated corpus")


def same(a, b):
    x, y = np.load(a / "cases.npz"), np.load(b / "cases.npz")
    assert sorted(x.files) == sorted(y.files)
    for k in x.files:
        assert x[k].dtype == y[k].dtype and np.array_equal(x[k], y[k]), k
    assert (a / "stream-report-all.txt").read_text() == (b / "stream-report-all.txt").read_text()
    assert (a / "keys.json").read_text() == (b / "keys.json").read_text()


@needs_corpus
def test_a_task_with_another_key_is_streamed_and_the_rest_is_reused(tmp_path):
    run(tmp_path / "first")
    keys = json.loads((tmp_path / "first/keys.json").read_text())
    stale = {t: {**v, "key": "stale"} if t == TASKS[0] else v for t, v in keys.items()}
    (tmp_path / "old").mkdir()
    for f in ("cases.npz", "stream-report-all.txt"):
        (tmp_path / "old" / f).write_bytes((tmp_path / "first" / f).read_bytes())
    (tmp_path / "old/keys.json").write_text(json.dumps(stale))
    assert run(tmp_path / "second", "--previous", str(tmp_path / "old")).startswith("1 tasks reused, 1 to stream")
    same(tmp_path / "first", tmp_path / "second")


@needs_corpus
def test_all_tasks_reused_and_a_fault_line_with_a_colon_after_the_task(tmp_path):
    run(tmp_path / "first")
    line = f"{TASKS[1]}: the checker refuses the case"
    report = tmp_path / "first/stream-report-all.txt"
    head, last = report.read_text().rstrip("\n").rsplit("\n", 1)
    report.write_text(head + "\n" + line + "\n" + last + "\n")
    assert run(tmp_path / "second", "--previous", str(tmp_path / "first")).startswith("2 tasks reused, 0 to stream")
    assert line in (tmp_path / "second/stream-report-all.txt").read_text().splitlines()
    assert len(np.load(tmp_path / "second/cases.npz")["task"]) == len(np.load(tmp_path / "first/cases.npz")["task"])


@needs_corpus
def test_previous_without_keys_gives_no_reuse_and_streams_pkl_is_refused(tmp_path):
    (tmp_path / "bare").mkdir()
    assert run(tmp_path / "out", "--previous", str(tmp_path / "bare")).startswith("0 tasks reused, 2 to stream")
    (tmp_path / "out/streams.pkl").write_bytes(b"")
    r = subprocess.run([sys.executable, str(ROOT / "lm/export.py"), "--out", str(tmp_path / "out"), "--previous", str(tmp_path / "bare")],
                       cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and "streams.pkl" in r.stderr
