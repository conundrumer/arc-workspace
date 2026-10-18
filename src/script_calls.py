"""The record of the calls of the scripts under `scripts/` of the main
tree: one JSON line per call, in a file per UTC day under
`.cache/script-calls/` of the main tree. `sitecustomize` starts the record
of a call, `record` writes its line at the call's end, and `read` gives the
lines `scripts/check_script_calls.py` judges.

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
         '"peak": {peak}, "session": "{session}"}}\n')

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


_started: tuple[str, str, float, float] | None = None
"""The day file, the key, the start time and the monotonic clock at the
start of this process's call, once `start` started its record."""


def start(tree: str, script: str, args: list[str]) -> None:
    """Starts the record of this process's call of the script `script` of
    the main tree `tree` with `args`, where its file name is one a line can
    hold."""
    global _started
    name = os.path.basename(script)
    if name and all(c in _NAME for c in name):
        now = time.time()
        _started = (day_file(os.path.join(tree, RECORDS), now), key(name, args), now, time.monotonic())


def grew(figure: float, usual: float, margin: float) -> bool:
    """Whether `figure` grew past `usual`: it is at least `CPU_RATIO` times
    `usual` plus `margin`."""
    return figure >= CPU_RATIO * usual + margin


def cpu_seconds() -> float:
    """The CPU seconds of this process and of its children it has waited
    for, user and system."""
    return sum(r.ru_utime + r.ru_stime for r in (resource.getrusage(resource.RUSAGE_SELF),
                                                 resource.getrusage(resource.RUSAGE_CHILDREN)))


def _peak() -> int:
    rss = max(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
    return rss * 1024 if _KIB else rss


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
    line = _LINE.format(key=k, start=begun, wall=time.monotonic() - clock, cpu=cpu_seconds(),
                        peak=_peak(), session=os.environ.get(SESSION_ENV, ""))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line.encode())
    finally:
        os.close(fd)


class Call:
    """One line of the record."""
    __slots__ = ("key", "start", "wall", "cpu", "peak", "session")

    def __init__(self, key: str, start: float, wall: float, cpu: float, peak: int,
                 session: str) -> None:
        self.key, self.start, self.wall, self.cpu, self.peak, self.session = (
            key, start, wall, cpu, peak, session)


def read(records: str, since: float) -> list[Call]:
    """The calls `records` holds that started at or after `since`, in the
    order of their start."""
    import json
    first = os.path.basename(day_file(records, since))
    calls: list[Call] = []
    for name in sorted(os.listdir(records)) if os.path.isdir(records) else []:
        if name.endswith(SUFFIX) and name >= first:
            with open(os.path.join(records, name)) as f:
                calls += [Call(**json.loads(text)) for text in f]
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
