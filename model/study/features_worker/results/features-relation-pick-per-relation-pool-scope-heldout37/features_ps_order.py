#!/usr/bin/env python
"""What written order leaves in: on forms whose atoms moved, saved bits in the random order against the same forms in written order, at gold-alive picks. The picks are matched on nothing but the form. No new held read: it reads saved-*.npy.

  python features_ps_order.py    appends to compare.jsonl
"""
import json
import os
import sys

import numpy as np

sys.argv = sys.argv[:1]
ME = os.path.dirname(os.path.abspath(__file__)) + '/'
np.seterr(all='ignore')
OUT = ME + 'scratch/'


def load(tag, data, points):
    z = np.load(OUT + 'data-%s.npz' % data, allow_pickle=False)
    sv = np.load(ME + 'saved-%s.npy' % tag)
    task, line, dead = z['m_task'].tolist(), z['m_line'].tolist(), z['m_gold_dead']
    if points is None:
        return task, line, ~dead, sv, None
    P = {}
    for x in open(ME + points):
        p = json.loads(x)
        P[p['line']] = p
    return task, [P[i]['form'] for i in line], ~dead, sv, [P[i]['stratum'] for i in line]


def tb(u, task, keep, sv):
    ix = {t: i for i, t in enumerate(u)}
    a, b = np.zeros(len(u)), np.zeros(len(u))
    for i, k in enumerate(keep):
        if k:
            a[ix[task[i]]] += sv[i]
            b[ix[task[i]]] += 1
    return a, b


def boot(sides, B=10000):
    n = len(sides[0][0])
    W = np.random.RandomState(0).multinomial(n, [1.0 / n] * n, B).astype(float)
    r, pt = 0.0, 0.0
    for sign, (a, b) in zip((1, -1), sides):
        r = r + sign * (W @ a) / np.maximum(W @ b, 1e-9)
        pt = pt + sign * a.sum() / max(b.sum(), 1)
    return round(float(pt), 4), round(float(np.percentile(r, 2.5)), 4), round(float(np.percentile(r, 97.5)), 4)


out = open(ME + 'compare.jsonl', 'a')
for label, ts, ds, ps, tw, dw, pw in (
    ('census, refit with no lexical order', 'final-orderfree-on-census-shuffled', 'census-shuffled', 'points-census-shuffled.jsonl', 'final-orderfree-on-held', 'held', None),
    ('census, model as fit', 'asfit-final-hyb-noorder-on-census-shuffled', 'census-shuffled', 'points-census-shuffled.jsonl', 'asfit-final-hyb-noorder-on-held', 'held', None),
    ('pool rows, refit with no lexical order', 'final-orderfree-on-held-pool-shuffled', 'held-pool-shuffled', 'points-held-pool-shuffled.jsonl', 'final-orderfree-on-held-pool', 'held-pool', 'points-held-pool.jsonl'),
    ('pool rows, refit on pool rows', 'final-orderfree-union-on-held-pool-shuffled', 'held-pool-shuffled', 'points-held-pool-shuffled.jsonl', 'final-orderfree-union-on-held-pool', 'held-pool', 'points-held-pool.jsonl'),
):
    if not os.path.exists(ME + 'saved-%s.npy' % ts):
        continue
    t1, f1, a1, s1, st = load(ts, ds, ps)
    t2, f2, a2, s2, _ = load(tw, dw, pw)
    for which in ('moved', 'unmoved'):
        forms = {(t, f) for t, f, x in zip(t1, f1, st) if x == which}
        u = sorted({t for t, _ in forms})
        k1 = [(t, f) in forms and bool(a) for t, f, a in zip(t1, f1, a1)]
        k2 = [(t, f) in forms and bool(a) for t, f, a in zip(t2, f2, a2)]
        x, y = tb(u, t1, k1, s1), tb(u, t2, k2, s2)
        rec = dict(kind='order', label=label, forms=len(forms), which=which, tasks=len(u), picks_random=int(sum(k1)), picks_written=int(sum(k2)), saved_random_order=boot([x]), saved_written_order=boot([y]), random_minus_written=boot([x, y]))
        print(json.dumps(rec))
        out.write(json.dumps(rec) + '\n')
