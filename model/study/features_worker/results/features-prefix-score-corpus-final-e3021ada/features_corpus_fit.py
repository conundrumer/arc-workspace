"""Fit a table score on corpus prefix rows, and rank gold's prefixes among the search's prefixes of equal place and atom count on held cases, by q alone and by q plus the score, by kind. Nothing from held or evaluation tasks enters the fit. A task-level bootstrap gives the interval.

  features_corpus_fit.py CORPUS_ROWS HELD_ROWS [MAX_FORMS]
"""
import collections, glob, gzip, math, os, pickle, random, statistics as st, sys
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier as H
corpus, held = sys.argv[1:3]
top = int(sys.argv[3]) if len(sys.argv) > 3 else None
NEG = 60  # negative rows kept per form
PLACES = ('RULE', 'DET', 'key', 'port')
rng = random.Random(0)


def load(f):
    with gzip.open(f, 'rb') as g:
        return pickle.load(g)


def label(r):
    """Marks each row whose atoms are all gold's, by relation and column names, as a bag. A walk row is gold."""
    bag = collections.Counter()
    for x in r['rows']:
        if x['src'] == 'gold':
            bag |= collections.Counter(x['sigs'])
    for x in r['rows']:
        x['gold'] = x['src'] == 'gold' or not (collections.Counter(x['sigs']) - bag)


PAIR = os.environ.get('FEATURES_PAIR')  # with: read only forms that have pair features; drop: the same forms without those columns


def has_pair(r):
    return any(k.startswith('pair.') for x in r['rows'] for k in x['f'])


def strip(r):
    if PAIR == 'drop':
        for x in r['rows']:
            x['f'] = {k: v for k, v in x['f'].items() if not k.startswith('pair.')}


fitdrop = set(open(os.environ['FEATURES_FIT_DROP_FILE']).read().split()) if 'FEATURES_FIT_DROP_FILE' in os.environ else set()
keys = set(); R = []; y = []; w = []; forms = 0; tasks = set()
fs = sorted(glob.glob(corpus + '/*.pkl.gz'))
rng.shuffle(fs)
for f in fs[:top]:
    try:
        r = load(f)
    except (EOFError, OSError):
        continue
    if r['task'] in fitdrop or (PAIR and not has_pair(r)):
        continue
    strip(r)
    label(r)
    pos = [x for x in r['rows'] if x['gold']]; neg = [x for x in r['rows'] if not x['gold']]
    if not pos or not neg:
        continue
    forms += 1; tasks.add(r['task'])
    if len(neg) > NEG:
        neg = rng.sample(neg, NEG)
    for x in pos:
        R.append(x); y.append(True); w.append(1 / len(pos))
    for x in neg:
        R.append(x); y.append(False); w.append(1 / len(neg))
    for x in pos + neg:
        keys.update(x['f'])
keys = sorted(keys); ix = {k: i for i, k in enumerate(keys)}
print('corpus files', len(fs), 'forms used', forms, 'tasks', len(tasks), 'rows', len(R), 'positive', sum(y), 'features', len(keys), flush=True)


def mat(rows):
    X = np.full((len(rows), len(ix) + 6), np.nan, np.float32)
    for i, x in enumerate(rows):
        X[i, -1] = x['atoms']; X[i, -2] = x['keyed']
        X[i, -3 - PLACES.index(x['place'])] = 1
        for k, v in x['f'].items():
            j = ix.get(k)
            if j is not None and v is not None:
                X[i, j] = v
    return X


m = H(max_iter=300, learning_rate=.06, max_depth=4, min_samples_leaf=20, l2_regularization=1., random_state=0).fit(mat(R), np.array(y), sample_weight=np.array(w) * len(R) / 2)
del R
if os.environ.get('FEATURES_MODEL_OUT'):
    with open(os.environ['FEATURES_MODEL_OUT'] + '.new', 'wb') as g:
        pickle.dump(dict(names=keys, places=PLACES, model=m), g)
    os.replace(os.environ['FEATURES_MODEL_OUT'] + '.new', os.environ['FEATURES_MODEL_OUT'])
FLOORS = [(float(a), float(c)) for a, c in (x.split(':') for x in os.environ.get('FEATURES_FLOORS', '').split())]; floors = collections.defaultdict(list)
res = collections.defaultdict(lambda: collections.defaultdict(list)); pools = collections.defaultdict(list); B = (0, .25, .5, 1, 2, 4)
for f in sorted(glob.glob(held + '/*.pkl.gz')):
    try:
        r = load(f)
    except (EOFError, OSError):
        continue
    if PAIR and not has_pair(r):
        continue
    strip(r)
    rows = [x for x in r['rows'] if x['logq'] is not None]
    if not rows:
        continue
    s = m.decision_function(mat(rows))
    for x, v in zip(rows, s):
        x['s'] = float(v)
    for g in (x for x in rows if x['src'] == 'gold'):
        pool = [x for x in rows if x['src'] == 'search' and x['place'] == g['place'] and x['atoms'] == g['atoms']]
        if len(pool) < 2:
            continue
        pools[r['kind']].append(len(pool))
        base = math.log2(1 + sum(x['logq'] > g['logq'] for x in pool))
        for fl, bt in FLOORS:
            sg = g['logq'] + bt * max(g['s'], fl)
            floors[r['kind'], fl, bt, 'easy' if base < 4 else 'hard'].append(((r['task'], r['line']), base - math.log2(1 + sum(x['logq'] + bt * max(x['s'], fl) > sg for x in pool))))
        for b in B:
            res[r['kind']][b].append(((r['task'], r['line']), math.log2(1 + sum(x['logq'] + b * x['s'] > g['logq'] + b * g['s'] for x in pool))))
if os.environ.get('FEATURES_RES_OUT'):
    pickle.dump({k: dict(v) for k, v in res.items()}, open(os.environ['FEATURES_RES_OUT'], 'wb'))
for key in sorted(floors):
    v = floors[key]
    print('floor', key, 'prefixes', len(v), 'mean gain %+.3f' % (sum(x for _, x in v) / len(v)), 'lose over 1 bit %.3f' % (sum(x < -1 for _, x in v) / len(v)), flush=True)
boot = random.Random(0)
drop = set(os.environ.get('FEATURES_DROP_TASKS', '').split())
for label, keep in (('all held', lambda t: True),) + ((('without dropped tasks', lambda t: t not in drop),) if drop else ()):
    print(label)
    for kind in sorted(res):
        K = [i for i, (t, _) in enumerate(res[kind][0]) if keep(t[0])]
        print(kind, 'gold prefixes', len(K), 'forms', len({res[kind][0][i][0] for i in K}), 'median pool', st.median(pools[kind][i] for i in K))
        for b in B[1:]:
            d = collections.defaultdict(list)
            for i in K:
                d[res[kind][0][i][0][0]].append(res[kind][0][i][1] - res[kind][b][i][1])
            T = list(d)
            mean = lambda p: sum(sum(d[t]) for t in p) / sum(len(d[t]) for t in p)
            bs = sorted(mean([boot.choice(T) for _ in T]) for _ in range(2000))
            print(f'  beta {b}: median log2 rank {st.median(res[kind][b][i][1] for i in K):.2f} mean gain {mean(T):+.2f} 90% {bs[100]:+.2f} {bs[1900]:+.2f}')
