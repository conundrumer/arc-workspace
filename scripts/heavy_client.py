"""The side of `scripts/run_heavy.py` that talks to the resource daemon
(`scripts/resource_daemon.py`): reaching it, starting it where none runs,
registering a call with it, changing a job's need, reading its registry.

Standard library only, Python 3.9."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

import heavy_protocol
from heavy_enforcer import HARD_GIB
from heavy_protocol import Refusal

START_SECONDS = 15
GIT_SECONDS = 5
ANSWER_SECONDS = 30
"""The seconds the daemon has to answer a request."""
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
    if heavy_protocol.private():
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


def ask(directory: str, request: Dict[str, Any], start: bool) -> Optional[Dict[str, Any]]:
    """The daemon's one-line answer to `request`, which this call starts a daemon for where none runs
    and `start` is set; None where none runs and `start` is not set. A daemon that restarts closes the
    connection or has no socket for a moment, and its registry still names it, so the request is sent
    again, for up to `START_SECONDS`."""
    deadline = time.monotonic() + START_SECONDS
    while time.monotonic() < deadline:
        conn = connect(directory, start)
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


def acquire(directory: str, request: Dict[str, Any]) -> None:
    """Register the call that `request` gives with the daemon, which starts where none runs. Raise
    `Refusal` where the daemon refuses."""
    reply = ask(directory, request, start=True)
    assert reply is not None
    if reply.get("status") != "granted":
        raise Refusal(reply.get("reason", f"unexpected answer {reply!r}"))


def queue(directory: str) -> Optional[Dict[str, Any]]:
    """The daemon's registry, or None where no daemon runs."""
    reply = ask(directory, {"op": "queue"}, start=False)
    if reply is None:
        return None
    if reply.get("status") != "queue":
        raise Refusal(reply.get("reason", f"unexpected answer {reply!r}"))
    return reply["registry"]


def change_need(directory: str, pid: int, need: str) -> str:
    """Give the job of client `pid` the need `need`, and say what became of it."""
    reply = ask(directory, {"op": "need", "pid": pid, "need": need}, start=False)
    if reply is None:
        raise Refusal(f"no job of pid {pid} runs: no daemon runs")
    if reply.get("status") != "changed":
        raise Refusal(reply.get("reason", f"unexpected answer {reply!r}"))
    return f"pid {pid} needs {reply['need']}: {reply['processes']} processes run at its nice value or higher"


def duration(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}m{secs:02d}s" if minutes else f"{secs}s"


def queue_text(registry: Dict[str, Any], now: float) -> str:
    """The queue view: the machine, and each job with its need."""
    machine = registry["machine"]
    lines: List[str] = [f"machine: {machine['cpus']} CPUs; no job waits for a start, and a job is killed over "
                        f"{HARD_GIB} GiB or at critical pressure; "
                        f"{machine['outside_gib']} GiB readable outside the jobs"]
    if registry["fault"]:
        lines.append(f"fault: {registry['fault']}")
    lines.append("running: pid owner kind need cpus gib elapsed peak-gib command")
    for job in registry["jobs"]:
        lines.append(" ".join([
            f"  {job['pid']}", job["owner"][:OWNER_CHARS], job["kind"], job["need"] or "-", str(job["cpus"]),
            f"{job['footprint_kib'] / (1 << 20):.1f}", duration(now - job["granted"]),
            f"{job['peak_kib'] / (1 << 20):.1f}", job["command"][:COMMAND_CHARS]]))
    return "\n".join(lines)
