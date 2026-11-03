"""Score pool nodes: is a node one of gold's relations? Task folds; reports gold's rank in each pool against a uniform pick. Rerun as tasks arrive."""
import collections, glob, json, math, os, pickle, sys
sys.path[:0] = ['/Users/davidlu/code/arc-workspace/model/study', os.path.dirname(os.path.abspath(__file__))]
import numpy as np
from judge3.framed_jsonl import iter_json
from nodefeat import features, load_pairs
from sklearn.ensemble import HistGradientBoostingClassifier as H
P = sys.argv[1]; HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(HERE + '/cache', exist_ok=True)
data = {}
for f in sorted(glob.glob(P + '/*.nodes.jsonl.zst')):
    t = os.path.basename(f)[:8]
    c = f'{HERE}/cache/{t}.pkl'
    if os.path.exists(c) and os.path.getmtime(c) > os.path.getmtime(f):
        data[t] = pickle.load(open(c, 'rb')); continue
    if os.path.getsize(f) < 1000:
        continue
    pairs = load_pairs(t); rows = []
    for r in iter_json(f):
        rows.append((features(r, pairs), (r.get('tags') or {}).get('kind') == 'gold', r['depth']))
    pickle.dump(rows, open(c, 'wb')); data[t] = rows
    print(t, len(rows), 'gold', sum(x[1] for x in rows), flush=True)
tasks = sorted(t for t, v in data.items() if any(x[1] for x in v))
print('tasks', len(data), 'with gold', len(tasks), 'nodes', sum(map(len, data.values())), 'gold', sum(x[1] for v in data.values() for x in v))
names = sorted({k for v in data.values() for x in v for k in x[0]})
ix = {n: i for i, n in enumerate(names)}
def mat(rows):
    X = np.full((len(rows), len(names)), np.nan, np.float32)
    for i, (d, _, _) in enumerate(rows):
        for k, v in d.items():
            X[i, ix[k]] = v
    return X, np.array([g for _, g, _ in rows]), np.array([x[2] for x in rows])
FOLDS = 4
ALL = sorted(data)
res = []; imp = collections.Counter()
for fold in range(FOLDS):
    te = [t for i, t in enumerate(ALL) if i % FOLDS == fold]; tr = [t for t in ALL if t not in te]
    Xt, yt, _ = mat([x for t in tr for x in data[t]])
    if yt.sum() < 10:
        continue
    m = H(max_iter=150, learning_rate=0.1, max_depth=5, min_samples_leaf=10, class_weight='balanced', random_state=0).fit(Xt, yt)
    for t in te:
        X, y, dep = mat(data[t])
        if not y.any():
            continue
        s = m.decision_function(X); order = np.argsort(-s); rank = np.empty(len(s), int); rank[order] = np.arange(1, len(s) + 1)
        for r, d in zip(rank[y], dep[y]):
            res.append((t, len(s), int(r), int(d)))
b = [math.log2(n) - math.log2(r) for _, n, r, _ in res]
print('gold nodes scored', len(res), 'mean bits gained against uniform', round(np.mean(b), 2), 'median', round(np.median(b), 2), 'share in top 10%', round(np.mean([r <= max(1, n * .1) for _, n, r, _ in res]), 3), 'in top 1%', round(np.mean([r <= max(1, n * .01) for _, n, r, _ in res]), 3))
by = collections.defaultdict(list)
for (t, n, r, d), g in zip(res, b):
    by[min(d, 4)].append(g)
print({k: (len(v), round(float(np.mean(v)), 2)) for k, v in sorted(by.items())})
json.dump(res, open(HERE + '/ranks.json', 'w'))
m = H(max_iter=150, learning_rate=0.1, max_depth=5, min_samples_leaf=10, class_weight='balanced', random_state=0)
