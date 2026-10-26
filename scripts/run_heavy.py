#!/usr/bin/python3
"""Run a command that uses much CPU or memory, within the machine's budget.

Usage: <checkout>/scripts/run_heavy.py [--cpus <n>] [--gib <g>] [--need now|soon|idle] [--minutes <m>]
                                       [--wait <seconds>] <command> [<arg> ...]
       <checkout>/scripts/run_heavy.py --cpus <n> bash -c '<simple command>; ...'
       <checkout>/scripts/run_heavy.py queue
       <checkout>/scripts/run_heavy.py need <pid> now|soon|idle

`--cpus` is the processes or threads the command runs at once (default 1),
and `--gib` the peak memory in GiB it is expected to reach (default `1 + <n>`). `--minutes`
is the time it is to run (default 5), and `--need` who waits on its result
(default `soon`): `now` where someone waits before the next step can start,
`soon` where the result feeds the next step and nothing sits idle for it,
`idle` where nothing waits on it. `--wait` is the seconds the call waits for
its share before it gives up with the expected start.

The heavy commands that run through this script at one time, in every session
and checkout of the machine, together hold at most the machine's CPU budget,
the logical CPUs (`hw.logicalcpu`). A request over the CPUs its need allows is cut
to them, with one line on stderr. Memory has no budget: the daemon starts no call
while the kernel's memory pressure is high, and at most one call between two of
its readings of the machine.

A call asks the resource daemon (`scripts/resource_daemon.py`) for a share of
the budget, and starts the daemon where none runs. The daemon starts a call
when it is first of its queue and fits, as `scripts/heavy_scheduler.py` gives
the rule: a job of at most 5 minutes draws on a reserve that no longer job
takes, and the others are ordered, and capped in what they hold together, by
need. The daemon starts none while the kernel's memory pressure level is warn
or critical or the swap-ins a second are over the load monitor's alert rate
(`scripts/machine_readings.py`). `queue` prints each job that holds a share,
each ungated process of a session that the daemon counts against the budget,
and each waiting call with its expected start.

The call replaces itself with the command by `exec` of `taskpolicy -c utility
<command>`, once the daemon grants the share. The command runs below the
user's interactive applications, as does each process it starts, as the call's
own process in the call's process group, with the caller's environment as it
stands, plus `ARC_HEAVY_CPUS` set to the CPUs granted, and `ARCLOG_THREADS`,
`CARGO_BUILD_JOBS` and `RAYON_NUM_THREADS` set to that number, each at most
the value the caller set. So a `timeout` around the call, the end of the Bash
call and `TaskStop` reach it as they reach the command run without this
script. The call exits with the command's status. The daemon holds the share
until that process ends, and kills the processes the command leaves behind.

A command that runs in this form and itself calls it starts at once:
`ARC_HEAVY_CPUS` is set, so the call takes no share, waits for nothing, and
cuts `--cpus` to the share it runs under.

`queue` and `need` are reserved as the first argument. `need <pid> <tier>` gives the waiting
call of that pid, which `queue` prints, the need `<tier>`, and the daemon orders the queues
again at once. It exits 125 where no call of that pid waits or `<tier>` is none of the three.

A call that waits says on stderr what it waits for, once, when the wait
starts. A call killed while it waits leaves the queue.

A failure before the command starts prints `run_heavy.py: <reason>` on
stderr and exits 125: no command given, a bad option, the daemon (it cannot be
reached or started, speaks another protocol, or reads no machine load), the
wait that ran out, `sysctl`, `vm_stat` or `taskpolicy`. A command that is not
found exits 127, and one that cannot be executed 126, as `env` does. A signal
before the command starts ends the call, and the command has not run.

`ARC_HEAVY_DIR` sets the directory of the daemon's files, for the tests."""

from __future__ import annotations

import math
import os
import shlex
import shutil
import signal
import sys
import time
from dataclasses import dataclass
from typing import List, Optional

import heavy_client
import heavy_protocol
from heavy_model import Need
from heavy_protocol import Refusal

SHARE_ENV = "ARC_HEAVY_CPUS"
POOL_ENVS = ("ARCLOG_THREADS", "CARGO_BUILD_JOBS", "RAYON_NUM_THREADS")
NOT_RUN = 125
NOT_EXECUTABLE = 126
NOT_FOUND = 127
DEFAULT_MINUTES = 5.0
DEFAULT_NEED = Need.SOON
QUEUE = "queue"
NEED = "need"


@dataclass(frozen=True)
class Options:
    cpus: Optional[int]
    gib: Optional[int]
    need: Need
    minutes: float
    wait: Optional[int]
    command: List[str]


def count(option: str, text: str) -> int:
    if not text.isdigit() or int(text) < 1:
        raise Refusal(f"{option} takes a whole number from 1, not {text!r}")
    return int(text)


def minutes(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        value = math.nan
    if not (math.isfinite(value) and value > 0):
        raise Refusal(f"--minutes takes a number over 0, not {text!r}")
    return value


def need(text: str) -> Need:
    try:
        return Need(text)
    except ValueError:
        raise Refusal(f"--need takes now, soon or idle, not {text!r}")


def parse(argv: List[str]) -> Options:
    """The options given, and the command."""
    given: dict[str, str] = {}
    rest = list(argv)
    while rest and rest[0].partition("=")[0] in ("--cpus", "--gib", "--need", "--minutes", "--wait"):
        option, equals, value = rest.pop(0).partition("=")
        if not equals:
            if not rest:
                raise Refusal(f"{option} takes a value")
            value = rest.pop(0)
        given[option] = value
    return Options(
        count("--cpus", given["--cpus"]) if "--cpus" in given else None,
        count("--gib", given["--gib"]) if "--gib" in given else None,
        need(given["--need"]) if "--need" in given else DEFAULT_NEED,
        minutes(given["--minutes"]) if "--minutes" in given else DEFAULT_MINUTES,
        count("--wait", given["--wait"]) if "--wait" in given else None,
        rest)


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


def say(line: str) -> None:
    print(f"run_heavy.py: {line}", file=sys.stderr)


def show_queue(args: List[str]) -> int:
    if args:
        raise Refusal(f"{QUEUE} takes no argument, not {args[0]!r}")
    registry = heavy_client.queue(heavy_protocol.heavy_dir())
    if registry is None:
        print("no daemon runs, so no job holds a share")
    else:
        print(heavy_client.queue_text(registry, time.time()))
    return 0


def change_need(args: List[str]) -> int:
    if len(args) != 2 or not args[0].isdigit() or int(args[0]) < 1:
        raise Refusal(f"{NEED} takes a pid and a need: {NEED} <pid> now|soon|idle")
    print(heavy_client.change_need(heavy_protocol.heavy_dir(), int(args[0]), need(args[1]).value))
    return 0


def run(argv: List[str]) -> int:
    """Replace this process with the command; return the exit status of a
    call that did not start it."""
    if argv[:1] == [QUEUE]:
        return show_queue(argv[1:])
    if argv[:1] == [NEED]:
        return change_need(argv[1:])
    options = parse(argv)
    command = options.command
    if not command:
        raise Refusal("no command given")
    if (status := not_started(command[0])) is not None:
        say(f"{command[0]}: " + ("not found" if status == NOT_FOUND else "not executable"))
        return status
    if shutil.which("taskpolicy") is None:
        raise Refusal("taskpolicy is not found")
    parent = os.environ.get(SHARE_ENV)
    if parent is not None:
        cpus = granted(options.cpus, parent)
    else:
        cpus = heavy_client.acquire(heavy_protocol.heavy_dir(), {
            "op": "acquire", "version": heavy_protocol.VERSION, "pid": os.getpid(), "cpus": options.cpus,
            "gib": options.gib, "need": options.need.value, "minutes": options.minutes, "wait": options.wait,
            "command": shlex.join(command)}, say)
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
        say(str(refusal))
        return NOT_RUN
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
