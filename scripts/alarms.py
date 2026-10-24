"""The alarms of a process, over the one SIGALRM and the one ITIMER_REAL timer
it has.

An `Alarm` has a callback and a due, a `time.monotonic()` time, and its owner
sets and clears it. Each alarm comes at its due, whatever other alarm is set
or cleared while it is due: the handler takes the alarm whose due came first out of the set
and runs its callback, and, once that callback returns or raises, sets the
timer for the earliest due left, at once where that due has passed, or
cancels the timer where none is left. An alarm set or cleared while a callback
runs takes effect then, so no callback runs inside another. A set and a clear
run with SIGALRM blocked, so the handler never meets the set of alarms
mid-change. A forked child holds no alarm of its parent.

No other code in a process sets the SIGALRM handler or the timer.
"""

import contextlib
import os
import signal
import time
from collections.abc import Callable, Iterator
from types import FrameType


class Alarm:
    """An alarm that runs `callback` at its due, once each time it is set."""

    def __init__(self, callback: Callable[[], None]) -> None:
        self.callback = callback

    def set(self, due: float) -> None:
        """Have the alarm come at the monotonic time `due`, in place of its due, if any."""
        with blocked():
            _set[self] = due
            _timer()

    def clear(self) -> None:
        """Have the alarm not come."""
        with blocked():
            _set.pop(self, None)
            _timer()


_set: dict[Alarm, float] = {}
"""The alarms that are set, each with its due, a `time.monotonic()` time."""

_running = False
"""Whether the handler runs a callback."""


@contextlib.contextmanager
def blocked() -> Iterator[None]:
    """Hold SIGALRM off for the block, so that an alarm that comes meanwhile comes after it."""
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM})
    try:
        yield
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


def _timer() -> None:
    """Set the timer for the earliest due of the set, at once where it has passed,
    or cancel it where the set is empty; do nothing while a callback runs."""
    if _running:
        return
    if signal.getsignal(signal.SIGALRM) is not _handle:
        signal.signal(signal.SIGALRM, _handle)
    signal.setitimer(signal.ITIMER_REAL,
                     max(min(_set.values()) - time.monotonic(), 0.001) if _set else 0)


def _handle(_signum: int, _frame: FrameType | None) -> None:
    global _running
    if _running:
        return
    now = time.monotonic()
    came = [alarm for alarm, due in _set.items() if due <= now]
    _running = True
    try:
        if came:
            first = min(came, key=_set.__getitem__)
            del _set[first]
            first.callback()
    finally:
        with blocked():
            _running = False
            _timer()


def _forget() -> None:
    """In a forked child: hold no alarm of the parent."""
    global _running
    _set.clear()
    _running = False


os.register_at_fork(after_in_child=_forget)
