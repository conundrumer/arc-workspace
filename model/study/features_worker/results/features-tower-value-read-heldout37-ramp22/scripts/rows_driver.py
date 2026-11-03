"""Runs build_rows.py over the read runs, at most --jobs at once, finished runs skipped. Streams a line when a run ends, with rate and ETA.

  scripts/run_heavy.py --cpus 4 --need soon <python> scripts/rows_driver.py --jobs 4
Needs rows/read/*.json (build_labels.py read) for the form counts.
"""
import argparse, glob, json, os, subprocess, sys, time
HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-tower-value-read-heldout37-ramp22/scripts'  # the data folder
sys.path.insert(0, HERE)
import common as C
ap = argparse.ArgumentParser()
ap.add_argument('--jobs', type=int, default=4)
ap.add_argument('--only', nargs='*')
ap.add_argument('--set', default='read', choices=['read', 'pass'])
a = ap.parse_args()
assert a.jobs <= 4
todo = []
if a.set == 'pass':
    runs = [(task, seed, '%s_%s_%s' % (arm, task, seed), arm) for g, seed, task, base, arm in C.pass_runs()]
else:
    runs = [(task, seed, '%s_%s' % (task, seed), None) for g, seed, task, base in C.read_runs()]
XD, LD = ('pass_x', 'pass') if a.set == 'pass' else ('read_x', 'read')
os.makedirs('%s/rows/%s' % (C.REC, XD), exist_ok=True)
for task, seed, stem, arm in runs:
    if a.only and task not in a.only:
        continue
    p = '%s/rows/%s/%s.progress.json' % (C.REC, XD, stem)
    if os.path.exists(p) and json.load(open(p)).get('done'):
        continue
    info = json.load(open('%s/rows/%s/%s.json' % (C.REC, LD, stem)))['info']
    todo.append((info['forms'], stem, seed, task, arm))
todo.sort(key=lambda x: -x[0])
total = sum(x[0] for x in todo)
print('runs to do', len(todo), 'forms', total, flush=True)
t0 = time.time()
running, done_forms, done = [], 0, 0
while todo or running:
    while todo and len(running) < a.jobs:
        f, stem, seed, task, arm = todo.pop(0)
        running.append((subprocess.Popen([HERE + '/rt_r1.sh', 'build_rows.py', task, seed, '1000000'] + ([arm] if arm else []), stdout=subprocess.DEVNULL, stderr=open('%s/rows/%s/%s.err' % (C.REC, XD, stem), 'w')), f, stem, ''))
    time.sleep(1)
    for item in list(running):
        if item[0].poll() is not None:
            running.remove(item)
            done += 1
            done_forms += item[1]
            el = time.time() - t0
            rate = done_forms / el
            left = total - done_forms
            print('%s exit %s | %d runs done, %.0f forms/s, eta %.0f s' % (item[2], item[0].returncode, done, rate, left / rate), flush=True)
