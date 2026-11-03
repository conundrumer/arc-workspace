#!/usr/bin/env python
"""Tune on task folds of the fit tasks. Each line of tune.jsonl is one arm at one fold, flushed as it ends. A rerun skips finished items. No held row is loaded.

  python features_ofree_tune.py GROUP ARM TIER LAMS FOLDS [MAXITER]     for example RULE clean dag 1,3,10 0,1 40
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features_ofree_lib as L  # noqa: E402
import features_ofree_ordered as O  # noqa: E402


def main():
    group, armn, tier, lams, folds = sys.argv[1:6]
    maxit = int(sys.argv[6]) if len(sys.argv) > 6 else 40
    out = L.ME + 'tune.jsonl'
    done = set()
    if os.path.exists(out):
        for x in open(out):
            d = json.loads(x)
            done.add((d['group'], d['arm'], d['tier'], d['lam'], d['fold'], d['maxiter']))
    todo = [(float(a), int(b)) for a in lams.split(',') for b in folds.split(',') if (group, armn, tier, float(a), int(b), maxit) not in done]
    if not todo:
        print('nothing to do')
        return
    t0 = time.time()
    recs = L.load('fit')
    libs = L.lib_vocab(recs)
    fa, fo = O.arm(armn, tier)
    D = L.Data(recs, group, libs, tier, fa, fo)
    print('%s %s %s: %d rows, %d facts, misses %d, %.0f s' % (group, armn, tier, D.n, D.F.shape[1], D.miss, time.time() - t0), flush=True)
    for n, (lam, fold) in enumerate(todo, 1):
        t1 = time.time()
        tr, te = np.nonzero(D.fold != fold)[0], np.nonzero(D.fold == fold)[0]
        m = L.Model(D, tr, lam, maxiter=maxit)
        s, b0 = m.saved(D, te)
        top = ~D.neg[te]
        row = dict(group=group, arm=armn, tier=tier, lam=lam, fold=fold, maxiter=maxit, rows=int(top.sum()), base=float(b0[top].mean()), saved=float(s[top].mean()), saved_not=float(s[~top].mean()) if (~top).any() else 0.0, keys=m.nk, facts=m.nf, nit=m.nit, seconds=round(time.time() - t1, 1))
        with open(out, 'a') as f:
            f.write(json.dumps(row) + '\n')
        r = (time.time() - t1)
        print(json.dumps(row), 'ETA %.0f s' % (r * (len(todo) - n)), flush=True)


if __name__ == '__main__':
    main()
