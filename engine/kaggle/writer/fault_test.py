#!/usr/bin/env python3
"""Runs supervisor.py with fake_worker.py on one task per fault, and checks that the submission is valid. Then checks a task that ends by FULL_EXIT, and the share line. A failed check raises."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import supervisor as V  # noqa: E402

MODES = ['ok', 'crash', 'exception', 'memory', 'hang', 'bad grid', 'no candidate', 'bad bank', 'renew']
d = tempfile.mkdtemp()
tasks = {'task%d' % i: dict(train=[dict(input=[[1]], output=[[2]], mode=m)], test=[dict(input=[[3, i]]), dict(input=[[4]])]) for i, m in enumerate(MODES)}
tasks['bad input'] = dict(train=[dict(input=[[1]], output=[[2]], mode='ok')], test=[dict(input=[])])
path = d + '/c.json'
json.dump(tasks, open(path, 'w'))
sub = d + '/submission.json'
SECONDS = 40
p = subprocess.Popen([sys.executable, HERE + '/supervisor.py', '--challenges', path, '--submission', sub, '--work', d + '/work', '--seconds', str(SECONDS),
                      '--workers', '10', '--rss-limit-mib', '300', '--stale-seconds', '12', '--worker-cmd', '%s %s/fake_worker.py' % (sys.executable, HERE)],
                     stdout=subprocess.PIPE, text=True)
time.sleep(1)
assert os.path.exists(sub), 'no fallback at the start'
outp = p.communicate(timeout=SECONDS + 100)[0]
print(outp)
assert p.returncode == 0, p.returncode
s = json.load(open(sub))
assert set(s) == set(tasks)
for t, e in s.items():
    assert len(e) == len(tasks[t]['test'])
    for x in e:
        assert V.valid_grid(x['attempt_1']) and V.valid_grid(x['attempt_2']), (t, x)
assert s['task0'][0]['attempt_1'] == [[1]], s['task0']       # a healthy worker's candidate is used
assert s['task1'][0]['attempt_1'] != [[3, 1]]                # a crash keeps what the worker wrote
assert s['task6'][0]['attempt_1'] == [[3, 6]]                # no candidate: the fallback
assert s['task4'][0]['attempt_1'] == [[1]] and 'no heartbeat' in outp, 'hang'
assert 'RSS' in outp, 'memory'
assert s['task7'][0]['attempt_1'] == [[7]], 'a bank file that ends each worker is removed'
assert s['task8'][0]['attempt_1'] == [[8]] and 'worker of task8 exited' not in outp, 'a worker that replaces itself stays one job'
for mode, i in (('crash', 1), ('exception', 2)):
    assert 'worker of task%d exited' % i in outp, mode

# A worker that exits FULL_EXIT ends its task: no respawn, no death, its slot goes to the next task, and its candidates reach the submission.
FULL_SECONDS = 24  # past MIN_LIFE_SECONDS, or no worker starts
tasks = {name: dict(train=[dict(input=[[1]], output=[[2]], mode=name)], test=[dict(input=[[3]])]) for name in ('full', 'ok')}
path, sub = d + '/c2.json', d + '/submission2.json'
json.dump(tasks, open(path, 'w'))
got = subprocess.run([sys.executable, HERE + '/supervisor.py', '--challenges', path, '--submission', sub, '--work', d + '/work2', '--seconds', str(FULL_SECONDS),
                      '--workers', '1', '--rss-limit-mib', '300', '--worker-cmd', '%s %s/fake_worker.py' % (sys.executable, HERE)], stdout=subprocess.PIPE, text=True, timeout=FULL_SECONDS + 100)
print(got.stdout)
assert got.returncode == 0, got.returncode
assert 'deaths 0 kills 0' in got.stdout, 'FULL_EXIT is no death'
assert 'task full lives 1 candidates' in got.stdout, 'FULL_EXIT has no respawn'
assert 'task ok allotted' in got.stdout and 'task ok lives 1 candidates' in got.stdout, 'the slot goes to the next task'
assert float(got.stdout.split('task ok allotted ')[1].split()[0]) > FULL_SECONDS / 2, 'the next task gets the time that the full task left'
assert json.load(open(sub))['full'][0]['attempt_1'] == [[9]], 'the candidates of a full task reach the submission'
assert os.path.exists(d + '/work2/full.out.jsonl.bank'), 'the bank file stays'


class Clock:
    now = 0.0

    def monotonic(self):
        return self.now

    def __getattr__(self, name):
        return getattr(time, name)


def shares(workers, seconds, count, early):
    """Runs start_next on count tasks with no process and a set clock. A job's worker ends at its end, or at once where its task is in early. Gives (allotted seconds of each task, time of each start)."""
    clock = Clock()
    real, V.time = V.time, clock
    try:
        args = argparse.Namespace(seconds=seconds, workers=workers, work=tempfile.mkdtemp(dir=d), rss_limit_mib=0)
        sup = V.Supervisor(args, {'t%d' % i: {} for i in range(count)})
        sup.safe_spawn = lambda job: None
        got = {}
        while sup.queue or sup.running:
            before = {j.tid for j in sup.running}
            sup.start_next()
            for j in sup.running:
                if j.tid not in before:
                    got[j.tid] = (j.end - clock.now, clock.now)
                    if j.tid in early:
                        j.end = clock.now + 1
            if not sup.running:
                break
            clock.now = min(j.end for j in sup.running)
            sup.running = [j for j in sup.running if j.end > clock.now]
        return got
    finally:
        V.time = real


got = shares(30, 1800, 46, ())
assert len(got) == 46 and sum(s for s, _ in got.values()) <= 30 * 1800 + 1e-6, sum(s for s, _ in got.values())
assert all(s > 0 for s, _ in got.values()), 'a late task has a share'
got = shares(4, 1000, 12, {'t1', 't5', 't9'})
late = max(got.values(), key=lambda x: x[1])
assert len(got) == 12 and late[0] > 0, late
print('FAULT TEST PASSED')
