#!/usr/bin/env python
"""Tables from saved bits already read, with no new held read: gold-alive saved bits by stratum, and paired differences between two reads of the same forms, with a 10,000 resample of tasks.

  python features_ps_compare.py strata TAG DATA POINTS
  python features_ps_compare.py pair TAG_A DATA_A POINTS_A TAG_B DATA_B POINTS_B     forms in both, each form's picks weighted as they fall; A minus B

TAG names saved-TAG.npy. A form is (task, form). Writes a line to compare.jsonl.
"""
import json
import os
import sys

import numpy as np

np.seterr(all='ignore')

ME = os.path.dirname(os.path.abspath(__file__)) + '/'
OUT = ME + 'scratch/'


def load(tag, data, points):
    z = np.load(OUT + 'data-%s.npz' % data, allow_pickle=False)
    sv = np.load(ME + 'saved-%s.npy' % tag)
    task, line, dead = z['m_task'], z['m_line'], z['m_gold_dead']
    goldrow = z['starts'][:-1] + z['gold']
    lq = z['S'][:, 0].astype(float)
    st = z['starts']
    q = np.array([np.exp(lq[goldrow[i]]) / np.exp(lq[st[i]:st[i + 1]]).sum() for i in range(len(goldrow))])
    bits = -np.log2(q)
    if points is None or points == '-':  # the census: `line` is the form
        form = line.tolist()
        strat = ['census'] * len(line)
    else:
        P = {}
        for x in open(points):
            p = json.loads(x)
            P[p['line']] = p
        form = [P[i]['form'] for i in line.tolist()]
        strat = [P[i]['stratum'] for i in line.tolist()]
    return task, np.array(form), np.array(strat), ~dead, sv, bits


def boot(rows, B=10000, seed=0):
    """rows: per-task (num, den) arrays, one pair per side. The ratio of sums, or the difference of two."""
    W = np.random.RandomState(seed).multinomial(len(rows[0][0]), [1.0 / len(rows[0][0])] * len(rows[0][0]), B).astype(float)
    r = 0.0
    pt = 0.0
    for sign, (a, b) in zip((1, -1), rows):
        d = W @ b
        r = r + sign * (W @ a) / np.maximum(d, 1e-9)
        pt = pt + sign * a.sum() / max(b.sum(), 1)
    return float(pt), float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))


def per_task(task, mask, sv, u):
    ix = {t: i for i, t in enumerate(u)}
    t = np.array([ix[x] for x in task[mask].tolist()])
    return np.bincount(t, sv[mask], len(u)), np.bincount(t, minlength=len(u)).astype(float)


def main():
    if sys.argv[1] == 'strata':
        tag, data, points = sys.argv[2:5]
        task, form, strat, alive, sv, bits = load(tag, data, points)
        u = sorted(set(task.tolist()))
        res = {}
        for s in sorted(set(strat.tolist())):
            m = (strat == s) & alive
            a = per_task(task, m, sv, u)
            res[s] = dict(picks=int(m.sum()), tasks=len(set(task[m].tolist())), forms=len({(t, f) for t, f in zip(task[m].tolist(), form[m].tolist())}), prior_bits=float(bits[m].mean()), saved=boot([a]))
            print(tag, s, res[s])
        rec = dict(kind='strata', tag=tag, data=data, strata=res)
    else:
        ta, da, pa, tb, db, pb = sys.argv[2:8]
        A, B = load(ta, da, pa), load(tb, db, pb)
        fa = set(zip(A[0].tolist(), A[1].tolist()))
        fb = set(zip(B[0].tolist(), B[1].tolist()))
        both = fa & fb
        ma = np.array([x in both for x in zip(A[0].tolist(), A[1].tolist())]) & A[3]
        mb = np.array([x in both for x in zip(B[0].tolist(), B[1].tolist())]) & B[3]
        u = sorted({t for t, _ in both})
        x, y = per_task(A[0], ma, A[4], u), per_task(B[0], mb, B[4], u)
        rec = dict(kind='pair', a=ta, b=tb, forms=len(both), tasks=len(u), picks_a=int(ma.sum()), picks_b=int(mb.sum()), prior_a=float(A[5][ma].mean()), prior_b=float(B[5][mb].mean()), saved_a=boot([x]), saved_b=boot([y]), a_minus_b=boot([x, y]))
        print(json.dumps(rec, indent=1))
    with open(ME + 'compare.jsonl', 'a') as f:
        f.write(json.dumps(rec) + '\n')


main()
