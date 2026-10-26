"""The readings of the machine's memory load that `scripts/load_monitor.py`
alerts on and `scripts/run_heavy.py` waits on: the kernel's memory pressure
level (`kern.memorystatus_vm_pressure_level`: 1 normal, 2 warn, 4 critical)
and the counters of `vm_stat`. A read that fails raises
`subprocess.CalledProcessError`, `OSError` or `ValueError`.

Standard library only, Python 3.9, since `run_heavy.py` runs under the
system Python."""

from __future__ import annotations

import re
import subprocess

SWAP_IN_RATE = 1000
"""Swap-ins a second above which the machine is under load."""

PRESSURE_LEVELS = frozenset({2, 4})
"""The pressure levels, warn and critical, at which the machine is under
load."""

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
