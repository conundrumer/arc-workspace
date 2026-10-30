"""The size of a process or thread pool: the CPUs the heavy command the
pool runs in declares (`scripts/run_heavy.py` sets `ARC_HEAVY_CPUS` to its `--cpus`), and
the machine's CPU count where the command runs outside it, and the
environment of a worker of a pool. Every package may import it."""

import os

SHARE_ENV = "ARC_HEAVY_CPUS"
"""The variable in which `scripts/run_heavy.py` gives the CPUs the command declares."""

POOL_ENVS = ("ARCLOG_THREADS", "CARGO_BUILD_JOBS", "RAYON_NUM_THREADS",
             "RUST_TEST_THREADS", "OMP_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")
"""The variables in which `scripts/run_heavy.py` bounds the threads of the
tools it runs; `scripts/run_heavy.py` and `engine/arclog-py/export_checks.py`,
which run under other interpreters, hold the same names."""


def pool_size() -> int:
    """The CPUs the process may use at once."""
    given = os.environ.get(SHARE_ENV)
    if given is not None:
        return int(given)
    count = os.cpu_count()
    if count is None:
        raise NotImplementedError("no CPU count on this platform")
    return count


def share_env(cpus: int) -> dict[str, str]:
    """The environment of a process that may use `cpus` CPUs at once: that
    of this process, with `SHARE_ENV` and each of `POOL_ENVS` set to
    `cpus`. A worker of a pool of `pool_size()` workers runs in
    `share_env(1)`, so the processes and threads of the pool together stay
    within the CPUs the command declares (`--cpus`, `ARC_HEAVY_CPUS`)."""
    return {**os.environ, SHARE_ENV: str(cpus), **{name: str(cpus) for name in POOL_ENVS}}
