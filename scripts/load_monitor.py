"""Watch the machine's CPU and memory pressure, and write an alert with the
processes of the largest physical footprint and the most CPU each time a
load alert rule holds. `HELP`, which `--help` prints, gives the readings,
the rules and the alert."""

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from controlled_markdown import mctx
from engine.cpu import busy_seconds, busy_ticks
from heavy_enforcer import ADOPT_CPUS, ADOPT_GIB
from heavy_protocol import heavy_dir, read_registry
from idle_sessions import running
from process_readings import harness_sessions, owners, rows, usage
from ticket_numbers import session_id
from tree_reads import main_tree
from machine_readings import GIB, KIB, PRESSURE_LEVELS, SWAP_IN_RATE, counters, output, pressure_level
from ticketing.times import stamp_time, utc_stamp

SAMPLE_SECONDS = 5
SWAP_IN_SAMPLES = 2
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
    - A rule counts only once {realert} s have passed since the last alert of the monitor's folder that gave it, so that a load that stays gives a load re-alert once in {realert} s, the command having exited at each alert.
    - On a rule that holds the command writes an alert to a new file `{alerts}/<session id>/<time>{suffix}` of the main tree, the session id being the monitor's own and the time the UTC time of the alert, prints the file's path, and exits 0. The alert gives the rules that held, then the {top} processes of the largest physical footprint, the memory the process takes from the machine, and the {top} of the most CPU, each with its pid, parent pid, footprint, CPU percent, elapsed time, session id and command line.
    - It appends each sample's readings to `{alerts}/<session id>/{readings}` of the main tree, one line a sample of tab-separated fields: the UTC time, the CPU busy percent, the memory pressure level, the swap-in rate, the page-in rate and the swap in use in MB. It keeps the last {keep} hours of them.
    - One monitor watches the machine. Where another `load_monitor.py` process runs for a session that runs, the command exits with a message that gives that process's pid and session id. It exits as well at the first check, made every {check} s, at which its own session is not among the sessions that run.
    - Where the resource daemon runs (`scripts/resource_daemon.py`), the processes of its registry, each job it counts with its descendants and each ungated process it has adopted, are left out of both lists, and the command writes an alert only where a process that stays holds {adopt_gib} GiB or runs over {adopt_cpu}% CPU: the daemon answers the load its registry explains, by its kills and its messages to the owning sessions.
    - It kills no process and notifies no one past its exit.
    """).format(sample=SAMPLE_SECONDS, swap_in=SWAP_IN_RATE, swap_in_samples=SWAP_IN_SAMPLES,
                pressure_samples=PRESSURE_SAMPLES, busy=BUSY_CPU, cpu=CPU_SAMPLES,
                realert=REALERT_SECONDS, alerts=ALERTS, suffix=SUFFIX, top=TOP, readings=READINGS,
                keep=READINGS_SECONDS // 3600, check=CHECK_SECONDS, adopt_gib=ADOPT_GIB,
                adopt_cpu=round(ADOPT_CPUS * 100))

SWAP_USED = re.compile(r"used = ([\d.]+)M")


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


def processes() -> list[Process]:
    """Each process of the machine, with the session id of its owning session, as
    `process_readings.owners` gives it."""
    table = rows()
    owner = owners(table, harness_sessions() or {})
    return [Process(row.pid, row.ppid, row.cpu, row.elapsed, owner[row.pid], row.command) for row in table]


def footprints(pids: list[int]) -> dict[int, int]:
    """The physical footprint in KiB of each of `pids` that `process_readings.usage` reads."""
    return {pid: read[0] for pid in pids if (read := usage(pid)) is not None}


def pressure_and_swap() -> tuple[int, float]:
    """The kernel's memory pressure level, and the swap in use in MB."""
    usage = output("sysctl", "-n", "vm.swapusage")
    m = SWAP_USED.search(usage)
    if m is None:
        raise ValueError(f"no swap in use in {usage!r}")
    return pressure_level(), float(m.group(1))


def cpus() -> int:
    n = os.cpu_count()
    if n is None:
        raise NotImplementedError(f"no CPU count on {sys.platform}")
    return n


SWAP_TEXT = mctx("swap-ins {rate:.0f} pages a second, over {limit} for {n} samples in a row")
PRESSURE_TEXT = mctx("memory pressure level {level}, at warn or critical for {n} samples in a row")
CPU_TEXT = mctx("CPU {busy:.0f}% busy, over {limit}% for {n} samples in a row")
TROUBLE = "trouble: "
TROUBLE_SEPARATOR = "; "


def text_pattern(text: str) -> re.Pattern[str]:
    """The pattern that matches `text`, a rule's text, filled in with any
    values."""
    return re.compile("[^;]+".join(re.escape(part) for part in re.split(r"\{[^}]*\}", text)))


def latest_alerts(folder: Path, texts: list[str]) -> list[float | None]:
    """For each of `texts`, the rule texts, the wall-clock time of the
    latest alert file in `folder` whose `trouble:` line gives that rule, or
    None. A file with no `trouble:` line, or a name that is no UTC time, is
    left out."""
    patterns = [text_pattern(text) for text in texts]
    latest: list[float | None] = [None] * len(texts)
    for path in folder.glob(f"*{SUFFIX}"):
        lines = path.read_text().splitlines()
        if not lines or not lines[0].startswith(TROUBLE):
            continue
        try:
            at = stamp_time(path.stem)
        except ValueError:
            continue
        for given in (lines[0][len(TROUBLE):].split(TROUBLE_SEPARATOR)):
            for j, pattern in enumerate(patterns):
                seen = latest[j]
                if pattern.fullmatch(given) and (seen is None or at > seen):
                    latest[j] = at
    return latest


class Rule:
    """One load alert rule, as `HELP` gives it."""

    def __init__(self, samples: int, text: str, last_alert: float | None, now: float) -> None:
        """`last_alert` is the wall-clock time of the latest alert that gave
        the rule, and `now` the wall-clock time at the monitor's start."""
        self.samples = samples
        self.text = text
        self.run = 0
        self.not_before: float | None = None
        if last_alert is not None and now < last_alert + REALERT_SECONDS:
            self.not_before = last_alert + REALERT_SECONDS

    def held(self, now: bool, at: float) -> bool:
        """Whether the rule holds at the sample made at wall-clock time
        `at`, `now` being whether its condition stands at the sample."""
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


def held_rules(swap: Rule, pressure: Rule, cpu: Rule, reading: Reading, at: float) -> list[str]:
    """The load alert rules that hold at `reading`."""
    held = []
    if swap.held(reading.swap_in > SWAP_IN_RATE, at):
        held.append(swap.text.format(rate=reading.swap_in, limit=SWAP_IN_RATE, n=SWAP_IN_SAMPLES))
    if pressure.held(reading.pressure in PRESSURE_LEVELS, at):
        held.append(pressure.text.format(level=reading.pressure, n=PRESSURE_SAMPLES))
    if cpu.held(reading.busy > BUSY_CPU, at):
        held.append(cpu.text.format(busy=reading.busy, limit=BUSY_CPU, n=CPU_SAMPLES))
    return held


def report(trouble: str, found: list[Process], footprint: dict[int, int]) -> str:
    known = [p for p in found if p.pid in footprint]
    by_memory = sorted(known, key=lambda p: (-footprint[p.pid], p.pid))[:TOP]
    by_cpu = sorted(known, key=lambda p: (-p.cpu, p.pid))[:TOP]
    return "\n".join([TROUBLE + trouble,
                      mctx("largest by physical footprint:"),
                      *(p.line(footprint[p.pid]) for p in by_memory),
                      mctx("largest by CPU:"), *(p.line(footprint[p.pid]) for p in by_cpu)])


def registered(registry: dict[str, Any] | None) -> set[int]:
    """The pids of each job in the daemon's `registry`, a gated job or an adopted process, and of
    its members; none where `registry` is None."""
    if registry is None:
        return set()
    return {int(pid) for job in registry["jobs"] for pid in [job["pid"], *job["members"]]}


def heavy(found: list[Process], footprint: dict[int, int]) -> bool:
    """Whether a process of `found` holds `ADOPT_GIB` GiB or runs at `ADOPT_CPUS` CPUs."""
    return any(footprint[p.pid] * KIB >= ADOPT_GIB * GIB or p.cpu >= ADOPT_CPUS * 100
               for p in found if p.pid in footprint)


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
    started = time.time()
    last = latest_alerts(folder, [SWAP_TEXT, PRESSURE_TEXT, CPU_TEXT])
    swap, pressure, cpu = (Rule(SWAP_IN_SAMPLES, SWAP_TEXT, last[0], started),
                           Rule(PRESSURE_SAMPLES, PRESSURE_TEXT, last[1], started),
                           Rule(CPU_SAMPLES, CPU_TEXT, last[2], started))
    ticks, at, counted = busy_ticks(), time.monotonic(), counters()
    checked, trimmed = at, at
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
        held = held_rules(swap, pressure, cpu, reading, time.time())
        if held:
            found = processes()
            registry = read_registry(heavy_dir())
            left = [p for p in found if p.pid not in registered(registry)]
            footprint = footprints([p.pid for p in left])
            if registry is not None and not heavy(left, footprint):
                continue
            path = folder / f"{utc_stamp(time.time())}{SUFFIX}"
            path.write_text(report(TROUBLE_SEPARATOR.join(held), left, footprint) + "\n")
            print(path)
            return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
