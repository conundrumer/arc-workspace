"""Where ARC_CPU_CLOCK is 1, time.monotonic gives this process's CPU seconds plus the seconds it has blocked on a scoring server (time.blocked_seconds, which the server's client adds to), so a worker's deadlines (--seconds, CLAUSE_SECONDS, the
progress and save intervals) count that time and not wall-clock time. A process keeps its CPU count across execv, and its blocked seconds through ARC_BLOCKED_SECONDS, so a renewal goes on from the same count.

Where ARC_WORK_CLOCK is a number R, time.monotonic gives the engine's work so far (arclog.work_total: the units every request of the process charged) divided by R, so the same deadlines count the
engine's work, and a job does the same work on any machine and under any load. Past ARC_WORK_GUARD CPU seconds of the process it gives a time past every deadline, so the guard ends a job whose work
stops growing. The count starts again at a renewal's execv, where the worker passes its time left as --seconds."""
import os
import time

if os.environ.get('ARC_WORK_CLOCK'):
    import arclog  # noqa: E402  (first, so the clock never changes units)

    _rate = float(os.environ['ARC_WORK_CLOCK'])
    _guard = float(os.environ.get('ARC_WORK_GUARD', 'inf'))
    _cpu = time.process_time
    _work = arclog.work_total
    time.blocked_seconds = 0.0

    def _work_clock():
        return 1e18 if _cpu() > _guard else _work() / _rate

    time.monotonic = _work_clock
elif os.environ.get('ARC_CPU_CLOCK') == '1':
    time.blocked_seconds = float(os.environ.get('ARC_BLOCKED_SECONDS', 0.0))
    _cpu = time.process_time
    time.monotonic = lambda: _cpu() + time.blocked_seconds
