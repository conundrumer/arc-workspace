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
directory, log, name, release = sys.argv[1:]
with rwlock.merge_lock(Path(directory), f"merging {name}"):
    with open(log, "a") as fh:
        fh.write(f"start {name}\\n")
    deadline = time.monotonic() + 30
    while not Path(release).exists():
        if time.monotonic() > deadline:
            sys.exit(1)
        time.sleep(0.02)
    with open(log, "a") as fh:
        fh.write(f"end {name}\\n")
"""


def start(tmp_path: Path, name: str) -> tuple[subprocess.Popen[str], Path, Path]:
    """A holder of the merge lock named `name`, the file whose creation makes it
    release the lock, and the file its stderr goes to."""
    env = {k: v for k, v in os.environ.items() if k != rwlock.HOLD_ENV}
    env["PYTHONPATH"] = str(SRC)
    release, err = tmp_path / f"release {name}", tmp_path / f"stderr {name}"
    with open(err, "w") as fh:
        proc = subprocess.Popen([sys.executable, "-c", HOLDER, str(tmp_path),
                                 str(tmp_path / "log"), name, str(release)],
                                env=env, stderr=fh, text=True)
    return proc, release, err


def until(cond) -> None:
    deadline = time.monotonic() + 20
    while not cond():
        assert time.monotonic() < deadline
        time.sleep(0.02)


def test_a_second_merge_waits_for_the_first_and_says_what_it_merges(tmp_path: Path):
    log = tmp_path / "log"
    log.touch()
    first, release_a, _ = start(tmp_path, "a")
    second = None
    try:
        until(lambda: "start a" in log.read_text())
        (tmp_path / "release b").touch()
        second, _, err_b = start(tmp_path, "b")
        until(lambda: "\n" in err_b.read_text() or second.poll() is not None)
        wait = rwlock.WAIT.format(noun=rwlock.MERGE.noun, path=tmp_path / rwlock.MERGE_FILE)
        assert err_b.read_text() == f"{wait} {rwlock.HOLDER.format(holder='merging a')}\n"
        assert "start b" not in log.read_text()
        release_a.touch()
        assert first.wait(timeout=30) == 0 and second.wait(timeout=30) == 0
        assert log.read_text().split("\n")[:4] == ["start a", "end a", "start b", "end b"]
    finally:
        for proc in (first, second):
            if proc is not None and proc.poll() is None:
                proc.kill()
                proc.wait()
