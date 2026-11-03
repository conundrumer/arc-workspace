"""Fit the two folds of the policy model on the super DAG pools. Each fold trains on half of the tasks, so a loop test on a task uses the fold that did not see it."""
import glob, json, os, pickle, sys
sys.path[:0] = ['/Users/davidlu/code/arc-workspace/model/study', os.path.dirname(os.path.abspath(__file__))]
import numpy as np
from judge3.framed_jsonl import iter_json
from nodefeat import features, load_pairs
from outfeat import link_features, out_features
from policy import task_key
from sklearn.ensemble import HistGradientBoostingClassifier as H
P = sys.argv[1]; OUT = sys.argv[2]; HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = HERE + '/cache2'
os.makedirs(CACHE, exist_ok=True)
data = {}
for f in sorted(glob.glob(P + '/*.nodes.jsonl.zst')):
    t = os.path.basename(f)[:8]
    c = f'{CACHE}/{t}.pkl'
    if not os.path.exists(f.replace('.nodes.jsonl.zst', '.done.json')):
        continue
    if os.path.exists(c) and os.path.getmtime(c) > os.path.getmtime(f):
        data[t] = pickle.load(open(c, 'rb')); continue
    pairs = load_pairs(t); rows = {}; N = {}
    for r in iter_json(f):
        d = features(r, pairs); o, s = out_features(r, pairs); d.update(o)
        N[r['token']] = (r.get('parents') or [], d, s)
        rows[r['token']] = (d, (r.get('tags') or {}).get('kind') == 'gold', r['depth'])
    link_features(N)
    rows = list(rows.values())
    pickle.dump(rows, open(c + '.new', 'wb')); os.replace(c + '.new', c); data[t] = rows
DROP = ('kid_',) + (('out_', 'fill_', 'near_', 'link_') if os.environ.get('POLICY_FEATS') == 'base' else ())
names = sorted({k for v in data.values() for x in v for k in x[0] if not k.startswith(DROP)})
ix = {n: i for i, n in enumerate(names)}
ALL = sorted(data)
print('tasks', len(ALL), 'nodes', sum(map(len, data.values())), 'gold', sum(x[1] for v in data.values() for x in v), 'feats', len(names), flush=True)
folds = []
for fold in (0, 1):
    tr = [t for i, t in enumerate(ALL) if i % 2 == fold]
    rows = [x for t in tr for x in data[t]]
    X = np.full((len(rows), len(names)), np.nan, np.float32)
    for i, (d, _, _) in enumerate(rows):
        for k, v in d.items():
            if k in ix:
                X[i, ix[k]] = v
    X[:, np.isnan(X).all(0)] = 0  # a column with no value in these rows stops the binner
    y = np.array([g for _, g, _ in rows])
    m = H(max_iter=150, learning_rate=0.1, max_depth=5, min_samples_leaf=10, class_weight='balanced', random_state=0).fit(X, y)
    folds.append(({task_key(json.load(open(f'/Users/davidlu/code/arc-workspace/data/tasks/{t}.json'))) for t in tr}, m))
    print('fold', fold, len(tr), 'tasks', len(rows), 'nodes', int(y.sum()), 'gold', flush=True)
pickle.dump(dict(names=names, folds=folds), open(OUT + '.new', 'wb')); os.replace(OUT + '.new', OUT)
print('wrote', OUT)
