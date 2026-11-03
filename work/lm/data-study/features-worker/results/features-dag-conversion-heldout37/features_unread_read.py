#!/usr/bin/env python
"""Unread forms at derived picks (item 14): the tables, from the pick rows of held-cut (all kinds) under off and live, with w from unread-fit.json (non-held walks).

  features_dagc_env.sh 1 features_unread_read.py [--seconds S] [--final] [--check]

Sets: unread_scope, unread_pick, and unread_only (the oracle of the program DAG, the ceiling) of features_unread_lib.py. A pick weighs its walks over the point's finished walks; a form is a (task, line) and its bits are the mean over its
points (the two seeds of the cut scope) of the mean walk total. Forms at 25 bits or more are cut by bits_mean under live (the live walks of the same part). No number here is fit on a held row: BAR is 25 and each w comes from unread-fit.json.

Tables (summary.json, partial.md, unread-cells.tsv is written by features_relation_pick_sets_by_cell.py from cells-input-unread.tsv):
  sizes       the sets at a derived pick, by kind, d_depth band and set: size, share of picks with gold's form inside
  inside      the picks with gold's form inside: bits paid against log2 of the derived options in the set
  oracle      a pick with gold inside pays log2 of the derived options in the set: forms at 25 or more taken under 25
  mixture     the mixture prior: saved per derived pick, net of the cost at all picks, forms taken under 25 and pushed over
  pool        the pool run's found forms (pool-tasks.jsonl of the source record), bits from held-cut
Verdict: unread status does not pay if the oracle takes under a quarter of the forms over 25.
--check scrambles the lines and bodies of programs and compares the sets of every point.
"""
import argparse
import collections
import json
import math
import os
import random
import statistics as st
import sys
import time
import zlib

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features_dag_order as D  # noqa: E402
import features_dagc_lib as L  # noqa: E402
import features_dagc_rows as RW  # noqa: E402
import features_dagc_unread_rows as UR  # noqa: E402
import features_unread_lib as UL  # noqa: E402

ME = RW.ME
SRC = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-unread-forms-heldout37/'
ARMS = ('control_search', 'factored_search')
NOT_IN_RUN = ('269e22fb', 'cbebaa4b')
KINDS = ('RULE', 'INIT', 'DET')


def arr(P, f):
    return np.array([f(p) for p in P])


def mixture_saved(P, name, variant, w_mix):
    """Per pick: bits saved by the mixture."""
    n = arr(P, lambda p: p['n'][name] if variant == 'forms' else p['o'][name]).astype(float)
    ins = arr(P, lambda p: bool(p['inside'][name]) and (variant == 'forms' or p['o'][name] > 0))
    q = arr(P, lambda p: p['bits']).astype(float)
    pr = 2.0 ** -q
    with np.errstate(divide='ignore'):
        new = -np.log2((1 - w_mix) * pr + np.where(ins & (n > 0), w_mix / np.maximum(n, 1), 0.0))
    return q - np.where(n > 0, new, q)


def form_table(R):
    """{(task, line_id): bits_mean}, the mean over the points of a form."""
    acc = collections.defaultdict(list)
    for f in R.forms.values():
        acc[f['task'], f['line_id']].append(f['bits_mean'])
    return {k: sum(v) / len(v) for k, v in acc.items()}


def point_delta(R, P, saved):
    """{(task, line_id): sum over the picks of a form's points of w * saved, mean over its points}."""
    byp = collections.defaultdict(float)
    for p, s in zip(P, saved):
        byp[p['point']] += p['w'] * s
    acc = collections.defaultdict(list)
    for pt, f in R.forms.items():
        acc[f['task'], f['line_id']].append(byp.get(pt, 0.0))
    return {k: sum(v) / len(v) for k, v in acc.items()}


def counts_under(base, new, live_bits):
    """(forms at 25+ by live bits, taken under 25, forms under 25 by live bits, pushed over 25)."""
    over = [k for k in live_bits if live_bits[k] >= UL.BAR and k in new]
    under = [k for k in live_bits if live_bits[k] < UL.BAR and k in new]
    return dict(forms_over=len(over), taken_under=sum(new[k] < UL.BAR for k in over), forms_under=len(under), pushed_over=sum(new[k] >= UL.BAR for k in under), now_under_in_over=sum(base[k] < UL.BAR for k in over if k in base))


def sizes_table(Pd, name):
    rows = []
    groups = [('all', np.ones(len(Pd), bool))]
    kd, bd = arr(Pd, lambda p: p['kind']), arr(Pd, lambda p: p['band'])
    groups += [(k, kd == k) for k in KINDS] + [('band ' + b, bd == b) for b in RW.BANDS] + [('%s, %s' % (k, b), (kd == k) & (bd == b)) for k in KINDS for b in RW.BANDS]
    wt = arr(Pd, lambda p: p['w'])
    ins = arr(Pd, lambda p: p['inside'][name])
    n = arr(Pd, lambda p: p['n'][name])
    o = arr(Pd, lambda p: p['o'][name])
    bits = arr(Pd, lambda p: p['bits'])
    ns = arr(Pd, lambda p: p['nscope'])
    for nm, m in groups:
        if not m.any():
            continue
        r = dict(group=nm, picks=int(m.sum()), tasks=len(set(arr(Pd, lambda p: p['task'])[m].tolist())), median_scope=float(np.median(ns[m])), bits=round(float(np.average(bits[m], weights=wt[m])), 3), median_forms=float(np.median(n[m])), median_options=float(np.median(o[m])),
                 empty=int((n[m] == 0).sum()), inside=int(ins[m].sum()), share=round(float(np.average(ins[m], weights=wt[m])), 4))
        mi = m & ins.astype(bool) & (o > 0)
        if mi.any():
            r.update(bits_inside=round(float(np.average(bits[mi], weights=wt[mi])), 3), log2_options_inside=round(float(np.average(np.log2(o[mi]), weights=wt[mi])), 3), log2_forms_inside=round(float(np.average(np.log2(np.maximum(n[mi], 1)), weights=wt[mi])), 3))
        rows.append(r)
    return rows


def pool_rows(Pd, held_p, cells_pool=None):
    pool = {a: {} for a in ARMS}
    path = SRC + 'pool-tasks.jsonl'
    for x in open(path):
        r = json.loads(x)
        pool[r['arm']][r['task']] = r
    line_of = {}
    for t in {p['task'] for p in Pd}:
        cp = D.ProgramDag(held_p[t])
        m = {}
        for i, x in enumerate(held_p[t]):
            k = 'OUT' if x.startswith('(OUT') else D.parse(x)[1]
            m.setdefault(cp.content[k], i)
        line_of[t] = m
    out = []
    P = [p for p in Pd if p['task'] not in NOT_IN_RUN]
    for arm in ARMS:
        for gname in ['all'] + list(KINDS):
            ps = [p for p in P if gname == 'all' or p['kind'] == gname]
            read, found, withnode = [], [], []
            for p in ps:
                pr = pool[arm].get(p['task'])
                if pr is None:
                    continue
                ln = line_of[p['task']].get(p['gold_ck'])
                t = next((x for x in pr['targets'] if x['line'] == ln), None)
                if t is None or t.get('found') is None:
                    continue
                read.append((p, pr, t))
                if cells_pool is not None:
                    cells_pool.write('pool\t%s\t%s\t%s %d\t%s\t%d\t%.6f\t%s\t%s\t%d\t%.4f\t%d\n' % (arm, p['task'], p['task'], p['line_id'], p['kind'], zlib.crc32(repr(p['key']).encode()), p['w'], p['band'], p['place'], int(bool(t['found'])), p['bits'], int(bool(t['found']) and 'node' in t and not t['read_end'])))
                if t['found']:
                    found.append((p, pr, t))
                    if 'node' in t:
                        withnode.append((p, pr, t))
            wt = lambda xs: np.array([x[0]['w'] for x in xs])
            r = dict(arm=arm, group=gname, picks=len(ps), readable=len(read), found=len(found), found_share=round(float(wt(found).sum() / wt(read).sum()), 4) if read else None, with_node=len(withnode))
            if read:
                ends = np.array([x[1]['unread'] for x in read])
                r.update(unread_end_median=float(np.median(ends)), forms_end_median=float(np.median([x[1]['forms'] for x in read])), bits_read_mean=round(float(np.average([x[0]['bits'] for x in read], weights=wt(read))), 3))
            if found:
                r.update(unread_at_found_median=float(np.median([x[2]['unread_at_found'] for x in found])), bits_found_mean=round(float(np.average([x[0]['bits'] for x in found], weights=wt(found))), 3),
                         log2_at_found_mean=round(float(np.average([math.log2(max(1, x[2]['unread_at_found'])) for x in found], weights=wt(found))), 3))
            if withnode:
                un = [x for x in withnode if not x[2]['read_end']]
                r.update(unread_end_inside=len(un), unread_end_inside_share=round(len(un) / len(withnode), 4), read_at_found=sum(x[2]['read_at_found'] for x in withnode))
                if un:
                    r.update(bits_inside_mean=round(float(np.average([x[0]['bits'] for x in un], weights=wt(un))), 3), log2_end_inside_mean=round(float(np.average([math.log2(x[1]['unread']) for x in un], weights=wt(un))), 3))
            out.append(r)
    return out


def check(R=None):
    """A scramble of the lines and bodies of programs leaves the sets of every point the same: the scope is the same set of forms, so the sets are the same functions of it."""
    held = L.base_gold()
    bad = n = 0
    for t in sorted(held)[:30]:
        lines = held[t]
        rnd = random.Random('scr|' + t)
        sh = lines[:]
        rnd.shuffle(sh)
        full0, full1 = D.ProgramDag(lines), D.ProgramDag(sh)
        for key in full0.lines:
            if key == 'OUT':
                continue
            o0 = full0.random_order(0, full0.non_descendants(key) | {key})
            o1 = full1.random_order(0, full1.non_descendants(key) | {key})
            s0 = UL.PointSets(full0.texts(o0[:o0.index(key)]), full0, key)
            s1 = UL.PointSets(full1.texts(o1[:o1.index(key)]), full1, key)
            n += 1
            bad += (s0.unread_scope, s0.unread_only) != (s1.unread_scope, s1.unread_only)
    print('scramble check: %d points on 30 tasks, %d differ' % (n, bad))
    return n, bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--seconds', type=float, default=20)
    ap.add_argument('--final', action='store_true')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    if a.check:
        return check()
    t0 = time.time()
    fit = json.load(open(ME + 'unread-fit.json'))
    held_p = L.base_gold()
    R = {s: UR.build('held-cut', s, seconds=a.seconds) for s in ('off', 'live')}
    print('rows: off %d picks %d points, live %d picks %d points; %.0fs' % (len(R['off'].picks), len(R['off'].forms), len(R['live'].picks), len(R['live'].forms), time.time() - t0), flush=True)
    live_bits = form_table(R['live'])
    out = dict(files={s: R[s].files for s in R}, fit_sources=fit['source'], forms_live=len(live_bits), forms_over_25_live=sum(v >= UL.BAR for v in live_bits.values()), tasks=len({k[0] for k in live_bits}), sets={})
    cells = open(ME + 'cells-input-unread.tsv', 'w')
    cells.write('read\tset\ttask\tform\tkind\tkey_hash\tw\tband\tplace\tcls\tsteers\tprior\tinside\tn_options\tn_forms\tsaved_options\tsaved_forms\tderived\n')
    for steers in ('off', 'live'):
        r = R[steers]
        P = r.picks
        Pd = [p for p in P if p['derived']]
        base_forms = form_table(r)
        res = dict(picks=len(P), derived_picks=len(Pd), forms=len(base_forms), no_gold_picks=r.no_gold, conf=r.conf, sizes={}, oracle=[], mixture=[])
        for name in UL.SETS:
            res['sizes'][name] = sizes_table(Pd, name)
        # oracle: a derived pick with gold inside pays log2 of the derived options in the set
        wt = arr(P, lambda p: p['w'])
        task = arr(P, lambda p: p['task'])
        for name in UL.SETS:
            sav = np.array([(p['bits'] - math.log2(p['o'][name])) if (p['derived'] and p['inside'][name] and p['o'][name] > 0) else 0.0 for p in P])
            delta = point_delta(r, P, sav)
            new = {k: base_forms[k] - delta.get(k, 0.0) for k in base_forms}
            c = counts_under(base_forms, new, live_bits)
            over = c['forms_over']
            res['oracle'].append(dict(set=name, picks_paying_log2=int((sav != 0).sum()), known_at_pick=name in UL.KNOWN, share_taken=round(c['taken_under'] / over, 4) if over else None, pays=bool(over and c['taken_under'] / over >= .25), **c))
        # mixture
        for name in UL.SETS:
            for variant in ('forms', 'options'):
                w_mix = fit['w'][steers]['%s:%s' % (name, variant)]['w']
                sv = mixture_saved(P, name, variant, w_mix)
                dmask = arr(P, lambda p: p['derived'])
                ds = RW.boot(wt * sv, wt, task, dmask)
                net = RW.boot(wt * sv, wt * dmask, task)
                delta = point_delta(r, P, sv)
                new = {k: base_forms[k] - delta.get(k, 0.0) for k in base_forms}
                c = counts_under(base_forms, new, live_bits)
                res['mixture'].append(dict(set=name, variant=variant, w=w_mix, derived_picks=int(dmask.sum()), saved_per_derived_pick=[round(x, 3) for x in ds], net_saved_per_derived_pick=[round(x, 3) for x in net], saved_per_relation_pick=round(float((wt * sv).sum() / wt.sum()), 4), **c))
                if variant == 'options':
                    for p, s_, sf in zip(P, sv, mixture_saved(P, name, 'forms', fit['w'][steers]['%s:forms' % name]['w'])):
                        cells.write('unread\t%s\t%s\t%s %d\t%s\t%d\t%.6f\t%s\t%s\t%s\t%s\t%.4f\t%d\t%d\t%d\t%.4f\t%.4f\t%d\n' % (name, p['task'], p['task'], p['line_id'], p['kind'], zlib.crc32(repr(p['key']).encode()), p['w'], p['band'], p['place'], p['cls'], steers, p['bits'],
                                                                                                                   p['inside'][name], p['o'][name], p['n'][name], s_, sf, p['derived']))
        if steers == 'live':
            cp = open(ME + 'cells-input-pool.tsv', 'w')
            cp.write('read\tset\ttask\tform\tkind\tkey_hash\tw\tband\tplace\tfound\tprior\tunread_end\n')
            res['pool'] = pool_rows(Pd, held_p, cp)
            cp.close()
        out['sets'][steers] = res
    cells.close()
    json.dump(out, open(ME + 'unread-read.json', 'w'), indent=1, default=lambda o: o.item() if hasattr(o, 'item') else str(o))
    if a.final:
        with open(ME + 'held-reads.jsonl', 'a') as f:
            for steers in ('off', 'live'):
                f.write(json.dumps(dict(name='unread-held_read', group='unread forms', arm='mixture', tier='unread_scope+unread_pick', steers=steers, control=False, time=time.strftime('%Y-%m-%dT%H:%M:%S'))) + '\n')
    md = write_md(out)
    print(md)


def write_md(o):
    L_ = ['# Unread forms at derived picks, held-cut (both seeds as a mean), all kinds', '', 'Walk files: %s.' % json.dumps(o['files']), 'Fit rows for w: %s.' % json.dumps({k: {x: v[x] for x in ('part', 'picks', 'forms', 'tasks')} for k, v in o['fit_sources'].items()}),
          'Forms with a live total: %d on %d tasks, %d at 25 bits or more by live bits_mean.' % (o['forms_live'], o['tasks'], o['forms_over_25_live']), '']
    for steers, r in o['sets'].items():
        L_ += ['## Steers %s' % steers, '', '%d picks, %d derived, %d forms, %d picks with gold outside the options.' % (r['picks'], r['derived_picks'], r['forms'], r['no_gold_picks']), '']
        L_.append('Oracle: a derived pick with gold inside the set pays log2 of the derived options in the set. Forms at 25 bits or more (by live bits_mean) taken under 25. The decision: unread status does not pay if the oracle takes under a quarter of those forms.')
        L_.append('')
        L_.append(RW.table_md(['Set', 'Known at the pick', 'Picks at log2', 'Forms over 25', 'Taken under 25', 'Share', 'Pays (at least a quarter)'], [[x['set'], x['known_at_pick'], x['picks_paying_log2'], x['forms_over'], x['taken_under'], x['share_taken'], x['pays']] for x in r['oracle']]))
        L_.append('Mixture prior (w from non-held walks):')
        L_.append('')
        L_.append(RW.table_md(['Set', 'Variant', 'w', 'Derived picks', 'Saved per derived pick', 'Net of the cost at all picks, per derived pick', 'Forms over 25 taken under', 'Forms under 25 pushed over'],
                              [[x['set'], x['variant'], x['w'], x['derived_picks'], RW.fmt3(x['saved_per_derived_pick']), RW.fmt3(x['net_saved_per_derived_pick']), '%d of %d' % (x['taken_under'], x['forms_over']), '%d of %d' % (x['pushed_over'], x['forms_under'])] for x in r['mixture']]))
        for name, rows in r['sizes'].items():
            if name == 'unread_only' and False:
                continue
            L_.append('Set %s at a derived pick:' % name)
            L_.append('')
            L_.append(RW.table_md(['Group', 'Picks', 'Tasks', 'Median scope', 'Bits paid', 'Median forms in set', 'Median derived options in set', 'Set empty', 'Gold inside', 'Share inside', 'Bits paid inside', 'log2 options inside', 'log2 forms inside'],
                                  [[x['group'], x['picks'], x['tasks'], x['median_scope'], x['bits'], x['median_forms'], x['median_options'], x['empty'], x['inside'], x['share'], x.get('bits_inside', ''), x.get('log2_options_inside', ''), x.get('log2_forms_inside', '')] for x in rows]))
        if 'pool' in r:
            L_.append('Pool forms (the run\'s nodes and parents; bits from held-cut, live):')
            L_.append('')
            L_.append(RW.table_md(['Arm', 'Group', 'Picks', 'Readable', 'Found', 'Found share', 'Found picks with a node', 'Unread at end, median', 'Unread at found, median', 'Bits found', 'log2 set at found', 'Target unread at end', 'Bits paid there', 'log2 set at end'],
                                  [[x['arm'], x['group'], x['picks'], x['readable'], x['found'], x['found_share'], x['with_node'], x.get('unread_end_median', ''), x.get('unread_at_found_median', ''), x.get('bits_found_mean', ''), x.get('log2_at_found_mean', ''),
                                    '%s of %s' % (x.get('unread_end_inside', ''), x['with_node']), x.get('bits_inside_mean', ''), x.get('log2_end_inside_mean', '')] for x in r['pool']]))
    md = '\n'.join(L_) + '\n'
    open(ME + 'unread-read.md', 'w').write(md)
    return md


if __name__ == '__main__':
    main()
