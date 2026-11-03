#!/usr/bin/env python
"""Read of the pool observables against a target file.

  features_signal_read.py TARGET.jsonl OUT.json [--boots N] [--drop-undrawable]

TARGET.jsonl comes from features_targets.py, so a later gold is one command: features_targets.py NAME TARGET.jsonl CENSUS.jsonl, then this script.
Reads signal-cheap.jsonl and signal-tables.shard*.jsonl next to this script. Prints the tables and writes them to OUT.json.

Fixed rules are in the manifest under read_plan.
"""
import collections
import glob
import json
import os
import sys
import warnings

import numpy as np
from scipy.stats import rankdata
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.model_selection import StratifiedKFold, KFold

warnings.filterwarnings('ignore', category=RuntimeWarning)  # numpy's matmul on Accelerate warns on finite results
HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = '/Users/davidlu/code/arc-workspace/'
W = MAIN + 'work/'
HELD = set(open(W + 'lm/data-study/sampler/sampler-worker/held/tasks.txt').read().split())
CUTS = '60', '300', '600'
BAR = 25.0
OBS = 'nodes', 'forms', 'proposals', 'best_out', 'shape_forms'
CHEAP = 'nodes', 'forms', 'proposals'
BOOTS = int(sys.argv[sys.argv.index('--boots') + 1]) if '--boots' in sys.argv else 2000
DROP = '--drop-undrawable' in sys.argv
ARMS_37 = [('job23', 'control_search'), ('job23', 'factored_search'), ('gate', 'control_search'), ('gate', 'gate_search'), ('context', 'control'), ('context', 'context_cover'), ('job17', 'search'), ('job17', 'draws')]
ARMS_46 = [('kaggle-v5', 'draws'), ('soak', 'search'), ('soak', 'draws')]
TABLE_RUNS = 'job23', 'gate', 'soak', 'kaggle-v5'


def load():
    rows = {}
    for l in open(HERE + '/signal-cheap.jsonl'):
        r = json.loads(l)
        rows[r['run'], r['arm'], r['task']] = r
    for f in glob.glob(HERE + '/signal-tables.shard*.jsonl'):
        for l in open(f):
            r = json.loads(l)
            k = r['run'], r['arm'], r['task']
            if 'error' in r or k not in rows:
                print('table error', k, r.get('error'))
                continue
            for S, v in r['cuts'].items():
                rows[k]['cuts'][S].update(v)
                rows[k]['cuts'][S].setdefault('nodes', v['table_nodes'])
                if rows[k]['machine_read'] == 'flat':
                    rows[k]['cuts'][S]['nodes'] = v['table_nodes']
            rows[k]['tables'] = True
    return rows


def area(t):
    """Mean cells of the train grids, and whether every train output has its input's size. Reads train pairs only."""
    d = json.load(open(f'{MAIN}data/tasks/{t}.json'))
    a = [len(g) * len(g[0]) for p in d['train'] for g in (p['input'], p['output'])]
    same = all(len(p['input']) == len(p['output']) and len(p['input'][0]) == len(p['output'][0]) for p in d['train'])
    return sum(a) / len(a), same


def auc_matrix(score, y):
    """Sign matrix over positives by negatives: 1, .5 or 0."""
    p, n = score[y], score[~y]
    return (p[:, None] > n[None, :]) + .5 * (p[:, None] == n[None, :])


class Strata:
    """Rows in arms, each row with a task and a weight. Pair comparisons stay inside an arm, and a task's rows share its bootstrap count."""

    def __init__(self, rows, tasks):
        self.tasks = tasks
        self.ix = {t: i for i, t in enumerate(tasks)}
        self.arms = collections.defaultdict(list)
        for r in rows:
            self.arms[r['key']].append(r)
        for v in self.arms.values():
            v.sort(key=lambda r: r['task'])

    def auc_stat(self, fn, tname):
        parts = []
        for v in self.arms.values():
            y = np.array([r[tname] for r in v], bool)
            if y.sum() == 0 or (~y).sum() == 0:
                continue
            s = np.array([fn(r) for r in v], float)
            w = np.array([r['w'] for r in v])
            ti = np.array([self.ix[r['task']] for r in v])
            parts.append((auc_matrix(s, y), ti[y], ti[~y], w[y], w[~y]))

        def stat(c):
            num = den = 0.
            for M, tp, tn, wp, wn in parts:
                a = c[tp] * wp
                b = c[tn] * wn
                num += a @ M @ b
                den += a.sum() * b.sum()
            return num / den if den else np.nan
        return stat, bool(parts)

    def spearman_stat(self, fn, tname):
        parts = []
        for v in self.arms.values():
            if len(v) < 5:
                continue
            s = np.array([fn(r) for r in v], float)
            y = np.array([r[tname] for r in v], float)
            ti = np.array([self.ix[r['task']] for r in v])
            w = np.array([r['w'] for r in v])
            parts.append((s, y, ti, w))

        def stat(c):
            num = den = 0.
            for s, y, ti, w in parts:
                k = c[ti].astype(int)
                if (k > 0).sum() < 4:
                    continue
                ss = np.repeat(s, k); yy = np.repeat(y, k)
                a, b = rankdata(ss), rankdata(yy)
                if a.std() == 0 or b.std() == 0:
                    continue
                rho = np.corrcoef(a, b)[0, 1]
                wt = (w * c[ti]).sum()
                num += rho * wt; den += wt
            return num / den if den else np.nan
        return stat, bool(parts)


def boot(stat, ntasks, rng):
    base = stat(np.ones(ntasks))
    vals = []
    for _ in range(BOOTS):
        c = np.bincount(rng.integers(0, ntasks, ntasks), minlength=ntasks).astype(float)
        vals.append(stat(c))
    v = np.array(vals); v = v[~np.isnan(v)]
    if not len(v):
        return base, None, None
    return base, float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))


def feat(r, S, obs):
    c = r['cuts'][S]
    out = []
    for o in obs:
        x = c.get(o)
        x = 0. if x is None else float(x)
        out.append(x if o == 'best_out' else np.log1p(x))
    return out


def arm_ranks(rows, S, obs):
    """Features as percentile ranks inside the arm, so that arms on different machines share a scale."""
    X = np.zeros((len(rows), len(obs)))
    by = collections.defaultdict(list)
    for i, r in enumerate(rows):
        by[r['key']].append(i)
    F = np.array([feat(r, S, obs) for r in rows])
    for ix in by.values():
        ix = np.array(ix)
        for j in range(len(obs)):
            X[ix, j] = rankdata(F[ix, j]) / len(ix)
    return X


def crossfit(rows, S, obs, tname, kind, seeds=5, folds=5):
    """Mean out-of-fold prediction over repeats of task folds. No row of a task trains the model that scores it."""
    X = arm_ranks(rows, S, obs)
    tasks = sorted({r['task'] for r in rows})
    w = np.array([r['w'] for r in rows])
    if kind == 'auc':
        ty = {t: max(r[tname] for r in rows if r['task'] == t) for t in tasks}
        y = np.array([r[tname] for r in rows], int)
    else:
        ty = {t: 0 for t in tasks}
        by = collections.defaultdict(list)
        for i, r in enumerate(rows):
            by[r['key']].append(i)
        y = np.zeros(len(rows))
        for ix in by.values():
            ix = np.array(ix)
            y[ix] = -rankdata([rows[i][tname] for i in ix]) / len(ix)  # a larger score reads as fewer bits, as for the observables
    pred = np.zeros(len(rows)); cnt = np.zeros(len(rows))
    tix = {t: i for i, t in enumerate(tasks)}
    rowt = np.array([tix[r['task']] for r in rows])
    ta = np.array(tasks)
    for seed in range(seeds):
        if kind == 'auc':
            lab = np.array([ty[t] for t in tasks])
            if min(lab.sum(), (1 - lab).sum()) < folds:
                return None
            sp = StratifiedKFold(folds, shuffle=True, random_state=seed).split(ta, lab)
        else:
            sp = KFold(folds, shuffle=True, random_state=seed).split(ta)
        for tr, te in sp:
            a = np.isin(rowt, tr); b = np.isin(rowt, te)
            if kind == 'auc':
                if len(set(y[a])) < 2:
                    continue
                m = LogisticRegression(C=1.0, class_weight='balanced', max_iter=500).fit(X[a], y[a], sample_weight=w[a])
                pred[b] += m.decision_function(X[b])
            else:
                m = Ridge(alpha=1.0).fit(X[a], y[a], sample_weight=w[a])
                pred[b] += m.predict(X[b])
            cnt[b] += 1
    return pred / np.maximum(cnt, 1)


def read_set(name, rows, obs, res, rng, cuts=CUTS, joint=True):
    tasks = sorted({r['task'] for r in rows})
    n = collections.Counter(r['task'] for r in rows)
    for r in rows:
        r['w'] = 1. / n[r['task']]
    st = Strata(rows, tasks)
    pos = {t: max(r['under_bar'] for r in rows if r['task'] == t) for t in tasks}
    third = {t: max(r['low_third'] for r in rows if r['task'] == t) for t in tasks}
    hdr = dict(tasks=len(tasks), rows=len(rows), arms=len(st.arms), under_bar_pos=sum(pos.values()), under_bar_neg=len(tasks) - sum(pos.values()), low_third_pos=sum(third.values()), low_third_neg=len(tasks) - sum(third.values()), undrawable=sum(r['undrawable'] > 0 for r in {x['task']: x for x in rows}.values()))
    print(f"\n== {name}: {hdr}", flush=True)
    out = dict(header=hdr, cuts={})
    for S in cuts:
        cols = {}
        items = [(o, lambda r, o=o: (r['cuts'][S].get(o) or 0.)) for o in obs]
        items.append(('area', lambda r: -r['area']))
        items.append(('same_size', lambda r: float(r['same_size'])))
        if any('covered' in r['cuts'][S] for r in rows):
            ref = [r for r in rows if 'covered' in r['cuts'][S]]
        else:
            ref = None
        for o, fn in items:
            cols[o] = one(st, fn, len(tasks), rng)
        if joint:
            for label, ob in (('joint', obs),) + ((('joint+area', tuple(obs) + ('area_cell',)),)):
                for r in rows:
                    r['cuts'][S]['area_cell'] = r['area']
                e = {}
                for tname, key, kind in (('under_bar', 'auc_bar', 'auc'), ('low_third', 'auc_third', 'auc'), ('total', 'rho', 'rho')):
                    p = crossfit(rows, S, ob, tname, kind)
                    if p is None:
                        e[key] = None
                        continue
                    for r, x in zip(rows, p):
                        r['_j'] = float(x)
                    stat, ok = (st.auc_stat if kind == 'auc' else st.spearman_stat)(lambda r: r['_j'], tname)
                    e[key] = boot(stat, len(tasks), rng) if ok else None
                cols[label] = e
        if ref:
            n2 = collections.Counter(r['task'] for r in ref)
            for r in ref:
                r['w'] = 1. / n2[r['task']]
            st2 = Strata(ref, tasks)
            cols['covered (needs gold)'] = one(st2, lambda r: r['cuts'][S].get('covered') or 0., len(tasks), rng)
            cols['covered (needs gold)']['rows'] = len(ref)
            for r in rows:
                r['w'] = 1. / n[r['task']]
        out['cuts'][S] = cols
        for o, e in cols.items():
            print(f"{S:>4} {o:<22} rho {fmt(e['rho'])} | AUC bar {fmt(e['auc_bar'])} | AUC low third {fmt(e['auc_third'])}", flush=True)
    res[name] = out


def one(st, fn, nt, rng):
    e = {}
    for tname, key, make in (('under_bar', 'auc_bar', st.auc_stat), ('low_third', 'auc_third', st.auc_stat), ('total', 'rho', st.spearman_stat)):
        stat, ok = make(fn, tname)
        e[key] = boot(stat, nt, rng) if ok else None
    return e


def fmt(x):
    if x is None:
        return 'none'
    a, b, c = x
    return f'{a:+.2f} ({b:+.2f} {c:+.2f})' if b is not None else f'{a:+.2f}'


def main():
    tfile, out = sys.argv[1], sys.argv[2]
    T = {r['task']: r for r in map(json.loads, open(tfile))}
    tname = next(iter(T.values()))['target']
    # A task with an undrawable form ranks above every task on total bits and is negative on both binary targets.
    top = max(r['total'] for r in T.values()) + 1
    good = sorted(r['worst'] for r in T.values() if not r['undrawable'] and r['worst'] is not None)
    cut = good[len(good) // 3] if good else None
    print('target', tname, 'tasks', len(T), 'with undrawable form', sum(bool(r['undrawable']) for r in T.values()), 'lowest third bar on worst form', cut)
    rows = load()
    A = {}
    R = []
    miss = collections.Counter()
    for (run, arm, t), r in rows.items():
        k = T.get(t)
        if k is None:
            miss[run, arm] += 1
            continue
        if DROP and k['undrawable']:
            continue
        if 'error' in r:
            continue
        r = dict(r, key=(run, arm))
        r['total'] = top if k['undrawable'] else k['total']
        r['under_bar'] = bool(not k['undrawable'] and k['worst'] is not None and k['worst'] < BAR)
        r['low_third'] = bool(not k['undrawable'] and k['worst'] is not None and k['worst'] <= cut)
        r['undrawable'] = k['undrawable']
        A.setdefault(t, area(t))
        r['area'], r['same_size'] = A[t]
        R.append(r)
    print('rows', len(R), 'left out for no target', dict(miss))
    # Kaggle version 5: forms covered at a cut from the replay labels, in the file that features_v5_cover.py writes.
    f = HERE + '/signal-v5-cover.jsonl'
    if os.path.exists(f):
        cov = {x['task']: x['covered'] for x in map(json.loads, open(f))}
        for r in R:
            if r['run'] == 'kaggle-v5' and r['task'] in cov:
                for S in CUTS:
                    r['cuts'][S]['covered'] = cov[r['task']][S]
    rng = np.random.default_rng(0)
    res = dict(target=tname, third_bar=cut, tasks=len(T), undrawable=sum(bool(r['undrawable']) for r in T.values()))
    res['arms'] = {}
    for key in sorted({r['key'] for r in R}):
        v = [r for r in R if r['key'] == key]
        ob = OBS if all(r.get('tables') for r in v) else CHEAP
        read_set(' '.join(key), v, ob, res['arms'], rng, joint=True)
    res['sets'] = {}
    tab = [r for r in R if r['run'] in TABLE_RUNS and r.get('tables')]
    s37 = [r for r in tab if r['task'] in HELD and r['key'] in ARMS_37 and 'search' in r['arm']]
    read_set('37 held, search arms with tables (job 23, gate)', s37, OBS, res['sets'], rng)
    s46 = [r for r in tab if r['key'] in ARMS_46]
    read_set('46: Kaggle version 5 and soak, tasks with a target', s46, OBS, res['sets'], rng)
    pool = [r for r in tab]
    read_set('pooled, arms with tables', pool, OBS, res['sets'], rng)
    read_set('Kaggle version 5 and the job 23 and gate search arms, tasks whose outputs keep the input size', [r for r in pool if r['same_size']], OBS, res['sets'], rng, joint=False)
    cheap = [r for r in R if r['task'] in HELD and r['key'] in ARMS_37 and r['arm'] != 'draws']
    read_set('37 held, every search arm, cheap observables', cheap, CHEAP, res['sets'], rng)
    with open(out + '.new', 'w') as f:
        json.dump(res, f, indent=0)
    os.replace(out + '.new', out)


if __name__ == '__main__':
    main()
