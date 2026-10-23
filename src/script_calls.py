"""The record of the calls of the scripts under `scripts/` of the main
tree: one JSON line per call, in a file per UTC day under
`.cache/script-calls/` of the main tree. `sitecustomize` starts the record
of a call, `record` writes its line at the call's end, and `read` gives the
lines `scripts/check_script_calls.py` judges. A line gives as well the
reads of `scripts/state_reads.py` during whose run the call's peak rose
most (`enter`, `leave`).

Every call of a script of the main tree imports this module, so it imports
no module that the interpreter's start has not imported but `resource`,
and `json` only in `read`. A line is one `os.write` on a file opened with
`O_APPEND`, so the concurrent calls of every session write whole lines."""

import os
import resource
import sys
import time

RECORDS = os.path.join(".cache", "script-calls")
"""The directory of the day files, under the main tree."""

WINDOW_SECONDS = 7 * 24 * 3600
"""How long the record keeps a day file, and the window of earlier calls
the check judges recent calls against."""

CPU_RATIO = 2
"""The factor by which a figure of the work of a call or a command grows
past its usual one (`grew`)."""
CPU_MARGIN = 1.0
"""The margin in CPU seconds by which a call's CPU time grows past its
usual one."""
INSTRUCTIONS_MARGIN = 10 ** 10
"""The margin in instructions retired by which a gate command's count
grows past its accepted one."""

DAY_FORM = "%Y-%m-%d"
SUFFIX = ".jsonl"

SESSION_ENV = "CLAUDE_CODE_SESSION_ID"

_LINE = ('{{"key": "{key}", "start": {start:.3f}, "wall": {wall:.3f}, "cpu": {cpu:.3f}, '
         '"peak": {peak}, "session": "{session}", "lifts": [{lifts}], "retained": {retained}, '
         '"queued": {queued:.3f}, "reads": {reads}, "footprint": {footprint}}}\n')

_KIB = sys.platform != "darwin"
"""Whether `ru_maxrss` counts KiB, as on Linux, in place of bytes, as on
darwin."""

_LOWER = frozenset("abcdefghijklmnopqrstuvwxyz")
_NAME = _LOWER | frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-")
"""The characters of a script file name that a line can hold as it
stands."""


def is_word(arg: str) -> bool:
    """Whether `arg` is a bare word, `[a-z][a-z-]*`, which a call's key
    holds where it is the first argument."""
    return arg[:1] in _LOWER and all(c in _LOWER or c == "-" for c in arg)


def key(script: str, args: list[str]) -> str:
    """The key of a call of the script file `script` with `args`: its
    file name, and its first argument where that is a bare word."""
    if args and is_word(args[0]):
        return f"{script} {args[0]}"
    return script


_cpu_started = 0.0
_retained = False
_queued = 0.0
"""The seconds this process's request waited in the resident's queue."""
_reads = 0
"""The count of the reads of `watched` that this process's call made."""


_started: tuple[str, str, float, float] | None = None
"""The day file, the key, the start time and the monotonic clock at the
start of this process's call, once `start` started its record."""


def start(tree: str, script: str, args: list[str]) -> None:
    """Starts the record of this process's call of the script `script` of
    the main tree `tree` with `args`, where its file name is one a line can
    hold."""
    global _started, _queued, _reads
    _queued, _reads = 0.0, 0
    name = os.path.basename(script)
    if name and all(c in _NAME for c in name):
        now = time.time()
        _started = (day_file(os.path.join(tree, RECORDS), now), key(name, args), now, time.monotonic())


def start_service(tree: str) -> None:
    """Keep startup CPU accounting when a service runs in a linked checkout too."""
    if _started is None:
        start(tree, "operate_service.py", ["startup"])


def count_read() -> None:
    """Count one read of `watched` in this process's call."""
    global _reads
    _reads += 1


def start_request(tree: str, script: str, args: list[str], queued: float = 0.0) -> None:
    """Start a resident request's CPU delta and retained process peak record;
    `queued` is the seconds the request waited in the resident's queue."""
    global _cpu_started, _retained, _credited, _queued
    record()
    start(tree, script, args)
    _queued = queued
    _cpu_started = cpu_seconds()
    _retained = True
    _lifts.clear()
    _credited = 0


def grew(figure: float, usual: float, margin: float) -> bool:
    """Whether `figure` grew past `usual`: it is at least `CPU_RATIO` times
    `usual` plus `margin`."""
    return figure >= CPU_RATIO * usual + margin


def cpu_seconds() -> float:
    """The CPU seconds of this process and of its children it has waited
    for, user and system."""
    return sum(r.ru_utime + r.ru_stime for r in (resource.getrusage(resource.RUSAGE_SELF),
                                                 resource.getrusage(resource.RUSAGE_CHILDREN)))


def release_free_memory() -> int:
    """Return to the system the free memory the allocator holds mapped in
    this process, and give the bytes returned: darwin's `malloc_zone_pressure_relief`
    over every zone, 0 elsewhere."""
    if sys.platform != "darwin":
        return 0
    import ctypes
    relief = ctypes.CDLL(None).malloc_zone_pressure_relief
    relief.argtypes, relief.restype = [ctypes.c_void_p, ctypes.c_size_t], ctypes.c_size_t
    return relief(None, 0)


def footprint() -> int:
    """The bytes of memory this process holds now: its physical footprint on
    darwin, its resident set on Linux, and 0 where neither can be read."""
    if sys.platform == "darwin":
        import ctypes
        import ctypes.util

        class Usage(ctypes.Structure):
            _fields_ = [("uuid", ctypes.c_ubyte * 16)] + [(f"f{i}", ctypes.c_uint64) for i in range(1, 19)]
            # RUSAGE_INFO_V2 fields from ri_uuid on; f8 is ri_phys_footprint.
        usage = Usage()
        libproc = ctypes.CDLL(ctypes.util.find_library("proc"))
        if libproc.proc_pid_rusage(os.getpid(), 2, ctypes.byref(usage)) != 0:
            return 0
        return usage.f8
    try:
        with open("/proc/self/statm") as f:
            return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError):
        return 0


def peak() -> int:
    """The peak memory in bytes of this process and of its children it has
    waited for."""
    rss = max(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
    return rss * 1024 if _KIB else rss


LIFTS = 3
"""How many reads a line gives in `lifts`."""

_lifts: dict[str, int] = {}
"""The rise of the peak credited to each read of this process, by the
read's name, summed over its runs."""
_credited = 0
"""The sum of the rises credited to reads so far."""


def enter() -> tuple[int, int]:
    """The peak and the sum of the rises credited so far, at the start of
    the run of a read, which `leave` takes at its end."""
    return peak(), _credited


def leave(name: str, entered: tuple[int, int]) -> None:
    """Credits the read `name` with the rise of the peak since `entered`,
    less the rises credited since then, which went to the reads whose runs
    stand inside its run."""
    global _credited
    before, credited = entered
    rise = peak() - before - (_credited - credited)
    if rise > 0:
        _lifts[name] = _lifts.get(name, 0) + rise
        _credited += rise


def lifts() -> list[tuple[str, int]]:
    """The `LIFTS` reads of this process with the largest credits, each
    with its credit, largest first."""
    return sorted(_lifts.items(), key=lambda lift: (-lift[1], lift[0]))[:LIFTS]


def day_file(records: str, t: float) -> str:
    return os.path.join(records, time.strftime(DAY_FORM, time.gmtime(t)) + SUFFIX)


def record() -> None:
    """Writes the line of this process's call, where `start` started its
    record and no line of it is written."""
    global _started
    s, _started = _started, None
    if s is None:
        return
    path, k, begun, clock = s
    line = _LINE.format(key=k, start=begun, wall=time.monotonic() - clock, cpu=cpu_seconds() - _cpu_started,
                        peak=peak(), retained="true" if _retained else "false", session=os.environ.get(SESSION_ENV, ""),
                        lifts=", ".join(f'["{name}", {rise}]' for name, rise in lifts()),
                        queued=_queued, reads=_reads,
                        footprint=footprint() if _retained else 0)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line.encode())
    finally:
        os.close(fd)


class Call:
    """One line of the record. A line written before the record gave
    `lifts` has none. `retained` identifies a resident process peak.
    `queued` is the seconds a resident request waited in the queue, and
    `reads` the count of its reads of `watched`, and `footprint` the bytes
    the resident held at the request's end; a line written before the
    record gave them has 0."""
    __slots__ = ("key", "start", "wall", "cpu", "peak", "session", "lifts", "retained", "queued", "reads", "footprint")

    def __init__(self, key: str, start: float, wall: float, cpu: float, peak: int,
                 session: str, lifts: tuple[tuple[str, int], ...] = (), retained: bool = False,
                 queued: float = 0.0, reads: int = 0, footprint: int = 0) -> None:
        self.retained = retained
        self.queued, self.reads, self.footprint = queued, reads, footprint
        self.key, self.start, self.wall, self.cpu, self.peak, self.session, self.lifts = (
            key, start, wall, cpu, peak, session, lifts)


def read(records: str, since: float) -> list[Call]:
    """The calls `records` holds that started at or after `since`, in the
    order of their start."""
    import json
    first = os.path.basename(day_file(records, since))
    calls: list[Call] = []
    for name in sorted(os.listdir(records)) if os.path.isdir(records) else []:
        if name.endswith(SUFFIX) and name >= first:
            with open(os.path.join(records, name)) as f:
                for text in f:
                    line = json.loads(text)
                    line["lifts"] = tuple((read_name, rise)
                                          for read_name, rise in line.get("lifts", ()))
                    calls.append(Call(**line))
    return sorted((c for c in calls if c.start >= since), key=lambda c: c.start)


def prune(records: str, before: float) -> list[str]:
    """Deletes the day files of the days before the day of `before`, and
    returns their paths."""
    first = os.path.basename(day_file(records, before))
    gone = [os.path.join(records, n) for n in sorted(os.listdir(records))
            if n.endswith(SUFFIX) and n < first] if os.path.isdir(records) else []
    for path in gone:
        os.remove(path)
    return gone
