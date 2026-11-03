#!/usr/bin/env python
"""One model per key on its own rows, in task folds and on all fit tasks. Each key's result lands in rows-ARM-wN.jsonl as soon as it exists, and a rerun skips the keys that have a line. Keys run in order of gold rows, the most first.

  python features_perrel_fit.py ARM --level rel [--procs 4] [--limit N] [--min-pos 5] [--rounds 400] [--eta .3] [--lam 10] [--cap 5000] [--ntok 60] [--label gold|drawn] [--seed 7] [--depth 1 or more]

ARM names the run. --label drawn fits and reads a label drawn from the prior (the control). A key with under --min-pos gold rows in the fit gets a line with no model: it stays at what its parent level gives, or the prior.
Each fold's line holds the key's solo gain, in bits, at each checkpoint of rounds, on out-of-fold fit picks (before) and on out-of-fold test-parents picks (parents).
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-dag-conversion-heldout37')
import features_perrel_lib as L  # noqa: E402

CPS = (0, 1, 3, 6, 12, 25, 50, 100, 200, 400)
G = {}


def fit_one(D, rows, a, seed):
    pos = int(D.isgold[rows].sum())
    if pos < 2:
        return [], 0, 0
    cap = int(min(a.cap, max(a.cap_min, a.cap_per * pos)))
    rs, w = L.sample_picks(D, rows, cap, seed)
    gid, gs, rest = L.groups(D, rs)
    q = D.q[rs]
    y = D.isgold[rs].astype(np.float64)
    B, fl = L.facts(D, rs, w, q, y, gid, gs, rest, a.ntok, a.lam, seed, a.selfkeys)
    if a.depth != 1:
        ts = L.boost_trees(q, y, w, gid, gs, rest, B, a.rounds, a.eta, a.lam, a.minh, a.depth)
        return [('T', L.tree_json(t, fl)) for t in ts], len(rs), B.shape[1]
    st = L.boost(q, y, w, gid, gs, rest, B, a.rounds, a.eta, a.lam, a.minh)
    out = []
    for c, v1, v0 in st:
        if c < 0:
            out.append(('i', 0, 0.0, round(v1, 5), round(v0, 5)))
        else:
            f = fl[c]
            out.append((f[0], f[1], f[2], round(v1, 5), round(v0, 5)))
    return out, len(rs), B.shape[1]


def gains(D, rows, stumps, eta):
    if len(rows) == 0:
        return [0.0] * len(CPS), 0, 0
    P = L.path(D, rows, stumps, eta, CPS)
    out = []
    for i in range(len(CPS)):
        g, _ = L.solo(D, rows, P[:, i])
        out.append(round(float(g.sum() / L.LN2), 3))
    return out, int(D.isgold[rows].sum()), len(np.unique(D.pick[rows]))


def job(key):
    D, RP, a, IX, IXP, names, wid = G['D'], G['RP'], G['a'], G['IX'], G['IXP'], G['names'], os.getpid()
    t0 = time.time()
    rows = IX.get(key)
    pos = int(D.isgold[rows].sum())
    line = dict(key=names[key], level=a.level, pos=pos, rows=int(len(rows)), picks=len(np.unique(D.pick[rows])))
    if pos < a.min_pos:
        line['sparse'] = True
    else:
        folds = []
        for fold in range(L.FOLDS):
            rf = rows[D.fold[D.pick[rows]] != fold]
            st, nf, nfacts = fit_one(D, rf, a, 100 + fold)
            ro = rows[D.fold[D.pick[rows]] == fold]
            rp = IXP.get(key)
            rp = rp[RP.fold[RP.pick[rp]] == fold]
            gb = gains(D, ro, st, a.eta)
            gp = gains(RP, rp, st, a.eta)
            folds.append(dict(fold=fold, stumps=st, nfit=nf, nfacts=nfacts, before=gb, parents=gp))
        st, nf, nfacts = fit_one(D, rows, a, 200)
        line.update(folds=folds, stumps=st, nfit=nf, nfacts=nfacts)
    line['secs'] = round(time.time() - t0, 2)
    with open(L.ME + 'rows-%s-w%d.jsonl' % (a.arm, wid), 'a') as f:
        f.write(json.dumps(line, separators=(',', ':')) + '\n')
    return line['secs']


def done_keys(arm):
    import glob
    got = set()
    for p in glob.glob(L.ME + 'rows-%s-w*.jsonl' % arm):
        for x in open(p):
            if x.endswith('\n'):
                got.add(json.loads(x)['key'])
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('arm')
    ap.add_argument('--level', default='rel')
    ap.add_argument('--procs', type=int, default=4)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--min-pos', type=int, default=5)
    ap.add_argument('--rounds', type=int, default=400)
    ap.add_argument('--eta', type=float, default=.3)
    ap.add_argument('--lam', type=float, default=10.0)
    ap.add_argument('--minh', type=float, default=1.0)
    ap.add_argument('--cap', type=int, default=5000)
    ap.add_argument('--cap-min', type=int, default=1500)
    ap.add_argument('--cap-per', type=int, default=30)
    ap.add_argument('--ntok', type=int, default=60)
    ap.add_argument('--label', default='gold')
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--depth', type=int, default=1)
    ap.add_argument('--selfkeys', type=int, default=0)
    ap.add_argument('--drop', default='', help='feature names to leave out; a name that ends in * leaves out the tokens with that prefix')
    a = ap.parse_args()
    t0 = time.time()
    V = L.Vocabs()
    D = L.Picks(os.environ['PS_FIT'].split(',') if os.environ.get('PS_FIT') else L.FIT_SETS, V)
    RP = L.Picks([os.environ.get('PS_TUNE', 'test-parents')], V)
    L.refine(D, V), L.refine(RP, V)
    L.refine_done = True
    D.freeze(V), RP.freeze(V)
    json.dump(V.m, open(L.OUT + 'vocab-%s.json' % a.arm, 'w'))
    if a.label == 'drawn':
        D.relabel(a.seed), RP.relabel(a.seed + 1)
    IX, IXP = L.Rows(D, a.level), L.Rows(RP, a.level)
    names = V.list(a.level)
    pos = np.bincount(D.key[a.level][D.goldrow], minlength=len(names))
    done = done_keys(a.arm)
    order = [int(k) for k in np.argsort(-pos, kind='stable') if len(IX.get(int(k))) and names[k] not in done]
    if a.limit:
        order = order[:a.limit]
    print('load %.0fs: %d fit picks, %d rows, %d read picks, %d keys left of %d, %d facts columns' % (time.time() - t0, D.n, len(D.q), RP.n, len(order), len(IX.ks), len(L.NAMES)), flush=True)
    drop = [x for x in a.drop.split(',') if x]
    L.DROP_COLS = {L.NAMES.index(x) for x in drop if not x.endswith('*')}
    pre = tuple(x[:-1] for x in drop if x.endswith('*'))
    if pre:
        L.DROP_TOK = np.array([t.startswith(pre) for t in V.list('heads')])
    G.update(D=D, RP=RP, a=a, IX=IX, IXP=IXP, names=names)
    t1 = time.time()
    with mp.get_context('fork').Pool(a.procs) as pool:
        tot = 0.0
        for c, s in enumerate(pool.imap(job, order, chunksize=1), 1):
            tot += s
            el = time.time() - t1
            if c % 10 == 0 or c == len(order):
                print('[%d/%d %.0fs, %.2f keys/s] cpu in keys %.0fs, key %s' % (c, len(order), el, c / el, tot, names[order[c - 1]]), flush=True)
    print('done', flush=True)


if __name__ == '__main__':
    main()
