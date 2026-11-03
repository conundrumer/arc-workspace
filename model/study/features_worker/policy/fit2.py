"""Score pool nodes with feature groups: base, base + OUT, base + OUT + links, and all with the readers' group. Task folds. Gold's rank in each pool against a uniform pick."""
import collections, glob, json, math, os, pickle, sys
sys.path[:0] = ['/Users/davidlu/code/arc-workspace/model/study', os.path.dirname(os.path.abspath(__file__))]
import numpy as np
from judge3.framed_jsonl import iter_json
from nodefeat import features, load_pairs
from outfeat import link_features, out_features
from sklearn.ensemble import HistGradientBoostingClassifier as H
P = sys.argv[1]; HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = HERE + '/cache2'
os.makedirs(CACHE, exist_ok=True)
data = {}
for f in sorted(glob.glob(P + '/*.nodes.jsonl.zst')):
    t = os.path.basename(f)[:8]
    c = f'{CACHE}/{t}.pkl'
    if os.path.exists(c) and os.path.getmtime(c) > os.path.getmtime(f):
        data[t] = pickle.load(open(c, 'rb')); continue
    if os.path.getsize(f) < 1000:
        continue
    pairs = load_pairs(t); rows = {}; N = {}
    for r in iter_json(f):
        d = features(r, pairs); o, s = out_features(r, pairs); d.update(o)
        N[r['token']] = (r.get('parents') or [], d, s)
        rows[r['token']] = (d, (r.get('tags') or {}).get('kind') == 'gold', r['depth'])
    link_features(N)
    rows = list(rows.values())
    pickle.dump(rows, open(c + '.new', 'wb')); os.replace(c + '.new', c); data[t] = rows
    print(t, len(rows), 'gold', sum(x[1] for x in rows), flush=True)
print('tasks', len(data), 'nodes', sum(map(len, data.values())), 'gold', sum(x[1] for v in data.values() for x in v), flush=True)
names = sorted({k for v in data.values() for x in v for k in x[0]})
OUT = ('out_', 'fill_', 'near_')
GROUPS = {'base': lambda k: not k.startswith(OUT + ('link_', 'kid_')),
          '+out': lambda k: not k.startswith(('link_', 'kid_')),
          '+link': lambda k: not k.startswith('kid_'),
          '+kid': lambda k: True}
ALL = sorted(data); FOLDS = 4
for tag, keep in GROUPS.items():
    use = [k for k in names if keep(k)]
    ix = {n: i for i, n in enumerate(use)}
    def mat(rows):
        X = np.full((len(rows), len(use)), np.nan, np.float32)
        for i, (d, _, _) in enumerate(rows):
            for k, v in d.items():
                if k in ix:
                    X[i, ix[k]] = v
        return X, np.array([g for _, g, _ in rows]), np.array([x[2] for x in rows])
    res = []
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
            res.extend((t, len(s), int(r), int(d)) for r, d in zip(rank[y], dep[y]))
    b = [math.log2(n) - math.log2(r) for _, n, r, _ in res]
    by = collections.defaultdict(list)
    for (t, n, r, d), g in zip(res, b):
        by[min(d, 4)].append(g)
    print(tag, len(use), 'feats | gold', len(res), 'mean bits', round(float(np.mean(b)), 3), 'median', round(float(np.median(b)), 3), 'top10%', round(float(np.mean([r <= max(1, n * .1) for _, n, r, _ in res])), 3), 'top1%', round(float(np.mean([r <= max(1, n * .01) for _, n, r, _ in res])), 3), {k: (len(v), round(float(np.mean(v)), 2)) for k, v in sorted(by.items())}, flush=True)
    json.dump(res, open(f'{HERE}/ranks{tag}.json', 'w'))
