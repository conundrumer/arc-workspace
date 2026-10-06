"""The CPU that processes outside the gate's process tree use over an
interval, from two samples of the machine's and the tree's CPU."""

import ctypes
import os
import resource
import sys
import time
from dataclasses import dataclass
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


def _busy_ticks() -> tuple[int, ...]:
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


def _tree_cpu() -> float:
    """The CPU seconds of the gate's process and of its children it has
    waited for, with theirs."""
    return sum(r.ru_utime + r.ru_stime for r in (resource.getrusage(resource.RUSAGE_SELF),
                                                 resource.getrusage(resource.RUSAGE_CHILDREN)))


@dataclass(frozen=True)
class CpuSample:
    """The machine's busy CPU ticks, the gate tree's CPU seconds, and the
    monotonic clock, at one moment."""
    busy: tuple[int, ...]
    tree: float
    at: float

    @classmethod
    def now(cls) -> "CpuSample":
        return cls(_busy_ticks(), _tree_cpu(), time.monotonic())

    def outside(self, end: "CpuSample") -> "OutsideCpu":
        """The CPU that processes outside the gate's process tree used from
        this sample to `end`, where the gate has waited for each child it
        started since this sample."""
        ticks = sum((b - a) % _TICKS for a, b in zip(self.busy, end.busy, strict=True))
        busy = ticks / os.sysconf("SC_CLK_TCK")
        return OutsideCpu(busy - (end.tree - self.tree), end.at - self.at)


@dataclass(frozen=True)
class OutsideCpu:
    """The CPU seconds processes outside the gate's process tree used over
    an interval, and the interval's seconds."""
    cpu: float
    interval: float

    @property
    def cores(self) -> float:
        return self.cpu / self.interval

    def __str__(self) -> str:
        return f"outside-cpu={self.cpu:.1f}s ({self.cores:.1f} cores on average)"
