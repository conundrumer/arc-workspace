"""Exact picks of every opening of the 26 hour runs, from the process seeds. Streams and resumes per run.

  python -I sampler-picks-cache.py SET SECONDS     (SET: hour or base)

Writes rows/sampler-picks-<arm>-<task>.npz (per opening: visit index, draw d0, alive nodes, the 5 scored picks, the least-used pick) and replay-checks.jsonl (one line per run).
"""
import json, os, sys, time
sys.dont_write_bytecode = True
HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop/'  # the data folder
sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop')
sys.path.insert(0, HERE)
import numpy as np
import poolrun, common2 as C2, sampler_replay as SR

SET = sys.argv[1]
LIMIT = float(sys.argv[2]) if len(sys.argv) > 2 else 25
ARMS = C2.SETS[SET]['arms']
TASKS = C2.SETS[SET]['tasks']
T0 = time.time()
ck = HERE + SET + '-sampler-replay-checks.jsonl'
done = {(json.loads(l)['arm'], json.loads(l)['task']) for l in open(ck)} if os.path.exists(ck) else set()
fh = open(ck, 'a')
ONLY = os.environ.get('ONLY')  # ARM/TASK: only that run (a pilot)
for arm, base in zip(ARMS, (0, 1000)):
    for task in TASKS:
        if (arm, task) in done or (ONLY and ONLY != '%s/%s' % (arm, task)):
            continue
        if time.time() - T0 > LIMIT:
            print('stopped at the limit', flush=True)
            sys.exit()
        R = poolrun.Run(SET, arm, task, labels=False)
        o = SR.replay(R, base)
        all_ops = o['openings']
        np.savez_compressed(HERE + 'rows/sampler-picks-%s-%s.npz' % (arm, task),
                            v=np.array([p['v'] for p in all_ops], np.int32), d0=np.array([p['d0'] for p in all_ops], np.int64), n=np.array([p['n'] for p in all_ops], np.int32),
                            best=np.array([(p['best'] + [-1] * 5)[:5] for p in all_ops], np.int32), rest=np.array([(p['rest'] + [-1])[0] for p in all_ops], np.int32))
        diff = int((o['uses'] != R.uses_end).sum())
        fh.write(json.dumps(dict(arm=arm, task=task, blocks=len(o['seeds']), seed_first=o['seeds'][0], seed_last=o['seeds'][-1], failed=o.get('failed'), openings=sum(p['v'] >= 0 for p in all_ops), fids_equal=o['ok'], fids_differ=len(o['bad']), refused_scopes=o['refused'],
                                 resume_flag_with_new_scope=o['flip'], uses_recorded=int(R.uses_end.sum()), uses_replayed=int(o['uses'].sum()), nodes_with_other_uses=diff, nodes=R.n)) + '\n')
        fh.flush()
print('done', round(time.time() - T0, 1), flush=True)
