"""Fit on live nodes of evaluation tasks only, with folds over all those tasks, and rank gold on held-out tasks against the bundled policy. Test nodes are the bundled policy's: table/full and table/oosb. Rows repeated across tables are kept once per task. Writes the fold models.

  live_eval.py OUT_TAG TRAIN_TAGS(comma)
"""
import collections, glob, hashlib, json, math, os, pickle, random, sys
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier as H
HERE = os.path.dirname(os.path.abspath(__file__))
tag, train = sys.argv[1], sys.argv[2].split(',')
FOLDS = 5; TEST = ('full', 'oosb')
B = [(1, 1, '1'), (2, 3, '2-3'), (4, 6, '4-6'), (7, 99, '7+')]
bucket = lambda x: next(n for a, b, n in B if a <= x <= b)
key = lambda t: hashlib.sha1(json.dumps(json.load(open(f'/Users/davidlu/code/arc-workspace/data/tasks/{t}.json'))['train'], sort_keys=True).encode()).hexdigest()
tasks = sorted({os.path.basename(f)[:8] for g in train for f in glob.glob(f'{HERE}/table/{g}/*.pkl')})
load = lambda g, t: pickle.load(open(f'{HERE}/table/{g}/{t}.pkl', 'rb')) if os.path.exists(f'{HERE}/table/{g}/{t}.pkl') else []
old = pickle.load(open('/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/ede6795c-2b6f-4633-a6da-08e90de33bc4/scratchpad/policy1/policy_model.pkl', 'rb'))
names = old['names']; ix = {k: i for i, k in enumerate(names)}


def mat(rows):
    X = np.full((len(rows), len(names)), np.nan, np.float32)
    for i, r in enumerate(rows):
        for k, v in r['f'].items():
            if k in ix:
                X[i, ix[k]] = v
    return X


def rows_of(ts):
    seen = {}
    for t in ts:
        for g in train:
            for r in load(g, t):
                seen[(t, r['gold'], tuple(sorted((k, v) for k, v in r['f'].items() if v is not None)))] = r
    return list(seen.values())


def bits(s, rows):
    out = collections.defaultdict(list)
    for j, r in enumerate(rows):
        if r['gold']:
            pool = [s[i] for i, x in enumerate(rows) if bucket(x['depth']) == bucket(r['depth'])]
            rank = 1 + sum(x > s[j] for x in pool) + (sum(x == s[j] for x in pool) - 1) / 2
            out[bucket(r['depth'])].append(math.log2(len(pool)) - math.log2(max(rank, 1)))
    return out


folds = []; d = {}
for fold in range(FOLDS):
    te = tasks[fold::FOLDS]; tr = [t for t in tasks if t not in te]
    rows = rows_of(tr)
    y = np.array([r['gold'] for r in rows])
    w = np.ones(len(rows)); w[y] = (~y).sum() / y.sum()
    m = H(max_iter=120, learning_rate=.06, max_depth=3, min_samples_leaf=8, l2_regularization=1., random_state=0).fit(mat(rows), y, sample_weight=w)
    folds.append(({key(t) for t in tr}, m))
    for t in te:
        k = key(t); o = next((x for trn, x in old['folds'] if k not in trn), old['folds'][0][1])
        for g in TEST:
            rs = load(g, t)
            if any(r['gold'] for r in rs):
                d[t + g] = (bits(list(o.decision_function(mat(rs))), rs), bits(list(m.decision_function(mat(rs))), rs))
    print('fold', fold, 'tasks', len(tr), 'fit', len(rows), 'gold', int(y.sum()), flush=True)
pickle.dump(dict(names=names, folds=folds), open(f'{HERE}/{tag}.pkl.new', 'wb')); os.replace(f'{HERE}/{tag}.pkl.new', f'{HERE}/{tag}.pkl')
rng = random.Random(0)
for name, keep in (('all', ''), ('46 record tasks', 'full'), ('54 others', 'oosb')):
    print(name)
    sub = {t: v for t, v in d.items() if t.endswith(keep)}
    for _, _, b in B:
        ts = [t for t in sub if sub[t][0].get(b)]
        if not ts:
            continue
        n = sum(len(sub[t][0][b]) for t in ts)
        o, a = sum(sum(sub[t][0][b]) for t in ts) / n, sum(sum(sub[t][1][b]) for t in ts) / n
        f = lambda p: sum(sum(sub[t][1][b]) - sum(sub[t][0][b]) for t in p) / sum(len(sub[t][0][b]) for t in p)
        bs = sorted(f([rng.choice(ts) for _ in ts]) for _ in range(2000))
        print(f'  {b}: tasks {len(ts)} gold {n} bundled {o:.2f} live {a:.2f} diff {a - o:+.2f} 90% {bs[100]:+.2f} {bs[1900]:+.2f}', flush=True)
