"""Watch the machine's free memory and CPU, and write an alert with the
largest processes each time either stays in trouble. `HELP`, which
`--help` prints, gives the trouble and the alert. The alert files of a
session are read back by `alert_files`."""

import argparse
import os
import re
import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from controlled_markdown import mctx
from gating.cpu import busy_seconds, busy_ticks
import script_calls
from file_ticket import main_tickets
from idle_sessions import harness_processes, running, take_main
from ticket_numbers import session_id
from tree_reads import main_tree
from file_reads import names_in
from ticketing.times import utc_stamp

SAMPLE_SECONDS = 30
LOW_MEMORY = 10
MEMORY_SAMPLES = 2
BUSY_CPU = 90
CPU_SAMPLES = 10
TOP = 10
ALERTS = Path(".cache") / "machine-alerts"
SUFFIX = ".txt"

HELP = mctx("""
    - The usage form:
        ```
        uv run python scripts/machine_watch.py
        ```
    - The command samples the machine every {sample} s, and runs until it is stopped. Trouble is free memory under {low}% of the machine's for {memory} samples in a row, or the machine's CPU over {busy}% busy for {cpu} samples in a row.
        - Trouble that holds at the first sample, or that held at the last alert, counts only after a sample without it.
    - On trouble it writes an alert, which gives the trouble that held and the {top} largest processes by resident memory and the {top} largest by CPU, to a new file `{alerts}/<session id>/<time>{suffix}` of the main tree, the session id being the watcher's own and the time the UTC time of the trouble.
    - Only the watcher of the main session samples, as `uv run python scripts/file_ticket.py main --help-all` gives that session. The watcher of another session keeps running, and samples from the first sample time at which its session is the main.
    - It kills no process and notifies no one.
    """).format(sample=SAMPLE_SECONDS, low=LOW_MEMORY, memory=MEMORY_SAMPLES, busy=BUSY_CPU,
            cpu=CPU_SAMPLES, top=TOP, alerts=ALERTS, suffix=SUFFIX)

SESSION = re.compile(rf"(?:^|\s){script_calls.SESSION_ENV}=(\S+)")
NO_SESSION = "-"


@dataclass(frozen=True)
class Process:
    pid: int
    ppid: int
    rss_kib: int
    cpu: float
    elapsed: str
    session: str
    command: str

    def line(self) -> str:
        return (f"pid={self.pid} ppid={self.ppid} rss={self.rss_kib // 1024}MB cpu={self.cpu:.0f}% "
                f"elapsed={self.elapsed} session={self.session} {self.command}")


def _ps(*args: str) -> list[str]:
    return subprocess.run(["ps", *args], capture_output=True, text=True, check=True).stdout.splitlines()


def processes() -> list[Process]:
    """Each process of the machine, with the session id of the nearest of
    itself and its ancestors that is a running Claude Code session's
    process, as the harness's file gives it, or whose environment gives a
    session id; the harness's file wins for a process that has both."""
    sessions: dict[int, str] = {}
    for text in _ps("-Eww", "-axo", "pid=,command="):
        pid, _, rest = text.strip().partition(" ")
        if (m := SESSION.search(rest)) is not None:
            sessions[int(pid)] = m.group(1)
    sessions |= harness_processes() or {}
    rows = [text.split(None, 5) for text in
            _ps("-ww", "-axo", "pid=,ppid=,rss=,%cpu=,etime=,command=")]
    parents = {int(row[0]): int(row[1]) for row in rows}
    return [Process(int(pid), int(ppid), int(rss), float(cpu), elapsed,
                    nearest_session(int(pid), sessions, parents), command)
            for pid, ppid, rss, cpu, elapsed, command in rows]


def nearest_session(pid: int, sessions: dict[int, str], parents: dict[int, int]) -> str:
    """The session id of `pid`, or of its nearest ancestor by `parents`
    that has one in `sessions`, or `NO_SESSION`."""
    seen: set[int] = set()
    while pid not in seen:
        if pid in sessions:
            return sessions[pid]
        seen.add(pid)
        if pid not in parents:
            break
        pid = parents[pid]
    return NO_SESSION


def free_memory() -> float:
    """The percent of the machine's memory that is free."""
    if sys.platform == "darwin":
        return float(subprocess.run(["sysctl", "-n", "kern.memorystatus_level"],
                                    capture_output=True, text=True, check=True).stdout)
    if sys.platform == "linux":
        info = {k: int(v.split()[0]) for k, _, v in
                (line.partition(":") for line in Path("/proc/meminfo").read_text().splitlines())}
        return 100 * info["MemAvailable"] / info["MemTotal"]
    raise NotImplementedError(f"no free memory on {sys.platform}")


class Trouble:
    """One kind of trouble, as `HELP` gives it."""

    def __init__(self, samples: int) -> None:
        self.samples = samples
        self.run = 0
        self.armed: bool | None = None

    def held(self, now: bool) -> bool:
        if self.armed is None:
            self.armed = not now
        elif not now:
            self.armed = True
        self.run = self.run + 1 if now else 0
        if self.armed and self.run >= self.samples:
            self.armed = False
            return True
        return False


def cpus() -> int:
    n = os.cpu_count()
    if n is None:
        raise NotImplementedError(f"no CPU count on {sys.platform}")
    return n


def troubles() -> tuple[Trouble, Trouble]:
    return Trouble(MEMORY_SAMPLES), Trouble(CPU_SAMPLES)


def watch(session: str) -> Iterator[str]:
    """Samples with no end, and gives what held each time a trouble
    counts."""
    tickets = main_tickets()
    memory, cpu = troubles()
    ticks, at = busy_ticks(), time.monotonic()
    while True:
        time.sleep(SAMPLE_SECONDS)
        now_ticks, now_at = busy_ticks(), time.monotonic()
        busy = 100 * busy_seconds(ticks, now_ticks) / ((now_at - at) * cpus())
        ticks, at = now_ticks, now_at
        if take_main(tickets, session, running(session)) != session:
            memory, cpu = troubles()
            continue
        free = free_memory()
        low, hot = memory.held(free < LOW_MEMORY), cpu.held(busy > BUSY_CPU)
        if low or hot:
            held = []
            if low:
                held.append(mctx("free memory {free:.0f}%, under {limit}% for {n} samples in a row").format(
                    free=free, limit=LOW_MEMORY, n=MEMORY_SAMPLES))
            if hot:
                held.append(mctx("CPU {busy:.0f}% busy, over {limit}% for {n} samples in a row").format(
                    busy=busy, limit=BUSY_CPU, n=CPU_SAMPLES))
            yield "; ".join(held)


def report(trouble: str, found: list[Process]) -> str:
    by_memory = sorted(found, key=lambda p: (-p.rss_kib, p.pid))[:TOP]
    by_cpu = sorted(found, key=lambda p: (-p.cpu, p.pid))[:TOP]
    return "\n".join([mctx("trouble: {trouble}").format(trouble=trouble),
                      mctx("largest by resident memory:"), *(p.line() for p in by_memory),
                      mctx("largest by CPU:"), *(p.line() for p in by_cpu)])


def alert_dir(main: Path, session: str) -> Path:
    return main / ALERTS / session


def alert_files(main: Path, session: str) -> tuple[Path, ...]:
    """The alert files the watcher of `session` wrote under the main tree
    `main`, in time order."""
    folder = alert_dir(main, session)
    return tuple(folder / n for n in sorted(names_in(folder)) if n.endswith(SUFFIX))


def main(argv: list[str]) -> int:
    argparse.ArgumentParser(description=HELP, formatter_class=argparse.RawDescriptionHelpFormatter,
                            usage=argparse.SUPPRESS).parse_args(argv)
    session = session_id()
    folder = alert_dir(main_tree(), session)
    for trouble in watch(session):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{utc_stamp(time.time())}{SUFFIX}").write_text(report(trouble, processes()) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
