"""Run a policy beside the bundled policy on the bundle's pinned code, then print the pair and the pass rule. Both arms start together, so they share one load.

  arm.py NAME POLICY_DIR [--env K=V ...] [--seconds 60] [--tasks 40|10] [--shards 2] [--base BASE_DIR] [--task-file FILE --points FILE]

Results go to arm/runs/NAME/ and arm/runs/NAME-base/. Each task is its own process, and a rerun skips finished tasks. A table prints after each pair of tasks finishes and at the end.
"""
import argparse, json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ARM = HERE + '/../policy2/arm'
BASE = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/ede6795c-2b6f-4633-a6da-08e90de33bc4/scratchpad/policy1'
ap = argparse.ArgumentParser()
ap.add_argument('name'); ap.add_argument('policy')
ap.add_argument('--env', action='append', default=[])
ap.add_argument('--seconds', type=int, default=60)
ap.add_argument('--tasks', type=int, default=40, choices=(40, 10))
ap.add_argument('--shards', type=int, default=2)
ap.add_argument('--base', default=BASE)
ap.add_argument('--task-file'); ap.add_argument('--points')
a = ap.parse_args()
os.makedirs(HERE + '/runs', exist_ok=True)
order = open(ARM + '/order.txt').read().split()
tasks = open(a.task_file).read().split() if a.task_file else order if a.tasks == 40 else order[0::4]
if a.points:
    os.environ['POINTS'] = a.points
env = dict(os.environ, **dict(x.split('=', 1) for x in a.env))
procs = []
for k in range(a.shards):
    f = f'{HERE}/runs/{a.name}.t{k}.txt'
    open(f, 'w').write('\n'.join(tasks[k::a.shards]) + '\n')
    for out, pol, e in ((f'../../arm/runs/{a.name}', a.policy, env), (f'../../arm/runs/{a.name}-base', a.base, os.environ)):
        log = open(f'{HERE}/runs/{os.path.basename(out)}.{k}.log', 'a')
        procs.append(subprocess.Popen([ARM + '/run_arm_p.sh', out, pol, str(a.seconds), f], env=e, stdout=log, stderr=log))
print('started', a.name, 'tasks', len(tasks), 'seconds', a.seconds, 'ETA minutes', round(len(tasks) * a.seconds / a.shards / 60 * 1.1), flush=True)
pair = [sys.executable, ARM + '/pair_p.py', f'../../arm/runs/{a.name}-base', f'../../arm/runs/{a.name}']
last = -1
while any(p.poll() is None for p in procs):
    time.sleep(30)
    n = len([x for x in os.listdir(f'{HERE}/runs/{a.name}') if x.endswith('.done.json')]) if os.path.isdir(f'{HERE}/runs/{a.name}') else 0
    if n // 10 != last // 10 and n:
        last = n
        print(subprocess.run(pair, capture_output=True, text=True).stdout, flush=True)
print(subprocess.run(pair, capture_output=True, text=True).stdout, flush=True)
print('rule: pass where non-DET at equal samples is higher, tasks better are at least twice tasks worse, and DET is lower by at most 2.', flush=True)
