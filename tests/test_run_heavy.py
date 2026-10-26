"""`scripts/run_heavy.py` starts no command while the shares it needs are
locked or the kernel reports memory pressure, starts calls in the order they
came, frees its shares when its command ends, and starts a nested call at
once.

The machine is a directory of readings that `sysctl` and `vm_stat` stubs on
`PATH` print, so a test sets the budget (2 CPU shares and 4 GiB shares) and
the pressure level it needs."""

import fcntl
import os
import subprocess
from pathlib import Path

import pytest

from engine import checkout

RUN_HEAVY = str(checkout.scripts() / "run_heavy.py")
SYSCTL = '#!/bin/sh\n[ "$1" = -n ] && shift\nfor key in "$@"; do cat "$FAKE_MACHINE/$key" || exit 1; done\n'
VM_STAT = '#!/bin/sh\ncat "$FAKE_MACHINE/vm_stat"\n'
SWAPINS = "Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPageins: 5.\nSwapins: 0.\n"
PRESSURE = "kern.memorystatus_vm_pressure_level"
CPU_SHARES = 2


class Machine:
    """A share directory and the readings of a machine, for one test."""

    def __init__(self, root: Path) -> None:
        self.shares = root / "shares"
        self.shares.mkdir()
        self.readings = root / "readings"
        self.readings.mkdir()
        bin = root / "bin"
        bin.mkdir()
        for name, text in (("sysctl", SYSCTL), ("vm_stat", VM_STAT)):
            (bin / name).write_text(text)
            (bin / name).chmod(0o755)
        self.set("hw.logicalcpu", CPU_SHARES)
        self.set("hw.memsize", 8 << 30)
        self.set(PRESSURE, 1)
        (self.readings / "vm_stat").write_text(SWAPINS)
        self.env = {"PATH": f"{bin}:/usr/bin:/bin:/usr/sbin", "ARC_HEAVY_DIR": str(self.shares),
                    "FAKE_MACHINE": str(self.readings)}

    def set(self, key: str, value: int) -> None:
        (self.readings / key).write_text(f"{value}\n")

    def hold(self, *names: str) -> list:
        """The share files `names`, locked, as running calls hold them; they
        stay locked until the list goes."""
        held = []
        for name in names:
            file = (self.shares / name).open("w")
            fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            held.append(file)
        return held

    def free(self, name: str) -> bool:
        with (self.shares / name).open("w") as file:
            try:
                fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return False
            return True

    def start(self, *args: str, env: dict[str, str] | None = None) -> subprocess.Popen[str]:
        return subprocess.Popen([RUN_HEAVY, *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env={**self.env, **(env or {})})


@pytest.fixture
def machine(tmp_path):
    return Machine(tmp_path)


def first_stderr_line(call: subprocess.Popen[str]) -> str:
    assert call.stderr is not None
    return call.stderr.readline()


def test_a_call_starts_no_command_while_every_cpu_share_is_locked(machine, tmp_path):
    held = machine.hold("cpu-0", "cpu-1")
    marker = tmp_path / "ran"
    call = machine.start("touch", str(marker))
    first_stderr_line(call)  # the call says it waits
    assert not marker.exists()
    held.clear()
    assert call.wait() == 0
    assert marker.exists()


def test_a_request_over_the_budget_waits_for_the_whole_budget(machine, tmp_path):
    held = machine.hold("cpu-0")
    marker = tmp_path / "ran"
    call = machine.start("--cpus", "99", "touch", str(marker))
    first_stderr_line(call)  # it is cut to the budget
    first_stderr_line(call)  # it waits for the share that is locked
    assert not marker.exists()
    held.clear()
    assert call.wait() == 0
    assert marker.exists()


def test_a_call_starts_no_command_under_memory_pressure(machine, tmp_path):
    machine.set(PRESSURE, 2)
    marker = tmp_path / "ran"
    call = machine.start("touch", str(marker))
    first_stderr_line(call)
    assert not marker.exists()
    machine.set(PRESSURE, 1)
    assert call.wait() == 0
    assert marker.exists()


def test_calls_start_in_the_order_they_came(machine, tmp_path):
    held = machine.hold("cpu-0")
    log = tmp_path / "log"
    first = machine.start("--cpus", "2", "sh", "-c", f"echo first >> {log}")
    first_stderr_line(first)  # it holds the free share and waits for the locked one
    second = machine.start("--cpus", "1", "sh", "-c", f"echo second >> {log}")
    first_stderr_line(second)  # it waits for the call before it
    held.clear()
    assert first.wait() == 0 and second.wait() == 0
    assert log.read_text() == "first\nsecond\n"


def test_a_call_killed_while_it_waits_frees_the_turnstile_and_its_shares(machine):
    held = machine.hold("cpu-0")
    call = machine.start("--cpus", "2", "true")
    first_stderr_line(call)
    call.kill()
    call.wait()
    assert machine.free("turnstile") and machine.free("cpu-1")
    del held


def test_the_command_is_the_calls_own_process_and_its_shares_end_with_it(machine):
    call = machine.start("sh", "-c", "echo $$; exec sleep 300")
    assert call.stdout is not None
    assert int(call.stdout.readline()) == call.pid
    assert not machine.free("cpu-0") and not machine.free("gib-0") and machine.free("gib-3")
    call.kill()  # SIGKILL
    call.wait()
    assert machine.free("cpu-0") and machine.free("gib-0")


def test_a_nested_call_starts_at_once_within_its_parents_share(machine):
    held = machine.hold("cpu-0", "cpu-1")
    machine.set(PRESSURE, 4)
    call = machine.start("--cpus", "5", "sh", "-c", "echo $ARC_HEAVY_CPUS $CARGO_BUILD_JOBS $ARCLOG_THREADS",
                         env={"ARC_HEAVY_CPUS": "2", "ARCLOG_THREADS": "1"})
    out, _ = call.communicate()
    assert call.returncode == 0
    assert out == "2 2 1\n"
    del held


def test_a_gated_command_gets_its_share_as_its_pool_sizes(machine):
    call = machine.start("--cpus", "2", "sh", "-c", "echo $ARC_HEAVY_CPUS $RAYON_NUM_THREADS")
    out, _ = call.communicate()
    assert out == "2 2\n"


def test_a_failure_before_the_start_exits_125_126_or_127(machine, tmp_path):
    assert machine.start().wait() == 125
    assert machine.start("--cpus", "none", "true").wait() == 125
    assert machine.start("no-such-command").wait() == 127
    plain = tmp_path / "plain"
    plain.write_text("")
    assert machine.start(str(plain)).wait() == 126


@pytest.mark.parametrize("reading", ["hw.logicalcpu", PRESSURE, "vm_stat"])
def test_a_reading_that_cannot_be_read_exits_125(machine, reading):
    (machine.readings / reading).write_text("garbage\n")
    assert machine.start("true").wait() == 125
