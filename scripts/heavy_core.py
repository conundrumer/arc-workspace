"""The state of the resource daemon (`scripts/resource_daemon.py`): the
jobs that run, and what each reading of the machine changes in them. It reads
and writes nothing: each call returns the effects, a log line, a signal to
send, that the daemon applies.

A call of `run_heavy.py` starts its command at once, and the daemon records it
as a gated job with the CPUs it declares. Memory gates no start: idle memory moves to swap at little cost,
and a job is kept from the thrash that active memory brings by the caps of
`scripts/heavy_enforcer.py`.

A job ends where its pid does, and the
processes it left behind are killed, if it belongs to a session. An ungated process,
which `scripts/heavy_enforcer.py` finds, is counted with the CPUs it measures.

A gated job that runs at more than twice its
CPUs for a minute gets one log line and one
message to its session. An ungated process that is a call of `run_heavy.py`,
of a gate older than the daemon, is counted and is sent no message that says it runs
outside the gate. A job whose footprint passes `SOFT_GIB` gets one log line and one message to its
session, and one that passes `HARD_GIB` is killed with its processes, and its session is told. Where the
memory pressure is critical, the largest job of a session is killed, as `scripts/heavy_enforcer.py` gives it.
Each reading is logged, each minute and at each reading whose swap-ins are over the load monitor's alert
rate, with the seconds the daemon took to read the machine.

Standard library only, Python 3.9."""

from __future__ import annotations

import math
import signal
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Optional, Tuple, Union

import heavy_notices
from heavy_notices import Reason
from heavy_enforcer import (ADOPT_CPU_SECONDS, ADOPT_CPUS, ADOPT_GIB, ADOPT_GIB_SECONDS, CPU_OVERRUN_FACTOR,
                            CPU_OVERRUN_SECONDS, CRITICAL_PAUSE_SECONDS, HARD_GIB, KILL_GRACE, SOFT_GIB,
                            command_roots, victims)
from heavy_model import Job, Kind, Need
from machine_readings import CRITICAL_PRESSURE, GIB, KIB, SWAP_IN_RATE
from process_readings import NO_SESSION

OUTSIDE_THE_GATE = frozenset({Reason.ADOPTED})
COMMAND_CHARS = 300


@dataclass(frozen=True)
class Proc:
    """A process of the machine. A footprint and CPU seconds are None where they were not read."""
    pid: int
    ppid: int
    start: float
    command: str
    session: str
    footprint_kib: Optional[int] = None
    cpu_seconds: Optional[float] = None


@dataclass(frozen=True)
class Sample:
    """One reading of the machine at wall-clock time `at`. `claude` maps the pid of each
    session's `claude` process to the session id. `alive` holds the pid of each gated job that
    runs with the start its job gives. `read_seconds` is the time the reading took."""
    at: float
    procs: Dict[int, Proc]
    claude: Dict[int, str]
    alive: FrozenSet[int]
    level: int
    swap_in: Optional[float]
    read_seconds: float


@dataclass(frozen=True)
class Log:
    event: str
    fields: Dict[str, Any]


@dataclass(frozen=True)
class Signal:
    """A signal to send process `pid`, where it still has the start `start`."""
    pid: int
    start: float
    number: int


@dataclass(frozen=True)
class SetClass:
    """The pid of an ungated process that is to run in the CPU class of the gated jobs."""
    pid: int




Effect = Union[Log, Signal, SetClass]


@dataclass
class Watch:
    """The times at which a command's CPU and memory last rose over the adoption thresholds
    and have stood since."""
    start: float
    cpu_since: Optional[float] = None
    memory_since: Optional[float] = None


def children_of(procs: Dict[int, Proc]) -> Dict[int, List[int]]:
    out: Dict[int, List[int]] = {}
    for p in procs.values():
        out.setdefault(p.ppid, []).append(p.pid)
    return out


def tree(root: int, children: Dict[int, List[int]], taken: FrozenSet[int] = frozenset()) -> List[int]:
    """`root` and its descendants, with each process of `taken`, and its descendants, left out."""
    found: List[int] = []
    stack = [root]
    while stack:
        pid = stack.pop()
        if pid in taken or pid in found:
            continue
        found.append(pid)
        stack += children.get(pid, [])
    return found


def ceil_gib(kib: int) -> int:
    return math.ceil(kib * KIB / GIB)


def gib_up(kib: int) -> int:
    return max(1, math.ceil(kib * KIB / GIB))


class Core:
    def __init__(self, cpus: int, isolated: bool) -> None:
        """`isolated` is set for a daemon that shares the machine with another (`heavy_protocol.private`):
        it adopts no process, so it acts on its own gated jobs alone."""
        self.cpus = cpus
        self.isolated = isolated
        self.outside_kib = 0
        self.jobs: Dict[int, Job] = {}
        self.fault: Optional[str] = None
        self.notices = heavy_notices.Notices()
        self.claude: Dict[str, int] = {}
        self.pending: Dict[Tuple[int, float], float] = {}
        self.leftovers: Dict[Tuple[int, float], str] = {}
        self.watch: Dict[int, Watch] = {}
        self.cpu_over: Dict[int, float] = {}
        self.cpu_seen: Dict[int, float] = {}
        self.last_at: Optional[float] = None
        self.critical_kill_after: Optional[float] = None
        self.reading_logged: Optional[float] = None
        self.level = 1
        self.hot = False

    def gated(self, pid: int) -> Optional[Job]:
        """The gated job of client `pid`, or None."""
        job = self.jobs.get(pid)
        return job if job is not None and job.kind is Kind.GATED else None

    def grant(self, pid: int, start: float, owner: str, need: Need, cpus: int, command: str,
              now: float) -> List[Effect]:
        """Record the call of client `pid` as a gated job that declares `cpus`."""
        self.jobs[pid] = Job(pid, start, owner, Kind.GATED, need, cpus, command, now, members={pid: start})
        return [Log("grant", {"pid": pid, "owner": owner, "need": need.value, "cpus": cpus,
                              "command": command[:COMMAND_CHARS]})]

    def set_need(self, job: Job, need: Need, processes: int) -> List[Effect]:
        """Give `job` the need `need`, which `processes` of its processes run at."""
        job.need = need
        return [Log("need", {"pid": job.pid, "owner": job.owner, "need": need.value, "processes": processes})]

    def finish(self, job: Job, now: float) -> List[Effect]:
        """End `job`, and queue the processes it left behind for a kill."""
        del self.jobs[job.pid]
        self.notices.forget(job.pid, job.start)
        self.cpu_over.pop(job.pid, None)
        for pid, start in job.members.items():
            if pid != job.pid:
                self.leftovers[(pid, start)] = job.owner
        return [Log("end", {"pid": job.pid, "owner": job.owner, "kind": job.kind.value,
                            "peak_gib": round(job.peak_kib * KIB / GIB, 2), "ran": round(now - job.granted)})]

    def reap(self, ended: List[int], now: float) -> List[Effect]:
        """End the jobs with pids `ended`, between two readings."""
        out: List[Effect] = []
        for pid in ended:
            if pid in self.jobs:
                out += self.finish(self.jobs[pid], now)
        return out

    def tick(self, sample: Sample, now: float) -> List[Effect]:
        """Take a reading of the machine in: the pressure level, the end of jobs, the measure of each job,
        the adoption of ungated commands, the overruns, the jobs past the soft cap, and the kills."""
        out: List[Effect] = []
        self.claude = {session: pid for pid, session in sample.claude.items()}
        elapsed = None if self.last_at is None else max(now - self.last_at, 1e-3)
        out += self.pressure(sample, now)
        out += self.ended(sample, now)
        claimed = self.measure(sample, now, elapsed)
        out += self.adopt(sample, now, elapsed, claimed)
        held = {pid for job in self.jobs.values() for pid in job.members}
        self.outside_kib = sum(p.footprint_kib or 0 for pid, p in sample.procs.items() if pid not in held)
        out += self.overruns(now)
        out += self.growth()
        out += self.kills(sample, now)
        out += self.reading(sample, now)
        self.cpu_seen = {p.pid: p.cpu_seconds for p in sample.procs.values() if p.cpu_seconds is not None}
        self.last_at = now
        return out

    def pressure(self, sample: Sample, now: float) -> List[Effect]:
        self.level = sample.level
        self.hot = sample.swap_in is not None and sample.swap_in > SWAP_IN_RATE
        if sample.level != CRITICAL_PRESSURE:
            self.critical_kill_after = None
        return []

    def reading(self, sample: Sample, now: float) -> List[Effect]:
        """A log line of the reading, with the seconds it took, each minute and at each reading whose
        swap-ins are over the load monitor's alert rate, for the evidence of what slows the machine."""
        hot = sample.swap_in is not None and sample.swap_in > SWAP_IN_RATE
        if not hot and self.reading_logged is not None and now - self.reading_logged < 60:
            return []
        self.reading_logged = now
        return [Log("reading", {
            "swap_in": None if sample.swap_in is None else round(sample.swap_in), "level": sample.level,
            "read_seconds": round(sample.read_seconds, 3),
            "jobs": [[job.pid, round(job.footprint_kib * KIB / GIB, 2), job.command[:60]]
                     for job in sorted(self.jobs.values(), key=lambda j: -j.footprint_kib)]})]

    def ended(self, sample: Sample, now: float) -> List[Effect]:
        out: List[Effect] = []
        for job in list(self.jobs.values()):
            if job.kind is Kind.GATED:
                runs = job.pid in sample.alive
            else:
                found = sample.procs.get(job.pid)
                runs = found is not None and found.start == job.start
            if not runs:
                out += self.finish(job, now)
        for (pid, start), owner in sorted(self.leftovers.items()):
            del self.leftovers[(pid, start)]
            found = sample.procs.get(pid)
            if found is None or found.start != start or owner == NO_SESSION or pid in sample.claude or pid <= 1:
                continue
            out += [Log("reap", {"pid": pid, "owner": owner, "command": found.command[:COMMAND_CHARS]}),
                    Signal(pid, start, signal.SIGTERM)]
            self.pending[(pid, start)] = now
        return out

    def rate(self, pids: List[int], sample: Sample, now: float, elapsed: Optional[float]) -> float:
        """The CPUs that the processes `pids` used since the last reading."""
        if elapsed is None:
            return 0.0
        used = 0.0
        for pid in pids:
            p = sample.procs[pid]
            if p.cpu_seconds is None:
                continue
            if pid in self.cpu_seen:
                used += max(0.0, p.cpu_seconds - self.cpu_seen[pid])
            elif now - p.start <= elapsed + 1:
                used += p.cpu_seconds
        return used / elapsed

    def measure(self, sample: Sample, now: float, elapsed: Optional[float]) -> FrozenSet[int]:
        """Set the members, footprint and CPU of each job, and give the pids that jobs hold."""
        children = children_of(sample.procs)
        claimed: FrozenSet[int] = frozenset()
        for job in sorted(self.jobs.values(), key=lambda j: (j.granted, j.pid)):
            found = tree(job.pid, children, claimed)
            found = [pid for pid in found if pid in sample.procs]
            kept = [pid for pid, start in job.members.items()
                    if pid in sample.procs and sample.procs[pid].start == start and pid not in claimed
                    and pid not in found]
            members = found + kept
            job.members = {pid: sample.procs[pid].start for pid in members}
            job.footprint_kib = sum(sample.procs[pid].footprint_kib or 0 for pid in members)
            job.peak_kib = max(job.peak_kib, job.footprint_kib)
            job.cpu = self.rate(members, sample, now, elapsed)
            if job.kind is Kind.UNGATED:
                job.cpus = max(1, math.ceil(job.cpu))
            claimed = claimed | frozenset(members)
        return claimed

    def adopt(self, sample: Sample, now: float, elapsed: Optional[float], claimed: FrozenSet[int]) -> List[Effect]:
        """Adopt each command of a session that runs without a grant and over the thresholds, unless
        the core is isolated."""
        if self.isolated:
            return []
        procs = sample.procs
        roots = command_roots({pid: p.command for pid, p in procs.items()},
                              {pid: p.ppid for pid, p in procs.items()}, sorted(sample.claude))
        children = children_of(procs)
        out: List[Effect] = []
        seen = set()
        for root in roots:
            if root in claimed or procs[root].session == NO_SESSION:
                continue
            found = tree(root, children, claimed)
            seen.add(root)
            watch = self.watch.get(root)
            if watch is None or watch.start != procs[root].start:
                watch = self.watch[root] = Watch(procs[root].start)
            footprint = sum(procs[pid].footprint_kib or 0 for pid in found)
            cpu = self.rate(found, sample, now, elapsed)
            watch.cpu_since = (watch.cpu_since if watch.cpu_since is not None else now) if cpu >= ADOPT_CPUS else None
            watch.memory_since = ((watch.memory_since if watch.memory_since is not None else now)
                                  if footprint * KIB >= ADOPT_GIB * GIB else None)
            if not ((watch.cpu_since is not None and now - watch.cpu_since >= ADOPT_CPU_SECONDS)
                    or (watch.memory_since is not None and now - watch.memory_since >= ADOPT_GIB_SECONDS)):
                continue
            p = procs[root]
            job = Job(root, p.start, p.session, Kind.UNGATED, None, max(1, math.ceil(cpu)), p.command, now,
                      footprint_kib=footprint, peak_kib=footprint, cpu=cpu,
                      members={pid: procs[pid].start for pid in found})
            self.jobs[root] = job
            claimed = claimed | frozenset(found)
            del self.watch[root]
            reason = "cpu" if watch.cpu_since is not None and now - watch.cpu_since >= ADOPT_CPU_SECONDS else "memory"
            out += [Log("adopt", {"pid": root, "owner": p.session, "reason": reason, "cpus": job.cpus,
                                  "gib": gib_up(footprint), "command": p.command[:COMMAND_CHARS]}),
                    SetClass(root)]
            self.tell(job, Reason.ADOPTED, heavy_notices.adopted(root, p.command, job.cpus, gib_up(footprint)))
        self.watch = {pid: w for pid, w in self.watch.items() if pid in seen}
        return out

    def tell(self, job: Job, reason: Reason, text: str) -> bool:
        """Queue `text` for the session of `job` unless one went out for this job and reason,
        or the text says the job runs outside the gate and the job is a call of `run_heavy.py`,
        and say whether this is the first for them. Such a call runs under a gate older than
        the daemon, so that text is false of it."""
        first = self.notices.once(job.pid, job.start, reason)
        false_of_gate_call = reason in OUTSIDE_THE_GATE and heavy_notices.is_gate_call(job.command)
        if first and job.owner != NO_SESSION and not false_of_gate_call:
            self.notices.add(job.owner, text)
        return first

    def overruns(self, now: float) -> List[Effect]:
        """Log each CPU overrun of a gated job once, and queue one message for it."""
        out: List[Effect] = []
        for job in self.jobs.values():
            if job.kind is not Kind.GATED:
                continue
            if job.cpu > CPU_OVERRUN_FACTOR * job.cpus:
                since = self.cpu_over.setdefault(job.pid, now)
                if now - since >= CPU_OVERRUN_SECONDS and self.tell(
                        job, Reason.CPU, heavy_notices.cpu_overrun(job.pid, job.command, job.cpu, job.cpus)):
                    out.append(Log("overrun", {"pid": job.pid, "owner": job.owner,
                                               "command": job.command[:COMMAND_CHARS], "reason": "cpu",
                                               "cpus": round(job.cpu, 1), "declared": job.cpus}))
            else:
                self.cpu_over.pop(job.pid, None)
        return out

    def kills(self, sample: Sample, now: float) -> List[Effect]:
        """Kill each job whose footprint passes `HARD_GIB`, and, where the pressure is critical and no
        kill waits (`critical_kill_after`), the first of `victims`, each unless its processes are already sent
        `SIGTERM`; and send `SIGKILL` to each process that outlives `KILL_GRACE` seconds after it."""
        out: List[Effect] = []
        for job in self.jobs.values():
            if job.footprint_kib * KIB > HARD_GIB * GIB and not self.terming(job):
                out += self.kill(job, sample, now, f"the job held more than the {HARD_GIB} GiB that no job may hold")
        if sample.level == CRITICAL_PRESSURE and (self.critical_kill_after is None
                                                  or now >= self.critical_kill_after):
            for job in victims(list(self.jobs.values())):
                if not self.terming(job):
                    out += self.kill(job, sample, now, "the memory pressure was critical, and it was the largest job")
                    break
        for key, since in list(self.pending.items()):
            found = sample.procs.get(key[0])
            if found is None or found.start != key[1]:
                del self.pending[key]
            elif now - since >= KILL_GRACE:
                out.append(Signal(key[0], key[1], signal.SIGKILL))
                del self.pending[key]
        return out

    def terming(self, job: Job) -> bool:
        """Whether a process of `job` has been sent `SIGTERM` and waits for `SIGKILL`."""
        return any((pid, start) in self.pending for pid, start in job.members.items())

    def growth(self) -> List[Effect]:
        """Log each job whose footprint passes `SOFT_GIB` once, and queue one message for it."""
        out: List[Effect] = []
        for job in self.jobs.values():
            if job.footprint_kib * KIB > SOFT_GIB * GIB and self.tell(
                    job, Reason.GROWTH, heavy_notices.passed_soft(job.pid, job.command, SOFT_GIB)):
                out.append(Log("soft", {"pid": job.pid, "owner": job.owner, "kind": job.kind.value,
                                        "gib": gib_up(job.footprint_kib), "command": job.command[:COMMAND_CHARS]}))
        return out

    def kill(self, job: Job, sample: Sample, now: float, reason: str) -> List[Effect]:
        """Kill the processes of `job` for `reason`, tell its session, and hold the next kill at critical
        pressure back until a reading below critical or `CRITICAL_PAUSE_SECONDS` seconds from now."""
        out: List[Effect] = [Log("kill", {"pid": job.pid, "owner": job.owner, "kind": job.kind.value,
                                          "need": job.need.value if job.need else None,
                                          "gib": gib_up(job.footprint_kib), "reason": reason,
                                          "command": job.command[:COMMAND_CHARS]})]
        for pid, start in sorted(job.members.items()):
            if pid in sample.claude or pid <= 1:
                continue
            out.append(Signal(pid, start, signal.SIGTERM))
            self.pending[(pid, start)] = now
        self.critical_kill_after = now + CRITICAL_PAUSE_SECONDS
        self.tell(job, Reason.KILLED, heavy_notices.killed(job.pid, job.command, gib_up(job.footprint_kib), reason))
        return out

    def messages(self, now: float) -> List[Tuple[int, str]]:
        """Each message that is due, with the pid of the `claude` process of the session it goes
        to; a message for a session whose process is not known is dropped."""
        out = []
        for session, text in self.notices.due(now):
            if session in self.claude:
                out.append((self.claude[session], text))
        return out

    def snapshot(self, now: float) -> Dict[str, Any]:
        """The registry: the jobs, and the machine's CPUs and the GiB held outside the jobs."""
        return {"at": now, "fault": self.fault,
                "machine": {"cpus": self.cpus, "outside_gib": ceil_gib(self.outside_kib)},
                "jobs": [job_record(job) for job in sorted(self.jobs.values(), key=lambda j: (j.granted, j.pid))],
                "notified": sorted([pid, start, reason.value] for pid, start, reason in self.notices.seen)}

    def restore(self, record: Dict[str, Any]) -> None:
        """Take the jobs and sent notices of a registry `snapshot` back, each job to be
        dropped at the first reading where its process does not run."""
        for item in record.get("jobs", []):
            job = job_from_record(item)
            self.jobs[job.pid] = job
        reasons = {reason.value: reason for reason in Reason}
        self.notices.seen = {(pid, start, reasons[reason]) for pid, start, reason in record.get("notified", [])
                             if reason in reasons}


def job_record(job: Job) -> Dict[str, Any]:
    return {"pid": job.pid, "start": job.start, "owner": job.owner, "kind": job.kind.value,
            "need": job.need.value if job.need else None, "cpus": job.cpus,
            "command": job.command[:COMMAND_CHARS], "granted": job.granted,
            "footprint_kib": job.footprint_kib, "peak_kib": job.peak_kib, "cpu": round(job.cpu, 2),
            "members": {str(pid): start for pid, start in sorted(job.members.items())}}


def job_from_record(item: Dict[str, Any]) -> Job:
    return Job(item["pid"], item["start"], item["owner"], Kind(item["kind"]),
               Need(item["need"]) if item["need"] else None, item["cpus"], item["command"], item["granted"],
               item["footprint_kib"], item["peak_kib"], item["cpu"],
               {int(pid): start for pid, start in item["members"].items()})
