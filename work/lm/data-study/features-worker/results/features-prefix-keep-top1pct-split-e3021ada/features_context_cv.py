"""Task-grouped folds on dumped RULE forms: the 87 table features against them plus the new families. Reads the share of forms with a gold prefix of 1 to 3 atoms in the top K of the form's prefixes, by form, with cost per prefix.

  features_context_cv.py DUMP_ROWS POLICY_DIR
"""
import collections, glob, gzip, hashlib, os, pickle, random, statistics as st, sys, time
sys.path[:0] = [sys.argv[2], os.path.dirname(os.path.abspath(__file__))]
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier as H
from nodefeat import Pair
import features_context as CTX
import json
Rows = []; forms = 0; cost = [0., 0]; P = {}
for f in sorted(glob.glob(sys.argv[1] + '/*.pkl.gz')):
    with gzip.open(f, 'rb') as g:
        r = pickle.load(g)
    if r['kind'] != 'RULE':
        continue
    t = r['task']
    P.setdefault(t, [Pair(p['input'], p['output']) for p in json.load(open(f'/Users/davidlu/code/arc-workspace/data/tasks/{t}.json'))['train']])
    bag = collections.Counter()
    for x in r['rows']:
        if x['src'] == 'gold':
            bag |= collections.Counter(x['sigs'])
    seen = {}
    for x in r['rows']:
        if x['place'] == 'RULE' and 1 <= x['atoms'] <= 3:
            x['y'] = x['src'] == 'gold' or not (collections.Counter(x['sigs']) - bag)
            seen.setdefault((x['y'], tuple(x['sigs'])), x)
    R = list(seen.values())
    if not any(x['y'] for x in R) or all(x['y'] for x in R):
        continue
    forms += 1
    for x in R:
        tb = x['table']; n = dict(types=[], table_types=tb['types'], x_rows=tb['x_rows'])
        t0 = time.process_time(); c = CTX.features(n, x['text'], P[t]); cost[0] += time.process_time() - t0; cost[1] += 1
        Rows.append((t, forms, x['y'], x['atoms'], x['f'], c))
print('forms', forms, 'tasks', len(P), 'rows', len(Rows), 'cost ms mean', round(cost[0] / cost[1] * 1000, 2), flush=True)
k87 = sorted({k for x in Rows for k in x[4]}); kc = sorted(CTX.FEATURES)
ix = {k: i for i, k in enumerate(k87 + kc)}
X = np.full((len(Rows), len(ix) + 1), np.nan, np.float32)
for i, x in enumerate(Rows):
    X[i, -1] = x[3]
    for d in (x[4], x[5]):
        for k, v in d.items():
            if v is not None and k in ix:
                X[i, ix[k]] = v
y = np.array([x[2] for x in Rows]); form = np.array([x[1] for x in Rows])
cnt = collections.Counter(zip(form, y)); w = np.array([1 / cnt[f, c] for f, c in zip(form, y)]); w *= len(w) / w.sum()
fold = np.array([int(hashlib.sha1(x[0].encode()).hexdigest(), 16) % 5 for x in Rows])
print('positive rate of filled ctx', {k: round(float((~np.isnan(X[:, ix[k]])).mean()), 2) for k in kc[:13]}, flush=True)
A = {'87': list(range(len(k87))) + [X.shape[1] - 1], '87+shape': [ix[k] for k in k87] + [ix[k] for k in kc if k.startswith('shape')] + [X.shape[1] - 1],
     '87+ctx': [ix[k] for k in k87] + [ix[k] for k in kc if k.startswith('ctx')] + [X.shape[1] - 1], '87+both': list(range(X.shape[1]))}
P_ = dict(max_iter=200, learning_rate=.06, max_depth=4, min_samples_leaf=20, l2_regularization=1., random_state=0)
Sc = {}
for n, c in A.items():
    s = np.zeros(len(y))
    for k in range(5):
        tr = fold != k; te = fold == k
        s[te] = H(**P_).fit(X[tr][:, c], y[tr], sample_weight=w[tr]).decision_function(X[te][:, c])
    Sc[n] = s; print('fit', n, flush=True)
rng = random.Random(0)
tasks = np.array([x[0] for x in Rows])
for K in (1, 3, 4, 16):
    res = {}
    for n, s in Sc.items():
        d = collections.defaultdict(list)
        for f in np.unique(form):
            m = form == f; o = np.argsort(-s[m])[:K]
            d[tasks[m][0]].append(bool(y[m][o].any()))
        res[n] = d
    T = list(res['87'])
    line = []
    for n in A:
        fn = lambda p, d=res[n]: sum(sum(d[t]) for t in p) / sum(len(d[t]) for t in p)
        line.append(f'{n} {fn(T):.3f}')
    dd = {t: [a - b for a, b in zip(res['87+both'][t], res['87'][t])] for t in T}
    fn = lambda p: sum(sum(dd[t]) for t in p) / sum(len(dd[t]) for t in p)
    bs = sorted(fn([rng.choice(T) for _ in T]) for _ in range(2000))
    print('K', K, ' | '.join(line), f'| both minus 87 {fn(T):+.3f} (95% {bs[50]:+.3f} {bs[1949]:+.3f})', flush=True)
print('mean pool', round(len(y) / forms, 1), 'mean positives', round(y.sum() / forms, 2))
