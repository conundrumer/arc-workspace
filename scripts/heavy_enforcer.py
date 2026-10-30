"""The rules by which the resource daemon (`scripts/resource_daemon.py`)
finds the processes of a session that run without a grant, and limits what
a job holds.

A command of a session is a process below one of the shells that run a Bash
call, the children of the session's `claude` process whose command line
sources a shell snapshot, with each shell it runs passed over. The session's hooks, MCP servers and shells are never one, and
no process of a job's own family is one.

A command is adopted as an ungated job where its tree, with the trees of
the jobs left out, runs at `ADOPT_CPUS` CPUs for `ADOPT_CPU_SECONDS`, or
holds `ADOPT_GIB` GiB for `ADOPT_GIB_SECONDS`.

A job whose footprint passes `HARD_GIB` GiB is killed at once, each of its processes with
`SIGTERM` and then, `KILL_GRACE` seconds later, `SIGKILL`; nothing overrides that.

At a reading of critical memory pressure level, the daemon kills the job of a session that holds
at least `VICTIM_GIB` GiB, the largest footprint first, as it kills a job past `HARD_GIB`. After a
kill, the next kill at critical pressure waits until a reading below critical, or until
`CRITICAL_PAUSE_SECONDS` more seconds of critical readings have passed. A job of no session never
goes for this.

A job whose footprint passes `SOFT_GIB` GiB is told once to fix its memory use, and runs on.

A gated job of need `now` that has run `LONG_NOW_SECONDS` seconds becomes `soon`: the daemon raises
the nice value of its processes as `need <pid> soon` does, and tells the job's session once, since
no call waits on a job that long.

Standard library only, Python 3.9."""

from __future__ import annotations

import os
from typing import Dict, List

from heavy_model import Job
from machine_readings import GIB, KIB
from process_readings import NO_SESSION

ADOPT_CPUS = 1.5
ADOPT_CPU_SECONDS = 60
ADOPT_GIB = 2
ADOPT_GIB_SECONDS = 30
HARD_GIB = 32
"""The footprint in GiB past which a job is killed. On the machine's 24 GiB, a decode that held at
44 GiB thrashed it for 39 minutes (2026-10-26), and a run that grew to 96 GiB; the largest run that
finished well held 20.6 GiB."""
SOFT_GIB = 12
"""The footprint in GiB past which a job's session is told to fix its memory use."""
LONG_NOW_SECONDS = 600
"""The seconds a gated job of need `now` runs before it becomes `soon`. A Bash call waits at most
600000 ms, so no call waits on a job past it."""
CRITICAL_PAUSE_SECONDS = 10
VICTIM_GIB = 1
KILL_GRACE = 5
SNAPSHOTS = "/shell-snapshots/"
SHELLS = frozenset({"bash", "sh", "zsh", "dash", "fish"})
CPU_OVERRUN_FACTOR = 2
CPU_OVERRUN_SECONDS = 60


def program(command: str) -> str:
    words = command.split()
    return os.path.basename(words[0]) if words else ""


def is_shell(command: str) -> bool:
    return program(command) in SHELLS


def runs_calls(command: str) -> bool:
    """Whether the command line is of the shell that runs a Bash call: `bash -c source
    <config dir>/shell-snapshots/<snapshot> ...`. A hook the harness starts as `sh -c <string>`
    is none."""
    words = command.split()
    return is_shell(command) and "-c" in words[1:] and SNAPSHOTS in command


def command_roots(commands: Dict[int, str], parents: Dict[int, int], sessions: List[int]) -> List[int]:
    """The pids of the commands of the sessions whose `claude` processes are `sessions`:
    below each child of a `claude` process that `runs_calls`, each process that is no shell
    and has only shells between it and that child."""
    children: Dict[int, List[int]] = {}
    for pid, parent in parents.items():
        children.setdefault(parent, []).append(pid)
    roots: List[int] = []

    def below(pid: int) -> None:
        for child in sorted(children.get(pid, [])):
            if is_shell(commands[child]):
                below(child)
            else:
                roots.append(child)

    for claude in sessions:
        for shell in sorted(children.get(claude, [])):
            if runs_calls(commands[shell]):
                below(shell)
    return roots


def victims(jobs: List[Job]) -> List[Job]:
    """The jobs of sessions that hold at least `VICTIM_GIB` GiB, in the order they are killed
    at critical pressure, the largest footprint first. A job of no session never goes."""
    owned = [job for job in jobs if job.owner != NO_SESSION and job.footprint_kib * KIB >= VICTIM_GIB * GIB]
    return sorted(owned, key=lambda job: (-job.footprint_kib, job.pid))
