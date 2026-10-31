#!/usr/bin/python3
"""Run a command that uses much CPU or memory, and tell the machine's daemon.

Usage: <checkout>/scripts/run_heavy.py [--cpus <n>] [--need now|soon|idle] <command> [<arg> ...]
       <checkout>/scripts/run_heavy.py --cpus <n> bash -c '<simple command>; ...'
       <checkout>/scripts/run_heavy.py queue
       <checkout>/scripts/run_heavy.py need <pid> now|soon|idle

`--cpus` is the processes or threads the command runs at once (default 1): the call tells the command
to use that many, and the daemon tells the session where the command runs at more than twice
that for a minute. `--gib`, `--minutes` and `--wait`, which older calls give, have no effect. `--need` is who waits on
the command's result (default `soon`), and sets the nice value of the command, which each process it starts
inherits: `now` where someone waits before the next step can start, nice value 0; `soon` where the result
feeds the next step and nothing sits idle for it, 5; `idle` where nothing waits on it, 15. A call that runs
at a higher nice value keeps it. A job of need `now` that has run `LONG_NOW_SECONDS` seconds becomes `soon`
(`scripts/heavy_enforcer.py`): the daemon raises the nice value of its processes as `need <pid> soon` does, and tells
the session once.

A call starts its command at once, whatever else runs. Memory gates no start: the daemon tells a job's session to fix its memory
use when the job passes `SOFT_GIB`, and kills the job when it passes `HARD_GIB`; and it kills the largest
job where the memory pressure is critical, as `scripts/heavy_enforcer.py` gives them.

A call registers its command with the resource daemon (`scripts/resource_daemon.py`), and starts the
daemon where none runs. `queue` prints each running job with its need, and each ungated process of a session
that the daemon counts.

The call replaces itself with the command by `exec`. The command runs as the call's
own process in the call's process group, with the caller's environment as it
stands, plus `ARC_HEAVY_CPUS` set to `--cpus`, and `ARCLOG_THREADS`,
`CARGO_BUILD_JOBS`, `RAYON_NUM_THREADS`, `RUST_TEST_THREADS`, `OMP_NUM_THREADS`
and `VECLIB_MAXIMUM_THREADS` set to that number, each at most the value the
caller set. So a `timeout` around the call, the end of the Bash
call and `TaskStop` reach it as they reach the command run without this
script. The call exits with the command's status. The daemon counts the job
until that process ends, and kills the processes the command leaves behind.

A command that runs in this form and itself calls it starts at once:
`ARC_HEAVY_CPUS` is set, so the call registers nothing and cuts `--cpus` to the
number it runs under.

`queue` and `need` are reserved as the first argument. `need <pid> <tier>` gives the processes
of the running job of that pid, which `queue` prints, the nice value of `<tier>`, or keeps a process's own
where that is higher. A user cannot lower a nice value, so the call exits 125 where `<tier>` is under the
job's need, says so, and changes nothing. It exits 125 as well where no job of that pid runs through this
script or `<tier>` is none of the three.

A failure before the command starts prints `run_heavy.py: <reason>` on
stderr and exits 125: no command given, a bad option, the daemon (it cannot be
reached or started, speaks another protocol, or reads no machine load), the
nice value, `sysctl` or `vm_stat`. A command that is not
found exits 127, and one that cannot be executed 126, as `env` does. A signal
before the command starts ends the call, and the command has not run.

`ARC_HEAVY_DIR` sets the directory of the daemon's files."""

from __future__ import annotations

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
# The same names stand in `src/engine/pool.py` and `engine/arclog-py/export_checks.py`, which run under other interpreters.
POOL_ENVS = ("ARCLOG_THREADS", "CARGO_BUILD_JOBS", "RAYON_NUM_THREADS",
             "RUST_TEST_THREADS", "OMP_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")
NOT_RUN = 125
NOT_EXECUTABLE = 126
NOT_FOUND = 127
DEFAULT_NEED = Need.SOON
QUEUE = "queue"
NEED = "need"
IGNORED = ("--gib", "--minutes", "--wait")
"""The options that older calls give and that have no effect."""


@dataclass(frozen=True)
class Options:
    cpus: int
    need: Need
    command: List[str]


def count(option: str, text: str) -> int:
    if not text.isdigit() or int(text) < 1:
        raise Refusal(f"{option} takes a whole number from 1, not {text!r}")
    return int(text)


def need(text: str) -> Need:
    try:
        return Need(text)
    except ValueError:
        raise Refusal(f"--need takes now, soon or idle, not {text!r}")


def parse(argv: List[str]) -> Options:
    """The options given, and the command."""
    given: dict[str, str] = {}
    rest = list(argv)
    while rest and rest[0].partition("=")[0] in ("--cpus", "--need", *IGNORED):
        option, equals, value = rest.pop(0).partition("=")
        if not equals:
            if not rest:
                raise Refusal(f"{option} takes a value")
            value = rest.pop(0)
        given[option] = value
    return Options(
        count("--cpus", given["--cpus"]) if "--cpus" in given else heavy_protocol.DEFAULT_CPUS,
        need(given["--need"]) if "--need" in given else DEFAULT_NEED,
        rest)


def granted(request: int, parent: str) -> int:
    """The CPUs a nested call runs with: its request, at most the CPUs of
    the call it runs under."""
    if not parent.isdigit() or int(parent) < 1:
        raise Refusal(f"{SHARE_ENV} is {parent!r}, not a whole number from 1")
    return min(request, int(parent))


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


def set_nice(wanted: Need) -> None:
    """Give this process the nice value of `wanted`, or keep its own where that is higher, which
    its children inherit."""
    try:
        os.setpriority(os.PRIO_PROCESS, 0, wanted.raised(os.getpriority(os.PRIO_PROCESS, 0)))
    except OSError as error:
        raise Refusal(f"nice value {wanted.nice}: {error.strerror}")


def say(line: str) -> None:
    print(f"run_heavy.py: {line}", file=sys.stderr)


def show_queue(args: List[str]) -> int:
    if args:
        raise Refusal(f"{QUEUE} takes no argument, not {args[0]!r}")
    registry = heavy_client.queue(heavy_protocol.heavy_dir())
    if registry is None:
        print("no daemon runs, so no job is counted")
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
    set_nice(options.need)
    parent = os.environ.get(SHARE_ENV)
    if parent is not None:
        cpus = granted(options.cpus, parent)
    else:
        cpus = options.cpus
        heavy_client.acquire(heavy_protocol.heavy_dir(), {
            "op": "acquire", "pid": os.getpid(), "cpus": cpus, "need": options.need.value,
            "command": shlex.join(command)})
    os.environ[SHARE_ENV] = str(cpus)
    for name in POOL_ENVS:
        os.environ[name] = str(bounded(os.environ.get(name), cpus))
    # Python ignores these signals, and an exec keeps an ignored signal.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    signal.signal(signal.SIGXFSZ, signal.SIG_DFL)
    try:
        os.execvp(command[0], command)
    except OSError as error:
        raise Refusal(f"{command[0]}: {error.strerror}")


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
