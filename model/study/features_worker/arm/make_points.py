"""Write a points file for the evaluation tasks in the test-row store that are outside the Kaggle record set, with each task's smallest gold, and the task list. These tasks trained no live fold.

  make_points.py OUT_JSON OUT_TASKS [rec]    with rec: the Kaggle record set instead
"""
import collections, glob, json, os, sys, time
STORE = 'work/lm/data-study/feat-exp/fstore-gen3/points-t'
EVAL = set(open('data/upstream/arc-agi-2/data/evaluation.txt').read().split())
rec = {os.path.basename(f)[:8] for f in glob.glob('work/lm/data-study/sampler/runs/kaggle-v5/record/*.zst')}
idx = collections.defaultdict(list)
for e in os.scandir(STORE):
    if not e.name.endswith('.building') and e.name[:8] in (rec if len(sys.argv) > 3 else EVAL - rec):
        idx[e.name[:8]].append(e.path)
out = []; t0 = time.time()
for t, ds in sorted(idx.items()):
    best = {}
    for d in ds:
        c = json.load(open(d + '/point.json'))['case']
        if c not in best:
            best[c] = open(d + '/gold.arclog').read()
    g = min(best.values(), key=lambda x: len(x.strip().split('\n')))
    out.append(dict(task=t, gold_sexp=g))
    print(t, len(ds), 'points', len(best), 'cases', len(g.strip().split('\n')), 'forms', round(time.time() - t0), 's', flush=True)
json.dump(out, open(sys.argv[1] + '.new', 'w')); os.replace(sys.argv[1] + '.new', sys.argv[1])
out.sort(key=lambda s: len(s['gold_sexp'].strip().split('\n')))
open(sys.argv[2], 'w').write('\n'.join(s['task'] for s in out) + '\n')
