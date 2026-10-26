"""The size of a process or thread pool: the CPUs the heavy command the
pool runs in was granted (`scripts/run_heavy.py` sets `ARC_HEAVY_CPUS`), and
the machine's CPU count where the command runs outside it. Every package
may import it."""

import os

SHARE_ENV = "ARC_HEAVY_CPUS"
"""The variable in which `scripts/run_heavy.py` gives the CPUs granted."""


def pool_size() -> int:
    """The CPUs the process may use at once."""
    given = os.environ.get(SHARE_ENV)
    if given is not None:
        return int(given)
    count = os.cpu_count()
    if count is None:
        raise NotImplementedError("no CPU count on this platform")
    return count
