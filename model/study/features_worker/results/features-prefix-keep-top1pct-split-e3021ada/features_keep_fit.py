"""Keep rule variants for a top-K keep of a search's prefixes, on non-held forms only. Fits on one task split and reads the other: the share of RULE forms with a gold prefix of 1 to 3 atoms in the top K of the search's prefixes, by fold of tasks.

  features_keep_fit.py SPLIT_FIT SPLIT_READ OUT
"""
import collections, glob, gzip, os, pickle, random, statistics as st, sys
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier as H
fit, read, out = sys.argv[1:4]
drop = set(open(os.environ['FEATURES_FIT_DROP_FILE']).read().split())
rng = random.Random(0); PLACES = ('RULE',)


def forms(d, top):
    fs = sorted(glob.glob(d + '/*.pkl.gz')); rng.shuffle(fs); n = 0
    for f in fs:
        if n >= top:
            return
        try:
            with gzip.open(f, 'rb') as g:
                r = pickle.load(g)
        except (EOFError, OSError):
            continue
        if r['kind'] != 'RULE' or r['task'] in drop or not any(k.startswith('pair.') for x in r['rows'] for k in x['f']):
            continue
        bag = collections.Counter()
        for x in r['rows']:
            if x['src'] == 'gold':
                bag |= collections.Counter(x['sigs'])
        for x in r['rows']:
            x['y'] = x['src'] == 'gold' or not (collections.Counter(x['sigs']) - bag)
        R = [x for x in r['rows'] if x['place'] == 'RULE' and 1 <= x['atoms'] <= 3]
        seen = {}
        for x in R:
            seen.setdefault((x['y'], tuple(x['sigs'])), x)
        R = list(seen.values())
        if any(x['y'] for x in R) and any(not x['y'] for x in R):
            n += 1
            yield r['task'], R


names = None


def arrays(rows):
    X = np.full((len(rows), len(ix) + 1), np.nan, np.float32)
    for i, x in enumerate(rows):
        X[i, -1] = x['atoms']
        for k, v in x['f'].items():
            j = ix.get(k)
            if j is not None and v is not None:
                X[i, j] = v
    return X


F = list(forms(fit, int(os.environ.get('FEATURES_FIT_FORMS', 2500))))
keys = sorted({k for _, R in F for x in R for k in x['f']}); ix = {k: i for i, k in enumerate(keys)}
print('fit forms', len(F), 'rows', sum(len(R) for _, R in F), 'features', len(keys), flush=True)
X = [arrays(R) for _, R in F]; Y = [np.array([x['y'] for x in R]) for _, R in F]; A = [np.array([x['atoms'] for x in R]) for _, R in F]
fm = lambda a: np.vstack(a) if a[0].ndim == 2 else np.concatenate(a)
P = dict(max_iter=300, learning_rate=.06, max_depth=4, min_samples_leaf=20, l2_regularization=1., random_state=0)


def w_form():
    return np.concatenate([np.where(y, 1 / max(y.sum(), 1), 1 / max((~y).sum(), 1)) for y in Y])


def w_atom():
    out = []
    for y, a in zip(Y, A):
        w = np.zeros(len(y))
        for k in np.unique(a):
            m = a == k
            if y[m].any() and (~y[m]).any():
                w[m & y] = 1 / y[m].sum(); w[m & ~y] = 1 / (~y[m]).sum()
        out.append(w)
    return np.concatenate(out)


Xa, ya = fm(X), fm(Y)
M = {}
M['form weight'] = H(**P).fit(Xa, ya, sample_weight=w_form() * len(ya))
print('fit form weight', flush=True)
w = w_atom(); M['atom weight'] = H(**P).fit(Xa, ya, sample_weight=w * len(ya))
print('fit atom weight', flush=True)
for name in ('form weight', 'atom weight'):
    base = w_form() if name == 'form weight' else w
    for rnd in (1,):
        ws = []; at = 0
        for x, y in zip(X, Y):
            s = M[name].decision_function(x); v = np.zeros(len(y)); neg = np.where(~y)[0]
            hard = neg[np.argsort(-s[neg])[:max(4, len(neg) // 50)]]
            v[hard] = 3 / max(len(hard), 1); ws.append(v)
        w2 = base + np.concatenate(ws)
        M[name + ', hard negatives'] = H(**P).fit(Xa, ya, sample_weight=w2 * len(ya))
        print('fit hard', name, flush=True)
pickle.dump(dict(names=keys, models=M), open(out + '/models.new', 'wb')); os.replace(out + '/models.new', out + '/models.pkl')
T = list(forms(read, 1500))
print('read forms', len(T), 'tasks', len({t for t, _ in T}), 'median pool', st.median(len(R) for _, R in T), flush=True)
Xr = [arrays(R) for _, R in T]; Yr = [np.array([x['y'] for x in R]) for _, R in T]
hit = {}
for name, m in M.items():
    d = collections.defaultdict(lambda: collections.defaultdict(list))
    for (t, R), x, y in zip(T, Xr, Yr):
        s = m.decision_function(x); o = np.argsort(-s)
        for lab, k in (('top 1', 1), ('top 4', 4), ('top 1%', max(1, len(s) // 100)), ('top 16', 16)):
            d[lab][t].append(bool(y[o[:k]].any()))
        rand = 1 - np.prod([(1 - y.sum() / len(y))]) if False else None
    for lab, v in d.items():
        T_ = list(v); f = lambda p: sum(sum(v[t]) for t in p) / sum(len(v[t]) for t in p)
        b = random.Random(0); bs = sorted(f([b.choice(T_) for _ in T_]) for _ in range(1000))
        hit[name, lab] = (f(T_), bs[25], bs[974])
for lab in ('top 1', 'top 1%', 'top 4', 'top 16'):
    print(lab, ' | '.join(f'{n}: %.3f (%.3f %.3f)' % hit[n, lab] for n in M), flush=True)
b = np.mean([y.mean() for y in Yr]); print('mean share of gold among pool rows', round(float(b), 4), flush=True)
