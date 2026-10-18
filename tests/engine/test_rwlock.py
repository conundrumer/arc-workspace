"""The heavy commands' lock across processes. A shared hold that waited
for another would serialize the commands that hold it, and a run shows
only that they took longer."""

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
started, release = map(Path, sys.argv[1:])
with rwlock.taken(rwlock.Hold.SHARED):
    started.touch()
    while not release.exists():
        time.sleep(0.01)
"""

TAKER = """
from engine import rwlock
with rwlock.taken(rwlock.Hold.SHARED):
    pass
"""


def test_a_shared_hold_is_taken_while_another_process_holds_one(tmp_path: Path):
    env = {k: v for k, v in os.environ.items() if k != rwlock.HOLD_ENV}
    env["PYTHONPATH"] = str(SRC)
    started, release = tmp_path / "started", tmp_path / "release"
    holder = subprocess.Popen([sys.executable, "-c", HOLDER, str(started), str(release)],
                              env=env)
    try:
        while not started.exists():
            assert holder.poll() is None
            time.sleep(0.01)
        taker = subprocess.run([sys.executable, "-c", TAKER], env=env, timeout=60)
        assert taker.returncode == 0
        assert holder.poll() is None
    finally:
        release.touch()
        assert holder.wait(timeout=60) == 0
