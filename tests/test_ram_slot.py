"""`scripts/ram_slot.py` starts no command while every slot is locked, and a
nested call starts its command at once whatever the slots hold."""

import fcntl
import subprocess
from pathlib import Path

from engine import checkout

RAM_SLOT = str(checkout.scripts() / "ram_slot.py")


def lock_all_slots(directory: Path) -> list[int]:
    """Lock every slot file under `directory`, as running calls do."""
    fds = []
    for number in range(3):
        fd = (directory / f"slot-{number}").open("w")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fds.append(fd)
    return fds


def start(directory: Path, env: dict[str, str], marker: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [RAM_SLOT, "touch", str(marker)], text=True, stderr=subprocess.PIPE,
        env={"ARC_RAM_SLOT_DIR": str(directory), "PATH": "/usr/bin:/bin", **env})


def test_a_call_runs_no_command_while_every_slot_is_locked(tmp_path):
    held = lock_all_slots(tmp_path)  # open files keep the locks
    marker = tmp_path / "ran"
    call = start(tmp_path, {}, marker)
    assert call.stderr is not None
    assert "waiting for a slot" in call.stderr.readline()
    call.terminate()
    call.wait()
    assert not marker.exists()


def test_a_nested_call_runs_its_command_while_every_slot_is_locked(tmp_path):
    held = lock_all_slots(tmp_path)  # open files keep the locks
    marker = tmp_path / "ran"
    call = start(tmp_path, {"ARC_RAM_SLOT": str(tmp_path / "slot-0")}, marker)
    assert call.wait() == 0
    assert marker.exists()
