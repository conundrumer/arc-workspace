"""Rank of a gold prefix among its own siblings. Fits on the rows of tasks outside the read list, on whatever forms have landed, and reads the tasks on that list; with --held it also reads the held forms. A group is one gold prefix and its siblings. A rerun refits on the rows there are.

  features_sibling_fit.py ROWS READ_TASKS KEEP_MODELS OUT [--held FORMS]
"""
import argparse, collections, glob, gzip, os, pickle, random
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier as H
ap = argparse.ArgumentParser(); ap.add_argument('rows'); ap.add_argument('read'); ap.add_argument('keep'); ap.add_argument('out'); ap.add_argument('--held'); a = ap.parse_args()
P = dict(max_iter=300, learning_rate=.06, max_depth=4, min_samples_leaf=20, l2_regularization=1., random_state=0)
read = set(open(a.read).read().split())
held = {tuple(l.split()[:2]) for l in open(a.held)} if a.held else set()
allheld = {tuple(l.split()[:2]) for l in open(os.environ['FEATURES_HELD_FORMS'])}
NEW = ('ctx.', 'shape.')


def groups():
    for f in sorted(glob.glob(a.rows + '/*.pkl.gz')):
        try:
            with gzip.open(f, 'rb') as g:
                r = pickle.load(g)
        except (EOFError, OSError):
            continue
        by = collections.defaultdict(list)
        for x in r['rows']:
            by[x['split']].append(x)
        for s, R in by.items():
            if any(x['gold'] for x in R) and any(not x['gold'] for x in R):
                yield r['task'], str(r['line']), s, R


G = list(groups())
is_held = lambda g: (g[0], g[1]) in allheld
fit = [g for g in G if not is_held(g) and g[0] not in read]
test = [g for g in G if not is_held(g) and g[0] in read]
hold = [g for g in G if (g[0], g[1]) in held]
print('groups fit', len(fit), 'read', len(test), 'held', len(hold), 'tasks fit', len({g[0] for g in fit}), 'read', len({g[0] for g in test}), flush=True)


def arrays(R, ix):
    X = np.full((len(R), len(ix) + 1), np.nan, np.float32)
    for i, x in enumerate(R):
        X[i, -1] = x['atoms']
        for k, v in x['f'].items():
            j = ix.get(k)
            if j is not None and v is not None:
                X[i, j] = v
    return X


def train(ix):
    X = np.vstack([arrays(g[3], ix) for g in fit])
    y = np.concatenate([[x['gold'] for x in g[3]] for g in fit])
    w = np.concatenate([np.where(np.array([x['gold'] for x in g[3]]), 1., 1 / (len(g[3]) - 1)) for g in fit])
    return H(**P).fit(X, y, sample_weight=w * len(y) / w.sum())


keep = pickle.load(open(a.keep, 'rb'))
keys = sorted({k for g in fit for x in g[3] for k in x['f']})
old = [k for k in keys if not k.startswith(NEW)]; new = [k for k in keys if k.startswith(NEW)]
sets = {'same features': old, 'with context': keys, 'context only': new}
print('features', len(old), '+', len(new), flush=True)
kix = {k: i for i, k in enumerate(keep['names'])}
M = {'current keep': (keep['models']['form weight'], kix)}
for n, s in sets.items():
    ix = {k: i for i, k in enumerate(s)}
    M[n] = (train(ix), ix); print('fit', n, flush=True)
    with open(a.out + '/sibling-models.new', 'wb') as g:
        pickle.dump({k: dict(model=m, names=list(i)) for k, (m, i) in M.items() if k != 'current keep'}, g)
    os.replace(a.out + '/sibling-models.new', a.out + '/sibling-models.pkl')


def ranks(gs, m, ix):
    out = []
    for g in gs:
        s = m.decision_function(arrays(g[3], ix)); y = np.array([x['gold'] for x in g[3]])
        v = s[y].max(); o = s[~y]
        wins = collections.defaultdict(list)
        for x, b in zip([x for x in g[3] if not x['gold']], o):
            wins[x['kind']].append(float(v > b) + .5 * float(v == b))
        out.append(dict(task=g[0], form=g[1], split=g[2], atoms=g[2], n=len(o), rank=1 + float((o > v).sum()) + .5 * float((o == v).sum()), wins=wins))
    return out


def rate(rows, k):
    t = collections.defaultdict(list)
    for r in rows:
        t[r['task']].append(r['rank'] <= k)
    T = list(t); f = lambda p: sum(sum(t[x]) for x in p) / max(sum(len(t[x]) for x in p), 1)
    b = random.Random(0); bs = sorted(f([b.choice(T) for _ in T]) for _ in range(1000))
    return f(T), bs[25], bs[974]


def paired(x, y, k):
    d = collections.defaultdict(list)
    for p, q in zip(x, y):
        d[p['task']].append((p['rank'] <= k) - (q['rank'] <= k))
    T = list(d); f = lambda p: sum(sum(d[x]) for x in p) / max(sum(len(d[x]) for x in p), 1)
    b = random.Random(0); bs = sorted(f([b.choice(T) for _ in T]) for _ in range(1000))
    return f(T), bs[25], bs[974]


def report(name, gs):
    if not gs:
        return
    print(f'== {name}: {len(gs)} groups, {len({g[0] for g in gs})} tasks, mean siblings {np.mean([len(g[3]) - 1 for g in gs]):.1f}', flush=True)
    R = {n: ranks(gs, m, ix) for n, (m, ix) in M.items()}
    for n, r in R.items():
        print(f'{n}: ' + ' | '.join('top %d %.3f (%.3f %.3f)' % ((k,) + rate(r, k)) for k in (1, 3)), ' chance top 1 %.3f' % np.mean([1 / (x['n'] + 1) for x in r]), flush=True)
        print('   by atoms: ' + ' | '.join(f"{s}: top 1 {np.mean([x['rank'] <= 1 for x in r if x['split'] == s]):.3f} of {sum(x['split'] == s for x in r)}" for s in (1, 2, 3)), flush=True)
        w = collections.defaultdict(list)
        for x in r:
            for k, v in x['wins'].items():
                w[k].append(float(np.mean(v)))
        print('   gold beats kind: ' + ' | '.join(f'{k} {np.mean(v):.3f}' for k, v in sorted(w.items())), flush=True)
    for x, y in (('same features', 'current keep'), ('with context', 'same features'), ('with context', 'current keep')):
        print(f'{x} minus {y}: ' + ' | '.join('top %d %+.3f (%+.3f %+.3f)' % ((k,) + paired(R[x], R[y], k)) for k in (1, 3)), flush=True)
    with open(f"{a.out}/ranks-{name.replace(' ', '-')}.pkl.new", 'wb') as g:
        pickle.dump({n: [{k: v for k, v in x.items() if k != 'wins'} for x in r] for n, r in R.items()}, g)
    os.replace(f"{a.out}/ranks-{name.replace(' ', '-')}.pkl.new", f"{a.out}/ranks-{name.replace(' ', '-')}.pkl")


report('non-held read', test)
report('held', hold)
