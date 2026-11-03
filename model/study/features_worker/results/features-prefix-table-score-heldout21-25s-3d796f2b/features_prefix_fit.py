"""Fit a table score on prefix rows of fit tasks, and rank gold's prefixes among the search's prefixes of equal atom count on held tasks, by q alone and by q plus the score. Nothing from held tasks enters the fit. A task-level bootstrap gives the interval.

  prefix_fit.py ROWS_DIR HELD_LIST
"""
import collections, glob, math, os, pickle, random, statistics as st, sys
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier as H
rows_dir, held_list = sys.argv[1:3]
HELD = {l.split()[0] + '.' + l.split()[2].strip('[]').replace(',', '-') for l in open(held_list)}
J = [pickle.load(open(f, 'rb')) for f in sorted(glob.glob(rows_dir + '/*.pkl'))]
stem = lambda r: f"{r['task']}.{r['point'][0]}-{r['point'][1]}"
te = [r for r in J if stem(r) in HELD]
heldt = {r['task'] for r in te}
tr = [r for r in J if stem(r) not in HELD and r['task'] not in heldt]
print('jobs', len(J), 'fit', len(tr), 'test', len(te), 'walk not valid', sum(bool(r.get('bad') or r.get('dead') or r.get('left')) for r in J))
keys = sorted({k for r in tr for x in r['rows'] for k in x['f']})
ix = {k: i for i, k in enumerate(keys)}


def mat(rows):
    X = np.full((len(rows), len(ix) + 1), np.nan, np.float32)
    for i, x in enumerate(rows):
        X[i, -1] = x['atoms']
        for k, v in x['f'].items():
            if k in ix and v is not None:
                X[i, ix[k]] = v
    return X


pos = neg = 0; R = []; y = []; w = []
for r in tr:
    a = [x for x in r['rows'] if x['atoms'] >= 1]
    p = sum(bool(x.get('gold')) for x in a); n = len(a) - p
    if not p or not n:
        continue
    for x in a:
        R.append(x); y.append(bool(x.get('gold'))); w.append(1 / p if x.get('gold') else 1 / n)
    pos += p; neg += n
print('fit rows', len(R), 'positive', pos, 'negative', neg, 'features', len(keys), flush=True)
m = H(max_iter=150, learning_rate=.06, max_depth=3, min_samples_leaf=20, l2_regularization=1., random_state=0).fit(mat(R), np.array(y), sample_weight=np.array(w) * len(R) / 2)
out = collections.defaultdict(list)
for r in te:
    if r.get('bad') or r.get('dead') or r.get('left') or not r.get('walk'):
        continue
    walk = [x for x in r['rows'] if x['src'] == 'walk' and x['atoms'] >= 1]
    if not walk:
        continue
    g = walk[-1]; bits = sum(a[2] or 0 for a in r['walk'][:g['atoms']]); lq = -bits * math.log(2)
    pool = [x for x in r['rows'] if x['src'] == 'search' and x['atoms'] == g['atoms'] and x.get('logq') is not None and not x.get('gold')]
    if len(pool) < 5:
        continue
    sc = m.decision_function(mat(pool + [g]))
    for beta in (0, .25, .5, 1, 2):
        gk = lq + beta * sc[-1]
        rank = 1 + sum(x['logq'] + beta * s > gk for x, s in zip(pool, sc[:-1]))
        out[beta].append((r['task'], math.log2(rank), bits, len(pool)))
n = len(out[0]); print('test cases', n, 'median pool', st.median(x[3] for x in out[0]))
rng = random.Random(0)
tasks = sorted({x[0] for x in out[0]})
for beta, v in sorted(out.items()):
    gain = collections.defaultdict(list)
    for a, b in zip(out[0], v):
        gain[a[0]].append(a[1] - b[1])
    mean = lambda p: sum(sum(gain[t]) for t in p) / sum(len(gain[t]) for t in p)
    bs = sorted(mean([rng.choice(tasks) for _ in tasks]) for _ in range(2000))
    print(f'beta {beta}: median log2 rank {st.median(x[1] for x in v):.2f} mean gain {mean(tasks):+.2f} 90% {bs[100]:+.2f} {bs[1900]:+.2f}', flush=True)
imp = sorted(keys, key=lambda k: -abs(np.corrcoef(np.nan_to_num(mat(R)[:, ix[k]]), np.array(y, float))[0, 1] if np.nanstd(mat(R)[:, ix[k]]) else 0))[:12] if len(R) < 200000 else []
print('top correlates', imp)
