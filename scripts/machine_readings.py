"""The readings of the machine that `scripts/load_monitor.py` alerts on and
`scripts/resource_daemon.py` holds requests on: the kernel's memory pressure
level (`kern.memorystatus_vm_pressure_level`: 1 normal, 2 warn, 4 critical),
the counters of `vm_stat`, and the machine's budget of CPUs and GiB. A read
that fails raises `subprocess.CalledProcessError`, `OSError` or `ValueError`.

Standard library only, Python 3.9, since `run_heavy.py` runs under the
system Python."""

from __future__ import annotations

import re
import subprocess

SWAP_IN_RATE = 1000
"""Swap-ins a second above which the machine is under load."""

CRITICAL_PRESSURE = 4
"""The kernel's critical pressure level."""

PRESSURE_LEVELS = frozenset({2, CRITICAL_PRESSURE})
"""The pressure levels, warn and critical, at which the machine is under
load."""

KIB = 1 << 10
GIB = 1 << 30
SYSTEM_GIB = 4
"""The memory in GiB that the budget leaves for the system and the terminal."""

VM_COUNTER = re.compile(r"^(Pageins|Swapins):\s+(\d+)\.$", re.MULTILINE)


def output(*args: str) -> str:
    """The standard output of the command `args`."""
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def counters() -> tuple[int, int]:
    """The swap-in and page-in counts since boot, as `vm_stat` gives them."""
    found = {name: int(count) for name, count in VM_COUNTER.findall(output("vm_stat"))}
    return found["Swapins"], found["Pageins"]


def pressure_level() -> int:
    """The kernel's memory pressure level."""
    return int(output("sysctl", "-n", "kern.memorystatus_vm_pressure_level"))


def budget() -> tuple[int, int]:
    """The CPUs (`hw.logicalcpu`) and the GiB of memory (`hw.memsize`, less `SYSTEM_GIB`) of the
    machine. The daemon takes the footprint of the processes outside its jobs off the GiB
    (`heavy_core.Core.available`)."""
    cpus, memory = output("sysctl", "-n", "hw.logicalcpu", "hw.memsize").split()
    return int(cpus), int(memory) // GIB - SYSTEM_GIB
