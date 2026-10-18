"""The instructions a process retired, as the kernel of darwin counts them
(`ri_instructions` of `proc_pid_rusage`), and the count a gate command
gives the gate.

The kernel gives no child's instructions to the process that reaps it, so
a process reads a child's count after it ends and before it reaps it
(`exited`, `retired`). The gate names a file in `COUNT_ENV` to the Python
process of each command it runs, and `sitecustomize` takes the name out
of the environment, so that the processes the command starts do not
inherit it (`count_to`). At its exit, that process writes to the file its
own count plus the count of each Souffle process it reaped (`reaped`), as
one decimal integer."""

import ctypes
import errno
import os
import sys
import threading

COUNT_ENV = "ARC_GATE_INSTRUCTIONS_FILE"
"""The environment variable that names the file a gate command's Python
process writes its count to."""

_P_PID = 1
_WEXITED = 0x04
_WNOHANG = 0x01
_WNOWAIT = 0x20
_SIGINFO_BYTES = 104
_RUSAGE_INFO_V4 = 4


class _RusageInfoV4(ctypes.Structure):
    """The head of `struct rusage_info_v4` of `<sys/resource.h>`, up to
    `ri_instructions`, and the fields after it."""
    _fields_ = [("ri_uuid", ctypes.c_uint8 * 16),
                ("ri_before", ctypes.c_uint64 * 29),
                ("ri_instructions", ctypes.c_uint64),
                ("ri_after", ctypes.c_uint64 * 5)]


_libc: ctypes.CDLL | None = None
_libproc: ctypes.CDLL | None = None


def _libs() -> tuple[ctypes.CDLL, ctypes.CDLL]:
    global _libc, _libproc
    if sys.platform != "darwin":
        raise NotImplementedError(f"no count of retired instructions on {sys.platform}")
    if _libc is None or _libproc is None:
        _libc = ctypes.CDLL("/usr/lib/libSystem.dylib", use_errno=True)
        _libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    return _libc, _libproc


def exited(pid: int, block: bool) -> bool:
    """Whether the child `pid` has ended, waiting for its end where
    `block`; the child stays unreaped."""
    libc, _ = _libs()
    info = ctypes.create_string_buffer(_SIGINFO_BYTES)
    options = _WEXITED | _WNOWAIT | (0 if block else _WNOHANG)
    while libc.waitid(_P_PID, ctypes.c_uint(pid), info, options) != 0:
        err = ctypes.get_errno()
        if err != errno.EINTR:
            raise OSError(err, os.strerror(err))
    si_pid = ctypes.c_int.from_buffer(info, 12).value
    return si_pid == pid


def retired(pid: int) -> int:
    """The instructions the process `pid`, which may be a child that ended
    and is not yet reaped, retired."""
    _, libproc = _libs()
    info = _RusageInfoV4()
    if libproc.proc_pid_rusage(pid, _RUSAGE_INFO_V4, ctypes.byref(info)) != 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))
    return info.ri_instructions


_to: str | None = None
_children = 0
_lock = threading.Lock()


def count_to(path: str) -> None:
    """Make this process write its count to `path` at its exit."""
    global _to
    import atexit
    _to = path
    atexit.register(_give)


def counting() -> bool:
    """Whether this process counts the instructions of the Souffle
    processes it reaps, as a gate command does."""
    return _to is not None


def reaped(pid: int) -> None:
    """Add the count of the child `pid`, which ended and is not yet
    reaped, to the children's count of this process."""
    global _children
    n = retired(pid)
    with _lock:
        _children += n


def _give() -> None:
    if _to is None:
        return
    with _lock:
        total = retired(os.getpid()) + _children
    with open(_to, "w") as fh:
        fh.write(f"{total}\n")
