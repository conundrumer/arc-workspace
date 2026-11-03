#!/usr/bin/env python
"""Tune read of per-key arms on test-parents picks: for each task fold, the models fit without that fold, cut at the rounds that the other folds' gains choose, summed and read as one soft-max. Reads no held task.

  python features_perrel_tune.py ARM[,ARM...] [--select before|both] [--alphas 1,.8,.6] [--every]

Arms in one call stack as levels: each key's delta adds. Prints saved bits per pick on the 4,193 test-parents picks, by class, and writes tune-ARM.json.
"""
import argparse
import glob
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features_perrel_lib as L  # noqa: E402

BEFORE_PICKS = 26237


def lines(arm):
    out = []
    for p in sorted(glob.glob(L.ME + 'rows-%s-w*.jsonl' % arm)):
        for x in open(p):
            if x.endswith('\n'):
                d = json.loads(x)
                if 'folds' in d:
                    out.append(d)
    return out


def choose(d, cps, skip, sel, min_gain):
    """The round count that the folds other than `skip` choose for a key: the most out-of-fold gain, or 0 under min_gain bits."""
    n = len(cps)
    tot = np.zeros(n)
    for f in d['folds']:
        if f['fold'] == skip:
            continue
        tot += np.array(f['before'][0])
        if sel == 'both':
            tot += np.array(f['parents'][0])
    i = int(np.argmax(tot))
    return cps[i] if tot[i] > min_gain else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('arms')
    ap.add_argument('--select', default='before')
    ap.add_argument('--alphas', default='1,.8,.6')
    ap.add_argument('--min-gain', type=float, default=0.0)
    ap.add_argument('--eta', type=float, default=.3)
    ap.add_argument('--cps', default='0,1,3,6,12,25,50,100,200,400')
    a = ap.parse_args()
    cps = [int(x) for x in a.cps.split(',')]
    arms = a.arms.split(',')
    V = L.Vocabs(L.OUT + 'vocab-%s.json' % arms[0])
    R = L.Picks(['test-parents'], V)
    L.refine(R, V)
    R.freeze(V)
    q0 = R.q.copy()
    t0 = time.time()
    res = {}
    F = np.zeros(len(R.q))
    used = {}
    for arm in arms:
        level = lines(arm)[0]['level']
        ix = L.Rows(R, level)
        names = V.m[level]
        for d in lines(arm):
            key = names.get(d['key'])
            if key is None:
                continue
            rows = ix.get(key)
            if len(rows) == 0:
                continue
            for f in d['folds']:
                rf = rows[R.fold[R.pick[rows]] == f['fold']]
                r = choose(d, cps, f['fold'], a.select, a.min_gain)
                used.setdefault(d['key'], []).append(r)
                if r == 0 or len(rf) == 0:
                    continue
                F[rf] += L.path(R, rf, [tuple(s) for s in f['stumps'][:r]], a.eta, [r])[:, 0]
    cl = L.klass(R)
    for alpha in [float(x) for x in a.alphas.split(',')]:
        sv = L.saved_bits(R, alpha * F)
        m = np.ones(R.n, bool)
        res[str(alpha)] = dict(all=L.boot(sv, R.task, m, 1000), alive=L.boot(sv, R.task, ~R.m['gold_dead'], 1000), **{c: round(float(sv[cl == c].mean()), 3) for c in ('derived', 'lib', 'own', 'rest')})
        print(a.arms, 'alpha', alpha, 'saved %.3f (%.3f to %.3f)' % tuple(res[str(alpha)]['all']), 'alive %.3f' % res[str(alpha)]['alive'][0], {c: res[str(alpha)][c] for c in ('derived', 'lib', 'own', 'rest')}, flush=True)
    onz = sum(1 for v in used.values() if any(v))
    print('keys', len(used), 'with a model in some fold', onz, 'mean rounds of those %.0f, %.0fs' % (np.mean([np.mean(v) for v in used.values() if any(v)]), time.time() - t0), flush=True)
    json.dump(res, open(L.ME + 'tune-%s-%s.json' % ('+'.join(arms), a.select), 'w'), indent=1)


if __name__ == '__main__':
    main()
