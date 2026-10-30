"""What `scripts/run_heavy.py` and `scripts/resource_daemon.py` share: where
the daemon's files are, the lines they send each other, and the registry the
daemon writes.

The daemon listens on a Unix socket, `daemon.sock` under the directory
`ARC_HEAVY_DIR` gives (`~/.cache/arc-workspace/heavy` where it is not set; a daemon of the directory
`ARC_HEAVY_DIR` gives is `private`), or
`/tmp/arc-heavy-<hash of the directory>.sock` where that path is too long for a
socket. A client sends one line of JSON and reads one line of JSON. A call of version
`LEGACY_VERSION` sends the fields `gib`, `minutes`, `wait` and `since` as well, and reads the lines that
`scripts/heavy_legacy.py` gives; the daemon gives its process the nice value of its need, as that call sets none.

    {"op": "acquire", "version": <int>, "pid": <int>, "cpus": <int>, "need": "now"|"soon"|"idle",
     "command": <text>}
        answered with `{"status": "granted"}` at once, or `{"status": "refused", "reason"}`.
    {"op": "queue", "version": <int>}
        answered with `{"status": "queue", "registry": <registry>}`.
    {"op": "need", "version": <int>, "pid": <int>, "need": "now"|"soon"|"idle"}
        answered with `{"status": "changed", "need", "processes"}` where the daemon gave the processes
        of the job of that pid the nice value of the need, or kept their own where that is higher, or `{"status": "refused", "reason"}` where
        no job of that pid runs under a grant or the need is under the job's, which a user cannot lower.

The daemon holds a `flock` on `daemon.lock` under the directory for as long as it runs. A daemon
that replaces its process by `os.execv` passes the open lock and the listening socket to the new
image in the descriptors that the environment variables `ARC_HEAVY_LOCK_FD` and `ARC_HEAVY_SOCKET_FD`
give, so the lock is held and the socket listens without a break.

The registry, `registry.json` under the directory, is the daemon's record of the jobs it counts, as
`heavy_core.Core.snapshot` gives it, with `daemon` the daemon's pid.
The daemon rewrites it at each change, and a reader takes it as stale where `daemon` does not run or
`at` is older than `FRESH_SECONDS`.

Standard library only, Python 3.9."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import time
from typing import Any, Dict, Optional

VERSION = 2
DEFAULT_CPUS = 1
"""The CPUs of a call that gives no `--cpus`."""
LEGACY_VERSION = 1
"""The version of the protocol before this one, which the daemon still serves."""
DIR_ENV = "ARC_HEAVY_DIR"
SOCKS_ENV = "ARC_HEAVY_SOCKS"
SOCKS = "/tmp/cc-socks"
SOCKET = "daemon.sock"
LOCK = "daemon.lock"
LOCK_FD_ENV = "ARC_HEAVY_LOCK_FD"
SOCKET_FD_ENV = "ARC_HEAVY_SOCKET_FD"
REGISTRY = "registry.json"
LOG = "daemon.log"
ERRORS = "daemon.err"
FRESH_SECONDS = 30
SOCKET_PATH_CHARS = 100
"""The most characters of a socket's path that stand under macOS's limit of 104 bytes."""


class Refusal(Exception):
    """A failure before the command starts, with the reason `run_heavy.py` gives."""


def private() -> bool:
    """Whether the daemon's directory comes from `ARC_HEAVY_DIR`: a daemon of a test, which shares the
    machine with the sessions' own daemon. It adopts no process, sends no message to a session (it logs
    what it would send), and signals only the processes of its own gated jobs."""
    return bool(os.environ.get(DIR_ENV))


def heavy_dir() -> str:
    return os.environ.get(DIR_ENV) or os.path.expanduser("~/.cache/arc-workspace/heavy")


def socks_dir() -> str:
    """The directory of the sessions' inbox sockets."""
    return os.environ.get(SOCKS_ENV) or SOCKS


def socket_path(directory: str) -> str:
    path = os.path.join(directory, SOCKET)
    if len(path) <= SOCKET_PATH_CHARS:
        return path
    return f"/tmp/arc-heavy-{hashlib.sha1(directory.encode()).hexdigest()[:16]}.sock"


def lock_held(directory: str) -> bool:
    """Whether a daemon holds the lock under `directory`: one that runs, restarts or stops."""
    fd = os.open(os.path.join(directory, LOCK), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    finally:
        os.close(fd)
    return False


def line(message: Dict[str, Any]) -> bytes:
    return json.dumps(message).encode() + b"\n"


def read_registry(directory: str) -> Optional[Dict[str, Any]]:
    """The registry under `directory`, or None where it is missing, unreadable, or stale."""
    try:
        with open(os.path.join(directory, REGISTRY)) as f:
            record = json.load(f)
        os.kill(record["daemon"], 0)
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return record if time.time() - record["at"] <= FRESH_SECONDS else None


def write_registry(directory: str, record: Dict[str, Any]) -> None:
    """Replace the registry whole, so that a reader sees the old or the new one."""
    path = os.path.join(directory, REGISTRY)
    tmp = f"{path}.{os.getpid()}"
    with open(tmp, "w") as f:
        json.dump(record, f)
    os.replace(tmp, path)
