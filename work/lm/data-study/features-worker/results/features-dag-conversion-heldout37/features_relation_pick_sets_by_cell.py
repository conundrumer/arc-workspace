#!/usr/bin/env python
"""Splits the reads of items 11, 12 and 14 into cells, from the per-pick tables that those reads write. No walk, no engine call. It reads the rows that exist, so it runs on a partial walk.

  features_dagc_env.sh 1 features_relation_pick_sets_by_cell.py [--lam any=.05,all=.07,keep=.04]

Inputs (one row per pick and set, written by the reads): cells-input-feasible.tsv (features_feasible_read.py), cells-input-within.tsv (features_within_task_read.py), cells-input-unread.tsv and cells-input-pool.tsv (features_unread_read.py).
Outputs: feasible-cells.tsv, within-cells.tsv, unread-cells.tsv, pool-cells.tsv, cells-report.tsv (the cells that are not thin and whose net interval is above 0), totals-check.tsv.

Cells. The split dimensions are:
  band   d_depth band of the pick: empty (D empty in the pick's conjunction), 1, 2, 3+. It takes the place of the atom's position and of the position in the body.
  kind   RULE, INIT, DET
  place  top, key, port, branch, outside, all (`key or port` is a rollup). No br1 or br2: `branch` is one place.
  cls    gold's class (derived, lib, own, macro, fact, NOT, comparison). A cell that reads gold's class has known_at_pick 0.
Thin: under 50 picks or under 8 tasks. A cell's intervals are 95% from 10,000 resamples of tasks, weighted by the pick weight. A cell differs from the pool when the pool's value is outside its interval.
Net: the saving over all the picks of the cell. feasible: with an escape weight (--lam, or the escape of feasible-read.json when it has one) the saving at every gold-alive pick; without it, no net is written and the cell carries the saving at gold-in picks only.
within: saved_theta at every gold-alive pick. unread: the mixture's saving at every pick, per derived pick. pool: the share of readable picks whose gold form the run found.
No number here is fit on a held row: the escape weights and w come from the reads, from non-held rows.
"""
import argparse
import collections
import csv
import itertools
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features_dagc_rows as RW  # noqa: E402

ME = RW.ME
THIN_PICKS, THIN_TASKS = 50, 8
VALUES = dict(
    band={b: ((b,), False) for b in RW.BANDS},
    kind={k: ((k,), False) for k in ('RULE', 'INIT', 'DET')},
    place={**{p: ((p,), False) for p in ('top', 'key', 'port', 'branch', 'outside', 'all')}, 'key or port': (('key', 'port'), True)},
    cls={**{c: ((c,), False) for c in ('derived', 'lib', 'macro', 'fact', 'NOT', 'comparison')}, 'own': (('own',), False)},
)
SPLITS = [(), ('band',), ('kind',), ('place',), ('cls',), ('band', 'kind'), ('band', 'place'), ('band', 'cls'), ('kind', 'place'), ('kind', 'cls')]


def cells(attrs_present):
    for dims in SPLITS:
        if any(d not in attrs_present for d in dims):
            continue
        for combo in itertools.product(*[VALUES[d].items() for d in dims]):
            yield (' x '.join(dims) or 'all', ', '.join(c[0] for c in combo) or 'all', {d: c[1][0] for d, c in zip(dims, combo)}, any(c[1][1] for c in combo), 'cls' in dims)


def mask_of(attrs, want):
    n = len(next(iter(attrs.values())))
    m = np.ones(n, bool)
    for d, base in want.items():
        m &= np.isin(attrs[d], list(base))
    return m


def read_tsv(path):
    with open(path) as f:
        return list(csv.DictReader(f, delimiter='\t'))


class Cells:
    def __init__(self, name, cols):
        self.name, self.cols, self.rows = name, cols, []

    def write(self):
        with open(ME + self.name, 'w') as f:
            f.write('\t'.join(self.cols) + '\n')
            for r in self.rows:
                f.write('\t'.join('' if r.get(c) is None else (('%.4f' % r[c]) if isinstance(r[c], float) else str(r[c])) for c in self.cols) + '\n')
        print('wrote %s, %d rows' % (self.name, len(self.rows)), flush=True)


def interval_differs(pool, t):
    return int(not (t[1] <= pool <= t[2])) if not any(map(math.isnan, t)) else 0


def split_group(out, label, A, value_fns, count_fn, pool_key, extra=None):
    """One row per cell for a group (a set and a steer). A: dict of arrays (task, form, w, band, kind, place, cls). value_fns: {column: (num array, den array)} ratios of sums; count_fn(mask) gives extra columns."""
    n = len(A['task'])
    attrs = {d: A[d] for d in VALUES if d in A}
    masks = {}
    pool = {}
    for split, cell, want, roll, known in cells(attrs):
        mk = (split, cell)
        m = mask_of(attrs, want)
        if not m.any():
            continue
        tasks = len(set(A['task'][m].tolist()))
        r = dict(label, split=split, cell=cell, rollup=int(roll), known_at_pick=int(not known), picks=int(m.sum()), tasks=tasks, forms=len(set(A['form'][m].tolist())), thin=int(m.sum() < THIN_PICKS or tasks < THIN_TASKS))
        for col, (num, den) in value_fns.items():
            t = RW.boot(num, den, A['task_code'], m)
            r[col], r[col + '_lo'], r[col + '_hi'] = t
            if split == 'all':
                pool[col] = t
            r[col + '_differs_from_pool'] = interval_differs(pool[col][0], t) if col in pool and split != 'all' else 0
        if count_fn:
            r.update(count_fn(m))
        out.append(r)
    return out


def cols_for(value_cols, extra):
    base = ['read', 'set', 'steers', 'split', 'cell', 'rollup', 'known_at_pick', 'picks', 'tasks', 'forms', 'thin']
    for c in value_cols:
        base += [c, c + '_lo', c + '_hi', c + '_differs_from_pool']
    return base + extra


def arrays(rows, steers=None):
    if steers is not None:
        rows = [r for r in rows if r['steers'] == steers]
    A = {k: np.array([r[k] for r in rows]) for k in ('task', 'form', 'band', 'kind', 'place', 'cls')}
    A['task_code'] = np.unique(A['task'], return_inverse=True)[1]
    A['w'] = np.array([float(r['w']) for r in rows])
    return A, rows


def feasible_cells(lam, chk, report):
    rows = read_tsv(ME + 'cells-input-feasible.tsv')
    out = Cells('feasible-cells.tsv', cols_for(['share_gold_in', 'saved_gold_in', 'saved_soft'], ['gold_in', 'complete_share', 'net_above_0']))
    summary = {}
    for v in ('any', 'all', 'keep'):
        sub = [r for r in rows if r['set'] == v]
        for steers in ('off', 'live'):
            col = 'prior_off' if steers == 'off' else 'prior_live'
            sel = [r for r in sub if r[col] != '']
            if not sel:
                continue
            A, sel = arrays(sel)
            w = A['w']
            prior = np.array([float(r[col]) for r in sel])
            inside = np.array([int(r['inside']) for r in sel], float)
            res = np.array([float(r['res_off' if steers == 'off' else 'res_live']) for r in sel])
            res_out = np.array([float(r['res_out_off' if steers == 'off' else 'res_out_live']) for r in sel])
            comp = np.array([int(r['complete']) for r in sel], float)
            vf = {'share_gold_in': (w * inside, w), 'saved_gold_in': (w * inside * (prior - res), w * inside)}
            if lam:
                cost = np.where(inside > 0, -math.log2(1 - lam[v]) + res, -math.log2(lam[v]) + res_out)
                vf['saved_soft'] = (w * (prior - cost), w)
            lab = dict(read='feasible', set=v, steers=steers)
            before = len(out.rows)
            def cnt(m):
                d = dict(gold_in=int(inside[m].sum()), complete_share=round(float(np.average(comp[m], weights=w[m])), 3))
                return d
            split_group(out.rows, lab, A, vf, cnt, v)
            for r in out.rows[before:]:
                r['net_above_0'] = int(not r['thin'] and 'saved_soft' in r and r['saved_soft_lo'] > 0)
                if r['net_above_0']:
                    report.append(dict(read='feasible', set=v, steers=steers, split=r['split'], cell=r['cell'], picks=r['picks'], tasks=r['tasks'], net=r['saved_soft'], lo=r['saved_soft_lo'], hi=r['saved_soft_hi'], known_at_pick=r['known_at_pick']))
            allr = next(r for r in out.rows[before:] if r['split'] == 'all')
            summary[v, steers] = allr
            chk.append(('feasible', '%s, %s' % (v, steers), 'picks', allr['picks']))
            chk.append(('feasible', '%s, %s' % (v, steers), 'gold in set', allr['gold_in']))
    out.write()
    return summary


def within_cells(chk, report):
    rows = read_tsv(ME + 'cells-input-within.tsv')
    out = Cells('within-cells.tsv', cols_for(['share_gold_in', 'saved'], ['gold_in', 'net_above_0']))
    names = sorted({r['set'] for r in rows})
    summary = {}
    for nm in names:
        for steers in ('off', 'live'):
            sel = [r for r in rows if r['set'] == nm and r['steers'] == steers]
            if not sel:
                continue
            A, sel = arrays(sel)
            w = A['w']
            inside = np.array([int(r['inside']) for r in sel], float)
            sv = np.array([float(r['saved_theta']) for r in sel])
            vf = {'share_gold_in': (w * inside, w), 'saved': (w * sv, w)}
            before = len(out.rows)
            split_group(out.rows, dict(read='within', set=nm, steers=steers), A, vf, lambda m: dict(gold_in=int(inside[m].sum())), nm)
            for r in out.rows[before:]:
                r['net_above_0'] = int(not r['thin'] and r['saved_lo'] > 0)
                if r['net_above_0']:
                    report.append(dict(read='within', set=nm, steers=steers, split=r['split'], cell=r['cell'], picks=r['picks'], tasks=r['tasks'], net=r['saved'], lo=r['saved_lo'], hi=r['saved_hi'], known_at_pick=r['known_at_pick']))
            allr = next(r for r in out.rows[before:] if r['split'] == 'all')
            summary[nm, steers] = allr
    out.write()
    return summary


def unread_cells(chk, report):
    rows = read_tsv(ME + 'cells-input-unread.tsv')
    out = Cells('unread-cells.tsv', cols_for(['share_gold_in', 'saved', 'net'], ['derived_picks', 'gold_in', 'net_above_0']))
    summary = {}
    for nm in ('unread_scope', 'unread_pick', 'unread_only'):
        for steers in ('off', 'live'):
            sel = [r for r in rows if r['set'] == nm and r['steers'] == steers]
            if not sel:
                continue
            A, sel = arrays(sel)
            w = A['w']
            der = np.array([int(r['derived']) for r in sel], float)
            inside = np.array([int(r['inside']) for r in sel], float)
            sv = np.array([float(r['saved_options']) for r in sel])
            vf = {'share_gold_in': (w * inside * der, w * der), 'saved': (w * sv * der, w * der), 'net': (w * sv, w * der)}
            before = len(out.rows)
            split_group(out.rows, dict(read='unread', set=nm, steers=steers), A, vf, lambda m: dict(derived_picks=int(der[m].sum()), gold_in=int((inside * der)[m].sum())), nm)
            for r in out.rows[before:]:
                r['net_above_0'] = int(not r['thin'] and r['net_lo'] > 0)
                if r['net_above_0']:
                    report.append(dict(read='unread', set=nm, steers=steers, split=r['split'], cell=r['cell'], picks=r['picks'], tasks=r['tasks'], net=r['net'], lo=r['net_lo'], hi=r['net_hi'], known_at_pick=r['known_at_pick']))
            allr = next(r for r in out.rows[before:] if r['split'] == 'all')
            summary[nm, steers] = allr
    out.write()
    return summary


def pool_cells(chk, report):
    rows = read_tsv(ME + 'cells-input-pool.tsv')
    out = Cells('pool-cells.tsv', cols_for(['found_share'], ['found', 'unread_end']))
    for arm in sorted({r['set'] for r in rows}):
        sel = [r for r in rows if r['set'] == arm]
        for r in sel:
            r['cls'] = 'derived'
        A, sel = arrays(sel)
        w = A['w']
        found = np.array([int(r['found']) for r in sel], float)
        ue = np.array([int(r['unread_end']) for r in sel], float)
        A.pop('cls')
        split_group(out.rows, dict(read='pool', set=arm, steers='live'), A, {'found_share': (w * found, w)}, lambda m: dict(found=int(found[m].sum()), unread_end=int(ue[m].sum())), arm)
    out.write()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--lam', default='')
    a = ap.parse_args()
    lam = None
    src = None
    if a.lam:
        lam = {kv.split('=')[0]: float(kv.split('=')[1]) for kv in a.lam.split(',')}
        src = '--lam'
    elif os.path.exists(ME + 'feasible-read.json'):
        e = json.load(open(ME + 'feasible-read.json')).get('escape')
        if e:
            lam = e['weight']
            src = e['source']
    print('escape weights for the feasible cells:', lam, src, flush=True)
    chk, report = [], []
    fs = feasible_cells(lam, chk, report)
    ws = within_cells(chk, report)
    us = unread_cells(chk, report)
    pool_cells(chk, report)
    with open(ME + 'cells-report.tsv', 'w') as f:
        cols = ['read', 'set', 'steers', 'split', 'cell', 'known_at_pick', 'picks', 'tasks', 'net', 'lo', 'hi']
        f.write('\t'.join(cols) + '\n')
        for r in report:
            f.write('\t'.join(str(round(r[c], 4)) if isinstance(r[c], float) else str(r[c]) for c in cols) + '\n')
    print('cells not thin with a net interval above 0: %d' % len(report), flush=True)
    totals(fs, ws, us)


def totals(fs, ws, us):
    """The all-cell row of each group against the totals of the item's own read (feasible-read.json, within-task-read.json, unread-read.json), and each split's cells (not rollups) summing to the pool."""
    rows = []

    def add(read, scope, q, got, ref, tol=0.0):
        ok = (got == ref) if tol == 0 else (got is not None and ref is not None and abs(got - ref) <= tol)
        rows.append(dict(read=read, scope=scope, quantity=q, got=got, reference=ref, tolerance=tol, equal=int(ok)))
    if os.path.exists(ME + 'feasible-read.json'):
        fr = json.load(open(ME + 'feasible-read.json'))
        for (v, steers), r in fs.items():
            if steers != 'off':
                continue
            ref = fr['bits']['all probed picks'][v]
            add('feasible', '%s, %s' % (v, steers), 'picks', r['picks'], fr['picks'])
            add('feasible', '%s, %s' % (v, steers), 'gold in set', r['gold_in'], ref['gold_in'])
    if os.path.exists(ME + 'within-task-read.json'):
        wr = json.load(open(ME + 'within-task-read.json'))
        for (nm, steers), r in ws.items():
            ref = wr['steers'][steers]['sets'].get(nm if nm != 'kept' else 'kept')
            if ref:
                add('within', '%s, %s' % (nm, steers), 'picks (a pick has one row per seed for the kept sets)', r['picks'], ref['picks'] * (2 if nm.startswith(('kept', 'both')) else 1))
    if os.path.exists(ME + 'unread-read.json'):
        ur = json.load(open(ME + 'unread-read.json'))
        for (nm, steers), r in us.items():
            add('unread', '%s, %s' % (nm, steers), 'derived picks', r['derived_picks'], ur['sets'][steers]['derived_picks'])
    for fname, key in (('feasible-cells.tsv', ('set', 'steers')), ('within-cells.tsv', ('set', 'steers')), ('unread-cells.tsv', ('set', 'steers')), ('pool-cells.tsv', ('set', 'steers'))):
        cs = read_tsv(ME + fname)
        groups = collections.defaultdict(list)
        for r in cs:
            groups[tuple(r[k] for k in key)].append(r)
        for g, rs in groups.items():
            pool = int(next(r for r in rs if r['split'] == 'all')['picks'])
            for split in sorted({r['split'] for r in rs} - {'all'}):
                sub = [r for r in rs if r['split'] == split and r['rollup'] == '0']
                add(fname, ', '.join(g), 'sum over cells of %s = pool picks' % split, sum(int(r['picks']) for r in sub), pool)
    with open(ME + 'totals-check.tsv', 'w') as f:
        cols = ['read', 'scope', 'quantity', 'got', 'reference', 'tolerance', 'equal']
        f.write('\t'.join(cols) + '\n')
        for r in rows:
            f.write('\t'.join(str(r[c]) for c in cols) + '\n')
    print('totals-check.tsv: %d checks, %d not equal' % (len(rows), sum(1 - r['equal'] for r in rows)), flush=True)


if __name__ == '__main__':
    main()
