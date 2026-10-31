#!/usr/bin/python3
"""The resource daemon: one process on the machine that records the heavy
commands of `scripts/run_heavy.py`, counts what the sessions run outside it, sets
the nice value of a job by its need, kills a job that holds too much memory, lowers a `now` job that has run
`LONG_NOW_SECONDS` seconds to `soon`, and tells the owning session what it did.

`run_heavy.py` starts it where none runs, from the main tree's copy of this
script (`heavy_client.daemon_script`). It runs while a Claude Code session
runs or a job runs, and exits `IDLE_EXIT_SECONDS` after neither does.
It is itself no member of a job: the readings leave its own process out, so no
job's footprint or CPU counts it, and no kill, reap or signal names it.

`scripts/heavy_protocol.py` gives its files, its socket and the registry,
`scripts/heavy_core.py` what it decides, and `scripts/heavy_enforcer.py` the
rules it applies. This module reads the
machine, performs each effect, and serves the socket.

Once a source file it runs (this script, and each module that lies beside it)
has changed and the next sample reads the file the same, it writes the registry,
replaces its process, by `os.execv`, with a run of the changed script, which keeps
the lock and the listening socket open (`heavy_protocol`), so that a call that connects meanwhile
waits in the socket's queue and no call starts another daemon. A call that sees its connection
close before it is answered connects again (`heavy_client.ask`).

It reads the machine every `SAMPLE_SECONDS` (`FAST_SAMPLE_SECONDS` while the
memory pressure is over normal or the swap-ins are over the load monitor's alert rate): `ps` for the processes, the sessions' files
for the sessions, and `proc_pid_rusage` for the footprint and CPU time of the
processes of sessions and jobs, and for the footprint of each other process, read
again each `OUTSIDE_SECONDS`. A job's pid is polled each `LOOP_SECONDS`, so
a job ends as soon as its command does.

Each grant, need change, adoption, overrun, soft-cap message, kill, reap, message, refusal and restart is a line of
JSON in `daemon.log` under the directory, with its reason, owner and figures.
A kill signals only a process that still has the start the daemon recorded for
it. A message is one line, `{"type":"user","message":{"role":"user","content":<text>}}`,
written to the socket `<claude pid>.sock` of the owning session in
`/tmp/cc-socks` (`ARC_HEAVY_SOCKS` sets that directory).

A daemon of a directory that `ARC_HEAVY_DIR` gives (`heavy_protocol.private`) adopts no process, writes
no message to a session socket but logs it as `message-withheld`, and so signals and renices only the
processes of its own gated jobs.

A restarted daemon, whether it was stopped or replaced itself, reads the
registry, and keeps each job whose process runs with the recorded start."""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import selectors
import signal
import socket
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import heavy_protocol
from heavy_core import Core, Demote, Effect, Log, Proc, Sample, Signal as SendSignal
from heavy_model import Job, Kind, Need
import heavy_legacy
from heavy_notices import Reason, message_line
from heavy_protocol import LEGACY_VERSION, VERSION, Refusal
from machine_readings import PRESSURE_LEVELS, budget, counters, pressure_level
from process_readings import NO_SESSION, harness_sessions, owners, process_started, rows, usage

SAMPLE_SECONDS = 5
FAST_SAMPLE_SECONDS = 1
LOOP_SECONDS = 0.25
IDLE_EXIT_SECONDS = 60
SOCKET_TIMEOUT = 2.0
OUTSIDE_SECONDS = 15
LOG_ROTATE_BYTES = 5 << 20
READ_ERRORS = (OSError, ValueError, KeyError, IndexError, subprocess.CalledProcessError)


class Sources:
    """The source files the daemon runs, with each one's `(st_mtime_ns, st_size)` at the start."""

    def __init__(self) -> None:
        here = os.path.dirname(os.path.abspath(__file__))
        files = {os.path.abspath(__file__)}
        for module in list(sys.modules.values()):
            file = getattr(module, "__file__", None)
            if file and os.path.dirname(os.path.abspath(file)) == here:
                files.add(os.path.abspath(file))
        self.paths = sorted(files)
        self.started = self.read()
        self.last = self.started

    def read(self) -> Dict[str, Optional[Tuple[int, int]]]:
        stamps: Dict[str, Optional[Tuple[int, int]]] = {}
        for path in self.paths:
            try:
                stat = os.stat(path)
            except OSError:
                stamps[path] = None
            else:
                stamps[path] = (stat.st_mtime_ns, stat.st_size)
        return stamps

    def changed(self) -> List[str]:
        """The files that differ from the start, once this reading is the same as the one before
        it, so that a merge that writes several files has ended; else none."""
        reading = self.read()
        settled = reading == self.last
        self.last = reading
        return [path for path in self.paths if reading[path] != self.started[path]] if settled else []


class Client:
    """A connection of a client."""

    def __init__(self, conn: socket.socket) -> None:
        self.conn = conn
        self.buffer = b""

    def send(self, message: Dict[str, Any]) -> None:
        try:
            self.conn.sendall(heavy_protocol.line(message))
        except OSError:
            pass


class Daemon:
    def __init__(self, directory: str) -> None:
        self.directory = directory
        self.core = Core(1, heavy_protocol.private())
        self.claude: Dict[int, str] = {}
        self.swap_before: Optional[Tuple[int, float]] = None
        self.others: Dict[int, Tuple[float, Optional[int]]] = {}
        self.others_at = 0.0
        self.dirty = True
        self.last_active = time.time()
        self.selector = selectors.DefaultSelector()
        self.sources = Sources()

    def log(self, event: str, fields: Dict[str, Any]) -> None:
        record = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": event, **fields}
        with open(os.path.join(self.directory, heavy_protocol.LOG), "a") as f:
            f.write(json.dumps(record) + "\n")

    def rotate_log(self) -> None:
        path = os.path.join(self.directory, heavy_protocol.LOG)
        if os.path.exists(path) and os.path.getsize(path) > LOG_ROTATE_BYTES:
            os.replace(path, path + ".1")

    def apply(self, effects: List[Effect]) -> None:
        for effect in effects:
            if isinstance(effect, Log):
                self.log(effect.event, effect.fields)
            elif isinstance(effect, SendSignal):
                self.send_signal(effect)
            elif isinstance(effect, Demote):
                self.demote(effect)

    def send_signal(self, effect: SendSignal) -> None:
        """Send the signal where the process still has the recorded start."""
        try:
            if not started_at(effect.pid, effect.start):
                self.log("signal-skipped", {"pid": effect.pid, "signal": effect.number})
                return
            os.kill(effect.pid, effect.number)
        except OSError as error:
            self.log("signal-failed", {"pid": effect.pid, "signal": effect.number, "error": repr(error)})

    def demote(self, effect: Demote) -> None:
        """Give the job of `effect` its need, where it still runs."""
        job = self.core.gated(effect.pid)
        if job is not None:
            self.give_need(job, effect.need, Reason.LONG_NOW)

    def post(self, claude: int, text: str) -> None:
        if heavy_protocol.private():
            self.log("message-withheld", {"claude": claude, "text": text})
            return
        path = os.path.join(heavy_protocol.socks_dir(), f"{claude}.sock")
        try:
            with socket.socket(socket.AF_UNIX) as conn:
                conn.settimeout(SOCKET_TIMEOUT)
                conn.connect(path)
                conn.sendall(message_line(text).encode())
        except OSError as error:
            self.log("message-failed", {"claude": claude, "error": repr(error)})
        else:
            self.log("message", {"claude": claude, "text": text})

    def read_cpus(self) -> int:
        """The machine's CPUs."""
        try:
            cpus, gib = budget()
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            raise Refusal(f"cannot read the budget from sysctl: {error!r}")
        if min(cpus, gib) < 1:
            raise Refusal(f"the machine's budget is {cpus} CPUs and {gib} GiB")
        return cpus

    def sample(self, now: float) -> Sample:
        """Read the machine."""
        began = time.monotonic()
        table = [row for row in rows() if row.pid != os.getpid()]
        found = harness_sessions()
        if found is not None:
            self.claude = found
        owner = owners(table, self.claude)
        wanted = {pid for pid, session in owner.items() if session != NO_SESSION}
        for job in self.core.jobs.values():
            wanted |= set(job.members) | {job.pid}
        refresh = now - self.others_at >= OUTSIDE_SECONDS
        procs: Dict[int, Proc] = {}
        for row in table:
            if row.pid in wanted:
                read = usage(row.pid)
                procs[row.pid] = Proc(row.pid, row.ppid, row.start, row.command, owner[row.pid],
                                      read[0] if read else None, read[1] if read else None)
                continue
            cached = self.others.get(row.pid)
            if refresh or cached is None or cached[0] != row.start:
                read = usage(row.pid)
                cached = self.others[row.pid] = (row.start, read[0] if read else None)
            procs[row.pid] = Proc(row.pid, row.ppid, row.start, row.command, owner[row.pid], cached[1], None)
        if refresh:
            self.others_at = now
            self.others = {pid: found for pid, found in self.others.items() if pid in procs}
        alive = set()
        for job in self.core.jobs.values():
            if job.kind is not Kind.GATED:
                continue
            started = process_started(job.pid)
            if started is None or started != int(job.start):
                continue
            alive.add(job.pid)
            if job.pid not in procs:
                read = usage(job.pid)
                procs[job.pid] = Proc(job.pid, 0, float(started), job.command, job.owner,
                                      read[0] if read else None, read[1] if read else None)
        swapins = counters()[0]
        swap_rate = None
        if self.swap_before is not None:
            swap_rate = (swapins - self.swap_before[0]) / max(now - self.swap_before[1], 1e-3)
        self.swap_before = (swapins, now)
        return Sample(now, procs, dict(self.claude), frozenset(alive), pressure_level(), swap_rate,
                      time.monotonic() - began)

    def tick(self, now: float) -> None:
        try:
            self.core.cpus = self.read_cpus()
            sample = self.sample(now)
        except Refusal as refusal:
            self.fail(str(refusal))
            return
        except READ_ERRORS as error:
            self.fail(f"cannot read the memory load from vm_stat, sysctl and ps: {error!r}")
            return
        self.core.fault = None
        self.apply(self.core.tick(sample, now))
        self.dirty = True

    def fail(self, reason: str) -> None:
        """Refuse each request until a reading succeeds."""
        if self.core.fault is None:
            self.log("fault", {"reason": reason})
        self.core.fault = reason

    def owner_of(self, pid: int) -> str:
        table = rows()
        found = harness_sessions() or self.claude
        return owners(table, found).get(pid, NO_SESSION)

    def acquire(self, request: Dict[str, Any], now: float) -> int:
        """Record the call of `request` as a gated job, and return the CPUs it declares."""
        pid = request["pid"]
        started = process_started(pid)
        if started is None:
            raise Refusal(f"pid {pid} does not run")
        if self.core.fault is not None:
            raise Refusal(self.core.fault)
        cpus = int(request["cpus"])
        if cpus < 1:
            raise Refusal(f"cpus is {cpus}, not a whole number from 1")
        self.apply(self.core.grant(pid, float(started), self.owner_of(pid), Need(request["need"]), cpus,
                                   request["command"], now))
        self.last_active = now
        self.dirty = True
        return cpus

    def renice(self, job: Job, need: Need) -> int:
        """Give each process of `job` that still has its recorded start the nice value of `need`, or
        keep its own where that is higher, and return how many processes are left at it. Raise `Refusal`
        where `need` is under the need of `job`, since a user cannot lower a nice value."""
        if job.need is not None and need.nice < job.need.nice:
            raise Refusal(f"pid {job.pid} needs {job.need.value}, and a user cannot lower a nice value to "
                          f"{need.value}'s {need.nice}")
        changed = 0
        for pid, start in sorted(job.members.items()):
            try:
                if started_at(pid, start):
                    raise_nice(pid, need)
                    changed += 1
            except ProcessLookupError:
                continue
            except OSError as error:
                self.log("nice-failed", {"pid": pid, "need": need.value, "error": repr(error)})
        return changed

    def renice_call(self, pid: int, need: Need) -> None:
        """Give the process of a legacy call, which sets no nice value of its own, the nice value of
        `need` by the rule `run_heavy.set_nice` applies. Raise `Refusal` where the system refuses it."""
        try:
            raise_nice(pid, need)
        except OSError as error:
            raise Refusal(f"the system refuses nice value {need.nice} for pid {pid}: {error.strerror}")

    def change_need(self, request: Dict[str, Any]) -> Tuple[Need, int]:
        """Give the job of `request` its need, and return it with the processes left at its nice value or higher."""
        pid = request["pid"]
        job = self.core.gated(pid)
        if job is None:
            raise Refusal(f"no job of pid {pid} runs under run_heavy.py")
        need = Need(request["need"])
        return need, self.give_need(job, need, None)

    def give_need(self, job: Job, need: Need, reason: Optional[Reason]) -> int:
        """Give `job` the need `need` for `reason` (None for a client's request), and return the
        processes left at its nice value or higher."""
        processes = self.renice(job, need)
        self.apply(self.core.set_need(job, need, processes, reason))
        self.dirty = True
        return processes

    def handle(self, client: Client, text: str, now: float) -> None:
        try:
            request = json.loads(text)
            version = request.get("version")
            if version not in (VERSION, LEGACY_VERSION):
                raise Refusal(f"the daemon speaks protocols {LEGACY_VERSION} and {VERSION}, this call {version}")
            legacy = version == LEGACY_VERSION
            if request.get("op") == "queue":
                registry = self.registry(now)
                client.send({"status": "queue", "registry": heavy_legacy.registry(registry) if legacy else registry})
            elif request.get("op") == "acquire":
                cpus = self.acquire(heavy_legacy.current(request) if legacy else request, now)
                if legacy:
                    self.renice_call(request["pid"], Need(request["need"]))
                for reply in heavy_legacy.granted(cpus) if legacy else [{"status": "granted"}]:
                    client.send(reply)
            elif request.get("op") == "need":
                need, processes = self.change_need(request)
                client.send(heavy_legacy.changed(need.value) if legacy else
                            {"status": "changed", "need": need.value, "processes": processes})
            else:
                raise Refusal(f"no operation {request.get('op')!r}")
        except Refusal as refusal:
            self.refuse(client, text, str(refusal))
        except (ValueError, KeyError, TypeError) as error:
            self.refuse(client, text, f"bad request: {error!r}")
        except READ_ERRORS as error:
            self.refuse(client, text, f"cannot read the machine: {error!r}")

    def refuse(self, client: Client, text: str, reason: str) -> None:
        """Log a refusal with its reason, the owner of the request's pid (`-` where the request
        gives none or the table cannot be read), and the figures it asks, and tell the client."""
        figures: Dict[str, Any] = {}
        owner = NO_SESSION
        try:
            asked = json.loads(text)
            figures = {key: asked.get(key) for key in ("op", "pid", "cpus", "need")}
            owner = self.owner_of(asked["pid"])
        except (ValueError, KeyError, TypeError, AttributeError, *READ_ERRORS):
            pass
        self.log("refusal", {"reason": reason, "owner": owner, **figures, "request": text[:300]})
        client.send({"status": "refused", "reason": reason})

    def registry(self, now: float) -> Dict[str, Any]:
        return {**self.core.snapshot(now), "daemon": os.getpid(), "protocol": VERSION}

    def close(self, client: Client) -> None:
        try:
            self.selector.unregister(client.conn)
        except (KeyError, ValueError):
            pass
        client.conn.close()

    def read(self, client: Client, now: float) -> None:
        try:
            data = client.conn.recv(65536)
        except OSError:
            data = b""
        if not data:
            self.close(client)
            return
        client.buffer += data
        while b"\n" in client.buffer:
            text, _, client.buffer = client.buffer.partition(b"\n")
            self.handle(client, text.decode(errors="replace"), now)

    def accept(self, server: socket.socket) -> None:
        conn, _ = server.accept()
        conn.settimeout(SOCKET_TIMEOUT)
        self.selector.register(conn, selectors.EVENT_READ, Client(conn))

    def restore(self) -> None:
        try:
            with open(os.path.join(self.directory, heavy_protocol.REGISTRY)) as f:
                self.core.restore(json.load(f))
        except FileNotFoundError:
            return
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.log("registry-unreadable", {"error": repr(error)})

    def run(self, server: socket.socket) -> List[str]:
        """Serve until no session runs and no job runs for `IDLE_EXIT_SECONDS`, and give
        no files, or until a source file has changed, and give the files that changed."""
        server.setblocking(False)
        self.selector.register(server, selectors.EVENT_READ, None)
        self.restore()
        self.tick(time.time())
        next_sample = time.time() + self.sample_seconds()
        while True:
            for key, _ in self.selector.select(LOOP_SECONDS):
                if key.data is None:
                    self.accept(server)
                else:
                    self.read(key.data, time.time())
            now = time.time()
            gone = [pid for pid, job in self.core.jobs.items() if job.kind is Kind.GATED and not runs(pid)]
            if gone:
                self.apply(self.core.reap(gone, now))
                self.dirty = True
            if now >= next_sample:
                self.tick(now)
                next_sample = now + self.sample_seconds()
                if self.should_exit(now):
                    return []
                changed = self.sources.changed()
                if changed:
                    self.log("restart", {"changed": [os.path.basename(path) for path in changed]})
                    heavy_protocol.write_registry(self.directory, self.registry(now))
                    return changed
            for claude, text in self.core.messages(now):
                self.post(claude, text)
            if self.dirty:
                heavy_protocol.write_registry(self.directory, self.registry(now))
                self.dirty = False

    def sample_seconds(self) -> float:
        return FAST_SAMPLE_SECONDS if self.core.level in PRESSURE_LEVELS or self.core.hot else SAMPLE_SECONDS

    def should_exit(self, now: float) -> bool:
        """Whether no session runs and no job runs, and none has for `IDLE_EXIT_SECONDS`."""
        if self.core.jobs or self.claude:
            self.last_active = now
        return now - self.last_active >= IDLE_EXIT_SECONDS


def started_at(pid: int, start: float) -> bool:
    """Whether process `pid` runs and has the start `start`, within a second."""
    started = process_started(pid)
    return started is not None and abs(started - start) <= 1


def raise_nice(pid: int, need: Need) -> None:
    """Give process `pid` the nice value of `need`, or keep its own where that is higher."""
    os.setpriority(os.PRIO_PROCESS, pid, need.raised(os.getpriority(os.PRIO_PROCESS, pid)))


def runs(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def inherited(name: str) -> Optional[int]:
    """The descriptor that a daemon which replaced its process passed on in the environment
    variable `name`, taken out of the environment, or None where this process is a new start."""
    value = os.environ.pop(name, None)
    return None if value is None else int(value)


def listen(directory: str, inherited_fd: Optional[int]) -> socket.socket:
    if inherited_fd is not None:
        server = socket.socket(fileno=inherited_fd)
        server.set_inheritable(False)
        return server
    path = heavy_protocol.socket_path(directory)
    if os.path.exists(path):
        os.unlink(path)
    server = socket.socket(socket.AF_UNIX)
    server.bind(path)
    os.chmod(path, 0o600)
    server.listen(64)
    return server


def main() -> int:
    directory = heavy_protocol.heavy_dir()
    os.makedirs(directory, exist_ok=True)
    lock = inherited(heavy_protocol.LOCK_FD_ENV)
    if lock is None:
        lock = os.open(os.path.join(directory, heavy_protocol.LOCK), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 0
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    daemon = Daemon(directory)
    daemon.rotate_log()
    server = listen(directory, inherited(heavy_protocol.SOCKET_FD_ENV))
    changed: List[str] = []
    ended = False
    try:
        changed = daemon.run(server)
        ended = not changed
    finally:
        if not changed:
            server.close()
            for path in [heavy_protocol.socket_path(directory)] + (
                    [] if not ended or daemon.core.jobs else [os.path.join(directory, heavy_protocol.REGISTRY)]):
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(path)
    if changed:
        for fd, name in ((lock, heavy_protocol.LOCK_FD_ENV), (server.fileno(), heavy_protocol.SOCKET_FD_ENV)):
            os.set_inheritable(fd, True)
            os.environ[name] = str(fd)
        os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
