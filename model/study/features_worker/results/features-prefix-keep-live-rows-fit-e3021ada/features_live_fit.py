"""Keep model fit on live prefix rows. Fits on tasks outside the read list and reads the tasks on that list, on the rows there are; with --held it also reads the held rows. The table by atom count gives the rank of gold's row among all rows, and among rows of its own atom count. A rerun refits.

  features_live_fit.py ROWS READ_TASKS KEEP_MODELS OUT [--held HELD_ROWS]
"""
import argparse, collections, glob, json, os, pickle, random, statistics as st, subprocess
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier as H
ap = argparse.ArgumentParser(); ap.add_argument('rows'); ap.add_argument('read'); ap.add_argument('keep'); ap.add_argument('out'); ap.add_argument('--held'); a = ap.parse_args()
P = dict(max_iter=300, learning_rate=.06, max_depth=4, min_samples_leaf=20, l2_regularization=1., random_state=0)
read = set(open(a.read).read().split())
drop = set(open(os.environ['FEATURES_DROP_STEMS']).read().split())
NEW = ('ctx.', 'shape.'); BAR = 8 * .6931; USE = 'live refit 8 bits with log chance'


def cases(d):
    for f in sorted(glob.glob(d + '/*.prefix-rows.jsonl.zst')):
        p = subprocess.run(['zstd', '-dcq', f], capture_output=True, text=True).stdout.splitlines()
        L = []
        for l in p:
            try:
                x = json.loads(l)
            except ValueError:
                continue
            if 'done' not in x and 1 <= x['atoms'] <= 3:
                x.pop('table', None); x['f']['logp'] = x['logp']; L.append(x)
        if L:
            t, form = os.path.basename(f).split('.')[:2]
            yield t, form, L


C = [c for c in cases(a.rows) if c[0] not in drop]
fit = [c for c in C if c[0] not in read and any(x['gold'] for x in c[2])]
if os.environ.get('FEATURES_FIT_SHARE'):
    fit = sorted(fit, key=lambda c: c[0])[:int(len(fit) * float(os.environ['FEATURES_FIT_SHARE']))]
test = [c for c in C if c[0] in read]
hold = list(cases(a.held)) if a.held else []
print('cases fit', len(fit), 'read', len(test), 'held', len(hold), 'rows fit', sum(len(c[2]) for c in fit), 'gold rows fit', sum(x['gold'] for c in fit for x in c[2]), flush=True)


def arrays(L, ix):
    X = np.full((len(L), len(ix) + 1), np.nan, np.float32)
    for i, x in enumerate(L):
        X[i, -1] = x['atoms']
        for k, v in x['f'].items():
            j = ix.get(k)
            if j is not None and v is not None:
                X[i, j] = v
    return X


def over(L):
    return [x for x in L if -x['logp'] >= BAR]


def train(ix, cs):
    cs = [c for c in cs if any(x['gold'] for x in c) and not all(x['gold'] for x in c)]
    X = np.vstack([arrays(c, ix) for c in cs])
    y = np.concatenate([[x['gold'] for x in c] for c in cs])
    w = np.concatenate([(lambda g: np.where(g, 1 / g.sum(), 1 / max((~g).sum(), 1)))(np.array([x['gold'] for x in c])) for c in cs])
    return H(**P).fit(X, y, sample_weight=w * len(y) / w.sum())


keep = pickle.load(open(a.keep, 'rb'))
keys = sorted({k for c in fit for x in c[2] for k in x['f']})
old = [k for k in keys if not k.startswith(NEW) and k != 'logp']


class Chance:
    def decision_function(self, X):
        return X[:, 0]


M = {'current keep': (keep['models']['form weight'], {k: i for i, k in enumerate(keep['names'])}), 'log chance': (Chance(), {'logp': 0})}
for n, s, cs in (('live refit', old, [c[2] for c in fit]), ('live refit 8 bits', old, [over(c[2]) for c in fit]), ('live refit 8 bits with context', [k for k in keys if k != 'logp'], [over(c[2]) for c in fit]), ('live refit 8 bits with log chance', old + ['logp'], [over(c[2]) for c in fit])):
    ix = {k: i for i, k in enumerate(s)}
    M[n] = (train(ix, cs), ix); print('fit', n, flush=True)
    with open(a.out + '/live-models.new', 'wb') as g:
        pickle.dump({k: dict(model=m, names=list(i)) for k, (m, i) in M.items() if k not in ('current keep', 'log chance')}, g)
    os.replace(a.out + '/live-models.new', a.out + '/live-models.pkl')
    if n == USE:
        with open(a.out + '/live-keep-model.new', 'wb') as g:
            pickle.dump(dict(names=list(ix), models={'form weight': M[n][0]}), g)
        os.replace(a.out + '/live-keep-model.new', a.out + '/live-keep-model.pkl')


def rank(v, o):
    return 1 + float((o > v).sum()) + .5 * float((o == v).sum() - 1)


def read_set(name, cs):
    if not cs:
        return
    if name.endswith('at 8 bits'):
        cs = [(t, form, over(L)) for t, form, L in cs]
        cs = [c for c in cs if len(c[2])]
    print(f'== {name}: {len(cs)} cases, {len({c[0] for c in cs})} tasks, mean rows {np.mean([len(c[2]) for c in cs]):.0f}', flush=True)
    for n, (m, ix) in M.items():
        by = collections.defaultdict(list); best = []
        for t, form, L in cs:
            s = m.decision_function(arrays(L, ix)); at = np.array([x['atoms'] for x in L]); G = [i for i, x in enumerate(L) if x['gold']]
            if not G:
                best.append((t, None)); continue
            bar = np.array([-x['logp'] >= BAR for x in L])
            best.append((t, min(rank(s[i], s) for i in G)))
            for i in G:
                by[int(at[i])].append((t, rank(s[i], s), len(s), rank(s[i], s[at == at[i]]), int((at == at[i]).sum()), bool(bar[i])))
        B = [r for _, r in best if r is not None]
        print(f'{n}: cases with a gold row {len(B)} of {len(best)} | best gold row top 3 {sum(r <= 3 for r in B)}, top 16 {sum(r <= 16 for r in B)}', flush=True)
        print('  atoms | gold rows | tasks | median share of pool | top 3 | top 16 | among own atoms: median share, top 3, top 16 | at or over 8 bits', flush=True)
        for k in (1, 2, 3):
            r = by[k]
            if r:
                print(f"  {k} | {len(r)} | {len({x[0] for x in r})} | {st.median(x[1] / x[2] for x in r):.3f} | {sum(x[1] <= 3 for x in r)} | {sum(x[1] <= 16 for x in r)} | {st.median(x[3] / x[4] for x in r):.3f}, {sum(x[3] <= 3 for x in r)}, {sum(x[3] <= 16 for x in r)} | {sum(x[5] for x in r)}", flush=True)
        with open(f"{a.out}/ranks-{name.replace(' ', '-').replace(',', '')}-{n.replace(' ', '-')}.json.new", 'w') as g:
            json.dump(dict(best=best, by_atoms={str(k): v for k, v in by.items()}), g)
        os.replace(f"{a.out}/ranks-{name.replace(' ', '-').replace(',', '')}-{n.replace(' ', '-')}.json.new", f"{a.out}/ranks-{name.replace(' ', '-').replace(',', '')}-{n.replace(' ', '-')}.json")


read_set('non-held read', test)
read_set('non-held read, rows at 8 bits', test)
read_set('held', hold)
read_set('held, rows at 8 bits', hold)
