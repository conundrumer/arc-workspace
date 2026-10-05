"""The merge lock across processes. Two merges that overlapped would each
pass their checks, and the later one's fast-forward would fail or land a
change checked against a stale `master`, so no run of one merge shows it."""

import os
import subprocess
import sys
import time
from pathlib import Path

from engine import rwlock

SRC = Path(__file__).resolve().parents[2] / "src"

HOLDER = """
import sys, time
from pathlib import Path
from engine import rwlock
directory, log, name, seconds = sys.argv[1:]
with rwlock.merge_lock(Path(directory), f"merging {name}"):
    with open(log, "a") as fh:
        fh.write(f"start {name}\\n")
    time.sleep(float(seconds))
    with open(log, "a") as fh:
        fh.write(f"end {name}\\n")
"""


def start(tmp_path: Path, name: str, seconds: float) -> subprocess.Popen[str]:
    env = {k: v for k, v in os.environ.items() if k != rwlock.HOLD_ENV}
    env["PYTHONPATH"] = str(SRC)
    return subprocess.Popen([sys.executable, "-c", HOLDER, str(tmp_path),
                             str(tmp_path / "log"), name, str(seconds)],
                            env=env, stderr=subprocess.PIPE, text=True)


def until(cond) -> None:
    deadline = time.monotonic() + 20
    while not cond():
        assert time.monotonic() < deadline
        time.sleep(0.02)


def test_a_second_merge_waits_for_the_first_and_says_what_it_merges(tmp_path: Path):
    log = tmp_path / "log"
    log.touch()
    first = start(tmp_path, "a", 1.0)
    until(lambda: "start a" in log.read_text())
    second = start(tmp_path, "b", 0.1)
    _, said = second.communicate(timeout=30)
    assert first.wait(timeout=30) == 0 and second.returncode == 0
    assert log.read_text().split("\n")[:4] == ["start a", "end a", "start b", "end b"]
    wait = rwlock.MERGE_WAIT.format(path=tmp_path / rwlock.MERGE_FILE)
    assert said == f"{wait} {rwlock.MERGE_HOLDER.format(holder='merging a')}\n"

