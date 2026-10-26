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

Under critical memory pressure, or a swap-in rate over the load monitor's
alert rate for `SWAP_IN_SAMPLES` samples, the daemon kills the jobs of a
session one at a time, each with `SIGTERM` and then, `KILL_GRACE` seconds
later, `SIGKILL`, in the order `victims` gives. Where the pressure has been
critical for `LAST_RESORT_SECONDS`, the order is the ungated processes, then
every gated job, the largest first, so the largest gated job of any need is
the next to go.

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
SWAP_IN_SAMPLES = 2
KILL_GRACE = 5
KILL_SETTLE = 10
"""The seconds after one kill starts before the next may."""
LAST_RESORT_SECONDS = 30
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


def over_declaration(job: Job) -> bool:
    return job.kind is Kind.GATED and job.footprint_kib * KIB > job.amount.gib * GIB


def victims(jobs: List[Job], last_resort: bool) -> List[Job]:
    """The jobs of sessions in the order they are killed: the ungated ones, a gated job over its
    declared GiB, then `idle` and `soon` jobs, each group largest footprint first. Where
    `last_resort` is set, the ungated ones and then every gated job, largest footprint first,
    whatever its need. A job of no session never goes."""
    owned = [job for job in jobs if job.owner != NO_SESSION]
    by_size = sorted(owned, key=lambda job: (-job.footprint_kib, job.pid))
    ungated = [job for job in by_size if job.kind is Kind.UNGATED]
    if last_resort:
        return ungated + [job for job in by_size if job.kind is Kind.GATED]
    groups = [
        ungated,
        [job for job in by_size if over_declaration(job)],
        [job for job in by_size if job.need is Need.IDLE],
        [job for job in by_size if job.need is Need.SOON],
    ]
    out: List[Job] = []
    for group in groups:
        out += [job for job in group if all(job is not found for found in out)]
    return out
