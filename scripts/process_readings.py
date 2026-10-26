"""The processes of the machine, the Claude Code session that owns each, and
the memory and CPU time of a process, as `scripts/resource_daemon.py` and
`scripts/load_monitor.py` read them.

A process belongs to the session of the nearest of itself and its ancestors
that is a running session's process, as the harness's file
`<config dir>/sessions/<pid>.json` gives it, or whose environment gives a
session id (`CLAUDE_CODE_SESSION_ID`); the harness's file wins for a process
that has both. A process of no session has `NO_SESSION`.

Standard library only, Python 3.9, since `scripts/run_heavy.py` runs under
the system Python and starts the daemon with it."""

from __future__ import annotations

import calendar
import ctypes
import ctypes.util
import json
import os
import re
import struct
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from claude_config import config_dir
from machine_readings import KIB, output

SESSION_ENV = "CLAUDE_CODE_SESSION_ID"
NO_SESSION = "-"
HARNESS_SESSIONS = "sessions"
"""The directory, in the harness's config directory, in which the harness
keeps a file `<pid>.json` for each running session, with its `sessionId`, its
`pid`, and its `procStart`, the start of that process in UTC, in the form
`ps -o lstart=` prints."""

PS_START_FORMAT = "%a %b %d %H:%M:%S %Y"
SESSION = re.compile(rf"(?:^|\s){SESSION_ENV}=(\S+)")
LIBC = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
LIBPROC = ctypes.CDLL(ctypes.util.find_library("proc"), use_errno=True)
CTL_KERN, KERN_PROC, KERN_PROC_PID = 1, 14, 1
KINFO_PROC_SIZE = 648
"""The size of macOS's `struct kinfo_proc`, whose first field,
`kp_proc.p_starttime.tv_sec`, is a 64-bit integer."""
RUSAGE_INFO_V0 = 0


class RUsage(ctypes.Structure):
    """macOS's `struct rusage_info_v0`."""
    _fields_ = [("uuid", ctypes.c_uint8 * 16)] + [
        (name, ctypes.c_uint64) for name in
        ("user_time", "system_time", "pkg_idle_wkups", "interrupt_wkups", "pageins", "wired_size",
         "resident_size", "phys_footprint", "proc_start_abstime", "proc_exit_abstime")]


class TimebaseInfo(ctypes.Structure):
    _fields_ = [("numer", ctypes.c_uint32), ("denom", ctypes.c_uint32)]


def timebase() -> Tuple[int, int]:
    """The numerator and denominator that turn the CPU times `proc_pid_rusage`
    gives, in Mach absolute time units, into nanoseconds."""
    info = TimebaseInfo()
    LIBC.mach_timebase_info(ctypes.byref(info))
    return info.numer, info.denom


NUMER, DENOM = timebase()


@dataclass(frozen=True)
class Row:
    """A line of the process table."""
    pid: int
    ppid: int
    cpu: float
    elapsed: str
    start: float
    command: str


def process_started(pid: int) -> Optional[int]:
    """The start of process `pid`, in seconds since the epoch, or None where
    it does not run. Raises OSError where `sysctl` fails."""
    mib = (ctypes.c_int * 4)(CTL_KERN, KERN_PROC, KERN_PROC_PID, pid)
    buf = ctypes.create_string_buffer(KINFO_PROC_SIZE)
    size = ctypes.c_size_t(KINFO_PROC_SIZE)
    if LIBC.sysctl(mib, 4, buf, ctypes.byref(size), None, 0) != 0:
        raise OSError(ctypes.get_errno(), os.strerror(ctypes.get_errno()))
    if size.value == 0:
        return None
    (seconds,) = struct.unpack_from("q", buf.raw, 0)
    return seconds


def harness_sessions() -> Optional[Dict[int, str]]:
    """The `pid` of each process the harness's file `<pid>.json` gives that
    runs, mapped to the `sessionId` of that file. A process counts only
    where it started when the file gives, so a `pid` another process has
    taken since does not count. None where a file is not readable or gives
    no `procStart`."""
    out: Dict[int, str] = {}
    for path in (config_dir() / HARNESS_SESSIONS).glob("*.json"):
        try:
            entry = json.loads(path.read_text())
        except FileNotFoundError:
            continue
        except json.JSONDecodeError:
            return None
        if "procStart" not in entry:
            return None
        started = calendar.timegm(time.strptime(entry["procStart"], PS_START_FORMAT))
        if process_started(entry["pid"]) == started:
            out[entry["pid"]] = entry["sessionId"]
    return out


def rows() -> List[Row]:
    """Each process of the machine, by `ps`."""
    found = []
    for text in output("ps", "-ww", "-axo", "pid=,ppid=,%cpu=,etime=,lstart=,command=").splitlines():
        parts = text.split(None, 9)
        started = time.mktime(time.strptime(" ".join(parts[4:9]), PS_START_FORMAT))
        found.append(Row(int(parts[0]), int(parts[1]), float(parts[2]), parts[3], started,
                         parts[9] if len(parts) > 9 else ""))
    return found


def environment_sessions() -> Dict[int, str]:
    """The session id that the environment of each process gives."""
    found: Dict[int, str] = {}
    for text in output("ps", "-Eww", "-axo", "pid=,command=").splitlines():
        pid, _, rest = text.strip().partition(" ")
        if (m := SESSION.search(rest)) is not None:
            found[int(pid)] = m.group(1)
    return found


def nearest_session(pid: int, sessions: Dict[int, str], parents: Dict[int, int]) -> str:
    """The session id of `pid`, or of its nearest ancestor by `parents`
    that has one in `sessions`, or `NO_SESSION`."""
    seen = set()
    while pid not in seen:
        if pid in sessions:
            return sessions[pid]
        seen.add(pid)
        if pid not in parents:
            break
        pid = parents[pid]
    return NO_SESSION


def owners(table: List[Row], claude: Dict[int, str]) -> Dict[int, str]:
    """The session id of each process of `table`, given the session
    processes `claude` that the harness's file gives."""
    sessions = {**environment_sessions(), **claude}
    parents = {row.pid: row.ppid for row in table}
    return {row.pid: nearest_session(row.pid, sessions, parents) for row in table}


def usage(pid: int) -> Optional[Tuple[int, float]]:
    """The physical footprint in KiB of process `pid`, as `top` gives it in
    its `MEM` column (compressed pages count), and the CPU seconds it has
    used, or None where the process ends or belongs to another user."""
    found = RUsage()
    if LIBPROC.proc_pid_rusage(pid, RUSAGE_INFO_V0, ctypes.byref(found)) != 0:
        return None
    return found.phys_footprint // KIB, (found.user_time + found.system_time) * NUMER / DENOM / 1e9
