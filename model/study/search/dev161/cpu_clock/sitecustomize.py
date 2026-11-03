"""Where ARC_CPU_CLOCK is 1, time.monotonic gives this process's CPU seconds, so a worker's deadlines (--seconds, CLAUSE_SECONDS, the
progress and save intervals) count CPU time and not wall-clock time. A process keeps its CPU count across execv, so a renewal goes on
from the same count."""
import os
import time

if os.environ.get('ARC_CPU_CLOCK') == '1':
    time.monotonic = time.process_time
