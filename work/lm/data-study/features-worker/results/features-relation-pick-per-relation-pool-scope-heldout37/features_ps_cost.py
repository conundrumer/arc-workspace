#!/usr/bin/env python
"""Cost per pick on pool scope rows, with no use of a label: trees scored in one batch, trees scored one pick at a time, and the walk's content facts per pick.

  python features_ps_cost.py MODEL DATA    writes cost-MODEL-on-DATA.json

Batch and alone follow the per-relation record: numpy over the arrays, one process. Facts here are the content facts of the walk's `content_cpu`, which hold the option tables, the join against the prefix and the prefix's table.
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features_perrel_lib as L  # noqa: E402
import features_ps_read as RD  # noqa: E402


def main():
    model, data = sys.argv[1], sys.argv[2]
    V = L.Vocabs(L.OUT + 'vocab-%s.json' % model.replace('as-fit:', ''))
    R = L.Picks([data], V)
    L.refine(R, V)
    R.freeze(V)
    z = np.load(L.OUT + 'data-%s.npz' % data, allow_pickle=False)
    forms = json.loads(str(z['forms']))
    ls = RD.lines(model)
    level = ls[0]['level']
    ix = L.Rows(R, level)
    names = V.m[level]
    mdl = {}
    for d in ls:
        if 'folds' in d and RD.chosen(d):
            mdl[d['key']] = [tuple(s) for s in d['stumps'][:RD.chosen(d)]]
    t0 = time.process_time()
    for k, st in mdl.items():
        if k in names:
            rows = ix.get(names[k])
            if len(rows):
                L.path(R, rows, st, .15, [len(st)])
    batch = (time.process_time() - t0) / R.n * 1000
    picks = np.random.RandomState(0).choice(R.n, min(100, R.n), replace=False)
    rn = V.list(level)
    t0 = time.process_time()
    for p in picks.tolist():
        rs = np.arange(R.starts[p], R.starts[p + 1])
        for k in np.unique(R.key[level][rs]).tolist():
            st = mdl.get(rn[k])
            if st:
                L.path(R, rs[R.key[level][rs] == k], st, .15, [len(st)])
    alone = (time.process_time() - t0) / len(picks) * 1000
    cc = sum(d['content_cpu'] for d in forms)
    np_ = sum(d['picks'] for d in forms)
    rep = dict(model=model, data=data, picks=int(R.n), options_per_pick=float(len(R.q) / R.n), trees=sum(len(s) for s in mdl.values()), keys=len(mdl), batch_ms_per_pick=batch, alone_ms_per_pick=alone, content_cpu_ms_per_pick=cc / max(np_, 1) * 1000, walk_cpu_ms_per_pick=sum(d['cpu'] for d in forms) / max(np_, 1) * 1000)
    json.dump(rep, open(L.ME + 'cost-%s-on-%s.json' % (model.replace('as-fit:', 'asfit-'), data), 'w'), indent=1)
    print(rep)


main()
