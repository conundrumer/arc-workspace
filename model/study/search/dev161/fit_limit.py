"""Sets a dev_run.py run's job limit to fit the machine, every --every seconds, from --start (HHMM, local time) on.

    fit_limit.py RUN_FOLDER [--start 2245] [--every 120] [--min 3] [--max 12] [--job-gib 1.5]

The limit is the jobs running now plus the idle cores (the idle share of the second sample of `top -l 2 -n 0` times the core count, less
one), held under the jobs that the free memory fits at --job-gib each. It prints each change, and ends when the run's results cover
every job (no worker of the run is left for 10 minutes).
"""
import argparse
import os
import re
import subprocess
import time
from pathlib import Path


def idle_cores():
    out = subprocess.run(['top', '-l', '2', '-n', '0'], capture_output=True, text=True).stdout
    idle = [float(x) for x in re.findall(r'([\d.]+)% idle', out)]
    return (idle[-1] if idle else 0.0) / 100 * os.cpu_count()


def free_gib():
    out = subprocess.run(['vm_stat'], capture_output=True, text=True).stdout
    page = int(re.search(r'page size of (\d+)', out).group(1))
    pages = sum(int(re.search(r'%s:\s+(\d+)' % k, out).group(1)) for k in ('Pages free', 'Pages inactive', 'Pages speculative'))
    return pages * page / 2 ** 30


def running(run):
    out = subprocess.run(['pgrep', '-f', 'kaggle_worker.py.*%s/jobs' % run.name], capture_output=True, text=True).stdout
    return len(out.split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run')
    ap.add_argument('--start', default='2245')
    ap.add_argument('--every', type=int, default=120)
    ap.add_argument('--min', type=int, default=3)
    ap.add_argument('--max', type=int, default=12)
    ap.add_argument('--job-gib', type=float, default=1.5)
    a = ap.parse_args()
    run, quiet = Path(a.run), 0
    while time.strftime('%H%M') < a.start and time.strftime('%H%M') >= '1200':
        time.sleep(30)
    while quiet < 600:
        n = running(run)
        quiet = quiet + a.every if n == 0 else 0
        want = n + int(idle_cores()) - 1
        fits = n + int(free_gib() / a.job_gib)
        limit = max(a.min, min(a.max, want, fits))
        try:
            old = int((run / 'limit').read_text())
        except (OSError, ValueError):
            old = None
        if limit != old:
            (run / 'limit').write_text('%d\n' % limit)
            print('%s limit %s -> %d (running %d, idle cores %.1f, free %.1f GiB)' % (time.strftime('%H:%M'), old, limit, n, idle_cores(), free_gib()), flush=True)
        time.sleep(a.every)


if __name__ == '__main__':
    main()
