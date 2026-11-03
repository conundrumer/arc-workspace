"""Does content signal in the prefix fit differ by relation? Task-grouped folds on corpus rows. Within a form, place and atom count, reads the rate at which a positive prefix outranks a negative, on pairs with the same last relation, so relation identity can't help and only content can. Arms: pooled content; content with the last relation as a category; a fit per relation where positives allow. Writes each fold's scores when it ends.

  features_prefix_byrel.py CORPUS_ROWS OUT MAX_FORMS
"""
import collections, glob, gzip, hashlib, json, os, pickle, random, sys
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier as H
corpus, out, top = sys.argv[1], sys.argv[2], int(sys.argv[3])
NEG, FOLDS, MIN_POS, PLACES = 60, 5, 400, ('RULE', 'DET', 'key', 'port')
drop = set(open(os.environ['FEATURES_FIT_DROP_FILE']).read().split())
rng = random.Random(0)
os.makedirs(out, exist_ok=True)


def rel(x):
    if not x['sigs']:
        return 'none'
    n = x['sigs'][-1][1]
    return '&scope' if n.startswith('&') else n


fs = sorted(glob.glob(corpus + '/*.pkl.gz')); rng.shuffle(fs)
R = []; forms = 0
for f in fs:
    if forms >= top:
        break
    try:
        with gzip.open(f, 'rb') as g:
            r = pickle.load(g)
    except (EOFError, OSError):
        continue
    if r['task'] in drop or not any(k.startswith('pair.') for x in r['rows'] for k in x['f']):
        continue
    bag = collections.Counter()
    for x in r['rows']:
        if x['src'] == 'gold':
            bag |= collections.Counter(x['sigs'])
    pos, neg = [], []
    for x in r['rows']:
        (pos if x['src'] == 'gold' or not (collections.Counter(x['sigs']) - bag) else neg).append(x)
    if not pos or not neg:
        continue
    forms += 1
    if len(neg) > NEG:
        neg = rng.sample(neg, NEG)
    for x, y in [(x, 1) for x in pos] + [(x, 0) for x in neg]:
        R.append(dict(form=forms, task=r['task'], place=x['place'], atoms=x['atoms'], keyed=x['keyed'], rel=rel(x), f=x['f'], y=y, w=1 / (len(pos) if y else len(neg))))
keys = sorted({k for x in R for k in x['f']}); ix = {k: i for i, k in enumerate(keys)}
print('forms', forms, 'tasks', len({x['task'] for x in R}), 'rows', len(R), 'features', len(keys), flush=True)
pc = collections.Counter(x['rel'] for x in R if x['y'])
print('positives by last relation, top 30', pc.most_common(30), flush=True)
print('relations', len(pc), 'with at least', MIN_POS, 'positives:', sum(v >= MIN_POS for v in pc.values()), flush=True)
common = [k for k, v in pc.most_common(60)]; cat = {k: i for i, k in enumerate(common)}
X = np.full((len(R), len(ix) + 6), np.nan, np.float32)
for i, x in enumerate(R):
    X[i, -1] = x['atoms']; X[i, -2] = x['keyed']; X[i, -3 - PLACES.index(x['place'])] = 1
    for k, v in x['f'].items():
        j = ix.get(k)
        if j is not None and v is not None:
            X[i, j] = v
C = np.array([cat.get(x['rel'], len(common)) for x in R], np.float32)[:, None]
y = np.array([x['y'] for x in R]); w = np.array([x['w'] for x in R]); w *= len(R) / w.sum()
fold = np.array([int(hashlib.sha1(x['task'].encode()).hexdigest(), 16) % FOLDS for x in R])
P = dict(max_iter=300, learning_rate=.06, max_depth=4, min_samples_leaf=20, l2_regularization=1., random_state=0)
S = {a: np.full(len(R), np.nan) for a in ('pooled', 'category', 'per')}
big = [k for k, v in pc.items() if v >= MIN_POS]
rel_arr = np.array([x['rel'] for x in R])
for k in range(FOLDS):
    tr, te = fold != k, fold == k
    S['pooled'][te] = H(**P).fit(X[tr], y[tr], sample_weight=w[tr]).decision_function(X[te])
    Z = np.hstack([X, C]); S['category'][te] = H(categorical_features=[Z.shape[1] - 1], **P).fit(Z[tr], y[tr], sample_weight=w[tr]).decision_function(Z[te])
    for b in big:
        a, c = tr & (rel_arr == b), te & (rel_arr == b)
        if c.any() and y[a].sum() >= 50 and (~y[a].astype(bool)).sum() >= 50:
            S['per'][c] = H(**{**P, 'max_iter': 150}).fit(X[a], y[a], sample_weight=w[a]).decision_function(X[c])
    pickle.dump(dict(S=S, fold=k), open(out + '/scores.new', 'wb')); os.replace(out + '/scores.new', out + '/scores')
    print('fold', k, 'done', flush=True)


def same_rel(arm):
    """Per relation, per task: wins and pairs of positive over negative in one stratum with the same last relation."""
    g = collections.defaultdict(list)
    for i, x in enumerate(R):
        g[x['form'], x['place'], x['atoms'], x['rel']].append(i)
    d = collections.defaultdict(lambda: collections.defaultdict(lambda: [0., 0]))
    for (_, _, _, b), I in g.items():
        p = [i for i in I if y[i]]; n = [i for i in I if not y[i]]
        for i in p:
            for j in n:
                a, c = S[arm][i], S[arm][j]
                if a == a and c == c:
                    e = d[b][R[i]['task']]; e[0] += (a > c) + .5 * (a == c); e[1] += 1
    return d


def read(tasks):
    r = sum(v[0] for v in tasks.values()) / max(sum(v[1] for v in tasks.values()), 1)
    T = list(tasks); bs = []
    for _ in range(500):
        s = [tasks[boot.choice(T)] for _ in T]
        bs.append(sum(v[0] for v in s) / max(sum(v[1] for v in s), 1))
    bs.sort()
    return r, bs[25], bs[474], len(T), sum(v[1] for v in tasks.values())


boot = random.Random(0)
D = {a: same_rel(a) for a in S}
print('relation | positives | tasks | same-relation pairs | pooled | category | per relation; rate, 95% task bootstrap; .5 is chance')
tot = collections.defaultdict(lambda: [0., 0])
for b, n in pc.most_common(40):
    row = [b, n]
    for a in ('pooled', 'category', 'per'):
        if D[a].get(b):
            q = read(D[a][b]); row += [f'{q[0]:.3f} ({q[1]:.3f} {q[2]:.3f})']
            if a == 'pooled':
                row[2:2] = [q[3], q[4]]
        else:
            row += ['-']
    print(' | '.join(map(str, row)), flush=True)
for a in S:
    if a == 'per':
        continue
    t = collections.defaultdict(lambda: [0., 0])
    for b, v in D[a].items():
        for k, e in v.items():
            t[k][0] += e[0]; t[k][1] += e[1]
    print('all relations', a, '%.3f (%.3f %.3f) tasks %d pairs %d' % read(t), flush=True)
