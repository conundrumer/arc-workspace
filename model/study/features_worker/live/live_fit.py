"""Retrain on live nodes with task folds, and rank gold within its depth band on held-out tasks, against the bundled policy's scores on the same nodes. Depth stays a feature. A task-level bootstrap gives the paired interval. The gold total is thin, so this screens and proves nothing alone.

  live_fit.py FAMILY ...   each family is full, p2 or both
"""
import collections, glob, math, os, pickle, random, sys, json
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier as H
HERE = os.path.dirname(os.path.abspath(__file__))
FOLDS = 5
B = [(1, 1, '1'), (2, 3, '2-3'), (4, 6, '4-6'), (7, 99, '7+')]
bucket = lambda x: next(n for a, b, n in B if a <= x <= b)
need = {'p2', 'both'} & set(sys.argv[1:])
tasks = sorted(os.path.basename(f)[:8] for f in glob.glob(HERE + '/table/full/*.pkl') if not need or os.path.exists(f.replace('/full/', '/p2/')))
T = {}
for t in tasks:
    a = pickle.load(open(f'{HERE}/table/full/{t}.pkl', 'rb'))
    p = {r['id']: r for r in pickle.load(open(f'{HERE}/table/p2/{t}.pkl', 'rb'))} if need else {}
    T[t] = [dict(id=r['id'], depth=r['depth'], gold=r['gold'], full=r['f'], p2={k: v for k, v in p.get(r['id'], {'f': {}})['f'].items() if '.' in k}) for r in a]
base = {t: json.load(open(f'{HERE}/rank/full-s/{t}.json')) for t in tasks if os.path.exists(f'{HERE}/rank/full-s/{t}.json')}
print('tasks', len(T), 'nodes', sum(map(len, T.values())), 'gold', sum(r['gold'] for v in T.values() for r in v), flush=True)


def names(fam):
    keys = set()
    for v in T.values():
        for r in v:
            for w in (('full', 'p2') if fam == 'both' else (fam,)):
                keys.update(r[w])
    return sorted(keys)


def mat(rows, fam, ix):
    X = np.full((len(rows), len(ix) + 1), np.nan, np.float32)
    for i, r in enumerate(rows):
        X[i, -1] = r['depth']
        for w in (('full', 'p2') if fam == 'both' else (fam,)):
            for k, v in r[w].items():
                if k in ix and v is not None:
                    X[i, ix[k]] = v
    X[:, np.isnan(X).all(0)] = 0
    return X


def bits(score, rows):
    out = collections.defaultdict(list)
    for j, r in enumerate(rows):
        if r['gold']:
            pool = [score[i] for i, x in enumerate(rows) if bucket(x['depth']) == bucket(r['depth'])]
            s = score[j]; rank = 1 + sum(x > s for x in pool) + (sum(x == s for x in pool) - 1) / 2
            out[bucket(r['depth'])].append(math.log2(len(pool)) - math.log2(max(rank, 1)))
    return out


ref = {t: bits([base[t]['score'][str(r['id'])] for r in T[t]], T[t]) for t in base}
rng = random.Random(0)
for fam in sys.argv[1:]:
    use = names(fam); ix = {k: i for i, k in enumerate(use)}; got = {}
    for fold in range(FOLDS):
        te = tasks[fold::FOLDS]; tr = [t for t in tasks if t not in te]
        rows = [r for t in tr for r in T[t]]
        y = np.array([r['gold'] for r in rows])
        w = np.ones(len(rows)); w[y] = (~y).sum() / max(y.sum(), 1)
        m = H(max_iter=120, learning_rate=.06, max_depth=3, min_samples_leaf=8, l2_regularization=1., random_state=0).fit(mat(rows, fam, ix), y, sample_weight=w)
        for t in te:
            got[t] = bits(list(m.decision_function(mat(T[t], fam, ix))), T[t])
    print(fam, len(use), 'feats', flush=True)
    for _, _, b in B:
        ts = [t for t in got if t in ref and got[t].get(b)]
        if not ts:
            continue
        n = sum(len(got[t][b]) for t in ts)
        new, old = sum(sum(got[t][b]) for t in ts) / n, sum(sum(ref[t][b]) for t in ts) / n
        m = lambda p: sum(sum(got[t][b]) - sum(ref[t][b]) for t in p) / sum(len(got[t][b]) for t in p)
        bs = sorted(m([rng.choice(ts) for _ in ts]) for _ in range(2000))
        print(f'  {b}: tasks {len(ts)} gold {n} live {new:.2f} bundled {old:.2f} diff {new - old:+.2f} 90% {bs[100]:+.2f} {bs[1900]:+.2f}', flush=True)
