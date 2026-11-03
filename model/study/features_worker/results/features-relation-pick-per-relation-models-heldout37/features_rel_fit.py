#!/usr/bin/env python
"""Softmax boosting over a pick's options, started at the steered prior: score(option) = log q(option) + eta * sum of trees. A tree is a Newton step on the softmax loss of the pick.

  python features_rel_fit.py cv FIT.npz[,..] --read READ.npz[,..]    task folds: fit on FIT's picks of the other folds, read on READ's picks of the fold
  python features_rel_fit.py final FIT.npz[,..] --read HELD.npz --arms ARM --rounds N --eta E --leaves L    an arm's fit on all fit tasks and its one read on the held tasks
  python features_rel_fit.py table x --read HELD.npz    the table of the arms

Arms: without content features, with content features, and the arm with content on a label drawn from q (the control: under that label the prior is right, and no feature can gain).
"""
import argparse
import json
import math
import os
import pickle
import sys
import time

import numpy as np
import zstandard
from sklearn.ensemble import HistGradientBoostingRegressor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features_rel_data as FD  # noqa: E402

OUT = FD.OUT
LN2 = math.log(2)
TOP = 24  # options per pick that a tree always fits on, by q; gold too
SHARE = 6  # one in this many of the other options is fit on, at this weight
LEX_A = 2.0
CLS = {'relation': 'derived', 'lib relation': 'lib'}
HELD = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/held/'


class Picks:
    def __init__(self, paths):
        S, Co, starts, gold, toks, last, self.m = [], [], [0], [], [], [], {}
        for p in paths:
            z = np.load(p, allow_pickle=False)
            S.append(z['S']), Co.append(z['C']), gold.append(z['gold']), toks.append(z['toks']), last.append(z['last'])
            starts += list(starts[-1] + z['starts'][1:])
            for k in z.files:
                if k.startswith('m_'):
                    self.m.setdefault(k[2:], []).append(z[k])
        self.S, self.C = np.vstack(S), np.vstack(Co)
        self.starts = np.array(starts)
        self.gold, self.toks, self.last = np.concatenate(gold), np.concatenate(toks), np.concatenate(last)
        self.m = {k: np.concatenate(v) for k, v in self.m.items()}
        self.n = len(self.gold)
        self.pick = np.repeat(np.arange(self.n), np.diff(self.starts))
        self.lq = self.S[:, 0].astype(np.float64)
        self.task = self.m['task']
        assert (self.gold >= 0).all()

    def base(self, arm):
        return self.S if arm == 'structure' else np.hstack([self.S, self.C])


def logsoft(score, pick, starts):
    mx = np.maximum.reduceat(score, starts[:-1])
    s = np.exp(score - mx[pick])
    return score - mx[pick] - np.log(np.add.reduceat(s, starts[:-1]))[pick]


def bits(score, D):
    return -logsoft(score, D.pick, D.starts)[D.starts[:-1] + D.gold] / LN2


def lex_tables(D, picks, gold):
    """{relation: [gold count, q mass]} and {(previous relation, relation): [count, mass]} over the picks. Only fit tasks' labels enter."""
    q = np.exp(logsoft(D.lq, D.pick, D.starts))
    t1, t2 = {}, {}
    for p in picks.tolist():
        s, e, g = D.starts[p], D.starts[p + 1], D.starts[p] + gold[p]
        la = str(D.last[p])
        for i in range(s, e):
            tk = str(D.toks[i])
            a = t1.setdefault(tk, [0.0, 0.0])
            y = float(i == g)
            a[0] += y
            a[1] += q[i]
            if la:
                b = t2.setdefault((la, tk), [0.0, 0.0])
                b[0] += y
                b[1] += q[i]
    return t1, t2


def lex_cols(D, tables, idx):
    """The log lift of each option's relation, and of the pair with the previous relation, with counts smoothed by LEX_A."""
    t1, t2 = tables
    out = np.zeros((len(idx), 2), np.float32)
    for j, (tk, la) in enumerate(zip(D.toks[idx].tolist(), D.last[D.pick[idx]].tolist())):
        a = t1.get(tk)
        if a is not None:
            out[j, 0] = math.log((a[0] + LEX_A) / (a[1] + LEX_A))
        b = t2.get((la, tk))
        if b is not None:
            out[j, 1] = math.log((b[0] + LEX_A) / (b[1] + LEX_A))
    return out


def task_fold(tasks, k, seed):
    u = sorted(set(tasks.tolist()))
    np.random.RandomState(seed).shuffle(u)
    return {t: i % k for i, t in enumerate(u)}


def lex_fit(D, picks, gold, folds=4):
    """Lex columns over all options of D: out of fold on `picks`, so a tree sees no row's label through them. (columns, the tables of all of `picks`)"""
    fid = task_fold(D.task[picks], folds, 1)
    f = np.array([fid[t] for t in D.task[picks].tolist()])
    X = np.zeros((len(D.toks), 2), np.float32)
    pf = np.full(D.n, -1)
    pf[picks] = f
    of = pf[D.pick]
    for i in range(folds):
        X[of == i] = lex_cols(D, lex_tables(D, picks[f != i], gold), np.nonzero(of == i)[0])
    return X, lex_tables(D, picks, gold)


def sample_rows(D, picks, gold, seed=0):
    pm = np.zeros(D.n, bool)
    pm[picks] = True
    rows = np.nonzero(pm[D.pick])[0]
    near = D.S[rows, FD.STRUCT.index('rank')] < math.log1p(TOP)
    near |= rows == D.starts[D.pick[rows]] + gold[D.pick[rows]]
    pick = np.random.RandomState(seed).random_sample(len(rows)) < 1.0 / SHARE
    keep = near | pick
    return rows[keep], np.where(near, 1.0, float(SHARE))[keep]


def boost(D, X, picks, gold, rounds, eta, leaves, leaf=60, l2=5.0, reads=(), every=50, label=''):
    """The trees on `picks`. reads: (name, D2, X2, picks2) sets; prints and gives the saved bits per pick on each at each listed round."""
    rows, wt = sample_rows(D, picks, gold)
    Xf = X[rows]
    gi = D.starts[D.pick[rows]] + gold[D.pick[rows]]
    y = (rows == gi).astype(np.float64)
    pm = np.zeros(D.n, bool)
    pm[picks] = True
    F = D.lq.copy()
    state = [(nm, D2, X2, p2, D2.lq.copy(), bits(D2.lq, D2)[p2]) for nm, D2, X2, p2 in reads]
    trees, hist = [], {}
    t0 = time.time()
    for r in range(1, rounds + 1):
        p = np.exp(logsoft(F, D.pick, D.starts)[rows])
        g = y - p
        h = np.maximum(p * (1 - p), 1e-6)
        m = HistGradientBoostingRegressor(max_iter=1, learning_rate=1.0, max_leaf_nodes=leaves, max_depth=4, min_samples_leaf=leaf, l2_regularization=l2, max_bins=32, early_stopping=False, validation_fraction=None, random_state=r)
        m.fit(Xf, g / h, sample_weight=h * wt)
        trees.append(m)
        F += eta * m.predict(X)
        for i, (nm, D2, X2, p2, F2, b0) in enumerate(state):
            state[i][4][:] = F2 + eta * m.predict(X2)
        if r % every == 0 or r == rounds:
            fit = float((-logsoft(F, D.pick, D.starts)[D.starts[:-1] + gold] / LN2)[picks].mean())
            line = {nm: float((b0 - bits(F2, D2)[p2]).mean()) for nm, D2, X2, p2, F2, b0 in state}
            hist[r] = {nm: v for nm, v in line.items()}
            print('%s round %d: fit bits %.3f %s (%.0fs)' % (label, r, fit, json.dumps({k: round(v, 4) for k, v in line.items()}), time.time() - t0), flush=True)
    return trees, hist


def score(D, X, trees, eta):
    F = D.lq.copy()
    for m in trees:
        F += eta * m.predict(X)
    return F


def sampled_gold(D, seed):
    """A label drawn from q at each pick."""
    rng = np.random.RandomState(seed)
    q = np.exp(logsoft(D.lq, D.pick, D.starts))
    return np.array([rng.choice(D.starts[i + 1] - D.starts[i], p=q[D.starts[i]:D.starts[i + 1]] / q[D.starts[i]:D.starts[i + 1]].sum()) for i in range(D.n)])


def design(D, R, arm, picks, gold, rp=None):
    """(fit matrix, read matrix) with the lex columns: out of fold on the fit picks, and from the fit picks' tables on the read."""
    Xl, tabs = lex_fit(D, picks, gold)
    X = np.hstack([D.base(arm), Xl])
    XR = np.hstack([R.base(arm), lex_cols(R, tabs, np.arange(len(R.toks)))])
    return X, XR, tabs


def cmd_cv(a):
    D = Picks(a.data.split(','))
    R = Picks(a.read.split(','))
    fid = task_fold(R.task, a.folds, 0)
    print('fit picks', D.n, 'tasks', len(set(D.task.tolist())), 'read picks', R.n, 'tasks', len(set(R.task.tolist())), 'read bits per pick %.3f' % bits(R.lq, R).mean(), flush=True)
    res = {}
    for name in filter(None, a.drop.split(',')):
        D.S[:, FD.STRUCT.index(name)] = 0
        R.S[:, FD.STRUCT.index(name)] = 0
    for arm in a.arms.split(','):
        for leaves in [int(x) for x in a.leaves.split(',')]:
            for eta in [float(x) for x in a.eta.split(',')]:
                tot = {}
                for i in range(a.use_folds):
                    dev = {t for t, f in fid.items() if f == i}
                    pf = np.nonzero([t not in dev for t in D.task.tolist()])[0]
                    pr = np.nonzero([t in dev for t in R.task.tolist()])[0]
                    gold = sampled_gold(D, i) if arm == 'control' else D.gold
                    X, XR, _ = design(D, R, 'content' if arm == 'control' else arm, pf, gold)
                    _, h = boost(D, X, pf, gold, a.rounds, eta, leaves, a.leaf, a.l2, [('read', R, XR, pr)], a.every, '%s l%d e%g f%d' % (arm, leaves, eta, i))
                    for r, v in h.items():
                        tot.setdefault(r, []).append((v['read'], len(pr)))
                c = {r: sum(v * n for v, n in x) / sum(n for _, n in x) for r, x in tot.items()}
                res['%s|l%d|e%g' % (arm, leaves, eta)] = c
                print('RESULT', arm, leaves, eta, json.dumps({k: round(v, 4) for k, v in c.items()}), flush=True)
    json.dump(res, open(a.out, 'w'), indent=1)


def boot(saved, tasks, mask, B=10000, seed=0):
    """(mean saved per pick, 95% interval) by resampling tasks."""
    u = sorted(set(tasks.tolist()))
    ix = {t: i for i, t in enumerate(u)}
    t = np.array([ix[x] for x in tasks.tolist()])
    s = np.bincount(t[mask], saved[mask], len(u))
    n = np.bincount(t[mask], minlength=len(u)).astype(float)
    W = np.random.RandomState(seed).multinomial(len(u), [1.0 / len(u)] * len(u), B)
    den = W @ n
    r = (W @ s)[den > 0] / den[den > 0]
    return float(s.sum() / max(n.sum(), 1)), float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))


def klass(R):
    out = []
    for k, own in zip(R.m['gold_kind'].tolist(), R.m['own'].tolist()):
        if k in ('NOT', 'CMP'):
            out.append('rest')
        elif own:
            out.append('own')
        else:
            out.append(CLS.get(k, 'rest'))
    return np.array(out)


def table(R, q, sv, atoms):
    """The final table: margins and cells, with both arms and the control."""
    cl, ord_ = klass(R), R.m['ord']
    pos = np.where(ord_ >= 4, 4, ord_)
    tasks = R.task
    lines = []

    def row(name, mask, thin=True):
        n, t = int(mask.sum()), len(set(tasks[mask].tolist()))
        if n == 0:
            return
        m = [boot(sv[a], tasks, mask) for a in ('structure', 'content')]
        tag = ' (thin)' if thin and (n < 50 or t < 8) else ''
        lines.append('| %s%s | %d | %d | %.2f | %+.2f (%+.2f to %+.2f) | %+.2f (%+.2f to %+.2f) |' % (name, tag, n, t, q[mask].mean(), m[0][0], m[0][1], m[0][2], m[1][0], m[1][1], m[1][2]))

    head = '| Picks read | Picks | Tasks | Prior bits per pick | Saved, no content | Saved, with content |\n|---|---|---|---|---|---|'
    lines.append(head)
    row('All', np.ones(R.n, bool), False)
    row('Gold alive', ~R.m['gold_dead'], False)
    names = dict(derived='Derived relation in scope', lib='Lib relation', own="The form's own earlier atom", rest='The rest')
    for c in ('derived', 'lib', 'own', 'rest'):
        row(names[c], cl == c, False)
    pn = {1: 'First atom', 2: 'Second atom', 3: 'Third atom', 4: 'Later atoms'}
    for p in (1, 2, 3, 4):
        row(pn[p], pos == p, False)
    for c in ('derived', 'lib', 'own', 'rest'):
        for p in (1, 2, 3, 4):
            row('%s, %s' % (names[c], pn[p].lower()), (cl == c) & (pos == p))
    return '\n'.join(lines)


def cmd_final(a):
    """One arm's fit on all fit tasks, and its read on the held tasks. `table` joins the arms."""
    D = Picks(a.data.split(','))
    R = Picks(a.read.split(','))
    picks = np.arange(D.n)
    held = set(open(HELD + 'tasks.txt').read().split())
    leave = set(open(HELD + 'leave_out.txt').read().split())
    fit_tasks = set(D.task.tolist())
    assert not fit_tasks & leave and not fit_tasks & held
    assert set(R.task.tolist()) == held
    rep = dict(fit_picks=int(D.n), fit_tasks=len(fit_tasks), fit_option_rows=int(len(D.toks)), read_picks=int(R.n), read_tasks=len(held), rounds=a.rounds, eta=a.eta, leaves=a.leaves, leaf=a.leaf, l2=a.l2)
    q = bits(R.lq, R)
    assert np.abs(q - R.m['q_bits']).max() < 1e-3
    cz = zstandard.ZstdCompressor(level=6)
    arm = a.arms
    gold = sampled_gold(D, 7) if arm == 'control' else D.gold
    X, XR, tabs = design(D, R, 'content' if arm == 'control' else arm, picks, gold)
    trees, _ = boost(D, X, picks, gold, a.rounds, a.eta, a.leaves, a.leaf, a.l2, [], 50, arm)
    t0 = time.process_time()
    F = score(R, XR, trees, a.eta)
    rep['score_ms_per_pick'] = (time.process_time() - t0) / R.n * 1000
    rep['threads'] = os.environ.get('OMP_NUM_THREADS')
    np.save(OUT + 'final-saved-%s.npy' % arm, q - bits(F, R))
    with open(OUT + 'model-%s.pkl.zst' % arm, 'wb') as f:
        f.write(cz.compress(pickle.dumps(dict(trees=trees, eta=a.eta, lex=tabs, names=FD.STRUCT + ([] if arm == 'structure' else FD.CONTENT) + ['lex1', 'lex2']))))
    json.dump(rep, open(OUT + 'final-%s.json' % arm, 'w'), indent=1)
    print('written', arm, flush=True)


def cmd_table(a):
    R = Picks(a.read.split(','))
    q = bits(R.lq, R)
    sv = {arm: np.load(OUT + 'final-saved-%s.npy' % arm) for arm in ('structure', 'content', 'control')}
    forms = json.loads(str(np.load(a.read.split(',')[0], allow_pickle=False)['forms']))
    atoms = sum(f['natoms'] for f in forms if not (f['error'] or f['dead'] or f['bad']))
    rep = {arm: json.load(open(OUT + 'final-%s.json' % arm)) for arm in sv}
    rep['atoms'] = atoms
    rep['prior_bits_per_pick'] = float(q.mean())
    for arm in sv:
        rep['saved_' + arm] = boot(sv[arm], R.task, np.ones(R.n, bool))
        rep['saved_per_atom_' + arm] = float(sv[arm].sum() / atoms)
    rep['content_minus_structure'] = boot(sv['content'] - sv['structure'], R.task, np.ones(R.n, bool))
    alive = ~R.m['gold_dead']
    rep['gold_alive'] = {arm: boot(sv[arm], R.task, alive) for arm in sv}
    txt = table(R, q, sv, atoms)
    np.savez(OUT + 'final-picks.npz', q=q, task=R.task, line=R.m['line'], ord=R.m['ord'], phase=R.m['phase'], **{'saved_' + k: v for k, v in sv.items()})
    json.dump(rep, open(OUT + 'final.json', 'w'), indent=1)
    open(OUT + 'final-table.md', 'w').write(txt + '\n')
    print(json.dumps({k: v for k, v in rep.items() if k not in sv}, indent=1))
    print(txt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd')
    ap.add_argument('data')
    ap.add_argument('--read', required=True)
    ap.add_argument('--folds', type=int, default=4)
    ap.add_argument('--use-folds', type=int, default=4)
    ap.add_argument('--rounds', type=int, default=200)
    ap.add_argument('--every', type=int, default=50)
    ap.add_argument('--eta', default='.1')
    ap.add_argument('--leaves', default='8')
    ap.add_argument('--leaf', type=int, default=60)
    ap.add_argument('--l2', type=float, default=5.0)
    ap.add_argument('--arms', default='structure,content')
    ap.add_argument('--out', default=OUT + 'cv.json')
    ap.add_argument('--drop', default='', help='cv: structure features set to 0 in the fit and the read')
    a = ap.parse_args()
    if a.cmd == 'cv':
        cmd_cv(a)
    elif a.cmd == 'table':
        cmd_table(a)
    else:
        a.eta, a.leaves = float(a.eta), int(a.leaves)
        cmd_final(a)


if __name__ == '__main__':
    main()
