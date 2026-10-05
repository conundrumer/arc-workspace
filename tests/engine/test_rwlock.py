"""The heavy commands' lock across processes. A reader that overtook a
waiting writer, or a writer that ran beside a reader, would skew the timed
run's wall times and no more, so no run shows it."""

import fcntl
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
hold, directory, log, name, seconds = sys.argv[1:]
with rwlock.lock_files(rwlock.Hold(hold), Path(directory), rwlock.Notice()):
    with open(log, "a") as fh:
        fh.write(f"start {name}\\n")
    time.sleep(float(seconds))
    with open(log, "a") as fh:
        fh.write(f"end {name}\\n")
"""


def test_a_waiting_writer_waits_for_the_readers_and_goes_before_later_ones(tmp_path: Path):
    log = tmp_path / "log"
    log.touch()
    env = {k: v for k, v in os.environ.items() if k != rwlock.HOLD_ENV}
    env["PYTHONPATH"] = str(SRC)

    def start(hold: rwlock.Hold, name: str, seconds: float) -> subprocess.Popen[bytes]:
        return subprocess.Popen([sys.executable, "-c", HOLDER, hold, str(tmp_path), str(log),
                                 name, str(seconds)], env=env, stderr=subprocess.DEVNULL)

    def until(cond) -> None:
        deadline = time.monotonic() + 20
        while not cond():
            assert time.monotonic() < deadline
            time.sleep(0.02)

    def pending_held() -> bool:
        with open(tmp_path / rwlock.PENDING_FILE, "a") as fh:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            return False

    procs = [start(rwlock.Hold.SHARED, "r1", 1.5), start(rwlock.Hold.SHARED, "r2", 1.5)]
    until(lambda: log.read_text().count("start") == 2)
    procs.append(start(rwlock.Hold.EXCLUSIVE, "w", 0.5))
    until(pending_held)
    procs.append(start(rwlock.Hold.SHARED, "r3", 0.1))
    for p in procs:
        assert p.wait(timeout=30) == 0
    events = log.read_text().split()
    order = [f"{a} {b}" for a, b in zip(events[::2], events[1::2])]
    assert set(order[:2]) == {"start r1", "start r2"}
    assert set(order[2:4]) == {"end r1", "end r2"}
    assert order[4:] == ["start w", "end w", "start r3", "end r3"]
