"""The machine's busy CPU time, from samples of its CPU tick
counters."""

import ctypes
import os
import sys
from pathlib import Path

_TICKS = 2 ** 32
"""The modulus of the CPU tick counters, which on darwin are 32-bit and
wrap."""
_HOST_CPU_LOAD_INFO = 3
_CPU_STATE_MAX = 4
_CPU_STATE_IDLE = 2
_PROC_STAT_BUSY = (0, 1, 2, 5, 6)
"""The user, nice, system, irq and softirq fields of the `cpu` line of
`/proc/stat`; its user and nice fields include its guest fields."""


def busy_ticks() -> tuple[int, ...]:
    """The machine's CPU ticks spent not idle, summed over its CPUs, one
    counter per CPU state."""
    if sys.platform == "darwin":
        libc = ctypes.CDLL("/usr/lib/libSystem.dylib")
        libc.mach_host_self.restype = ctypes.c_uint
        info = (ctypes.c_uint * _CPU_STATE_MAX)()
        count = ctypes.c_uint(_CPU_STATE_MAX)
        kr = libc.host_statistics(libc.mach_host_self(), _HOST_CPU_LOAD_INFO,
                                  info, ctypes.byref(count))
        if kr != 0:
            raise OSError(f"host_statistics returned {kr}")
        return tuple(t for i, t in enumerate(info) if i != _CPU_STATE_IDLE)
    if sys.platform == "linux":
        fields = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
        return tuple(int(fields[i]) for i in _PROC_STAT_BUSY)
    raise NotImplementedError(f"no system-wide CPU total on {sys.platform}")


def busy_seconds(start: tuple[int, ...], end: tuple[int, ...]) -> float:
    """The machine's CPU seconds spent not idle, summed over its CPUs,
    from the `busy_ticks` sample `start` to the later one `end`."""
    ticks = sum((b - a) % _TICKS for a, b in zip(start, end, strict=True))
    return ticks / os.sysconf("SC_CLK_TCK")
