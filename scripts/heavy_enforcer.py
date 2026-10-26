"""The rules by which the resource daemon (`scripts/resource_daemon.py`)
finds the processes of a session that run without a grant, and picks the
jobs to kill under memory pressure.

A command of a session is a process below one of the shells that run a Bash
call, the children of the session's `claude` process whose command line
sources a shell snapshot, with each shell it runs passed over. The session's hooks, MCP servers and shells are never one, and
no process of a job's own family is one.

A command is adopted as an ungated job where its tree, with the trees of
the jobs left out, runs at `ADOPT_CPUS` CPUs for `ADOPT_CPU_SECONDS`, or
holds `ADOPT_GIB` GiB for `ADOPT_GIB_SECONDS`.

While the swap-ins a second stay over `THRASH_RATE` for `THRASH_SECONDS`, the
daemon kills the jobs of sessions that hold at least `VICTIM_GIB` GiB one at a time, each with
`SIGTERM` and then, `KILL_GRACE` seconds later, `SIGKILL`, the largest footprint first. Each kill
starts the `THRASH_SECONDS` again, so the swap-ins of the processes that read their pages back
after a kill do not count toward the next.

Standard library only, Python 3.9."""

from __future__ import annotations

import os
from typing import Dict, List

from heavy_model import Job, Kind, Need
from machine_readings import GIB, KIB
from process_readings import NO_SESSION

ADOPT_CPUS = 1.5
ADOPT_CPU_SECONDS = 60
ADOPT_GIB = 2
ADOPT_GIB_SECONDS = 30
THRASH_RATE = 5000
"""Swap-ins a second at which the machine thrashes: the rates of the thrash episodes of
2026-10-22 and 23 ran from 5,000 to 36,000."""
THRASH_SECONDS = 15
VICTIM_GIB = 1
KILL_GRACE = 5
KILL_SETTLE = 10
"""The seconds after one kill starts before the next may."""
SNAPSHOTS = "/shell-snapshots/"
SHELLS = frozenset({"bash", "sh", "zsh", "dash", "fish"})
CPU_OVERRUN_FACTOR = 2
CPU_OVERRUN_SECONDS = 60
TIME_OVERRUN_FACTOR = 2


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
    """The jobs of sessions that hold at least `VICTIM_GIB` GiB, in the order they are killed,
    the largest footprint first. A job of no session never goes."""
    owned = [job for job in jobs if job.owner != NO_SESSION and job.footprint_kib * KIB >= VICTIM_GIB * GIB]
    return sorted(owned, key=lambda job: (-job.footprint_kib, job.pid))
