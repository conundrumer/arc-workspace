"""Write the gold programs of the tasks outside the evaluation set, one per task, and the list of their RULE, DET and INIT forms in a fixed random order. Each program is the smallest gold among up to 60 points of the task.

  features_corpus_points.py STORE EXCLUDE_JSON OUT_POINTS OUT_FORMS
"""
import collections, hashlib, json, os, sys, time
store, excl, out_p, out_f = sys.argv[1:5]
EVAL = set(open('data/upstream/arc-agi-2/data/evaluation.txt').read().split()) | {x['task'] for x in json.load(open(excl))}
idx = collections.defaultdict(list)
for e in os.scandir(store):
    if not e.name.endswith('.building') and not e.name.startswith('.') and e.name[:8] not in EVAL:
        idx[e.name[:8]].append(e.path)
print('tasks', len(idx), 'points', sum(map(len, idx.values())), flush=True)
pts, forms = [], []; t0 = time.time()
for i, (t, ds) in enumerate(sorted(idx.items()), 1):
    best = {}
    for d in sorted(ds)[:60]:
        try:
            c = json.load(open(d + '/point.json'))['case']
            if c not in best:
                best[c] = open(d + '/gold.arclog').read()
        except OSError:
            continue
    if not best:
        continue
    g = min(best.values(), key=lambda x: len(x.strip().split('\n')))
    pts.append(dict(task=t, gold_sexp=g))
    L = [x for x in g.splitlines() if x.strip()]
    forms += [(t, j, x.split()[0].lstrip('(')) for j, x in enumerate(L) if x.split()[0].lstrip('(') in ('RULE', 'DET', 'INIT')]
    if i % 100 == 0:
        print(i, len(idx), len(forms), round(time.time() - t0), 's', flush=True)
json.dump(pts, open(out_p + '.new', 'w')); os.replace(out_p + '.new', out_p)
forms.sort(key=lambda x: hashlib.sha256(f'{x[0]} {x[1]}'.encode()).hexdigest())
with open(out_f + '.new', 'w') as f:
    f.writelines(f'{t} {j} {k}\n' for t, j, k in forms)
os.replace(out_f + '.new', out_f)
print('tasks', len(pts), 'forms', len(forms), collections.Counter(k for *_, k in forms), flush=True)
