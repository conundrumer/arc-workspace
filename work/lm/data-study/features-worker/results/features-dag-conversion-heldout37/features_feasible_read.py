#!/usr/bin/env python
"""Value join read (item 11): the sets any, all and keep of the probe rows, on the relation picks of held-parents RULE forms, over `off` and over `live`.

  features_dagc_env.sh 1 features_feasible_read.py [--seconds S] [--lam-stand-in] [--tag T]

Rows: the probe rows of probe-held-shard*.jsonl (features_dagc_probe.py, steers off), the pick tables of walks/held-parents-off-* and walks/held-parents-live-*. A pick is one pick key of one point (a form on a scope),
and weighs the count of walks that reach it over the point's finished walks, so each form weighs what one order weighs. A probe row is joined to the pick table by pick key and its options by name; the
check prints the largest gap between -log2 of the probe row's gold share and the pick table's q_bits.

The probes stopped at part of the held picks and may resume, so the read takes the picks that have a probe row, and writes feasible-left-out.tsv: each RULE point of held-parents with its picks probed
over its picks in the pick table. `forms complete` in the output is the forms whose every pick has a probe row. The tables carry both: all probed picks, and the picks of complete forms.

The escape weight of a set is the share of test-parents gold-alive picks where gold is out of the set, from probe-test-shard*.jsonl. Where those rows do not exist, no number with an escape weight is written, unless
--lam-stand-in is passed: then the weights of the source record (feasible-read.json of features-relation-pick-feasible-by-value-join-heldout37, from written-order test walks) stand in, marked as such.

Sets (feasible-definition.md of the source record), all on the options alive by column type:
  any   some map gives a row on at least one train example (a filter: removes a row and keeps a row on one example)
  all   one map gives a row on every train example where the prefix has a row
  keep  as any, with a filter that need only keep a row
An undetermined option stays in each set.
Over `off`: the prior is the weight of the off walk. Over `live`: the prior is the weight of the live walk at the same pick key and option name (picks that the live walks have not reached are left out of that column).
Split by d_depth band (empty = D empty in the pick's conjunction, 1, 2, 3+) in place of the atom's position. No number here is fit on a held row.
"""
import argparse
import collections
import glob
import json
import math
import os
import statistics as st
import sys
import time
import zlib

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features_dagc_rows as RW  # noqa: E402

ME = RW.ME
NAME, KIND, W, DEAD, OWN, U, A, EU, EA, UND, TABLES, MS = range(12)
CLASS = {'relation': 'derived', 'lib relation': 'lib', 'relation macro': 'macro', 'fact relation': 'fact', 'NOT': 'NOT', 'CMP': 'comparison', 'd': 'derived', 'l': 'lib', 'm': 'macro', 'f': 'fact', 'N': 'NOT', 'C': 'comparison'}
VARIANTS = 'any', 'all', 'keep'
SOURCE = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-feasible-by-value-join-heldout37/'


def read_jsonl(path):
    with open(path) as f:
        for line in f:
            if line.endswith('\n') and line.strip():
                try:
                    yield json.loads(line)
                except ValueError:
                    continue


def in_set(r, x, v):
    """Whether option x of probe row r is in set v."""
    if x[DEAD]:
        return False
    rows = r['pre']['rows']
    if x[KIND] == 'N':
        return rows is None or any(c > 0 for c in rows.values())
    filt = x[KIND] == 'C' or r['phase'] == 'root2'
    if x[UND]:
        return True
    if v == 'any':
        return (x[EU] if filt else x[U]) > 0
    if v == 'all':
        return bool(x[EA] if filt else x[A])
    return x[U] > 0


def per_example(r):
    """Mean over the train examples with a prefix row of the size of the set on that example alone."""
    rows = r['pre']['rows'] or {}
    sizes = []
    for e, c in rows.items():
        if c:
            b = 1 << int(e)
            n = 0
            for x in r['o']:
                if x[DEAD]:
                    continue
                filt = x[KIND] == 'C' or r['phase'] == 'root2'
                n += x[KIND] == 'N' or bool(x[UND]) or bool((x[EU] if filt else x[U]) & b)
            sizes.append(n)
    return st.mean(sizes) if sizes else 0.0


def why_out(r):
    """The kind of pick where gold's relation is out of the `any` set."""
    pre = r['pre']['rows'] or {}
    ga = r['gold_atom']
    gr = ga.get('rows') or {}
    if not any(pre.values()):
        return 'the prefix has no row on a train example'
    if r['gold_kind'] == 'NOT':
        return 'other NOT'
    if r['gold_kind'] == 'CMP' or r['phase'] == 'root2':
        name = 'comparison' if r['gold_kind'] == 'CMP' else 'NOT'
        if ga.get('err'):
            return "%s: gold's atom gives no table" % name
        eff = [e for e, c in pre.items() if c and 0 < gr.get(e, 0) < c]
        if eff:
            return "%s: gold's atom removes and keeps a row, and no map shows it" % name
        if all(gr.get(e, 0) == c for e, c in pre.items()):
            return "%s: gold's atom removes no row on any train example" % name
        if not any(gr.values()):
            return "%s: gold's atom removes every row" % name
        return "%s: gold's atom removes all on some examples and none on the others" % name
    if ga.get('err'):
        return "gold's atom gives no table: %s" % str(ga['err'])[:30]
    if ga.get('reads', 0) == 0:
        return "gold's atom reads no bound label%s" % (', inside a branch' if r.get('flat') else '')
    if not any(gr.values()):
        return "gold's atom reads a bound label and has no row on a train example"
    return "gold's atom has a row, and no map shows it"


def cls(r):
    return 'own' if r['own'] else CLASS[r['gold_kind']]


def escape_weights(a):
    """{set: share of test-parents gold-alive picks with gold out of the set}, and the count; None where there are no test probe rows."""
    files = sorted(glob.glob(ME + 'probe-test-shard*.jsonl'))
    if not files:
        return None
    rows = [r for p in files for r in read_jsonl(p) if r['rec'] == 'probe']
    T = [r for r in rows if r['gold_idx'] is not None and not r['o'][r['gold_idx']][DEAD]]
    if not T:
        return None
    lam = {v: sum(not in_set(r, r['o'][r['gold_idx']], v) for r in T) / len(T) for v in VARIANTS}
    return dict(weight=lam, test_picks=len(T), test_tasks=len({r['task'] for r in T}), source='probe-test rows of this conversion')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--seconds', type=float, default=20)
    ap.add_argument('--lam-stand-in', action='store_true')
    ap.add_argument('--tag', default='')
    a = ap.parse_args()
    t0 = time.time()
    probes, pforms = {}, 0
    for p in sorted(glob.glob(ME + 'probe-held-shard*.jsonl')):
        for r in read_jsonl(p):
            if r['rec'] == 'probe':
                probes[RW_key(r)] = r
            else:
                pforms += 1
    off = RW.load('held-parents', 'off', seconds=a.seconds)
    live = RW.load('held-parents', 'live', seconds=a.seconds)
    print('probe rows %d, probed walks %d; off table %d entries (%d walks ok), live table %d entries; %.0fs' % (len(probes), pforms, len(off.entries), sum(off.nok.values()), len(live.entries), time.time() - t0), flush=True)
    # coverage by point
    pts = [json.loads(x) for x in open(ME + 'points-held-parents.jsonl')]
    rule_pts = [p for p in pts if p['kind'] == 'RULE']
    per_point = collections.defaultdict(lambda: [0, 0])
    for (pt, k), e in off.entries.items():
        per_point[pt][0] += 1
        per_point[pt][1] += k in probes
    complete = {pt for pt, (n, m) in per_point.items() if n and n == m}
    with open(ME + 'feasible-left-out.tsv', 'w') as f:
        f.write('task\tline_id\tform\tscope_id\tpicks_in_pick_table\tpicks_probed\tstate\n')
        for p in rule_pts:
            n, m = per_point.get(p['line'], [0, 0])
            state = 'no finished walk' if n == 0 else 'complete' if n == m else 'none probed' if m == 0 else 'partial'
            f.write('%s\t%d\t%s\t%s\t%d\t%d\t%s\n' % (p['task'], p['line_id'], p['form'], p['scope_id'], n, m, state))
    states = collections.Counter()
    for p in rule_pts:
        n, m = per_point.get(p['line'], [0, 0])
        states['no finished walk' if n == 0 else 'complete' if n == m else 'none probed' if m == 0 else 'partial'] += 1
    # rows
    P, gap, name_diff, live_missing = [], 0.0, 0, 0
    for (pt, k), e in off.entries.items():
        r = probes.get(k)
        if r is None or r['gold_idx'] is None:
            continue
        g = r['gold_idx']
        if r['o'][g][DEAD]:
            continue
        names = [x[NAME] for x in r['o']]
        if names != [x[0] for x in e['opts']] or e['gold_idx'] != g:
            name_diff += 1
            continue
        w = np.array([x[W] for x in r['o']], float)
        q = w / w.sum()
        gap = max(gap, abs(-math.log2(q[g]) - e['q_bits']))
        le = live.entries.get((pt, k))
        wl = None
        if le is not None and [x[0] for x in le['opts']] == names:
            wl = np.array([x[2] for x in le['opts']], float)
        elif le is not None:
            live_missing += 1
        P.append(dict(pt=pt, r=r, e=e, w=RW.weight(off, e), wl=wl, comp=pt in complete, g=g, cls=cls(r), band=e['band'], task=e['task'], kind=e['kind'], form='%s %d' % (e['task'], e['line_id'])))
    print('%d gold-alive probed picks; name or gold mismatch with the pick table %d; live options differ %d; largest gap of the probe row\'s q_bits to the pick table %.4f' % (len(P), name_diff, live_missing, gap), flush=True)
    lamd = escape_weights(a)
    if lamd is None and a.lam_stand_in:
        src = json.load(open(SOURCE + 'feasible-read.json'))['escape']
        lamd = dict(weight=src['weight'], test_picks=src['test_picks'], test_tasks=src['test_tasks'], source='STAND-IN: feasible-read.json of the source record (written-order test walks), not this conversion')
    res = dict(probe_rows=len(probes), picks=len(P), tasks=len({d['task'] for d in P}), forms=len({d['form'] for d in P}), forms_complete=len({d['form'] for d in P if d['comp']}), rule_points=len(rule_pts), point_states=dict(states), gap_to_pick_table=round(gap, 4),
               name_mismatch=name_diff, escape=lamd, weight_in_pick_table=float(sum(RW.weight(off, e) for e in off.entries.values())), weight_probed=float(sum(d['w'] for d in P)))
    # per pick arrays
    n = len(P)
    wt = np.array([d['w'] for d in P])
    tk = np.array([d['task'] for d in P])
    cl = np.array([d['cls'] for d in P])
    bd = np.array([d['band'] for d in P])
    kd = np.array([d['kind'] for d in P])
    comp = np.array([d['comp'] for d in P])
    has_live = np.array([d['wl'] is not None for d in P])
    Q = {}
    for v in VARIANTS:
        Q[v] = dict(size=np.zeros(n), inside=np.zeros(n, bool), res=np.zeros(n), res_out=np.zeros(n), resl=np.zeros(n), resl_out=np.zeros(n))
    alive_n = np.zeros(n)
    qb = np.zeros(n)
    qbl = np.full(n, np.nan)
    ex = np.zeros(n)
    for i, d in enumerate(P):
        r, g = d['r'], d['g']
        w = np.array([x[W] for x in r['o']], float)
        al = np.array([not x[DEAD] for x in r['o']], bool)
        alive_n[i] = al.sum()
        ex[i] = per_example(r)
        q = w / w.sum()
        qb[i] = -math.log2(q[g])
        if d['wl'] is not None:
            ql = d['wl'] / d['wl'].sum()
            qbl[i] = -math.log2(ql[g])
        for v in VARIANTS:
            m = np.array([in_set(r, x, v) for x in r['o']], bool)
            c = Q[v]
            c['size'][i] = m.sum()
            c['inside'][i] = m[g]
            rest = al & ~m
            for tag, qq in (('', q), ('l', ql if d['wl'] is not None else None)):
                if qq is None:
                    continue
                if m[g]:
                    c['res' + tag][i] = -math.log2(qq[g] / qq[m].sum())
                else:
                    c['res%s_out' % tag][i] = -math.log2(qq[g] / qq[rest].sum())
    # tables
    def row_stats(mask, wl_ok=False):
        return int(mask.sum()), len(set(tk[mask].tolist()))
    out = dict(res)
    out['sizes'] = {}
    groups = [('all picks', np.ones(n, bool))] + [('band ' + b, bd == b) for b in RW.BANDS]
    for nm, m in groups:
        if m.any():
            out['sizes'][nm] = dict(picks=int(m.sum()), alive=RW.quart(alive_n[m]), any=RW.quart(Q['any']['size'][m]), all=RW.quart(Q['all']['size'][m]), keep=RW.quart(Q['keep']['size'][m]), mean_example=RW.quart(ex[m]))
    out['bits'] = {}
    for sub_name, sub in (('all probed picks', np.ones(n, bool)), ('picks of complete forms', comp)):
        out['bits'][sub_name] = {}
        for v in VARIANTS:
            c = Q[v]
            ing = c['inside'] & sub
            e = dict(picks=int(sub.sum()), gold_in=int(ing.sum()), share=round(float(wt[ing].sum() / max(wt[sub].sum(), 1e-12)), 4))
            for steer, qprior, resk, ok in (('off', qb, 'res', np.ones(n, bool)), ('live', qbl, 'resl', has_live)):
                s = ing & ok
                if not s.any():
                    continue
                uni = np.log2(np.maximum(c['size'], 1))
                e[steer] = dict(picks=int(s.sum()), prior_same_picks=round(float(np.average(qprior[s], weights=wt[s])), 3), uniform_alive_same_picks=round(float(np.average(np.log2(alive_n[s]), weights=wt[s])), 3), uniform_set=round(float(np.average(uni[s], weights=wt[s])), 3),
                                prior_in_set=round(float(np.average(c[resk][s], weights=wt[s])), 3), saved_prior_in_set=[round(x, 3) for x in RW.boot(wt[s] * (qprior[s] - c[resk][s]), wt[s], tk[s])])
            out['bits'][sub_name][v] = e
    if lamd:
        out['soft'] = {}
        for v in VARIANTS:
            lam = lamd['weight'][v]
            c = Q[v]
            out['soft'][v] = {}
            for steer, qprior, resk, resk_out, ok in (('off', qb, 'res', 'res_out', np.ones(n, bool)), ('live', qbl, 'resl', 'resl_out', has_live)):
                cost = np.where(c['inside'], -math.log2(1 - lam) + c[resk], -math.log2(lam) + c[resk_out])
                uni = np.where(c['inside'], -math.log2(1 - lam) + np.log2(np.maximum(c['size'], 1)), -math.log2(lam) + np.log2(np.maximum(alive_n - c['size'], 1)))
                s = ok
                out['soft'][v][steer] = dict(picks=int(s.sum()), prior=round(float(np.average(qprior[s], weights=wt[s])), 3), uniform=round(float(np.average(uni[s], weights=wt[s])), 3), with_prior=round(float(np.average(cost[s], weights=wt[s])), 3),
                                             saved=[round(x, 3) for x in RW.boot(wt[s] * (qprior[s] - cost[s]), wt[s], tk[s], s)], total_saved_bits=round(float((wt[s] * (qprior[s] - cost[s])).sum()), 1))
    out['by_class'], out['by_band'], out['by_class_band'], out['by_kind'] = {}, {}, {}, {}
    c = Q['any']
    def cell(m):
        ing = c['inside'] & m
        e = dict(picks=int(m.sum()), gold_in_any=int(ing.sum()), tasks=len(set(tk[m].tolist())))
        if ing.any():
            e.update(prior_same_picks=round(float(np.average(qb[ing], weights=wt[ing])), 3), prior_in_set=round(float(np.average(c['res'][ing], weights=wt[ing])), 3), uniform_set=round(float(np.average(np.log2(np.maximum(c['size'], 1))[ing], weights=wt[ing])), 3),
                     saved_in_set=[round(x, 3) for x in RW.boot(wt[ing] * (qb[ing] - c['res'][ing]), wt[ing], tk[ing])])
            ok = ing & has_live
            if ok.any():
                e['live_saved_in_set'] = [round(x, 3) for x in RW.boot(wt[ok] * (qbl[ok] - c['resl'][ok]), wt[ok], tk[ok])]
        if lamd:
            lam = lamd['weight']['any']
            cost = np.where(c['inside'], -math.log2(1 - lam) + c['res'], -math.log2(lam) + c['res_out'])
            if m.any():
                e['saved_soft_off'] = [round(x, 3) for x in RW.boot(wt[m] * (qb[m] - cost[m]), wt[m], tk[m])]
        return e
    for cname in ('derived', 'lib', 'own', 'macro', 'NOT', 'fact', 'comparison'):
        m = cl == cname
        if m.any():
            out['by_class'][cname] = cell(m)
    for b in RW.BANDS:
        m = bd == b
        if m.any():
            out['by_band'][b] = cell(m)
    for cname in ('derived', 'lib', 'own'):
        for b in RW.BANDS:
            m = (cl == cname) & (bd == b)
            if m.any():
                out['by_class_band']['%s, %s' % (cname, b)] = cell(m)
    # gold out
    outc = collections.Counter()
    for i, d in enumerate(P):
        if not Q['any']['inside'][i]:
            outc[why_out(d['r'])] += 1
    out['gold_out_any'] = dict(outc.most_common())
    out['gold_out_all_only'] = int((Q['any']['inside'] & ~Q['all']['inside']).sum())
    # check against the source's gold-in share by class
    src = json.load(open(SOURCE + 'feasible-read.json'))
    chk = {}
    for cname, v in src['bits_by_class'].items():
        m = cl == cname
        if m.any():
            chk[cname] = dict(picks=int(m.sum()), share_gold_in_any=round(float(Q['any']['inside'][m].mean()), 3), source_share=round(v['gold_in_any'] / v['picks'], 3))
    out['check_gold_in_vs_source'] = chk
    out['check_gold_in_all'] = dict(share=round(float(Q['any']['inside'].mean()), 4), source_share=0.9675)
    # per pick rows for item 13
    with open(ME + 'cells-input-feasible%s.tsv' % a.tag, 'w') as f:
        f.write('read\tset\ttask\tform\tkind\tkey_hash\tw\tband\tplace\tcls\tcomplete\tprior_off\tprior_live\tinside\tsize\talive\tres_off\tres_out_off\tres_live\tres_out_live\n')
        for i, d in enumerate(P):
            for v in VARIANTS:
                c = Q[v]
                f.write('feasible\t%s\t%s\t%s\t%s\t%s\t%.6f\t%s\t%s\t%s\t%d\t%.4f\t%s\t%d\t%d\t%d\t%.4f\t%.4f\t%.4f\t%.4f\n' % (v, d['task'], d['form'], d['kind'], zlib.crc32(repr(d['e']['key']).encode()), d['w'], d['band'], d['e']['place'], d['cls'], d['comp'], qb[i],
                        '' if np.isnan(qbl[i]) else '%.4f' % qbl[i], c['inside'][i], c['size'][i], alive_n[i], c['res'][i], c['res_out'][i], c['resl'][i], c['resl_out'][i]))
    json.dump(out, open(ME + 'feasible-read%s.json' % a.tag, 'w'), indent=1)
    md = write_md(out, a)
    print(md)


def RW_key(r):
    return (r['task'], r['line_id'], r['form'], r['scope_id'], r['phase'], r['atom'], r['dsid'])


def write_md(o, a):
    L = ['# Value join set at the relation pick, held-parents RULE forms, steers off', '']
    L.append('Rows: %d probe rows; %d gold-alive probed picks on %d tasks and %d forms (%d forms complete). RULE points of held-parents: %s. Probed weight %.1f of %.1f in the pick table. Largest gap of the probe row\'s prior to the pick table %s bits.' % (
        o['probe_rows'], o['picks'], o['tasks'], o['forms'], o['forms_complete'], o['point_states'], o['weight_probed'], o['weight_in_pick_table'], o['gap_to_pick_table']))
    L.append('')
    L.append('The forms that the read leaves out are listed in feasible-left-out.tsv: states `no finished walk` and `none probed` have no pick in the read, `partial` has the picks that were probed.')
    L.append('')
    if o.get('escape'):
        L.append('Escape weights: %s from %d test picks on %d tasks (%s).' % ({k: round(x, 4) for k, x in o['escape']['weight'].items()}, o['escape']['test_picks'], o['escape']['test_tasks'], o['escape']['source']))
    else:
        L.append('Escape weights: none. probe-test rows do not exist yet, so no number with an escape weight is written.')
    L.append('')
    L.append(RW.table_md(['Picks', 'Count', 'Alive: Q1, median, Q3', 'any', 'all', 'keep', 'One example at a time'], [[k, v['picks'], *[', '.join(str(x) for x in v[s]) for s in ('alive', 'any', 'all', 'keep', 'mean_example')]] for k, v in o['sizes'].items()]))
    for sub, tab in o['bits'].items():
        L.append('Gold in the set, %s:' % sub)
        L.append('')
        rows = []
        for v, e in tab.items():
            for steer in ('off', 'live'):
                if steer in e:
                    s = e[steer]
                    rows.append([v, steer, e['picks'], e['gold_in'], e['share'], s['picks'], s['prior_same_picks'], s['uniform_alive_same_picks'], s['uniform_set'], s['prior_in_set'], RW.fmt3(s['saved_prior_in_set'])])
        L.append(RW.table_md(['Set', 'Prior', 'Picks', 'Gold in set', 'Share', 'Picks read', 'Prior bits, same picks', 'Uniform over alive', 'Uniform over set', 'Prior in set', 'Saved by the prior in set, 95% by task'], rows))
    if 'soft' in o:
        L.append('All picks, with an escape weight:')
        L.append('')
        rows = [[v, steer, s['picks'], s['prior'], s['uniform'], s['with_prior'], RW.fmt3(s['saved']), s['total_saved_bits']] for v, t in o['soft'].items() for steer, s in t.items()]
        L.append(RW.table_md(['Set', 'Prior', 'Picks', 'Prior bits', 'Uniform over set, escape', 'Prior in set, escape', 'Saved, 95%', 'Saved bits, total'], rows))
    for nm in ('by_class', 'by_band', 'by_class_band'):
        L.append('Set any, %s:' % nm.replace('_', ' '))
        L.append('')
        L.append(RW.table_md(['Cell', 'Picks', 'Tasks', 'Gold in any', 'Prior bits', 'Prior in set', 'Saved in set off', 'Saved in set live', 'Saved with escape off'],
                             [[k, v['picks'], v['tasks'], v['gold_in_any'], v.get('prior_same_picks', ''), v.get('prior_in_set', ''), RW.fmt3(v['saved_in_set']) if 'saved_in_set' in v else '', RW.fmt3(v['live_saved_in_set']) if 'live_saved_in_set' in v else '',
                               RW.fmt3(v['saved_soft_off']) if 'saved_soft_off' in v else ''] for k, v in o[nm].items()]))
    L.append('Gold out of the `any` set:')
    L.append('')
    L += ['- %s: %d' % (k, v) for k, v in o['gold_out_any'].items()]
    L.append('')
    L.append('Gold in the `any` set against the source record (feasible-read.json, written-order walks): %s; all classes %s.' % (json.dumps(o['check_gold_in_vs_source']), o['check_gold_in_all']))
    md = '\n'.join(L) + '\n'
    open(ME + 'feasible-read%s.md' % a.tag, 'w').write(md)
    return md


if __name__ == '__main__':
    main()
