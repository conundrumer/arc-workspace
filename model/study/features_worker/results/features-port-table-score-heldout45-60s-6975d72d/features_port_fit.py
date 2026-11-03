"""Fit a table score on INIT prefix rows of fit tasks, and rank gold's prefixes among the search's prefixes of equal place and atom count on held forms, by q alone and by q plus the score. Nothing from held tasks enters the fit. A task-level bootstrap gives the interval.

  features_port_fit.py ROWS_DIR HELD_FORMS
"""
import collections, glob, math, pickle, random, statistics as st, sys
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier as H
rows_dir, held_list = sys.argv[1:3]
HELD = {tuple(l.split()) for l in open(held_list) if l.strip()}
J = [pickle.load(open(f, 'rb')) for f in sorted(glob.glob(rows_dir + '/*.pkl'))]
te = [r for r in J if (r['task'], str(r['line'])) in HELD]
heldt = {t for t, _ in HELD}
tr = [r for r in J if r['task'] not in heldt]
print('jobs', len(J), 'fit', len(tr), 'test', len(te))


def label(r):
    """Marks each search row whose atoms are all gold's, by relation and column names, as a bag. Each gold row counts as gold."""
    bag = collections.Counter()
    for x in r['rows']:
        if x['src'] == 'gold' and len(x['sigs']) > sum(bag.values()):
            bag = collections.Counter(x['sigs']) | bag
    for w in r.get('walk') or []:
        pass
    for x in r['rows']:
        x['gold'] = x['src'] == 'gold' or not (collections.Counter(x['sigs']) - bag)


for r in J:
    label(r)
keys = sorted({k for r in tr for x in r['rows'] for k in x['f']})
ix = {k: i for i, k in enumerate(keys)}


def mat(rows):
    X = np.full((len(rows), len(ix) + 3), np.nan, np.float32)
    for i, x in enumerate(rows):
        X[i, -1] = x['atoms']; X[i, -2] = x['place'] == 'key'; X[i, -3] = x['keyed']
        for k, v in x['f'].items():
            if k in ix and v is not None:
                X[i, ix[k]] = v
    return X


R, y, w = [], [], []
for r in tr:
    a = r['rows']
    p = sum(x['gold'] for x in a); n = len(a) - p
    if not p or not n:
        continue
    for x in a:
        R.append(x); y.append(x['gold']); w.append(1 / p if x['gold'] else 1 / n)
print('fit rows', len(R), 'positive', sum(y), 'features', len(keys), flush=True)
m = H(max_iter=150, learning_rate=.06, max_depth=3, min_samples_leaf=20, l2_regularization=1., random_state=0).fit(mat(R), np.array(y), sample_weight=np.array(w) * len(R) / 2)
res = collections.defaultdict(list); poolsz = []
for r in te:
    rows = r['rows']
    if not rows:
        continue
    s = m.decision_function(mat(rows))
    for x, v in zip(rows, s):
        x['s'] = float(v)
    logs = [x['logq'] for x in rows if x['logq'] is not None]
    for g in (x for x in rows if x['src'] == 'gold' and x['logq'] is not None):
        pool = [x for x in rows if x['src'] == 'search' and x['place'] == g['place'] and x['atoms'] == g['atoms'] and x['logq'] is not None]
        if len(pool) < 2:
            continue
        poolsz.append(len(pool))
        for b in (0, .25, .5, 1, 2):
            f = lambda x: x['logq'] + b * x['s']
            k = 1 + sum(f(x) > f(g) for x in pool)
            res[b].append((r['task'], math.log2(k)))
print('gold prefixes ranked', len(res[0]), 'forms', len({t for t, _ in res[0]}), 'median pool', st.median(poolsz) if poolsz else None)
rng = random.Random(0)
for b in (0, .25, .5, 1, 2):
    d = collections.defaultdict(list)
    for (t, a), (_, c) in zip(res[0], res[b]):
        d[t].append(a - c)
    T = list(d)
    mean = lambda p: sum(sum(d[t]) for t in p) / sum(len(d[t]) for t in p)
    bs = sorted(mean([rng.choice(T) for _ in T]) for _ in range(2000)) if T else [0] * 2000
    if not T:
        continue
    print(f'beta {b}: median log2 rank {st.median(x for _, x in res[b]):.2f} mean gain {mean(T) if T else 0:+.2f} 90% {bs[100]:+.2f} {bs[1900]:+.2f}')
