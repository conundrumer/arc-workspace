"""Score the derived picks of the pool rows: gold's rank among the pool's nodes, against a uniform pick. Task folds. Rerun as tasks arrive.

Unrelated gold nodes and the junk that reads them are out of each pool. Depth columns are masked in the `-depth` runs, because gold ancestors are
placed in the pool and junk reads them, so depth can tell them apart by construction.
"""
import collections, glob, json, math, os, pickle, sys
sys.path[:0] = ['/Users/davidlu/code/arc-workspace/model/study', os.path.dirname(os.path.abspath(__file__))]
import numpy as np
from judge3.framed_jsonl import iter_json
from nodefeat import features, load_pairs
from outfeat import link_features, out_features
from sklearn.ensemble import HistGradientBoostingClassifier as H
P = sys.argv[1]; HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = HERE + '/cache4'
os.makedirs(CACHE, exist_ok=True)


def load(f):
    t = os.path.basename(f)[:8]
    c = f'{CACHE}/{t}.pkl'
    if os.path.exists(c) and os.path.getmtime(c) > os.path.getmtime(f):
        return t, pickle.load(open(c, 'rb'))
    pairs = load_pairs(t); N = {}; out = set()
    nodes = list(iter_json(f.replace('.rows.', '.nodes.')))
    parents = {r['token']: r.get('parents') or [] for r in nodes}
    out = {r['token'] for r in nodes if (r.get('tags') or {}).get('role') == 'unrelated'}
    grew = True
    while grew:
        grew = False
        for tok, ps in parents.items():
            if tok not in out and (r := next((p for p in ps if p in out), None)) is not None:
                out.add(tok); grew = True
    for r in nodes:
        if r['token'] in out:
            continue
        d = features(r, pairs); o, s = out_features(r, pairs); d.update(o)
        N[r['token']] = ([p for p in parents[r['token']] if p not in out], d, s)
    link_features(N)
    picks = []
    for row in iter_json(f):
        if row['pick'] != 'derived':
            continue
        toks = [x['token'] for x in row['options'] if x['token'] in N]
        if row['gold'] in toks:
            picks.append((row['gold'], toks, row['cols']))
    v = (dict((k, x[1]) for k, x in N.items()), picks)
    pickle.dump(v, open(c + '.new', 'wb')); os.replace(c + '.new', c)
    return t, v


data = dict(load(f) for f in sorted(glob.glob(P + '/*.rows.jsonl.zst')) if os.path.getsize(f) > 100)
picks = sum(len(v[1]) for v in data.values())
print('tasks', len(data), 'derived picks', picks, 'mean options', round(float(np.mean([len(p[1]) for v in data.values() for p in v[1]])), 1) if picks else '-', flush=True)
names = sorted({k for v in data.values() for d in v[0].values() for k in d})
OUT = ('out_', 'fill_', 'near_', 'split_')
DEP = ('depth', 'link_np', 'n_parents', 'kid_n')
BASE = lambda k: not k.startswith(OUT + ('link_', 'kid_')) and k not in DEP
FAM = {'types': lambda k: k.startswith('t_') or k == 'arity',
       'size': lambda k: k.startswith('rows_') and k not in ('rows_eq_changed', 'rows_eq_ofg') or k in ('empty_any', 'one_row', 'capped', 'n_train'),
       'sameness': lambda k: k in ('same_hash', 'test_same', 'test_empty'),
       'variety': lambda k: k in ('const_cols', 'live_cols', 'distinct_min', 'distinct_max', 'row_distinct')}
FAM['relate'] = lambda k: not any(g(k) for n, g in FAM.items() if n != 'relate')
GROUPS = {'base-depth': BASE, '+split': lambda k: BASE(k) or k.startswith('split_')}
ALL = sorted(data); FOLDS = min(4, len(ALL))


def whole(X, y):
    """A column with no value in these rows stops the binner, so it takes 0."""
    X[:, np.isnan(X).all(0)] = 0
    return X, y


KEPT = {}
for tag, keep in GROUPS.items():
    use = [k for k in names if keep(k)]
    ix = {n: i for i, n in enumerate(use)}
    def mat(ts, y):
        X = np.full((len(ts), len(use)), np.nan, np.float32)
        for i, d in enumerate(ts):
            for k, v in d.items():
                if k in ix:
                    X[i, ix[k]] = v
        return X, np.array(y)
    res = []
    for fold in range(FOLDS):
        te = [t for i, t in enumerate(ALL) if i % FOLDS == fold]; tr = [t for t in ALL if t not in te]
        rows, ys = [], []
        for t in tr:
            D, ps = data[t]
            for g, toks, _ in ps:
                rows += [D[x] for x in toks]; ys += [x == g for x in toks]
        if sum(ys) < 5:
            continue
        m = H(max_iter=100, learning_rate=0.1, max_depth=4, min_samples_leaf=5, class_weight='balanced', random_state=0).fit(*whole(*mat(rows, ys)))
        for t in te:
            D, ps = data[t]
            for g, toks, _ in ps:
                X, _ = mat([D[x] for x in toks], [0] * len(toks))
                s = m.decision_function(X); g0 = s[toks.index(g)]; r = 1 + int((s > g0).sum()) + (int((s == g0).sum()) - 1) / 2  # ties take their middle rank
                res.append((t, len(toks), r))
    if res:
        b = [math.log2(n) - math.log2(max(r, 1)) for _, n, r in res]
        print(tag, len(use), 'feats | picks', len(res), 'mean bits', round(float(np.mean(b)), 3), 'median', round(float(np.median(b)), 3), 'top10%', round(float(np.mean([r <= max(1, n * .1) for _, n, r in res])), 3), end=' ', flush=True)
        KEPT[tag] = np.array(b)
        d = KEPT[tag] - KEPT['base-depth']
        print('| vs base', round(float(d.mean()), 3), '+-', round(float(d.std() / max(len(d) ** .5, 1)), 3), flush=True)
