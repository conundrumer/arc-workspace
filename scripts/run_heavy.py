#!/usr/bin/python3
"""Run a command that uses much CPU or memory, within the machine's budget.

Usage: <checkout>/scripts/run_heavy.py [--cpus <n>] [--gib <g>] <command> [<arg> ...]
       <checkout>/scripts/run_heavy.py --cpus <n> bash -c '<simple command>; ...'

`--cpus` is the processes or threads the command runs at once (default 1),
and `--gib` the memory in GiB it may reach (default `1 + <n>`). The heavy
commands that run through this script at one time, in every session and
checkout of the machine, together hold at most the machine's CPU budget, the
logical CPUs (`hw.logicalcpu`), and its memory budget, the physical memory
(`hw.memsize`) less 4 GiB for the system and the terminal. A request over a
budget is cut to it, with one line on stderr.

A call takes the turnstile, then one share of the CPU budget for each CPU it
asks for and one of the memory budget for each GiB, then waits while the
kernel's memory pressure level is warn or critical or the swap-ins a second
are over the load monitor's alert rate (`scripts/machine_readings.py`, read
as `scripts/load_monitor.py` reads them, the swap-ins between two reads one
second apart), then frees the turnstile and replaces itself with the command
by `exec` of `taskpolicy -c utility <command>`. The calls so start in the
order they came, and no two calls hold part of a budget while both wait. A
call that asks for more than a budget holds starts once the whole budget is
free, and runs alone.

The command runs below the user's interactive applications, as does each
process it starts, as the call's own process in the call's process group,
with the caller's environment as it stands, plus `ARC_HEAVY_CPUS` set to
the CPUs granted, and `ARCLOG_THREADS`, `CARGO_BUILD_JOBS` and
`RAYON_NUM_THREADS` set to that number, each at most the value the caller
set. So a `timeout` around the call, the end of the Bash call and
`TaskStop` reach it as they reach the command run without this script. The
call exits with the command's status.

A share is a file under `~/.cache/arc-workspace/heavy-shares/` (`cpu-<i>`,
`gib-<i>`) that the call locks with `flock`. The open descriptors stay in the
command and in each process that inherits them, so the shares stay taken
until every one of them has ended, `SIGKILL` included, and no file needs to
be cleaned up. A call killed while it waits frees the turnstile and its
shares. A command that runs in this form and itself calls it starts at once:
`ARC_HEAVY_CPUS` is set, so the call takes no share, waits for nothing, and
cuts `--cpus` to the share it runs under.

A call that waits says on stderr what it waits for, once, when the wait
starts.

A failure before the command starts prints `run_heavy.py: <reason>` on
stderr and exits 125: no command given, a bad option, the share directory,
`sysctl`, `vm_stat` or `taskpolicy`. A command that is not found exits 127,
and one that cannot be executed 126, as `env` does. A signal before the
command starts ends the call, and the command has not run.

`ARC_HEAVY_DIR` sets the share directory, for the tests."""

from __future__ import annotations

import fcntl
import os
import shutil
import signal
import subprocess
import sys
import time
from typing import Callable, List, Optional, Tuple

from machine_readings import PRESSURE_LEVELS, SWAP_IN_RATE, counters, output, pressure_level

POLL_SECONDS = 1.0
GIB = 1 << 30
SYSTEM_GIB = 4
SHARE_ENV = "ARC_HEAVY_CPUS"
DIR_ENV = "ARC_HEAVY_DIR"
POOL_ENVS = ("ARCLOG_THREADS", "CARGO_BUILD_JOBS", "RAYON_NUM_THREADS")
TURNSTILE = "turnstile"
NOT_RUN = 125
NOT_EXECUTABLE = 126
NOT_FOUND = 127


class Refusal(Exception):
    """A failure before the command starts."""


def share_dir() -> str:
    return os.environ.get(DIR_ENV) or os.path.expanduser("~/.cache/arc-workspace/heavy-shares")


def budget() -> Tuple[int, int]:
    """The CPU shares and the GiB shares of the machine."""
    try:
        cpus, memory = output("sysctl", "-n", "hw.logicalcpu", "hw.memsize").split()
        shares = int(cpus), int(memory) // GIB - SYSTEM_GIB
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        raise Refusal(f"cannot read the budget from sysctl: {error!r}")
    if min(shares) < 1:
        raise Refusal(f"the machine's budget is {shares[0]} CPUs and {shares[1]} GiB")
    return shares


def count(option: str, text: str) -> int:
    if not text.isdigit() or int(text) < 1:
        raise Refusal(f"{option} takes a whole number from 1, not {text!r}")
    return int(text)


def parse(argv: List[str]) -> Tuple[Optional[int], Optional[int], List[str]]:
    """The `--cpus` and `--gib` given, and the command."""
    given: dict[str, Optional[int]] = {"--cpus": None, "--gib": None}
    rest = list(argv)
    while rest and rest[0].partition("=")[0] in given:
        option, equals, value = rest.pop(0).partition("=")
        if not equals:
            if not rest:
                raise Refusal(f"{option} takes a value")
            value = rest.pop(0)
        given[option] = count(option, value)
    return given["--cpus"], given["--gib"], rest


def lock(directory: str, name: str, wait: bool) -> Optional[int]:
    """The descriptor of the file `name` under `directory`, locked: after
    the wait for the lock where `wait` is set, and at once or None where
    another process holds it and `wait` is not set."""
    fd = os.open(os.path.join(directory, name), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX if wait else fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    except OSError:
        os.close(fd)
        raise
    return fd


def take_shares(directory: str, prefix: str, wanted: int, total: int, sleep: Callable[[float], None]) -> None:
    """Lock `wanted` of the `total` files `<prefix>-<i>`, leaving their
    descriptors open and inheritable, and wait while too few are free."""
    pending = [f"{prefix}-{i}" for i in range(total)]
    held = 0
    said = False
    while True:
        for name in list(pending):
            fd = lock(directory, name, wait=False)
            if fd is None:
                continue
            os.set_inheritable(fd, True)
            pending.remove(name)
            held += 1
            if held == wanted:
                return
        if not said:
            print(f"run_heavy.py: waiting for {wanted} {prefix} shares of {total}", file=sys.stderr)
            said = True
        sleep(POLL_SECONDS)


def swap_in_rate_blocks(previous: Tuple[int, float]) -> Tuple[Optional[str], Tuple[int, float]]:
    """The reason the swap-ins since the reading `previous` hold a call, or
    None, and the reading now."""
    swapins = counters()[0]
    now = time.monotonic()
    rate = (swapins - previous[0]) / (now - previous[1])
    reason = f"swap-ins: {rate:.0f} pages a second, over {SWAP_IN_RATE}" if rate > SWAP_IN_RATE else None
    return reason, (swapins, now)


def wait_for_machine(sleep: Callable[[float], None] = time.sleep) -> None:
    """Return once the memory pressure level is normal and the swap-in rate
    over one poll is at most `SWAP_IN_RATE`."""
    try:
        reading = (counters()[0], time.monotonic())
        said = False
        while True:
            sleep(POLL_SECONDS)
            level = pressure_level()
            reason, reading = swap_in_rate_blocks(reading)
            if level in PRESSURE_LEVELS:
                reason = f"memory pressure: level {level}"
            if reason is None:
                return
            if not said:
                print(f"run_heavy.py: waiting for {reason}", file=sys.stderr)
                said = True
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        raise Refusal(f"cannot read the memory load from vm_stat and sysctl: {error!r}")


def acquire(cpus: int, gib: int, cpu_total: int, gib_total: int) -> None:
    """Hold `cpus` CPU shares and `gib` memory shares, once the memory load
    allows, with the descriptors left open for the command to inherit."""
    directory = share_dir()
    try:
        os.makedirs(directory, exist_ok=True)
        turnstile = lock(directory, TURNSTILE, wait=False)
        if turnstile is None:
            print("run_heavy.py: waiting for the calls before this one", file=sys.stderr)
            turnstile = lock(directory, TURNSTILE, wait=True)
        assert turnstile is not None
        take_shares(directory, "cpu", cpus, cpu_total, time.sleep)
        take_shares(directory, "gib", gib, gib_total, time.sleep)
    except OSError as error:
        raise Refusal(f"share directory {directory}: {error}")
    wait_for_machine()
    os.close(turnstile)


def granted(request: Optional[int], parent: str) -> int:
    """The CPUs a nested call runs with: its request, at most the share of
    the call it runs under."""
    if not parent.isdigit() or int(parent) < 1:
        raise Refusal(f"{SHARE_ENV} is {parent!r}, not a whole number from 1")
    return min(request or 1, int(parent))


def bounded(given: Optional[str], share: int) -> int:
    """`given`, a caller's pool size, where it is a whole number under
    `share`, and `share` otherwise."""
    if given is not None and given.isdigit() and 1 <= int(given) < share:
        return int(given)
    return share


def not_started(program: str) -> Optional[int]:
    """The status of a command `program` that cannot start, or None."""
    if shutil.which(program) is not None:
        return None
    return NOT_EXECUTABLE if os.sep in program and os.path.exists(program) else NOT_FOUND


def run(argv: List[str]) -> int:
    """Replace this process with the command; return the exit status of a
    call that did not start it."""
    asked_cpus, asked_gib, command = parse(argv)
    if not command:
        raise Refusal("no command given")
    if (status := not_started(command[0])) is not None:
        print(f"run_heavy.py: {command[0]}: " + ("not found" if status == NOT_FOUND else "not executable"),
              file=sys.stderr)
        return status
    if shutil.which("taskpolicy") is None:
        raise Refusal("taskpolicy is not found")
    parent = os.environ.get(SHARE_ENV)
    if parent is not None:
        cpus = granted(asked_cpus, parent)
    else:
        cpu_total, gib_total = budget()
        cpus = min(asked_cpus or 1, cpu_total)
        gib = min(asked_gib or 1 + cpus, gib_total)
        if (cpus, gib) != (asked_cpus or 1, asked_gib or 1 + cpus):
            print(f"run_heavy.py: cut to the budget: {cpus} CPUs and {gib} GiB of {cpu_total} and {gib_total}",
                  file=sys.stderr)
        acquire(cpus, gib, cpu_total, gib_total)
    os.environ[SHARE_ENV] = str(cpus)
    for name in POOL_ENVS:
        os.environ[name] = str(bounded(os.environ.get(name), cpus))
    # Python ignores these signals, and an exec keeps an ignored signal.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    signal.signal(signal.SIGXFSZ, signal.SIG_DFL)
    try:
        os.execvp("taskpolicy", ["taskpolicy", "-c", "utility", *command])
    except OSError as error:
        raise Refusal(f"taskpolicy: {error.strerror}")


def main(argv: List[str]) -> int:
    if argv[:1] in (["--help"], ["-h"]):
        print(__doc__)
        return 0
    try:
        return run(argv)
    except Refusal as refusal:
        print(f"run_heavy.py: {refusal}", file=sys.stderr)
        return NOT_RUN
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
