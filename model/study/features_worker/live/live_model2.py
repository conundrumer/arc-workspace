"""Second round: fit fold models on several live tables and compare with the first round's models on held-out tasks. The folds match live-f.pkl's. Rows repeated across tables are kept once per task. The rank is within a depth band, on one test table at a time. A table named after a task-less tag such as oos trains every fold.

  live_model2.py OUT_TAG EXTRA_TAGS(comma) [ALWAYS_TRAIN_TAGS(comma)]
"""
import collections, glob, hashlib, json, math, os, pickle, random, sys
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier as H
HERE = os.path.dirname(os.path.abspath(__file__))
tag, extra = sys.argv[1], sys.argv[2].split(','); always = sys.argv[3].split(',') if len(sys.argv) > 3 else []
FOLDS = 5
B = [(1, 1, '1'), (2, 3, '2-3'), (4, 6, '4-6'), (7, 99, '7+')]
bucket = lambda x: next(n for a, b, n in B if a <= x <= b)
key = lambda t: hashlib.sha1(json.dumps(json.load(open(f'/Users/davidlu/code/arc-workspace/data/tasks/{t}.json'))['train'], sort_keys=True).encode()).hexdigest()
tasks = sorted(os.path.basename(f)[:8] for f in glob.glob(HERE + '/table/full/*.pkl'))
load = lambda g, t: pickle.load(open(f'{HERE}/table/{g}/{t}.pkl', 'rb')) if os.path.exists(f'{HERE}/table/{g}/{t}.pkl') else []
old = pickle.load(open(f'{HERE}/live-f.pkl', 'rb')); names = old['names']; ix = {k: i for i, k in enumerate(names)}


def mat(rows):
    X = np.full((len(rows), len(names)), np.nan, np.float32)
    for i, r in enumerate(rows):
        for k, v in r['f'].items():
            if k in ix:
                X[i, ix[k]] = v
    return X


def rows_of(tags, ts):
    seen = {}
    for t in ts:
        for g in tags:
            for r in load(g, t):
                seen[(t, r['gold'], tuple(sorted((k, v) for k, v in r['f'].items() if v is not None)))] = r
    return list(seen.values())


def bits(score, rows):
    out = collections.defaultdict(list)
    for j, r in enumerate(rows):
        if r['gold']:
            pool = [score[i] for i, x in enumerate(rows) if bucket(x['depth']) == bucket(r['depth'])]
            s = score[j]; rank = 1 + sum(x > s for x in pool) + (sum(x == s for x in pool) - 1) / 2
            out[bucket(r['depth'])].append(math.log2(len(pool)) - math.log2(max(rank, 1)))
    return out


folds = []; got = collections.defaultdict(dict)
base = sorted({os.path.basename(f)[:8] for g in always for f in glob.glob(f'{HERE}/table/{g}/*.pkl')} - set(tasks))
for fold in range(FOLDS):
    te = tasks[fold::FOLDS]; tr = [t for t in tasks if t not in te]
    rows = rows_of(['full'] + extra, tr) + rows_of(always, base)
    y = np.array([r['gold'] for r in rows])
    w = np.ones(len(rows)); w[y] = (~y).sum() / y.sum()
    m = H(max_iter=120, learning_rate=.06, max_depth=3, min_samples_leaf=8, l2_regularization=1., random_state=0).fit(mat(rows), y, sample_weight=w)
    folds.append(({key(t) for t in tr + base}, m))
    m0 = old['folds'][fold][1]
    for t in te:
        for g in ('full', 'lf', 'lfu003'):
            rs = load(g, t)
            if rs:
                got[g][t] = (bits(list(m0.decision_function(mat(rs))), rs), bits(list(m.decision_function(mat(rs))), rs))
    print('fold', fold, 'fit', len(rows), 'gold', int(y.sum()), flush=True)
pickle.dump(dict(names=names, folds=folds), open(f'{HERE}/{tag}.pkl.new', 'wb')); os.replace(f'{HERE}/{tag}.pkl.new', f'{HERE}/{tag}.pkl')
rng = random.Random(0)
for g, d in got.items():
    print('test nodes:', g)
    for _, _, b in B:
        ts = [t for t in d if d[t][0].get(b)]
        if not ts:
            continue
        n = sum(len(d[t][0][b]) for t in ts)
        o, a = sum(sum(d[t][0][b]) for t in ts) / n, sum(sum(d[t][1][b]) for t in ts) / n
        f = lambda p: sum(sum(d[t][1][b]) - sum(d[t][0][b]) for t in p) / sum(len(d[t][0][b]) for t in p)
        bs = sorted(f([rng.choice(ts) for _ in ts]) for _ in range(2000))
        print(f'  {b}: tasks {len(ts)} gold {n} first {o:.2f} second {a:.2f} diff {a - o:+.2f} 90% {bs[100]:+.2f} {bs[1900]:+.2f}', flush=True)
