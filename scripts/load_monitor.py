"""Watch the machine's CPU and memory pressure, and write an alert with the
processes of the largest physical footprint and the most CPU each time a
load alert rule holds. `HELP`, which `--help` prints, gives the readings,
the rules and the alert."""

import argparse
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from controlled_markdown import mctx
from gating.cpu import busy_seconds, busy_ticks
import script_calls
from idle_sessions import harness_processes, running
from ticket_numbers import session_id
from tree_reads import main_tree
from ticketing.times import stamp_time, utc_stamp

SAMPLE_SECONDS = 5
SWAP_IN_RATE = 1000
SWAP_IN_SAMPLES = 2
PRESSURE_LEVELS = frozenset({2, 4})
PRESSURE_SAMPLES = 2
BUSY_CPU = 90
CPU_SAMPLES = 6
REALERT_SECONDS = 600
CHECK_SECONDS = 60
READINGS_SECONDS = 24 * 3600
TOP = 10
ALERTS = Path(".cache") / "load-alerts"
SUFFIX = ".txt"
READINGS = "readings.tsv"

HELP = mctx("""
    - The usage form:
        ```
        uv run python scripts/load_monitor.py
        ```
    - The command runs on macOS, and samples the machine every {sample} s until a load alert rule holds. Each sample reads the machine's CPU busy share, the kernel's memory pressure level (`kern.memorystatus_vm_pressure_level`: 1 normal, 2 warn, 4 critical), the swap-in and page-in rates in pages a second from the counters of `vm_stat` since the last sample, and the swap in use (`vm.swapusage`).
    - The load alert rules:
        - The swap-in rate over {swap_in} pages a second for {swap_in_samples} samples in a row.
        - The memory pressure level at warn or critical for {pressure_samples} samples in a row.
        - The CPU over {busy}% busy for {cpu} samples in a row.
    - A rule that holds at the first sample counts only once it has held for {realert} s, or after a sample without it, so that a load that stays gives a load re-alert once in {realert} s, the command having exited at each alert.
    - On a rule that holds the command writes an alert to a new file `{alerts}/<session id>/<time>{suffix}` of the main tree, the session id being the monitor's own and the time the UTC time of the alert, prints the file's path, and exits 0. The alert gives the rules that held, then the {top} processes of the largest physical footprint, the memory the process takes from the machine, and the {top} of the most CPU, each with its pid, parent pid, footprint, CPU percent, elapsed time, session id and command line.
    - It appends each sample's readings to `{alerts}/<session id>/{readings}` of the main tree, one line a sample of tab-separated fields: the UTC time, the CPU busy percent, the memory pressure level, the swap-in rate, the page-in rate and the swap in use in MB. It keeps the last {keep} hours of them.
    - One monitor watches the machine. Where another `load_monitor.py` process runs for a session that runs, the command exits with a message that gives that process's pid and session id. It exits as well at the first check, made every {check} s, at which its own session is not among the sessions that run.
    - It kills no process and notifies no one past its exit.
    """).format(sample=SAMPLE_SECONDS, swap_in=SWAP_IN_RATE, swap_in_samples=SWAP_IN_SAMPLES,
                pressure_samples=PRESSURE_SAMPLES, busy=BUSY_CPU, cpu=CPU_SAMPLES,
                realert=REALERT_SECONDS, alerts=ALERTS, suffix=SUFFIX, top=TOP, readings=READINGS,
                keep=READINGS_SECONDS // 3600, check=CHECK_SECONDS)

SESSION = re.compile(rf"(?:^|\s){script_calls.SESSION_ENV}=(\S+)")
NO_SESSION = "-"
SWAP_USED = re.compile(r"used = ([\d.]+)M")
VM_COUNTER = re.compile(r"^(Pageins|Swapins):\s+(\d+)\.$", re.MULTILINE)
FOOTPRINT = re.compile(r"(\d+)([BKMG])[+-]?")
UNIT_KIB = {"B": 1 / 1024, "K": 1, "M": 1024, "G": 1024 ** 2}


@dataclass(frozen=True)
class Process:
    pid: int
    ppid: int
    cpu: float
    elapsed: str
    session: str
    command: str

    def line(self, footprint_kib: int) -> str:
        return (f"pid={self.pid} ppid={self.ppid} footprint={footprint_kib // 1024}MB cpu={self.cpu:.0f}% "
                f"elapsed={self.elapsed} session={self.session} {self.command}")


@dataclass(frozen=True)
class Reading:
    """One sample of the machine."""
    busy: float
    pressure: int
    swap_in: float
    page_in: float
    swap_used_mb: float

    def row(self, at: float) -> str:
        return "\t".join([utc_stamp(at), f"{self.busy:.1f}", str(self.pressure), f"{self.swap_in:.0f}",
                          f"{self.page_in:.0f}", f"{self.swap_used_mb:.0f}"])


def _run(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def processes() -> list[Process]:
    """Each process of the machine, with the session id of the nearest of
    itself and its ancestors that is a running Claude Code session's
    process, as the harness's file gives it, or whose environment gives a
    session id; the harness's file wins for a process that has both."""
    sessions: dict[int, str] = {}
    for text in _run("ps", "-Eww", "-axo", "pid=,command=").splitlines():
        pid, _, rest = text.strip().partition(" ")
        if (m := SESSION.search(rest)) is not None:
            sessions[int(pid)] = m.group(1)
    sessions |= harness_processes() or {}
    rows = [text.split(None, 4) for text in
            _run("ps", "-ww", "-axo", "pid=,ppid=,%cpu=,etime=,command=").splitlines()]
    parents = {int(row[0]): int(row[1]) for row in rows}
    return [Process(int(pid), int(ppid), float(cpu), elapsed,
                    nearest_session(int(pid), sessions, parents), command)
            for pid, ppid, cpu, elapsed, command in rows]


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


def footprints() -> dict[int, int]:
    """The physical footprint in KiB of each process, as the `MEM` column
    of `top` gives it."""
    out: dict[int, int] = {}
    for text in _run("top", "-l", "1", "-stats", "pid,mem").splitlines():
        pid, _, mem = text.partition(" ")
        if not pid.isdigit():
            continue
        m = FOOTPRINT.fullmatch(mem.strip())
        if m is None:
            raise ValueError(f"no footprint in the `top` line {text!r}")
        out[int(pid)] = int(int(m.group(1)) * UNIT_KIB[m.group(2)])
    return out


def counters() -> tuple[int, int]:
    """The swap-in and page-in counts since boot, as `vm_stat` gives them."""
    found = {name: int(count) for name, count in VM_COUNTER.findall(_run("vm_stat"))}
    return found["Swapins"], found["Pageins"]


def pressure_and_swap() -> tuple[int, float]:
    """The kernel's memory pressure level, and the swap in use in MB."""
    level, usage = _run("sysctl", "-n", "kern.memorystatus_vm_pressure_level", "vm.swapusage").splitlines()
    m = SWAP_USED.search(usage)
    if m is None:
        raise ValueError(f"no swap in use in {usage!r}")
    return int(level), float(m.group(1))


def cpus() -> int:
    n = os.cpu_count()
    if n is None:
        raise NotImplementedError(f"no CPU count on {sys.platform}")
    return n


class Rule:
    """One load alert rule, as `HELP` gives it."""

    def __init__(self, samples: int) -> None:
        self.samples = samples
        self.run = 0
        self.not_before: float | None = None

    def held(self, now: bool, at: float, first: bool) -> bool:
        """Whether the rule holds at the sample made at monotonic time
        `at`, `now` being whether its condition stands at the sample and
        `first` whether this is the monitor's first sample."""
        if first and now:
            self.not_before = at + REALERT_SECONDS
        elif not now:
            self.not_before = None
        self.run = self.run + 1 if now else 0
        return self.run >= self.samples and (self.not_before is None or at >= self.not_before)


def other_monitor(me: Process, found: list[Process], sessions_running: frozenset[str]) -> Process | None:
    """A process of `found` other than `me` that runs this script for a
    session of `sessions_running`."""
    for p in found:
        words = p.command.split()
        if (p.pid != me.pid and len(words) > 1 and Path(words[0]).name.startswith("python")
                and Path(words[-1]).name == Path(__file__).name and p.session in sessions_running):
            return p
    return None


def check(session: str) -> str | None:
    """The message that tells why the monitor of `session` is to exit, or
    None."""
    held = running(session)
    if held is None or session not in held:
        return mctx("the session {session} is not among the sessions that run").format(session=session)
    found = processes()
    me = next(p for p in found if p.pid == os.getpid())
    if (other := other_monitor(me, found, held)) is not None:
        return mctx("another load monitor runs: pid {pid}, session {session}").format(
            pid=other.pid, session=other.session)
    return None


def write_reading(path: Path, at: float, reading: Reading) -> None:
    with path.open("a") as f:
        f.write(reading.row(at) + "\n")


def trim_readings(path: Path, now: float) -> None:
    """Drops the lines of `path` older than `READINGS_SECONDS`."""
    if not path.exists():
        return
    kept = [line for line in path.read_text().splitlines()
            if stamp_time(line.split("\t", 1)[0]) >= now - READINGS_SECONDS]
    path.write_text("".join(line + "\n" for line in kept))


def held_rules(swap: Rule, pressure: Rule, cpu: Rule, reading: Reading, at: float, first: bool) -> list[str]:
    """The load alert rules that hold at `reading`."""
    held = []
    if swap.held(reading.swap_in > SWAP_IN_RATE, at, first):
        held.append(mctx("swap-ins {rate:.0f} pages a second, over {limit} for {n} samples in a row").format(
            rate=reading.swap_in, limit=SWAP_IN_RATE, n=SWAP_IN_SAMPLES))
    if pressure.held(reading.pressure in PRESSURE_LEVELS, at, first):
        held.append(mctx("memory pressure level {level}, at warn or critical for {n} samples in a row").format(
            level=reading.pressure, n=PRESSURE_SAMPLES))
    if cpu.held(reading.busy > BUSY_CPU, at, first):
        held.append(mctx("CPU {busy:.0f}% busy, over {limit}% for {n} samples in a row").format(
            busy=reading.busy, limit=BUSY_CPU, n=CPU_SAMPLES))
    return held


def report(trouble: str, found: list[Process], footprint: dict[int, int]) -> str:
    known = [p for p in found if p.pid in footprint]
    by_memory = sorted(known, key=lambda p: (-footprint[p.pid], p.pid))[:TOP]
    by_cpu = sorted(known, key=lambda p: (-p.cpu, p.pid))[:TOP]
    return "\n".join([mctx("trouble: {trouble}").format(trouble=trouble),
                      mctx("largest by physical footprint:"),
                      *(p.line(footprint[p.pid]) for p in by_memory),
                      mctx("largest by CPU:"), *(p.line(footprint[p.pid]) for p in by_cpu)])


def alert_dir(main: Path, session: str) -> Path:
    return main / ALERTS / session


def main(argv: list[str]) -> int:
    argparse.ArgumentParser(description=HELP, formatter_class=argparse.RawDescriptionHelpFormatter,
                            usage=argparse.SUPPRESS).parse_args(argv)
    if sys.platform != "darwin":
        print(f"the load monitor runs on macOS alone, not on {sys.platform}", file=sys.stderr)
        return 1
    session = session_id()
    folder = alert_dir(main_tree(), session)
    folder.mkdir(parents=True, exist_ok=True)
    readings = folder / READINGS
    trim_readings(readings, time.time())
    if (stop := check(session)) is not None:
        print(stop, file=sys.stderr)
        return 1
    swap, pressure, cpu = Rule(SWAP_IN_SAMPLES), Rule(PRESSURE_SAMPLES), Rule(CPU_SAMPLES)
    ticks, at, counted = busy_ticks(), time.monotonic(), counters()
    checked, trimmed, first = at, at, True
    while True:
        time.sleep(SAMPLE_SECONDS)
        now_ticks, now_at, now_counted = busy_ticks(), time.monotonic(), counters()
        span = now_at - at
        level, used = pressure_and_swap()
        reading = Reading(100 * busy_seconds(ticks, now_ticks) / (span * cpus()), level,
                          (now_counted[0] - counted[0]) / span, (now_counted[1] - counted[1]) / span, used)
        ticks, at, counted = now_ticks, now_at, now_counted
        write_reading(readings, time.time(), reading)
        if at - trimmed >= READINGS_SECONDS / 24:
            trim_readings(readings, time.time())
            trimmed = at
        if at - checked >= CHECK_SECONDS:
            checked = at
            if (stop := check(session)) is not None:
                print(stop, file=sys.stderr)
                return 1
        held = held_rules(swap, pressure, cpu, reading, at, first)
        first = False
        if held:
            path = folder / f"{utc_stamp(time.time())}{SUFFIX}"
            path.write_text(report("; ".join(held), processes(), footprints()) + "\n")
            print(path)
            return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
