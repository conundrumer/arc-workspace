#!/usr/bin/env python
"""Per-relation models on pool scopes (item 18): the table "Per-relation models on pool scopes, and written order", from the reads that exist. It runs no model and adds no held read.

  features_dagc_env.sh 1 features_dagc_pool_summary.py [--tag T]       writes pool-summary.md and pool-summary.json

Arms (fit rows in features_dagc_pool_fits.sh): `parents` is the model of item 10 (arm hyb, control `control`) fit on fit-cut RULE; `pool` is fit on fit-pool; `union` is fit on fit-pool and fit-cut RULE; each has a control on a label drawn from the offset.
Reads, each arm once per data set (features_dagc_pool_reads.sh): held-pool, held-wide (an oracle context: the pool's visit forms stand with gold's parents and the forms of one late visit, as measures.md defines one), held-parents (union only).
A cell is the saved bits per gold-alive pick over `off` (the offset) and over `live` (the mean live bits at the same pick keys less the model's bits), 95% from 10,000 resamples of tasks, weighted by the pick weight.
By stratum: held-pool `holds`, `built`, `noreads`; held-wide `found`, `oracle`. The stratum is the point's, from points-held-pool.jsonl and points-held-wide.jsonl, joined through the data file's point id.
Bars (gold-alive picks, over live): 1 bit makes a gain a candidate for a steer, under .3 closes it, between the two it stands as a finding. A steer is the sampler lane's work. A control must read 0 within its interval.
There is no written-order row: every walk stands in a valid order.
"""
import argparse
import glob
import json
import os
import sys

import numpy as np

sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-dag-conversion-heldout37')
import features_dagc_rows as RW  # noqa: E402

ME = RW.ME
ROWS = ME + 'perrel/'
ARMS = [('parents (item 10 model)', 'hyb', 'control'), ('pool', 'pool', 'pool-control'), ('union', 'union', 'union-control')]
DATA = [('held-pool', 'held-pool-off', 'points-held-pool.jsonl'), ('held-wide', 'held-wide-off', 'points-held-wide.jsonl'), ('held-parents', 'held-parents-off', None)]
STRATA = {'held-pool': ('holds', 'built', 'noreads'), 'held-wide': ('found', 'oracle')}
CLASSES = [('Derived relation in scope'), ('Lib relation'), ("The form's own earlier atom"), ('The rest')]


def read_of(model, data):
    p = ROWS + 'read-%s-on-%s.json' % (model, data)
    return json.load(open(p)) if os.path.exists(p) else None


def cell(r, name='Gold alive'):
    if r is None:
        return 'not read', 'not read'
    row = {x['name']: x for x in r['table']}.get(name)
    if row is None:
        return 'no picks', 'no picks'
    return RW.fmt3(row['over_off'], 2), (RW.fmt3(row['over_live'], 2) if row['live_picks'] else 'no live rows')


def verdict(r):
    row = {x['name']: x for x in r['table']}.get('Gold alive') if r else None
    if row is None or row['live_picks'] == 0:
        return ''
    m, lo, hi = row['over_live']
    return 'candidate for a steer' if m >= 1 and lo > 0 else 'closes' if m < .3 else 'finding'


def strata_rows(model, data, points):
    p = ROWS + 'saved-%s-on-%s.npz' % (model, data)
    if not os.path.exists(p) or not points:
        return None
    z = np.load(ME + 'scratch/data-%s.npz' % data, allow_pickle=False)
    sv = np.load(p)
    idx = np.nonzero(np.isin(z['m_kind'], ['RULE']) & (z['gold'] >= 0))[0]
    if len(idx) != len(sv['pkey']) or not (z['pkey'][idx] == sv['pkey']).all():
        return None
    P = {}
    for x in open(ME + points):
        q = json.loads(x)
        P[q['line']] = q
    line = z['m_line'][idx]
    strat = np.array([P[i]['stratum'] for i in line.tolist()])
    alive = ~z['m_gold_dead'][idx]
    w = z['w'][idx].astype(float)
    task = z['m_task'][idx]
    off = sv['saved_off']
    live = sv['live']
    has = ~np.isnan(live)
    over_live = np.where(has, live - (sv['q_off'] - off), 0.0)
    out = {}
    for s in sorted(set(strat.tolist())):
        m = (strat == s) & alive
        if not m.any():
            continue
        e = dict(picks=int(m.sum()), tasks=len(set(task[m].tolist())), prior_bits=float(np.average(sv['q_off'][m], weights=w[m])), over_off=RW.boot(w * off, w, task, m))
        ml = m & has
        e['over_live'] = RW.boot(w * over_live, w, task, ml) if ml.any() else None
        out[s] = e
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--tag', default='')
    ap.add_argument('--smoke', action='store_true', help='mechanical check on a non-held pilot: one arm, one data set. Its numbers are not a read')
    a = ap.parse_args()
    global ARMS, DATA, STRATA
    if a.smoke:
        ARMS = [('pilot', 'pilotpool', 'pilotpool')]
        DATA = [('held-pool', 'mine-fpt', 'points-fit-pool.jsonl')]
        STRATA = {'held-pool': ('fit',)}
    res = dict(cells={}, strata={}, controls={})
    L_ = ['# Per-relation models on pool scopes, valid orders', '', 'Saved bits per gold-alive pick over `off` and over `live`, 95% by task. `held-wide` is an oracle context. No written-order row: every walk stands in a valid order.', '']
    head = ['Model'] + ['%s, over off' % d for d, _n, _p in DATA] + ['%s, over live' % d for d, _n, _p in DATA] + ['Verdict (held-pool, over live)']
    rows = []
    for name, model, control in ARMS:
        for label, m in ((name, model), ('control of %s' % name, control)):
            reads = {d: read_of(m, n) for d, n, _p in DATA}
            c = {d: cell(r) for d, r in reads.items()}
            rows.append([label] + [c[d][0] for d, _n, _p in DATA] + [c[d][1] for d, _n, _p in DATA] + [verdict(reads['held-pool']) if m == model else ''])
            res['cells'][label] = {d: dict(off=c[d][0], live=c[d][1], read=reads[d] is not None) for d, _n, _p in DATA}
            if m == control:
                r = reads['held-pool']
                if r:
                    row = {x['name']: x for x in r['table']}.get('Gold alive')
                    res['controls'][label] = dict(reads_zero=bool(row and row['over_off'][1] <= 0 <= row['over_off'][2]), over_off=row['over_off'] if row else None)
    L_.append(RW.table_md(head, rows))
    for d, n, p in DATA:
        L_ += ['## %s: by class and d_depth band' % d, '']
        rows = []
        names = list(CLASSES) + ['D empty (band 0)', 'band 1', 'band 2', 'band 3 or more']
        for nm in names:
            line = [nm]
            for label_model in ARMS:
                r = read_of(label_model[1], n)
                o, l = cell(r, nm)
                line += [o, l]
            rows.append(line)
        L_.append(RW.table_md(['Picks read'] + sum([['%s, off' % a_[0], '%s, live' % a_[0]] for a_ in ARMS], []), rows))
        if d in STRATA:
            L_ += ['%s: by stratum (gold-alive picks)' % d, '']
            rows = []
            for name, model, control in ARMS:
                sr = strata_rows(model, n, p)
                res['strata'].setdefault(d, {})[name] = sr
                for s in STRATA[d]:
                    e = (sr or {}).get(s)
                    rows.append([name, s, e['picks'] if e else '', e['tasks'] if e else '', RW.fmt3(e['over_off'], 2) if e else 'not read', RW.fmt3(e['over_live'], 2) if e and e['over_live'] else ''])
            L_.append(RW.table_md(['Model', 'Stratum', 'Picks', 'Tasks', 'Over off', 'Over live'], rows))
    L_ += ['## Controls', '', json.dumps(res['controls']), '']
    open(ME + 'pool-summary%s.md' % a.tag, 'w').write('\n'.join(L_) + '\n')
    json.dump(res, open(ME + 'pool-summary%s.json' % a.tag, 'w'), indent=1, default=str)
    print('\n'.join(L_))


if __name__ == '__main__':
    main()
