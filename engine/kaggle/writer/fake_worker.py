#!/usr/bin/env python3
"""A worker with a fault picked by the task's first train input: fault test data for supervisor.py."""
import argparse
import json
import os
import sys
import time

from supervisor import FULL_EXIT

ap = argparse.ArgumentParser()
for k in ('task', 'out', 'beat', 'seconds', 'seed', 'rss-limit-mib'):
    ap.add_argument('--' + k)
a = ap.parse_args()
task = json.load(open(a.task))
mode = task['train'][0]['mode']
grid = [[int(a.seed) % 10]]
good = json.dumps(dict(attempts=[[grid] for _ in task['test']], score=1, size=1)) + '\n'
out = open(a.out, 'a')
out.write(good)
out.flush()
end = time.monotonic() + float(a.seconds)


def best(value):
    out.write(json.dumps(dict(attempts=[[[[value]]] for _ in task['test']], score=2, size=1)) + '\n')
    out.flush()


if mode == 'bad bank':  # each worker that finds a bank file dies at once, as one would on a bank that ends it
    if os.path.exists(a.out + '.bank') or not os.path.exists(a.out + '.once'):
        open(a.out + '.bank', 'w').close()
        open(a.out + '.once', 'w').close()
        os.abort()
    best(7)
if mode == 'renew':
    if os.environ.get('RENEWED'):
        best(8)
    else:
        os.environ['RENEWED'] = '1'
        argv = list(sys.orig_argv)
        argv[argv.index('--seconds') + 1] = str(float(a.seconds) - 3)  # the time left, as a real renewal passes it
        os.execv(sys.executable, [sys.executable] + argv[1:])
if mode == 'full':  # the bank has reached its bound: the bank file stays and the task needs no more workers
    best(9)
    open(a.out + '.bank', 'w').close()
    os.utime(a.beat)
    os._exit(FULL_EXIT)
if mode == 'crash':
    os.abort()
if mode == 'exception':
    raise RuntimeError('import failed')
if mode == 'memory':
    keep = []
    while True:
        keep.append(bytearray(64 << 20))
        for i in range(0, len(keep[-1]), 4096):
            keep[-1][i] = 1
        os.utime(a.beat)
        time.sleep(0.02)
if mode == 'hang':
    time.sleep(10 ** 6)
if mode == 'bad grid':
    out.write(json.dumps(dict(attempts=[[[[99, -1]], [[1, 2], [3]], 'x', None]])) + '\n{"attempts": [[[[1')
    out.flush()
    os._exit(0)
if mode == 'no candidate':
    out.truncate(0)
    out.close()
while time.monotonic() < end:
    os.utime(a.beat)
    time.sleep(0.2)
