"""The side of `scripts/run_heavy.py` that talks to the resource daemon
(`scripts/resource_daemon.py`): reaching it, starting it where none runs,
asking it for a share, reading its queue.

Standard library only, Python 3.9."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from typing import Any, Callable, Dict, List, Optional

import heavy_protocol
from heavy_protocol import Refusal

START_SECONDS = 15
ANSWER_SECONDS = 30
"""The seconds the daemon has to answer a request before the first line that says it waits or
starts."""
RECONNECTS = 5
ERROR_LINES = 5
OWNER_CHARS = 8
COMMAND_CHARS = 60


def daemon_script() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "resource_daemon.py")


def last_errors(directory: str) -> str:
    try:
        with open(os.path.join(directory, heavy_protocol.ERRORS)) as f:
            return " ".join(f.read().splitlines()[-ERROR_LINES:])
    except OSError:
        return ""


def spawn(directory: str) -> "subprocess.Popen[bytes]":
    try:
        with open(os.path.join(directory, heavy_protocol.ERRORS), "ab") as errors:
            return subprocess.Popen([sys.executable, daemon_script()], stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL, stderr=errors, start_new_session=True)
    except OSError as error:
        raise Refusal(f"cannot start the daemon: {error}")


def connect(directory: str, start: bool) -> Optional[socket.socket]:
    """A connection to the daemon, which this call starts where none runs and `start` is set;
    None where none runs and `start` is not set."""
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError as error:
        raise Refusal(f"daemon directory {directory}: {error}")
    path = heavy_protocol.socket_path(directory)
    process = None
    deadline = time.monotonic() + START_SECONDS
    while True:
        conn = socket.socket(socket.AF_UNIX)
        try:
            conn.connect(path)
            return conn
        except (FileNotFoundError, ConnectionRefusedError):
            conn.close()
        except OSError as error:
            conn.close()
            raise Refusal(f"cannot reach the daemon at {path}: {error}")
        if not start:
            return None
        if process is None:
            process = spawn(directory)
        elif process.poll() not in (None, 0):
            raise Refusal(f"the daemon exited with status {process.returncode}: {last_errors(directory)}")
        if time.monotonic() >= deadline:
            raise Refusal(f"the daemon did not start within {START_SECONDS} s: {last_errors(directory)}")
        time.sleep(0.05)


def clock(at: Optional[float]) -> str:
    return "unknown" if at is None else time.strftime("%H:%M:%S", time.localtime(at))


def acquire(directory: str, request: Dict[str, Any], say: Callable[[str], None]) -> int:
    """Return the CPUs granted, once the daemon grants the share that `request` asks, and raise
    `Refusal` where it refuses or the wait runs out. `say` takes the one line that tells the
    request was cut and the one that tells it waits."""
    since = time.time()
    waited = False
    cpus = 0
    for _ in range(RECONNECTS):
        conn = connect(directory, start=True)
        assert conn is not None
        with conn, conn.makefile("rb") as stream:
            conn.settimeout(ANSWER_SECONDS)
            try:
                conn.sendall(heavy_protocol.line({**request, "since": since}))
                for raw in stream:
                    reply = json.loads(raw)
                    status = reply["status"]
                    if status == "accepted":
                        conn.settimeout(None)
                        cpus = reply["cpus"]
                        if reply["cut"]:
                            say(f"cut to the budget: {reply['cpus']} CPUs and {reply['gib']} GiB of "
                                f"{reply['limit_cpus']} and {reply['limit_gib']}")
                    elif status == "waiting" and not waited:
                        waited = True
                        say(f"waiting for {reply['reason']}; place {reply['position']} in the "
                            f"{reply['lane']} queue, expected start {clock(reply['eta'])}")
                    elif status == "granted":
                        return cpus
                    elif status == "refused":
                        raise Refusal(reply["reason"])
                    elif status == "timeout":
                        raise Refusal(f"{reply['reason']}; expected start {clock(reply['eta'])}")
            except socket.timeout:
                raise Refusal(f"the daemon did not answer within {ANSWER_SECONDS} s")
            except (ConnectionError, ValueError):
                pass
    raise Refusal("the daemon keeps closing the connection")


def queue(directory: str) -> Optional[Dict[str, Any]]:
    """The daemon's registry, or None where no daemon runs."""
    conn = connect(directory, start=False)
    if conn is None:
        return None
    with conn, conn.makefile("rb") as stream:
        conn.settimeout(ANSWER_SECONDS)
        try:
            conn.sendall(heavy_protocol.line({"op": "queue", "version": heavy_protocol.VERSION}))
            reply = json.loads(stream.readline())
        except (OSError, ValueError) as error:
            raise Refusal(f"cannot read the daemon's queue: {error!r}")
    if reply.get("status") != "queue":
        raise Refusal(reply.get("reason", f"unexpected answer {reply!r}"))
    return reply["registry"]


def change_need(directory: str, pid: int, need: str) -> str:
    """Give the waiting request of client `pid` the need `need`, and say what became of it."""
    conn = connect(directory, start=False)
    if conn is None:
        raise Refusal(f"no request of pid {pid} waits: no daemon runs")
    with conn, conn.makefile("rb") as stream:
        conn.settimeout(ANSWER_SECONDS)
        try:
            conn.sendall(heavy_protocol.line({"op": "need", "version": heavy_protocol.VERSION, "pid": pid,
                                              "need": need}))
            reply = json.loads(stream.readline())
        except (OSError, ValueError) as error:
            raise Refusal(f"cannot reach the daemon: {error!r}")
    if reply.get("status") != "changed":
        raise Refusal(reply.get("reason", f"unexpected answer {reply!r}"))
    if not reply["waiting"]:
        return f"pid {pid} needs {reply['need']} and starts now"
    return (f"pid {pid} needs {reply['need']}: place {reply['position']} in the {reply['lane']} queue, "
            f"expected start {clock(reply['eta'])}")


def duration(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}m{secs:02d}s" if minutes else f"{secs}s"


def queue_text(registry: Dict[str, Any], now: float) -> str:
    """The queue view: the budget, each job that holds a share, and each waiting request in the
    order it starts, with its expected start."""
    budget = registry["budget"]
    lines: List[str] = [f"budget: {budget['cpus']} CPUs and {budget['gib']} GiB, which is {budget['fixed_gib']} GiB "
                        f"less {budget['outside_gib']} GiB held outside the jobs, of which "
                        f"{budget['reserve_cpus']} CPUs and {budget['reserve_gib']} GiB are the short jobs' reserve"]
    if registry["hold"]:
        lines.append(f"hold: {registry['hold']}")
    lines.append("running: pid owner kind need cpus gib minutes elapsed peak-gib command")
    for job in registry["jobs"]:
        lines.append(" ".join([
            f"  {job['pid']}", job["owner"][:OWNER_CHARS], job["kind"], job["need"] or "-",
            str(job["cpus"]), str(job["gib"]), "-" if job["minutes"] is None else f"{job['minutes']:g}",
            duration(now - job["granted"]), f"{job['peak_kib'] / (1 << 20):.1f}", job["command"][:COMMAND_CHARS]]))
    lines.append("waiting: pid owner lane need cpus gib minutes waited expected-start command")
    for w in sorted(registry["waiting"], key=lambda w: (w["lane"] != "short", w["position"])):
        lines.append(" ".join([
            f"  {w['pid']}", w["owner"][:OWNER_CHARS], w["lane"], w["need"], str(w["cpus"]), str(w["gib"]),
            f"{w['minutes']:g}", duration(now - w["arrived"]), clock(w["eta"]), w["command"][:COMMAND_CHARS]]))
    return "\n".join(lines)
