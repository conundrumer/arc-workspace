#!/usr/bin/env python
"""Runs a script of this record over several argument lists at once, one thread per process.

  python features_ofree_pool.py N SCRIPT 'ARGS' 'ARGS' ...

Each child's lines come through as they are written.
"""
import os
import shlex
import subprocess
import sys
import threading
import time

ME = os.path.dirname(os.path.abspath(__file__)) + '/'
env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')


def main():
    n, script, jobs = int(sys.argv[1]), sys.argv[2], sys.argv[3:]
    t0 = time.time()
    run = []
    total = len(jobs)

    def pump(p, tag):
        for x in p.stdout:
            print(tag, x, end='', flush=True)

    ended = 0
    while jobs or run:
        while jobs and len(run) < n:
            a = jobs.pop(0)
            p = subprocess.Popen([sys.executable, '-u', ME + script] + shlex.split(a), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
            threading.Thread(target=pump, args=(p, '[%s]' % a), daemon=True).start()
            run.append(p)
        for p in list(run):
            if p.poll() is not None:
                run.remove(p)
                ended += 1
                if p.returncode:
                    print('job failed with', p.returncode, flush=True)
                print('%d of %d jobs ended, %.0f s' % (ended, total, time.time() - t0), flush=True)
        time.sleep(.2)


if __name__ == '__main__':
    main()
