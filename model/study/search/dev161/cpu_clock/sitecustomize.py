"""Where ARC_CPU_CLOCK is 1, time.monotonic gives this process's CPU seconds plus the seconds it has blocked on a scoring server (time.blocked_seconds, which the server's client adds to), so a worker's deadlines (--seconds, CLAUSE_SECONDS, the
progress and save intervals) count that time and not wall-clock time. A process keeps its CPU count across execv, and its blocked seconds through ARC_BLOCKED_SECONDS, so a renewal goes on from the same count."""
import os
import time

if os.environ.get('ARC_CPU_CLOCK') == '1':
    time.blocked_seconds = float(os.environ.get('ARC_BLOCKED_SECONDS', 0.0))
    _cpu = time.process_time
    time.monotonic = lambda: _cpu() + time.blocked_seconds
