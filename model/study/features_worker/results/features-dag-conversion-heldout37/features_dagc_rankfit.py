#!/usr/bin/env python
"""Rank refit (item 9): softmax boosting over a pick's options, started at the offset `lq` of the `off` walks: score(option) = lq + eta * sum of trees. A tree is a Newton step on the softmax loss of the pick.

  features_dagc_env.sh 4 features_dagc_rankfit.py cv FIT.npz[,..] --read READ.npz[,..] [--arms structure,content,control]       task folds: fit on the picks of the other folds of READ's tasks, read the fold
  features_dagc_env.sh 4 features_dagc_rankfit.py final FIT.npz[,..] --read HELD.npz --arms ARM --held [--rounds N --eta E --leaves L]    one arm: fit on all fit tasks, ONE read on the held tasks. Writes a line to held-reads.jsonl.
  features_dagc_env.sh 1 features_dagc_rankfit.py table --read HELD.npz --live-bits bits-live.npz [--forms form-bits-dag.tsv]            the tables from the saved bits of the arms. No new read.

Copy of features_rel_fit.py with: the offset `lq` of `off` (no steer swap, no cross-fit); picks that carry a weight `w` (the share of a form's finished walks that reach the pick key), used in the sampling, the Newton step and every mean;
the columns of features_dagc_matrix (S = structure, C = content); `lex1` (the lift of the option's relation token) and no `lex2` (it read the previous relation); an internal rank by `lq` with ties at their lowest place,
used to choose the rows that a tree always fits on and read by no tree; classes as before; `d_depth` bands 0, 1, 2, 3+ in place of the first, second, third and later atom. Arms: structure, content, control (content, on a label drawn from `lq`).
Measures: bits per pick weighted by `w`, 95% from 10,000 resamples of tasks. Saved over `off` at the same pick keys; saved over `live`: the mean live bits at the same pick keys (bits-*.npz) less the model's bits. Per form: the sum
of w * saved over a form's picks is the mean over its orders of the sum over a walk's picks.
Resume: `final` saves its trees every 50 rounds in rank/ckpt-ARM.pkl and continues from them. `cv` appends each (arm, leaves, eta, fold) to rank/cv-lines.jsonl and skips lines it holds.
Held guard: `cv` stops if READ holds a held task. `final` stops unless READ holds the 37 held tasks and FIT holds none.
Smoke: `final --smoke` and `table --smoke` run the same code on rows with no held task (READ is non-held, for example dev-cut), write under rank-smoke/, and write no ledger line.
"""
import argparse
import hashlib
import json
import math
import os
import pickle
import sys
import time

import numpy as np
import zstandard
from sklearn.ensemble import HistGradientBoostingRegressor

sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-dag-conversion-heldout37')
import features_dagc_facts as F  # noqa: E402
import features_dagc_lib as L  # noqa: E402
import features_dagc_matrix as M  # noqa: E402

ME = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-dag-conversion-heldout37/'  # the data folder
OUT = ME + 'rank/'
LN2 = math.log(2)
TOP = 24  # options per pick that a tree always fits on, by lq; gold too
SHARE = 6  # one in this many of the other options is fit on, at this weight
LEX_A = 2.0
CLS = {'relation': 'derived', 'lib relation': 'lib'}
BANDS = {0: 'D empty (band 0)', 1: 'band 1', 2: 'band 2', 3: 'band 3 or more'}


def held_tasks():
    return set(L.held_tasks())


class Picks:
    """Picks of data-NAME.npz files (features_dagc_data.py). Picks without gold among the options are dropped (count in `dropped`)."""

    def __init__(self, paths, kinds=('RULE',)):
        S, Co, starts, gold, w, toks, pk, self.m = [], [], [0], [], [], [], [], {}
        vocab, self.dropped, self.forms, self.scope_known = {}, 0, [], []
        for p in paths:
            z = np.load(p, allow_pickle=False)
            if 'checked' not in z.files:
                raise SystemExit('%s has no `checked` field: rebuild it with features_dagc_data.py' % p)
            F.check_columns(list(z['names']))
            self.scope_known.append(json.loads(str(z['checked'])).get('scope_in_rows'))
            self.forms += json.loads(str(z['forms']))
            st = z['starts']
            kind = z['m_kind']
            keep = np.isin(kind, list(kinds)) & (z['gold'] >= 0)
            self.dropped += int((np.isin(kind, list(kinds)) & (z['gold'] < 0)).sum())
            idx = np.nonzero(keep)[0]
            rows = np.concatenate([np.arange(st[i], st[i + 1]) for i in idx]) if len(idx) else np.zeros(0, np.int64)
            S.append(z['S'][rows]), Co.append(z['C'][rows])
            for i in idx:
                starts.append(starts[-1] + int(st[i + 1] - st[i]))
            gold.append(z['gold'][idx]), w.append(z['w'][idx]), pk.append(z['pkey'][idx])
            vt = z['v_tok']
            toks.append(np.array([vocab.setdefault(t, len(vocab)) for t in vt.tolist()], np.int32)[z['tok'][rows]])
            for k in z.files:
                if k.startswith('m_'):
                    self.m.setdefault(k[2:], []).append(z[k][idx])
        self.S, self.C = np.vstack(S), np.vstack(Co)
        self.starts = np.array(starts)
        self.gold, self.w, self.toks, self.pkey = np.concatenate(gold), np.concatenate(w).astype(np.float64), np.concatenate(toks), np.concatenate(pk)
        self.m = {k: np.concatenate(v) for k, v in self.m.items()}
        self.vocab = vocab
        self.n = len(self.gold)
        self.pick = np.repeat(np.arange(self.n), np.diff(self.starts))
        self.lq = self.S[:, 0].astype(np.float64)
        self.task = self.m['task']
        self.rk = rank_min(self.lq, self.pick, self.starts)

    def base(self, arm):
        return self.S if arm == 'structure' else np.hstack([self.S, self.C])

    def names(self, arm):
        return M.STRUCT + ([] if arm == 'structure' else M.CONTENT) + ['lex1']


def rank_min(lq, pick, starts):
    """Within a pick, the count of options with a larger lq: ties share their lowest place, so no tie reads an option's place."""
    o = np.lexsort((-lq, pick))
    s = lq[o]
    p = pick[o]
    new = np.ones(len(o), bool)
    new[1:] = (s[1:] != s[:-1]) | (p[1:] != p[:-1])
    first = np.maximum.accumulate(np.where(new, np.arange(len(o)), 0))
    r = np.empty(len(o), np.float64)
    r[o] = first - starts[p]
    return r


def logsoft(score, pick, starts):
    mx = np.maximum.reduceat(score, starts[:-1])
    s = np.exp(score - mx[pick])
    return score - mx[pick] - np.log(np.add.reduceat(s, starts[:-1]))[pick]


def bits(score, D):
    return -logsoft(score, D.pick, D.starts)[D.starts[:-1] + D.gold] / LN2


def lex1_tables(D, picks, gold):
    """({token id: (weighted gold count, weighted q mass)}) as two arrays over the vocabulary, from the fit picks alone."""
    pm = np.zeros(D.n, bool)
    pm[picks] = True
    rows = np.nonzero(pm[D.pick])[0]
    q = np.exp(logsoft(D.lq, D.pick, D.starts))
    wr = D.w[D.pick[rows]]
    isg = (rows == D.starts[D.pick[rows]] + gold[D.pick[rows]]).astype(np.float64)
    nv = len(D.vocab)
    return np.bincount(D.toks[rows], isg * wr, nv), np.bincount(D.toks[rows], q[rows] * wr, nv)


def lex1_cols(D, tabs, idx):
    g, m = tabs
    t = D.toks[idx]
    return np.log((g[t] + LEX_A) / (m[t] + LEX_A)).astype(np.float32)[:, None]


def task_fold(tasks, k, seed):
    u = sorted(set(tasks.tolist()))
    np.random.RandomState(seed).shuffle(u)
    return {t: i % k for i, t in enumerate(u)}


def lex_fit(D, picks, gold, folds=4):
    """The lex column over all options of D: out of fold on `picks` (a tree sees no row's label through it). (column, tables of all `picks`)"""
    fid = task_fold(D.task[picks], folds, 1)
    f = np.array([fid[t] for t in D.task[picks].tolist()])
    X = np.zeros((len(D.toks), 1), np.float32)
    pf = np.full(D.n, -1)
    pf[picks] = f
    of = pf[D.pick]
    for i in range(folds):
        X[of == i] = lex1_cols(D, lex1_tables(D, picks[f != i], gold), np.nonzero(of == i)[0])
    return X, lex1_tables(D, picks, gold)


def sample_rows(D, picks, gold, seed=0):
    pm = np.zeros(D.n, bool)
    pm[picks] = True
    rows = np.nonzero(pm[D.pick])[0]
    near = D.rk[rows] < TOP
    near |= rows == D.starts[D.pick[rows]] + gold[D.pick[rows]]
    pick = np.random.RandomState(seed).random_sample(len(rows)) < 1.0 / SHARE
    keep = near | pick
    return rows[keep], np.where(near, 1.0, float(SHARE))[keep] * D.w[D.pick[rows]][keep]


def save_ckpt(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + '.tmp', 'wb') as f:
        pickle.dump(obj, f)
    os.replace(path + '.tmp', path)


def boost(D, X, picks, gold, rounds, eta, leaves, leaf=60, l2=5.0, reads=(), every=50, label='', ckpt=None):
    """The trees on `picks`. reads: (name, D2, X2, picks2) sets; prints the saved bits per pick (weighted) on each at each listed round. ckpt: a path; the run continues from it."""
    rows, wt = sample_rows(D, picks, gold)
    Xf = X[rows]
    gi = D.starts[D.pick[rows]] + gold[D.pick[rows]]
    y = (rows == gi).astype(np.float64)
    F_ = D.lq.copy()
    state = [(nm, D2, X2, p2, D2.lq.copy(), bits(D2.lq, D2)[p2]) for nm, D2, X2, p2 in reads]
    trees, hist, start = [], {}, 1
    if ckpt and os.path.exists(ckpt):
        c = pickle.load(open(ckpt, 'rb'))
        trees, F_, hist, start = c['trees'], c['F'], c['hist'], len(c['trees']) + 1
        for i, s in enumerate(c['state']):
            state[i][4][:] = s
        print('%s: continuing from round %d' % (label, start - 1), flush=True)
    t0 = time.time()
    for r in range(start, rounds + 1):
        p = np.exp(logsoft(F_, D.pick, D.starts)[rows])
        g = y - p
        h = np.maximum(p * (1 - p), 1e-6)
        m = HistGradientBoostingRegressor(max_iter=1, learning_rate=1.0, max_leaf_nodes=leaves, max_depth=4, min_samples_leaf=leaf, l2_regularization=l2, max_bins=32, early_stopping=False, validation_fraction=None, random_state=r)
        m.fit(Xf, g / h, sample_weight=h * wt)
        trees.append(m)
        F_ += eta * m.predict(X)
        for i, (nm, D2, X2, p2, F2, b0) in enumerate(state):
            state[i][4][:] = F2 + eta * m.predict(X2)
        if r % every == 0 or r == rounds:
            fit = float(np.average((-logsoft(F_, D.pick, D.starts)[D.starts[:-1] + gold] / LN2)[picks], weights=D.w[picks]))
            line = {nm: float(np.average(b0 - bits(F2, D2)[p2], weights=D2.w[p2])) for nm, D2, X2, p2, F2, b0 in state}
            hist[r] = line
            print('%s round %d: fit bits %.3f %s (%.0fs)' % (label, r, fit, json.dumps({k: round(v, 4) for k, v in line.items()}), time.time() - t0), flush=True)
            if ckpt:
                save_ckpt(ckpt, dict(trees=trees, F=F_, hist=hist, state=[s[4] for s in state]))
    return trees, hist


def score(D, X, trees, eta):
    F_ = D.lq.copy()
    for m in trees:
        F_ += eta * m.predict(X)
    return F_


def sampled_gold(D, seed):
    """A label drawn from q at each pick (the control)."""
    rng = np.random.RandomState(seed)
    q = np.exp(logsoft(D.lq, D.pick, D.starts))
    return np.array([rng.choice(D.starts[i + 1] - D.starts[i], p=q[D.starts[i]:D.starts[i + 1]] / q[D.starts[i]:D.starts[i + 1]].sum()) for i in range(D.n)])


def design(D, R, arm, picks, gold):
    """(fit matrix, read matrix, lex tables): the lex column out of fold on the fit picks, and from their tables on the read."""
    Xl, tabs = lex_fit(D, picks, gold)
    X = np.hstack([D.base(arm), Xl])
    XR = np.hstack([R.base(arm), lex1_cols(R, tabs, np.arange(len(R.toks)))])
    return X, XR, tabs


def cmd_cv(a):
    D = Picks(a.data.split(','))
    R = Picks(a.read.split(','))
    if set(R.task.tolist()) & held_tasks() or set(D.task.tolist()) & held_tasks():
        raise SystemExit('cv: a held task is in the rows')
    os.makedirs(OUT, exist_ok=True)
    fid = task_fold(R.task, a.folds, 0)
    print('fit picks %d (dropped with no gold %d) tasks %d, read picks %d tasks %d, read bits per pick %.3f; scope types in rows: %s' % (D.n, D.dropped, len(set(D.task.tolist())), R.n, len(set(R.task.tolist())),
          float(np.average(bits(R.lq, R), weights=R.w)), D.scope_known), flush=True)
    done = {}
    lp = OUT + 'cv-lines.jsonl'
    if os.path.exists(lp):
        for x in open(lp):
            d = json.loads(x)
            done[d['key']] = d
    res = {}
    for arm in a.arms.split(','):
        for leaves in [int(x) for x in a.leaves.split(',')]:
            for eta in [float(x) for x in a.eta.split(',')]:
                tot = {}
                for i in range(a.use_folds):
                    key = '%s|%s|l%d|e%g|f%d|r%d|n%d' % (a.tag, arm, leaves, eta, i, a.rounds, D.n)
                    if key in done:
                        h = {int(r): v for r, v in done[key]['hist'].items()}
                        npk = done[key]['npicks']
                    else:
                        dev = {t for t, f in fid.items() if f == i}
                        pf = np.nonzero([t not in dev for t in D.task.tolist()])[0]
                        pr = np.nonzero([t in dev for t in R.task.tolist()])[0]
                        gold = sampled_gold(D, i) if arm == 'control' else D.gold
                        X, XR, _ = design(D, R, 'content' if arm == 'control' else arm, pf, gold)
                        _, h = boost(D, X, pf, gold, a.rounds, eta, leaves, a.leaf, a.l2, [('read', R, XR, pr)], a.every, '%s l%d e%g f%d' % (arm, leaves, eta, i))
                        npk = float(R.w[pr].sum())
                        with open(lp, 'a') as f:
                            f.write(json.dumps(dict(key=key, hist={str(r): v for r, v in h.items()}, npicks=npk)) + '\n')
                    for r, v in h.items():
                        tot.setdefault(r, []).append((v['read'], npk))
                c = {r: sum(v * n for v, n in x) / sum(n for _, n in x) for r, x in tot.items()}
                res['%s|l%d|e%g' % (arm, leaves, eta)] = c
                print('RESULT', arm, leaves, eta, json.dumps({k: round(v, 4) for k, v in c.items()}), flush=True)
    json.dump(res, open(a.out, 'w'), indent=1)


def boot(saved, tasks, mask, w, B=10000, seed=0):
    """(weighted mean saved per pick, 95% interval) by resampling tasks. NaNs where the mask holds no pick."""
    np.seterr(all='ignore')  # Accelerate's matmul sets the flags on finite values
    if not mask.any():
        return float('nan'), float('nan'), float('nan')
    u = sorted(set(tasks.tolist()))
    ix = {t: i for i, t in enumerate(u)}
    t = np.array([ix[x] for x in tasks.tolist()])
    s = np.bincount(t[mask], (saved * w)[mask], len(u))
    n = np.bincount(t[mask], w[mask], len(u))
    W = np.random.RandomState(seed).multinomial(len(u), [1.0 / len(u)] * len(u), B)
    den = W @ n
    r = (W @ s)[den > 0] / den[den > 0]
    return float(s.sum() / max(n.sum(), 1e-12)), float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))


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


def band(R):
    return np.minimum(R.m['d_depth'], 3)


def live_bits(R, path):
    """Mean live bits at the pick keys of R, NaN where the live walks hold none."""
    z = np.load(path)
    ix = np.searchsorted(z['pkey'], R.pkey)
    ix = np.minimum(ix, len(z['pkey']) - 1)
    ok = z['pkey'][ix] == R.pkey
    return np.where(ok, z['bits'][ix], np.nan)


def form_table(R, sv_off, sv_live, forms_tsv, arms, part):
    """Per form: the sum over a form's picks of w * saved, which is the mean over its orders of the sum over a walk's picks. Forms at 25 bits or more by `bits_mean` under live, and forms under 25."""
    bm = {}
    for line in open(forms_tsv):
        f = line.rstrip('\n').split('\t')
        if f[0] != 'live' or f[1] != part:
            continue
        bm[f[2], int(f[3]), f[7]] = float(f[14])
    keys = list(zip(R.task.tolist(), R.m['line_id'].tolist(), R.m['scope_id'].tolist()))
    byform = {}
    for i, k in enumerate(keys):
        byform.setdefault(k, []).append(i)
    out = []
    for arm in arms:
        rows = {}
        for k, ix in byform.items():
            if k not in bm:
                continue
            ix = np.array(ix)
            rows[k] = (bm[k], float((R.w[ix] * sv_off[arm][ix]).sum()), float((R.w[ix] * np.nan_to_num(sv_live[arm][ix])).sum()), R.task[ix[0]])
        for name, sel in (('25 bits or more', lambda b: b >= 25), ('under 25 bits', lambda b: b < 25)):
            v = [x for x in rows.values() if sel(x[0])]
            if not v:
                continue
            tasks = np.array([x[3] for x in v])
            so = np.array([x[1] for x in v])
            sl = np.array([x[2] for x in v])
            ones = np.ones(len(v))
            mask = np.ones(len(v), bool)
            taken = sum(1 for x in v if x[0] >= 25 and x[0] - x[2] < 25)
            out.append(dict(arm=arm, forms=name, n=len(v), saved_off=boot(so, tasks, mask, ones), saved_live=boot(sl, tasks, mask, ones), mean_bits=float(np.mean([x[0] for x in v])), taken_under_25_over_live=taken))
    return out


def table(R, q, sv_off, sv_live, arms, thin=True):
    cl, bd = klass(R), band(R)
    tasks, w = R.task, R.w
    lines = []

    def row(name, mask, check_thin=True):
        n, t = int(mask.sum()), len(set(tasks[mask].tolist()))
        if n == 0:
            return
        cells = []
        for a in arms:
            o = boot(sv_off[a], tasks, mask, w)
            ok = mask & ~np.isnan(sv_live[a])
            lv = boot(np.nan_to_num(sv_live[a]), tasks, ok, w) if ok.any() else (float('nan'),) * 3
            cells.append('%+.2f (%+.2f to %+.2f) | %+.2f (%+.2f to %+.2f)' % (*o, *lv))
        tag = ' (thin)' if check_thin and thin and (n < 50 or t < 8) else ''
        lines.append('| %s%s | %d | %d | %.2f | %s |' % (name, tag, n, t, float(np.average(q[mask], weights=w[mask])), ' | '.join(cells)))

    head = '| Picks read | Picks | Tasks | Bits per pick under off | ' + ' | '.join('Saved over off, %s | Saved over live, %s' % (a, a) for a in arms) + ' |\n|---|---|---|---|' + '---|---|' * len(arms)
    lines.append(head)
    row('All', np.ones(R.n, bool), False)
    row('Gold alive', ~R.m['gold_dead'], False)
    names = dict(derived='Derived relation in scope', lib='Lib relation', own="The form's own earlier atom", rest='The rest')
    for c in names:
        row(names[c], cl == c, False)
    for b in BANDS:
        row(BANDS[b], bd == b, False)
    for c in names:
        for b in BANDS:
            row('%s, %s' % (names[c], BANDS[b].lower()), (cl == c) & (bd == b))
    return '\n'.join(lines)


def cmd_final(a):
    """One arm's fit on all fit tasks, and its one read on the held tasks."""
    if not a.held and not a.smoke:
        raise SystemExit('final is a held read: pass --held (or --smoke on rows with no held task)')
    D = Picks(a.data.split(','))
    R = Picks(a.read.split(','))
    held = held_tasks()
    leave = set(open(L.WORKER / 'held/leave_out.txt').read().split())
    fit_tasks = set(D.task.tolist())
    if a.smoke:
        assert not (fit_tasks | set(R.task.tolist())) & held, 'smoke: a held task is in the rows'
    else:
        assert not fit_tasks & leave and not fit_tasks & held, 'a held task is in the fit rows'
        assert set(R.task.tolist()) <= held, 'the read rows hold a non-held task'
    os.makedirs(OUT, exist_ok=True)
    arm = a.arms
    picks = np.arange(D.n)
    q = bits(R.lq, R)
    gap = np.abs(q - R.m['q_bits']).max()
    assert gap < 1e-3, 'the off bits differ from the walk q_bits by %g' % gap
    rep = dict(arm=arm, fit_picks=int(D.n), fit_tasks=len(fit_tasks), fit_option_rows=int(len(D.toks)), read_picks=int(R.n), read_tasks=len(set(R.task.tolist())), rounds=a.rounds, eta=a.eta, leaves=a.leaves, leaf=a.leaf, l2=a.l2,
               off_bits_vs_q_bits_max_gap=float(gap), scope_types_in_rows=D.scope_known)
    gold = sampled_gold(D, 7) if arm == 'control' else D.gold
    X, XR, tabs = design(D, R, 'content' if arm == 'control' else arm, picks, gold)
    trees, _ = boost(D, X, picks, gold, a.rounds, a.eta, a.leaves, a.leaf, a.l2, [], 50, arm, ckpt=OUT + 'ckpt-%s-%s.pkl' % (arm, hashlib.sha1(('%s|%s|%s|%s|%s|%d' % (a.data, a.eta, a.leaves, a.leaf, a.l2, D.n)).encode()).hexdigest()[:8]))
    t0 = time.process_time()
    Fs = score(R, XR, trees, a.eta)
    rep['score_ms_per_pick'] = (time.process_time() - t0) / R.n * 1000
    mb = bits(Fs, R)
    np.savez(OUT + 'final-saved-%s.npz' % arm, pkey=R.pkey, q_off=q, model=mb)
    cz = zstandard.ZstdCompressor(level=6)
    with open(OUT + 'model-%s.pkl.zst' % arm, 'wb') as f:
        f.write(cz.compress(pickle.dumps(dict(trees=trees, eta=a.eta, lex=tabs, names=R.names('content' if arm == 'control' else arm)))))
    json.dump(rep, open(OUT + 'final-%s.json' % arm, 'w'), indent=1)
    if not a.smoke:
        with open(ME + 'held-reads.jsonl', 'a') as f:
            f.write(json.dumps(dict(time=time.strftime('%Y-%m-%dT%H:%M:%S'), script='features_dagc_rankfit.py', item=9, arm=arm, read=a.read, picks=int(R.n))) + '\n')
    print('written', arm, flush=True)


def cmd_check(a):
    """Checks on rows with no held task needed (the held rows too, as no model reads them): the columns pass, no pick is without gold, the `lq` softmax bits equal the walk's q_bits at every pick, and the weights are in (0, 1]."""
    R = Picks(a.read.split(','))
    q = bits(R.lq, R)
    gap = float(np.abs(q - R.m['q_bits']).max())
    ok_w = bool(((R.w > 0) & (R.w <= 1 + 1e-6)).all())
    print('rank check: %d picks, %d dropped with no gold, off bits equal q_bits to %.5f bits, weights in (0, 1]: %s, scope types in rows: %s' % (R.n, R.dropped, gap, ok_w, R.scope_known))
    assert gap < 1e-3 and ok_w


def cmd_table(a):
    R = Picks(a.read.split(','))
    q = bits(R.lq, R)
    arms = [x for x in ('structure', 'content', 'control') if os.path.exists(OUT + 'final-saved-%s.npz' % x)]
    sv_off, sv_live, rep = {}, {}, {}
    lb = live_bits(R, a.live_bits) if a.live_bits else np.full(R.n, np.nan)
    rep['live_bits_coverage_by_weight'] = float(R.w[~np.isnan(lb)].sum() / R.w.sum())
    for x in arms:
        z = np.load(OUT + 'final-saved-%s.npz' % x)
        assert (z['pkey'] == R.pkey).all()
        sv_off[x] = z['q_off'] - z['model']
        sv_live[x] = lb - z['model']
    rep['prior_bits_per_pick_off'] = float(np.average(q, weights=R.w))
    rep['prior_bits_per_pick_live'] = float(np.average(lb[~np.isnan(lb)], weights=R.w[~np.isnan(lb)])) if (~np.isnan(lb)).any() else None
    alive = ~R.m['gold_dead']
    rep['gold_alive'] = {x: dict(over_off=boot(sv_off[x], R.task, alive, R.w), over_live=boot(np.nan_to_num(sv_live[x]), R.task, alive & ~np.isnan(lb), R.w)) for x in arms}
    rep['all'] = {x: dict(over_off=boot(sv_off[x], R.task, np.ones(R.n, bool), R.w), over_live=boot(np.nan_to_num(sv_live[x]), R.task, ~np.isnan(lb), R.w)) for x in arms}
    if 'structure' in arms and 'content' in arms:
        rep['content_minus_structure'] = boot(sv_off['content'] - sv_off['structure'], R.task, np.ones(R.n, bool), R.w)
    if a.forms:
        rep['per_form'] = form_table(R, sv_off, sv_live, a.forms, arms, a.part)
    txt = table(R, q, sv_off, sv_live, arms)
    json.dump(rep, open(OUT + 'final.json', 'w'), indent=1)
    open(OUT + 'final-table.md', 'w').write(txt + '\n')
    print(json.dumps(rep, indent=1))
    print(txt)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd')
    ap.add_argument('data', nargs='?', default='')
    ap.add_argument('--read', required=True)
    ap.add_argument('--folds', type=int, default=4)
    ap.add_argument('--use-folds', type=int, default=4)
    ap.add_argument('--rounds', type=int, default=500)
    ap.add_argument('--every', type=int, default=50)
    ap.add_argument('--eta', default='.1')
    ap.add_argument('--leaves', default='8')
    ap.add_argument('--leaf', type=int, default=60)
    ap.add_argument('--l2', type=float, default=5.0)
    ap.add_argument('--arms', default='structure,content')
    ap.add_argument('--tag', default='')
    ap.add_argument('--out', default=OUT + 'cv.json')
    ap.add_argument('--held', action='store_true')
    ap.add_argument('--smoke', action='store_true')
    ap.add_argument('--live-bits', default='')
    ap.add_argument('--forms', default='')
    ap.add_argument('--part', default='held-parents', help='the part of form-bits-dag.tsv whose live bits_mean sets the 25 bit cut')
    a = ap.parse_args()
    if a.smoke:
        globals()['OUT'] = ME + 'rank-smoke/'
    os.makedirs(OUT, exist_ok=True)
    if a.cmd == 'cv':
        cmd_cv(a)
    elif a.cmd == 'table':
        cmd_table(a)
    elif a.cmd == 'check':
        cmd_check(a)
    else:
        a.eta, a.leaves = float(a.eta), int(a.leaves)
        cmd_final(a)


if __name__ == '__main__':
    main()
