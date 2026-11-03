#!/usr/bin/env python
"""What the top keys of a final model learned, from the fit rows, in terms a person can check.

  python features_perrel_learned.py ARM --eta E [--top 10]     writes learned-ARM.md and learned-ARM.json

For each key, by net bits on held. For each fact the key's trees use: the model's mean change in log odds where the fact holds against where it does not, weighted by the prior's mass of the option, and the observed rate of gold against the prior's mass on each side, on all fit rows of the key. A fact stands in words with the two rates, so a reader can check it against the rows. Only fit rows enter.
Also the share of tree splits by kind of fact, and the cost of one pick scored alone.
"""
import argparse
import collections
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features_perrel_lib as L  # noqa: E402
import features_perrel_read as RD  # noqa: E402


def walk(t, out):
    if isinstance(t, list):
        out.append(tuple(t[0]))
        walk(t[1], out), walk(t[2], out)


def fact_name(f, V):
    if f[0] == 'x':
        n = L.NAMES[f[1]]
        return '%s >= %.3g' % (n, f[2]) if abs(f[2] - round(f[2])) > 1e-6 else ('%s >= %d' % (n, round(f[2])))
    if f[0] == 't':
        return V.list('heads')[f[1]]
    if f[0] == 'c':
        return 'own component ' + V.list('comp')[f[1]]
    return 'own relation key ' + V.list('rel')[f[1]]


def group(name):
    if name in L.STRUCT:
        return 'prior' if name in ('lq', 'lp', 'steer', 'rank', 'gap_top', 'share_kind', 'entropy', 'top_q') else 'structure'
    if name in L.CONTENT:
        return 'content'
    if name.startswith('grid_'):
        return 'grid'
    return 'scope and form'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('arm')
    ap.add_argument('--eta', type=float, default=.15)
    ap.add_argument('--top', type=int, default=10)
    a = ap.parse_args()
    arm = a.arm
    V = L.Vocabs(L.OUT + 'vocab-%s.json' % arm)
    D = L.Picks(L.FIT_SETS, V)
    L.refine(D, V)
    D.freeze(V)
    res = json.load(open(L.ME + 'read-%s.json' % arm))
    ls = {d['key']: d for d in RD.lines(arm)}
    level = res['level']
    ix = L.Rows(D, level)
    names = V.m[level]
    uses = collections.Counter()
    for k, d in ls.items():
        if 'folds' not in d:
            continue
        for s in d['stumps'][:RD.chosen(d)]:
            if s[0] == 'T':
                o = []
                walk(s[1], o)
                for f in o:
                    uses['token' if f[0] == 't' else ('own key' if f[0] in 'cr' else group(L.NAMES[f[1]]))] += 1
    tot = sum(uses.values())
    top = sorted([k for k in res['keys_table'] if k['t'] >= 8 or k['n'] >= 50], key=lambda r: -r['net_total'])[:a.top]
    out, md = [], ['# What the top keys learned', '', 'Keys of `%s`, by net bits on held. Each row is one fact the key uses. "Gold / prior" is the count of gold at the option, divided by the prior\'s mass there, over fit rows: where the fact holds, then where it does not. A ratio over 1 means the prior gives the option too little. "Change" is the mean change in log odds that the model gives where the fact holds, less where it does not, weighted by the prior\'s mass.' % arm, '']
    for r in top:
        d = ls[r['key']]
        k = names[r['key']]
        rows = ix.get(k)
        n = RD.chosen(d)
        st = [tuple(s) for s in d['stumps'][:n]]
        dl = L.path(D, rows, st, a.eta, [n])[:, 0]
        q = D.q[rows]
        y = D.isgold[rows]
        fs = collections.Counter()
        for s in st:
            if s[0] == 'T':
                o = []
                walk(s[1], o)
                fs.update(o)
        cache = {}
        items = []
        Q = q.sum()
        for f, c in fs.most_common(150):
            x = L.mask_of(D, rows, f, cache)
            q1, q0 = q[x].sum(), q[~x].sum()
            if q1 < .03 * Q or q0 < .03 * Q:
                continue
            e = (dl[x] * q[x]).sum() / q1 - (dl[~x] * q[~x]).sum() / q0
            l1, l0 = y[x].sum() / q1, y[~x].sum() / q0
            items.append(dict(fact=fact_name(f, V), change=float(e), holds_share=float(q1 / Q), gold_prior_holds=float(l1), gold_prior_not=float(l0), splits=c, score=float(abs(e) * np.sqrt(q1 * q0) / Q)))
        items.sort(key=lambda z: -z['score'])
        up = [z for z in items if z['change'] > 0][:3]
        dn = [z for z in items if z['change'] < 0][:3]
        rate = float(y.sum() / Q)
        out.append(dict(key=r['key'], net_bits=r['net_total'], net_per_gold=r['net'], saved_at_gold=r['saved'], gold_picks=r['n'], fit_gold=r['fit'], rounds=n, gold_prior_all=rate, raises=up, lowers=dn))
        md += ['## %s' % r['key'], '', 'Held: %d gold picks, net %+.1f bits, %+.2f per gold pick (%+.2f to %+.2f). Fit: %d gold rows, %d trees, gold / prior %.2f over all its rows.' % (r['n'], r['net_total'], *r['net'], r['fit'], n, rate), '', '| Direction | Fact | Share of prior mass where it holds | Gold / prior, holds | Gold / prior, not | Change |', '|---|---|---|---|---|---|']
        for t, zs in (('raises', up), ('lowers', dn)):
            for z in zs:
                md.append('| %s | `%s` | %.2f | %.2f | %.2f | %+.2f |' % (t, z['fact'], z['holds_share'], z['gold_prior_holds'], z['gold_prior_not'], z['change']))
        md.append('')
    md += ['## Splits by kind of fact', '', '| Kind | Share of tree splits |', '|---|---|'] + ['| %s | %.3f |' % (k, v / tot) for k, v in uses.most_common()] + ['']
    # The cost of one pick scored alone: each key of the pick evaluates its trees on one row, in numpy.
    t0 = time.process_time()
    picks = np.random.RandomState(0).choice(D.n, 100, replace=False)
    mdl = {k: [tuple(s) for s in d['stumps'][:RD.chosen(d)]] for k, d in ls.items() if 'folds' in d and RD.chosen(d)}
    rn = V.list(level)
    t0 = time.process_time()
    for p in picks.tolist():
        rs = np.arange(D.starts[p], D.starts[p + 1])
        for k in np.unique(D.key[level][rs]).tolist():
            st = mdl.get(rn[k])
            if st:
                L.path(D, rs[D.key[level][rs] == k], st, a.eta, [len(st)])
    alone = (time.process_time() - t0) / len(picks) * 1000
    json.dump(dict(keys=out, split_share={k: v / tot for k, v in uses.items()}, numpy_ms_per_pick_alone=alone), open(L.ME + 'learned-%s.json' % arm, 'w'), indent=1)
    open(L.ME + 'learned-%s.md' % arm, 'w').write('\n'.join(md) + '\n')
    print('\n'.join(md))
    print('numpy ms per pick alone', alone)


if __name__ == '__main__':
    main()
