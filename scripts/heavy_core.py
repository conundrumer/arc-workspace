"""The state of the resource daemon (`scripts/resource_daemon.py`): the
waiting requests, the jobs that hold a share, and what each reading of the
machine changes in them. It reads and writes nothing: each call returns the
effects, a log line, a signal to send, a grant, that the daemon applies.

The budget that admission and the expected starts use is `available`: the machine's
CPUs, and `UNBOUNDED_GIB`, so that no request waits for GiB. Memory gates no start: idle
memory moves to swap at little cost, and the thrash that active memory brings is met by the
kill below.

A request waits, as `scripts/heavy_scheduler.py` orders it, and starts where the daemon
reads the machine. A job ends where its pid does, and the
processes it left behind are killed, if it belongs to a session. A gated job holds its
declared CPUs, and, for its first `DECLARED_SECONDS`, its declared GiB, or the GiB it
measures where that is more. After that it holds its measured peak, rounded up to a GiB, and
`HEADROOM_GIB` more, so a job that declares more than it uses frees the rest for the waiting
requests. An
ungated process, which `scripts/heavy_enforcer.py` finds, holds what it measures.

A short gated job that runs past its declared minutes holds from then on as a long job of
its need, with its CPUs and GiB unchanged; no process is signalled for it.

A gated job that runs at more than twice its
CPUs for a minute, or runs past twice its minutes gets one log line and one
message to its session. Memory pressure at warn gets each session that has
an ungated process one message. An ungated process that is a call of `run_heavy.py`,
of a gate older than the daemon, is counted and is sent no message that says it runs
outside the gate. Where the swap-ins stay high, a kill follows, as `scripts/heavy_enforcer.py` gives it.

Standard library only, Python 3.9."""

from __future__ import annotations

import math
import signal
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Optional, Tuple, Union

import heavy_notices
from heavy_notices import Reason
from heavy_enforcer import (ADOPT_CPU_SECONDS, ADOPT_CPUS, ADOPT_GIB, ADOPT_GIB_SECONDS, CPU_OVERRUN_FACTOR,
                            CPU_OVERRUN_SECONDS, KILL_GRACE, KILL_SETTLE, THRASH_RATE, THRASH_SECONDS,
                            TIME_OVERRUN_FACTOR, command_roots, victims)
from heavy_model import Amount, Job, Kind, Lane, Need, Waiter
from heavy_scheduler import Holding, estimates, next_waiters, queues, reserve, resolve
from machine_readings import GIB, KIB, PRESSURE_LEVELS, SWAP_IN_RATE
from process_readings import NO_SESSION

OUTSIDE_THE_GATE = frozenset({Reason.ADOPTED, Reason.WARN})
COMMAND_CHARS = 300
DECLARED_SECONDS = 60
"""A gated job holds its declared GiB for this long after its grant."""
HEADROOM_GIB = 1
"""What a gated job holds beyond its measured peak, once its declared GiB no longer counts."""
UNBOUNDED_GIB = 1 << 20
"""The GiB of the budget: more than any request asks."""


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
    runs with the start its job gives."""
    at: float
    procs: Dict[int, Proc]
    claude: Dict[int, str]
    alive: FrozenSet[int]
    level: int
    swap_in: Optional[float]


@dataclass(frozen=True)
class Log:
    event: str
    fields: Dict[str, Any]


@dataclass(frozen=True)
class Accepted:
    """A request that waits or starts, cut to `waiter.ask` where `cut` is set, out of the most `cap` a job
    of its lane and need may ask."""
    waiter: Waiter
    cut: bool
    cap: Amount


@dataclass(frozen=True)
class Grant:
    waiter: Waiter
    job: Job


@dataclass(frozen=True)
class Refuse:
    waiter: Waiter
    reason: str


@dataclass(frozen=True)
class GiveUp:
    """A waiter whose `--wait` has run out, with its expected start."""
    waiter: Waiter
    eta: Optional[float]


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




Effect = Union[Log, Accepted, Grant, Refuse, GiveUp, Signal, SetClass]


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


def refusal_fields(waiter: Waiter, reason: str) -> Dict[str, Any]:
    """The reason, owner and figures of a refused request."""
    return {"reason": reason, "owner": waiter.owner, "op": "acquire", "pid": waiter.pid,
            "cpus": waiter.ask.cpus, "gib": waiter.ask.gib, "need": waiter.need.value, "minutes": waiter.minutes}


def ceil_gib(kib: int) -> int:
    return math.ceil(kib * KIB / GIB)


def gib_up(kib: int) -> int:
    return max(1, math.ceil(kib * KIB / GIB))


class Core:
    def __init__(self, total: Amount) -> None:
        self.total = total
        self.outside_kib = 0
        self.jobs: Dict[int, Job] = {}
        self.waiters: Dict[int, Waiter] = {}
        self.hold: Optional[str] = None
        self.fault: Optional[str] = None
        self.notices = heavy_notices.Notices()
        self.claude: Dict[str, int] = {}
        self.pending: Dict[Tuple[int, float], float] = {}
        self.leftovers: Dict[Tuple[int, float], str] = {}
        self.watch: Dict[int, Watch] = {}
        self.cpu_over: Dict[int, float] = {}
        self.cpu_seen: Dict[int, float] = {}
        self.last_at: Optional[float] = None
        self.last_kill: Optional[float] = None
        self.thrash_since: Optional[float] = None
        self.reading_logged: Optional[float] = None
        self.level = 1

    def available(self) -> Amount:
        """The budget that admission and expected starts use: the CPUs of `total`, and
        `UNBOUNDED_GIB`."""
        return Amount(self.total.cpus, UNBOUNDED_GIB)

    def set_need(self, pid: int, need: Need, now: float) -> Optional[Waiter]:
        """Give the waiting request of client `pid` the need `need`, with its ask cut again to
        what the need allows; None where none of that pid waits."""
        for w in self.waiters.values():
            if w.pid == pid:
                w.need = need
                w.ask, _, _ = resolve(w.asked_cpus, w.asked_gib, w.lane, need, self.available())
                return w
        return None

    def holdings(self, now: float) -> List[Holding]:
        """What each job takes from the budget at `now`. A short gated job that runs past its
        declared minutes takes as a long job of its need. A gated job takes its declared GiB
        for `DECLARED_SECONDS` after its grant, or the GiB it measures where that is more, and
        then its measured peak and `HEADROOM_GIB`; a job with no measure takes its declared
        GiB."""
        out = []
        for job in self.jobs.values():
            if job.kind is Kind.GATED:
                held = gib_up(job.footprint_kib) if job.footprint_kib else 0
                overrun = job.lane is Lane.SHORT and job.ends is not None and now > job.ends
                lane = Lane.LONG if overrun else job.lane
                if now - job.granted < DECLARED_SECONDS or not job.peak_kib:
                    gib = max(job.amount.gib, held)
                else:
                    gib = gib_up(job.peak_kib) + HEADROOM_GIB
                out.append(Holding(lane, job.need, Amount(job.amount.cpus, gib), job.ends))
            else:
                out.append(Holding(job.lane, None, job.amount, None))
        return out

    def submit(self, waiter: Waiter, cut: bool, cap: Amount) -> List[Effect]:
        """Queue `waiter`, whose ask is cut where `cut` is set, to `cap`, or refuse it."""
        if self.fault is not None:
            return [Log("refusal", refusal_fields(waiter, self.fault)), Refuse(waiter, self.fault)]
        self.waiters[waiter.id] = waiter
        return [Accepted(waiter, cut, cap)]

    def withdraw(self, waiter_id: int) -> None:
        self.waiters.pop(waiter_id, None)

    def admit(self, now: float) -> List[Effect]:
        """Start each waiter that is first of its queue and fits, where no hold stands."""
        if self.hold is not None or self.fault is not None:
            return []
        out: List[Effect] = []
        for w in next_waiters(self.waiters.values(), self.holdings(now), self.available(), now):
            del self.waiters[w.id]
            job = Job(w.pid, w.start, w.owner, Kind.GATED, w.need, w.ask, w.minutes, w.command, now,
                      members={w.pid: float(w.start)})
            self.jobs[w.pid] = job
            out += [Log("grant", {"pid": w.pid, "owner": w.owner, "need": w.need.value, "cpus": w.ask.cpus,
                                  "gib": w.ask.gib, "minutes": w.minutes, "waited": round(now - w.arrived),
                                  "command": w.command[:COMMAND_CHARS]}),
                    Grant(w, job)]
        return out

    def expire(self, now: float) -> List[Effect]:
        """Give up each waiter whose `--wait` has run out."""
        out: List[Effect] = []
        gone = [w for w in self.waiters.values() if w.deadline is not None and w.deadline <= now]
        if gone:
            etas = estimates(list(self.waiters.values()), self.holdings(now), self.available(), now)
            for w in gone:
                del self.waiters[w.id]
                out += [Log("timeout", {"pid": w.pid, "owner": w.owner, "need": w.need.value}),
                        GiveUp(w, etas.get(w.id))]
        return out

    def refuse_all(self, reason: str) -> List[Effect]:
        out: List[Effect] = []
        for w in list(self.waiters.values()):
            del self.waiters[w.id]
            out += [Log("refusal", refusal_fields(w, reason)), Refuse(w, reason)]
        return out

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
        """Take a reading of the machine in: the hold, the end of jobs, the measure of each job,
        the adoption of ungated commands, the overruns, and the kills."""
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
        out += self.kills(sample, now)
        out += self.reading(sample, now)
        self.cpu_seen = {p.pid: p.cpu_seconds for p in sample.procs.values() if p.cpu_seconds is not None}
        self.last_at = now
        return out

    def pressure(self, sample: Sample, now: float) -> List[Effect]:
        self.level = sample.level
        if sample.swap_in is not None and sample.swap_in > THRASH_RATE:
            self.thrash_since = self.thrash_since if self.thrash_since is not None else now
        else:
            self.thrash_since = None
        return []

    def reading(self, sample: Sample, now: float) -> List[Effect]:
        """A log line of the reading, each minute and at each reading whose swap-ins are over the
        load monitor's alert rate, for the evidence of what thrashes the machine."""
        hot = sample.swap_in is not None and sample.swap_in > SWAP_IN_RATE
        if not hot and self.reading_logged is not None and now - self.reading_logged < 60:
            return []
        self.reading_logged = now
        return [Log("reading", {
            "swap_in": None if sample.swap_in is None else round(sample.swap_in), "level": sample.level,
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
                job.amount = Amount(max(1, math.ceil(job.cpu)), gib_up(job.footprint_kib))
            claimed = claimed | frozenset(members)
        return claimed

    def adopt(self, sample: Sample, now: float, elapsed: Optional[float], claimed: FrozenSet[int]) -> List[Effect]:
        """Adopt each command of a session that runs without a grant and over the thresholds."""
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
            job = Job(root, p.start, p.session, Kind.UNGATED, None,
                      Amount(max(1, math.ceil(cpu)), gib_up(footprint)), None, p.command, now,
                      footprint_kib=footprint, peak_kib=footprint, cpu=cpu,
                      members={pid: procs[pid].start for pid in found})
            self.jobs[root] = job
            claimed = claimed | frozenset(found)
            del self.watch[root]
            reason = "cpu" if watch.cpu_since is not None and now - watch.cpu_since >= ADOPT_CPU_SECONDS else "memory"
            out += [Log("adopt", {"pid": root, "owner": p.session, "reason": reason, "cpus": job.amount.cpus,
                                  "gib": job.amount.gib, "command": p.command[:COMMAND_CHARS]}),
                    SetClass(root)]
            self.tell(job, Reason.ADOPTED, heavy_notices.adopted(root, p.command, job.amount.cpus, job.amount.gib))
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
        """Log each overrun of a gated job once, and queue one message for it."""
        out: List[Effect] = []
        for job in self.jobs.values():
            if job.kind is not Kind.GATED or job.minutes is None:
                continue
            figures = {"pid": job.pid, "owner": job.owner, "command": job.command[:COMMAND_CHARS]}
            if job.cpu > CPU_OVERRUN_FACTOR * job.amount.cpus:
                since = self.cpu_over.setdefault(job.pid, now)
                if now - since >= CPU_OVERRUN_SECONDS and self.tell(
                        job, Reason.CPU, heavy_notices.cpu_overrun(job.pid, job.command, job.cpu, job.amount.cpus)):
                    out.append(Log("overrun", {**figures, "reason": "cpu", "cpus": round(job.cpu, 1),
                                               "declared": job.amount.cpus}))
            else:
                self.cpu_over.pop(job.pid, None)
            minutes = (now - job.granted) / 60
            if minutes > TIME_OVERRUN_FACTOR * job.minutes and self.tell(
                    job, Reason.TIME, heavy_notices.time_overrun(job.pid, job.command, minutes, job.minutes)):
                out.append(Log("overrun", {**figures, "reason": "time", "minutes": round(minutes),
                                           "declared": job.minutes}))
        return out

    def kills(self, sample: Sample, now: float) -> List[Effect]:
        out: List[Effect] = []
        for key, since in list(self.pending.items()):
            found = sample.procs.get(key[0])
            if found is None or found.start != key[1]:
                del self.pending[key]
            elif now - since >= KILL_GRACE:
                out.append(Signal(key[0], key[1], signal.SIGKILL))
                del self.pending[key]
        if self.level in PRESSURE_LEVELS:
            for job in self.jobs.values():
                if job.kind is Kind.UNGATED:
                    self.tell(job, Reason.WARN, heavy_notices.warned(job.pid, job.command, gib_up(job.footprint_kib)))
        severe = self.thrash_since is not None and now - self.thrash_since >= THRASH_SECONDS
        if not severe or (self.last_kill is not None and now - self.last_kill < KILL_SETTLE):
            return out
        for job in victims(list(self.jobs.values())):
            if any((pid, start) in self.pending for pid, start in job.members.items()):
                continue
            out += self.kill(job, sample, now)
            break
        return out

    def kill(self, job: Job, sample: Sample, now: float) -> List[Effect]:
        reason = f"swap-ins over {THRASH_RATE} pages a second for {THRASH_SECONDS} s"
        out: List[Effect] = [Log("kill", {"pid": job.pid, "owner": job.owner, "kind": job.kind.value,
                                          "need": job.need.value if job.need else None,
                                          "gib": gib_up(job.footprint_kib), "reason": reason,
                                          "command": job.command[:COMMAND_CHARS]})]
        for pid, start in sorted(job.members.items()):
            if pid in sample.claude or pid <= 1:
                continue
            out.append(Signal(pid, start, signal.SIGTERM))
            self.pending[(pid, start)] = now
        self.last_kill = now
        self.tell(job, Reason.KILLED, heavy_notices.killed(job.pid, job.command, max(job.amount.cpus, math.ceil(job.cpu)),
                                                 gib_up(job.footprint_kib), reason))
        return out

    def messages(self, now: float) -> List[Tuple[int, str]]:
        """Each message that is due, with the pid of the `claude` process of the session it goes
        to; a message for a session whose process is not known is dropped."""
        out = []
        for session, text in self.notices.due(now):
            if session in self.claude:
                out.append((self.claude[session], text))
        return out

    def wait_info(self, waiter: Waiter, now: float) -> Dict[str, Any]:
        """What a waiting request is told: the reason it waits, its place in its queue, and its
        expected start."""
        lanes = queues(self.waiters.values(), now)
        lane = waiter.lane
        etas = estimates(list(self.waiters.values()), self.holdings(now), self.available(), now)
        position = [w.id for w in lanes[lane]].index(waiter.id) + 1
        return {"reason": self.hold or "the machine's budget", "position": position, "lane": lane.value,
                "eta": etas.get(waiter.id)}

    def snapshot(self, now: float) -> Dict[str, Any]:
        """The registry: the jobs, the waiting requests with their expected starts, and the
        budget."""
        etas = estimates(list(self.waiters.values()), self.holdings(now), self.available(), now)
        waiting = []
        for lane, queue in queues(self.waiters.values(), now).items():
            for position, w in enumerate(queue, 1):
                waiting.append({"id": w.id, "pid": w.pid, "owner": w.owner, "need": w.need.value,
                                "cpus": w.ask.cpus, "gib": w.ask.gib, "minutes": w.minutes, "lane": lane.value,
                                "position": position, "arrived": w.arrived, "eta": etas.get(w.id),
                                "command": w.command[:COMMAND_CHARS]})
        reserved = reserve(self.available())
        return {"at": now, "hold": self.hold or self.fault,
                "budget": {"cpus": self.total.cpus, "gib": self.available().gib, "fixed_gib": self.total.gib,
                           "outside_gib": ceil_gib(self.outside_kib),
                           "reserve_cpus": reserved.cpus, "reserve_gib": reserved.gib},
                "jobs": [job_record(job) for job in sorted(self.jobs.values(), key=lambda j: (j.granted, j.pid))],
                "waiting": waiting,
                "notified": sorted([pid, start, reason.value] for pid, start, reason in self.notices.seen)}

    def restore(self, record: Dict[str, Any]) -> None:
        """Take the jobs and sent notices of a registry `snapshot` back, each job to be
        dropped at the first reading where its process does not run."""
        for item in record.get("jobs", []):
            job = job_from_record(item)
            self.jobs[job.pid] = job
        self.notices.seen = {(pid, start, Reason(reason)) for pid, start, reason in record.get("notified", [])}


def job_record(job: Job) -> Dict[str, Any]:
    return {"pid": job.pid, "start": job.start, "owner": job.owner, "kind": job.kind.value,
            "need": job.need.value if job.need else None, "cpus": job.amount.cpus, "gib": job.amount.gib,
            "minutes": job.minutes, "command": job.command[:COMMAND_CHARS], "granted": job.granted,
            "footprint_kib": job.footprint_kib, "peak_kib": job.peak_kib, "cpu": round(job.cpu, 2),
            "ends": job.ends, "members": {str(pid): start for pid, start in sorted(job.members.items())}}


def job_from_record(item: Dict[str, Any]) -> Job:
    return Job(item["pid"], item["start"], item["owner"], Kind(item["kind"]),
               Need(item["need"]) if item["need"] else None, Amount(item["cpus"], item["gib"]), item["minutes"],
               item["command"], item["granted"], item["footprint_kib"], item["peak_kib"], item["cpu"],
               {int(pid): start for pid, start in item["members"].items()})
