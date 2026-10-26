"""`scripts/ram_slot.py` starts no command while every slot is locked or
while swap, load or memory is out of bounds, and a nested call starts its
command at once whatever the slots and the machine hold."""

import fcntl
import subprocess
from pathlib import Path

import pytest

from engine import checkout
from tests.conftest import script

ram_slot = script("ram_slot")
GIB = 1 << 30

VM_STAT = """Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free:                               100.
Pages active:                             900.
Pages inactive:                           800.
Pages speculative:                         30.
"""

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


def test_available_memory_counts_free_and_inactive_pages_only():
    assert ram_slot.parse_available(VM_STAT) == (100 + 800) * 16384


def test_swap_used_is_read_in_bytes_from_the_sysctl_line():
    line = "total = 2048.00M  used = 1.50G  free = 1721.38M  (encrypted)"
    assert ram_slot.parse_swap_used(line) == int(1.5 * GIB)
    assert ram_slot.parse_swap_used(line.replace("1.50G", "326.50M")) == 326.5 * (1 << 20)


def test_a_sysctl_line_with_no_swap_in_use_is_not_read():
    with pytest.raises(ValueError):
        ram_slot.parse_swap_used("total = 0.00M")


def test_swap_blocks_above_two_gib_only():
    assert ram_slot.swap_blocks(lambda: 2 * GIB) is None
    reason = ram_slot.swap_blocks(lambda: 5 * GIB // 2)
    assert reason is not None and "2.5 GiB in use" in reason


def test_load_blocks_above_twice_the_core_count_only():
    assert ram_slot.load_blocks(lambda: (16.0, 8)) is None
    reason = ram_slot.load_blocks(lambda: (16.5, 8))
    assert reason is not None and "16.5" in reason and "2 x 8 cores" in reason


def test_memory_blocks_below_six_gib_only():
    assert ram_slot.memory_blocks(lambda: 6 * GIB) is None
    reason = ram_slot.memory_blocks(lambda: 5 * GIB)
    assert reason is not None and "5.0 GiB" in reason


def test_a_wait_says_what_it_waits_for_once_and_polls_until_clear(capsys):
    readings = iter([4 * GIB, 3 * GIB, GIB])
    slept: list[float] = []
    ram_slot.wait_while(lambda: ram_slot.swap_blocks(lambda: next(readings)),
                        slept.append)
    assert slept == [ram_slot.POLL_SECONDS] * 2
    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 1 and lines[0].startswith("ram_slot.py: waiting for swap")


def test_a_clear_machine_prints_nothing_and_sleeps_never(capsys):
    ram_slot.wait_while(lambda: None, lambda seconds: pytest.fail("slept"))
    assert capsys.readouterr().err == ""


def test_an_unreadable_core_count_is_a_refusal(monkeypatch):
    monkeypatch.setattr(ram_slot.os, "cpu_count", lambda: None)
    with pytest.raises(ram_slot.Refusal):
        ram_slot.load_and_cores()


def test_an_unreadable_load_average_is_a_refusal(monkeypatch):
    def fail() -> tuple[float, float, float]:
        raise OSError("no load")
    monkeypatch.setattr(ram_slot.os, "getloadavg", fail)
    with pytest.raises(ram_slot.Refusal):
        ram_slot.load_and_cores()


def test_an_unreadable_swap_is_a_refusal(monkeypatch):
    def fail(*args, **kwargs):
        raise FileNotFoundError("sysctl")
    monkeypatch.setattr(ram_slot.subprocess, "run", fail)
    with pytest.raises(ram_slot.Refusal):
        ram_slot.swap_used_bytes()


def test_a_call_waits_for_the_machine_after_its_slot_and_a_nested_call_does_not(monkeypatch):
    events: list[str] = []
    monkeypatch.setattr(ram_slot, "wait_for_slot", lambda directory: events.append("slot") or "slot-0")
    monkeypatch.setattr(ram_slot, "wait_for_machine", lambda: events.append("machine"))
    monkeypatch.setattr(ram_slot.os, "execvp", lambda file, args: events.append("exec"))
    monkeypatch.setattr(ram_slot.signal, "signal", lambda number, handler: None)
    monkeypatch.setenv(ram_slot.SLOT_ENV, "")  # restores the variable at the end
    monkeypatch.delenv(ram_slot.SLOT_ENV)
    ram_slot.run(["true"])
    assert events == ["slot", "machine", "exec"]
    events.clear()
    ram_slot.run(["true"])  # SLOT_ENV is now set, as in a nested call
    assert events == ["exec"]
