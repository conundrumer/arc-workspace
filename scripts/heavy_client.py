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
GIT_SECONDS = 5
ANSWER_SECONDS = 30
"""The seconds the daemon has to answer a request before the first line that says it waits or
starts."""
RECONNECTS = 5
"""The connections in a row that may end with no answer line before `acquire` gives up."""
RETRY_SECONDS = 0.2
ERROR_LINES = 5
OWNER_CHARS = 8
COMMAND_CHARS = 60


def daemon_script() -> str:
    """The daemon's script: the copy in the main tree, so that the daemon runs the code that master
    holds whichever checkout starts it, or the copy beside this file where `ARC_HEAVY_DIR` is set
    (the daemon of that checkout's own tests) or the main tree cannot be found."""
    here = os.path.dirname(os.path.abspath(__file__))
    own = os.path.join(here, "resource_daemon.py")
    if os.environ.get(heavy_protocol.DIR_ENV):
        return own
    try:
        common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=here,
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True,
                                timeout=GIT_SECONDS).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return own
    main = os.path.join(os.path.dirname(common), "scripts", "resource_daemon.py")
    return main if os.path.isfile(main) else own


def last_errors(directory: str) -> str:
    try:
        with open(os.path.join(directory, heavy_protocol.ERRORS)) as f:
            return " ".join(f.read().splitlines()[-ERROR_LINES:])
    except OSError:
        return ""


LAUNCH = ("import subprocess, sys; subprocess.Popen([sys.executable, sys.argv[1]], "
          "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, start_new_session=True)")
"""The program of the process that starts the daemon and exits, so that the daemon is no child of
the call, which execs into its command and never reaps a child."""


def spawn(directory: str) -> None:
    """Start the daemon, which outlives this call and is the child of no process of it."""
    try:
        with open(os.path.join(directory, heavy_protocol.ERRORS), "ab") as errors:
            launcher = subprocess.Popen([sys.executable, "-c", LAUNCH, daemon_script()], stdin=subprocess.DEVNULL,
                                        stdout=subprocess.DEVNULL, stderr=errors, start_new_session=True)
            status = launcher.wait(timeout=START_SECONDS)
    except (OSError, subprocess.SubprocessError) as error:
        raise Refusal(f"cannot start the daemon: {error}")
    if status:
        raise Refusal(f"cannot start the daemon, status {status}: {last_errors(directory)}")


def connect(directory: str, start: bool) -> Optional[socket.socket]:
    """A connection to the daemon, which this call starts where none runs and `start` is set;
    None where none runs and `start` is not set. A daemon that holds the lock but has no socket
    to connect to is restarting or stopping, and is waited for, not replaced."""
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError as error:
        raise Refusal(f"daemon directory {directory}: {error}")
    path = heavy_protocol.socket_path(directory)
    started = False
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
        if not started and not heavy_protocol.lock_held(directory):
            spawn(directory)
            started = True
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
    cut_said = False
    cpus = 0
    failures = 0
    while failures < RECONNECTS:
        conn = connect(directory, start=True)
        assert conn is not None
        with conn, conn.makefile("rb") as stream:
            conn.settimeout(ANSWER_SECONDS)
            try:
                conn.sendall(heavy_protocol.line({**request, "since": since}))
                for raw in stream:
                    failures = 0
                    reply = json.loads(raw)
                    status = reply["status"]
                    if status == "accepted":
                        conn.settimeout(None)
                        cpus = reply["cpus"]
                        if reply["cut"] and not cut_said:
                            cut_said = True
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
        failures += 1
    raise Refusal("the daemon keeps closing the connection")


def ask(directory: str, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The daemon's one-line answer to `request`, or None where no daemon runs. A daemon that
    restarts closes the connection or has no socket for a moment, and its registry still names it,
    so the request is sent again, for up to `START_SECONDS`."""
    deadline = time.monotonic() + START_SECONDS
    while time.monotonic() < deadline:
        conn = connect(directory, start=False)
        if conn is None:
            if heavy_protocol.read_registry(directory) is None:
                return None
        else:
            with conn, conn.makefile("rb") as stream:
                conn.settimeout(ANSWER_SECONDS)
                try:
                    conn.sendall(heavy_protocol.line({**request, "version": heavy_protocol.VERSION}))
                    answer = stream.readline()
                    if answer:
                        return json.loads(answer)
                except (OSError, ValueError) as error:
                    raise Refusal(f"cannot reach the daemon: {error!r}")
        time.sleep(RETRY_SECONDS)
    raise Refusal(f"the daemon did not answer within {START_SECONDS} s")


def queue(directory: str) -> Optional[Dict[str, Any]]:
    """The daemon's registry, or None where no daemon runs."""
    reply = ask(directory, {"op": "queue"})
    if reply is None:
        return None
    if reply.get("status") != "queue":
        raise Refusal(reply.get("reason", f"unexpected answer {reply!r}"))
    return reply["registry"]


def change_need(directory: str, pid: int, need: str) -> str:
    """Give the waiting request of client `pid` the need `need`, and say what became of it."""
    reply = ask(directory, {"op": "need", "pid": pid, "need": need})
    if reply is None:
        raise Refusal(f"no request of pid {pid} waits: no daemon runs")
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
    lines: List[str] = [f"budget: {budget['cpus']} CPUs, of which {budget['reserve_cpus']} are the short jobs' "
                        f"reserve; memory admits by pressure alone, one start a reading; "
                        f"{budget['outside_gib']} GiB readable outside the jobs"]
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
