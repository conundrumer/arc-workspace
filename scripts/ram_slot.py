#!/usr/bin/python3
"""Run a command that uses much memory once a slot and the memory are free.

Usage: <checkout>/scripts/ram_slot.py <command> [<arg> ...]
       <checkout>/scripts/ram_slot.py bash -c '<simple command>; ...'

The call takes one of 3 slots, which every session and checkout of the
machine shares, waits until the memory `vm_stat` gives as free or inactive
is at least 6 GiB, and then replaces itself with the command by `exec`.
The command runs with the caller's environment as it stands, plus
`ARC_RAM_SLOT`, as the call's own process in the call's process group, so
a `timeout` around the call, the end of the Bash call and `TaskStop` reach
it as they reach the command run without this script. The call exits with
the command's status.

A slot is a file under `~/.cache/arc-workspace/ram-slots/` that the call
locks with `flock`. The open descriptor stays in the command and in each
process that inherits it, so the slot stays taken until every one of them
has ended, `SIGKILL` included, and no file needs to be cleaned up. A
command that runs in this form and itself calls it starts at once, in the
slot of the call it runs under, since `ARC_RAM_SLOT` is set.

A call that waits says on stderr what it waits for. Memory is read once the
slot is held, so two calls that take slots at the same moment can both read
the memory above the floor and start.

A failure before the command starts prints `ram_slot.py: <reason>` on
stderr and exits 125: no command given, the slot directory, `vm_stat`. A
failure to start the command exits 127 where it is not found, and 126
otherwise, as `env` does. A signal before the command starts ends the call,
and the command has not run.

`ARC_RAM_SLOT_DIR` sets the slot directory, for the tests."""

from __future__ import annotations

import fcntl
import os
import signal
import subprocess
import sys
import time

SLOTS = 3
FLOOR_GIB = 6
POLL_SECONDS = 1.0
GIB = 1 << 30
SLOT_ENV = "ARC_RAM_SLOT"
DIR_ENV = "ARC_RAM_SLOT_DIR"
NOT_RUN = 125
NOT_EXECUTABLE = 126
NOT_FOUND = 127


class Refusal(Exception):
    """A failure before the command starts."""


def slot_dir() -> str:
    return os.environ.get(DIR_ENV) or os.path.expanduser(
        "~/.cache/arc-workspace/ram-slots")


def try_slot(directory: str) -> str | None:
    """The path of the first slot this process locked, with its descriptor
    left open and inheritable, or None where all are taken."""
    for number in range(SLOTS):
        path = os.path.join(directory, f"slot-{number}")
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            continue
        os.set_inheritable(fd, True)
        return path
    return None


def available_bytes() -> int:
    """The bytes of memory `vm_stat` gives as free or inactive."""
    try:
        out = subprocess.run(["vm_stat"], capture_output=True, text=True,
                             check=True).stdout
        lines = out.splitlines()
        size = int(lines[0].split("page size of ")[1].split()[0])
        pages = {name: int(value.strip().rstrip("."))
                 for name, value in (line.split(":") for line in lines[1:]
                                     if ":" in line)}
        return (pages["Pages free"] + pages["Pages inactive"]) * size
    except (OSError, subprocess.CalledProcessError, IndexError, KeyError,
            ValueError) as error:
        raise Refusal(f"cannot read the free memory from vm_stat: {error!r}")


def wait_for_slot(directory: str) -> str:
    try:
        os.makedirs(directory, exist_ok=True)
        path = try_slot(directory)
        if path is None:
            print(f"ram_slot.py: waiting for a slot: all {SLOTS} are taken",
                  file=sys.stderr)
        while path is None:
            time.sleep(POLL_SECONDS)
            path = try_slot(directory)
        return path
    except OSError as error:
        raise Refusal(f"slot directory {directory}: {error}")


def wait_for_memory() -> None:
    waiting = False
    while (free := available_bytes()) < FLOOR_GIB * GIB:
        if not waiting:
            print(f"ram_slot.py: waiting for memory: {free / GIB:.1f} GiB "
                  f"free or inactive, {FLOOR_GIB} GiB needed",
                  file=sys.stderr)
            waiting = True
        time.sleep(POLL_SECONDS)


def run(command: list[str]) -> int:
    """Replace this process with `command`; return the exit status of a
    call that did not start it."""
    if not command:
        raise Refusal("no command given")
    if SLOT_ENV not in os.environ:
        os.environ[SLOT_ENV] = wait_for_slot(slot_dir())
        wait_for_memory()
    # Python ignores these signals, and an exec keeps an ignored signal.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    signal.signal(signal.SIGXFSZ, signal.SIG_DFL)
    try:
        os.execvp(command[0], command)
    except OSError as error:
        print(f"ram_slot.py: {command[0]}: {error.strerror}", file=sys.stderr)
        return NOT_FOUND if isinstance(error, FileNotFoundError) \
            else NOT_EXECUTABLE


def main(argv: list[str]) -> int:
    if argv[:1] in (["--help"], ["-h"]):
        print(__doc__)
        return 0
    try:
        return run(argv)
    except Refusal as refusal:
        print(f"ram_slot.py: {refusal}", file=sys.stderr)
        return NOT_RUN
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
