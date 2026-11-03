#!/usr/bin/env python
"""INIT forms that a body rewrite leaves over 25 bits (item 15): the parts table, the pairs table, the reads of earlier forms and the component pick, on the walks of the 77 rewritten INIT forms (init77) in valid orders.

  features_dagc_env.sh 1 read_rows.py [--seconds S] [--steers off|live|both]

Rows: walks/init77-STEERS-*.jsonl.zst (features_dagc_init77.py walk), points-init77.jsonl (scope `cut`, seeds 0 and 1, on the rewritten program's DAG), init77-programs.jsonl (each rewritten program and its target), and from the source record
features-init-residual-bits-split-74forms: form-set.jsonl (held, group, census bits), component-rows.jsonl (the trial of each component on gold's bound ports as tables: ports have no order, and the file stands), comp-priors.json and
pool-components.jsonl (the pool run's components, as it stands).
Changes against the source read_rows.py:
  - a form's bits are bits_mean: the mean over its finished walks of a point, then over the points of the form (the two seeds). Its parts are means in the same way, from the `form` lines of the walks. The parts sum to the total.
  - `earlier` is the forms of the point's scope. unread_before and unread_so_far are unread_scope and unread_pick of features_unread_lib.py (the forms of the scope that no form of the scope reads; those, less the forms that an atom of D reads),
    and "forms that no later form reads" becomes unread_scope.
  - a read of an earlier form is a relation pick of the INIT at a key or port body whose gold option is a derived relation. Its bits are the pick's q_bits. The sets `fit` and `fit_head_key` of the source need the head needs of the port
    from the engine's trial, which the walk rows do not hold, so they are left out.
  - `earlier_gold_components` is recomputed from the scope with no engine: the components of the INIT forms in the point's scope. A pick's value is the mean over the two seeds.
Outputs (R, suffix -STEERS): init77-parts-by-form, init77-parts-table, init77-pairs-table, init77-read-counts, init77-component-picks, init77-component-summary (tsv), init77-summary.json, init77-partial.md.
"""
import argparse
import collections
import itertools
import json
import math
import os
import statistics as st
import sys

import numpy as np

sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-dag-conversion-heldout37')
import features_dag_order as D  # noqa: E402
import features_dagc_rows as RW  # noqa: E402
import features_unread_lib as UL  # noqa: E402

ME = RW.ME
SRC = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-init-residual-bits-split-74forms/'
BAR = 25.0
ARTS = ('component', 'ports', 'key labels', 'heads', 'reads')
READ_PARTS = ('relation', 'columns', 'values', 'stops', 'join mix', 'OR and ALL coins')
UNITS = ('component', 'ports', 'key labels', 'heads') + READ_PARTS
SETS = (('all', lambda r: True), ('not held', lambda r: not r['held']), ('held', lambda r: r['held']))
PORT_COINS = {'keyed', 'port: taken or skipped', 'outside: taken or skipped', 'port: empty'}
HEAD_LABELS = {'head: bound', 'head: names a key label', 'head: body reads no key', 'head: count of labels', 'head: which label'}
KEY_LABELS = {'key: count of labels', 'key: which labels'}
BODY_COINS = ('or:take', 'top:no OR', 'top:no ALL', 'or:branches', 'or:after', 'br:else-NOT coin', 'br:else-NOT pick', 'br:nest coin', 'br:nest first coin', 'br:bind quit', 'or:export coin', 'all:guard stops', 'long body', 'key partly read')
READ_SETS = ('all', 'unread_scope', 'unread_pick')


def unit(label):
    """The part of a walk label of or_q.py. A label that this does not know stops the read: no part goes unnamed."""
    if label == 'component':
        return 'component'
    if label in PORT_COINS:
        return 'ports'
    if label in HEAD_LABELS:
        return 'heads'
    if label in KEY_LABELS or label.endswith('key: which labels an OR exports'):
        return 'key labels'
    if 'atom: ' in label:
        sub = label.split('atom: ', 1)[1]
        if sub in ('relation', 'relation (op)'):
            return 'relation'
        if sub in ('column', 'fcol'):
            return 'columns'
        if sub.startswith('value') or sub == 'op':
            return 'values'
        if sub == 'column stop':
            return 'stops'
        if sub == 'join mix':
            return 'join mix'
        raise ValueError('an atom label with no part: ' + label)
    if label.endswith(('top:stop', 'br:stop', 'br:go on')):
        return 'stops'
    if label.endswith(BODY_COINS):
        return 'OR and ALL coins'
    raise ValueError('a label with no part: ' + label)


def load_jsonl(path):
    out = []
    if os.path.exists(path):
        for line in open(path):
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def quart(xs):
    xs = sorted(xs)
    if not xs:
        return (None, None, None)
    if len(xs) < 2:
        return (xs[0], xs[0], xs[0])
    q = st.quantiles(xs, n=4, method='inclusive')
    return tuple(round(x, 2) for x in q)


def fmt(x, d=1):
    return '%.*f' % (d, x) if x is not None else ''


def split_form(parts):
    d = dict.fromkeys(UNITS, 0.0)
    for k, v in parts.items():
        d[unit(k)] += v
    d['reads'] = sum(d[p] for p in READ_PARTS)
    return d


def forms_of(steers, seconds):
    """(rows, picks, points): rows are the forms of the set with bits_mean and mean parts; picks are the read picks with sets."""
    pts = {}
    for x in open(ME + 'points-init77.jsonl'):
        p = json.loads(x)
        pts[p['line']] = p
    fs = {r['key']: r for r in load_jsonl(SRC + 'form-set.jsonl')}
    progs = {r['rkey']: r for r in load_jsonl(ME + 'init77-programs.jsonl')}
    T = RW.load('init77', steers, kinds=('INIT',), parts=True, seconds=seconds)
    byp = collections.defaultdict(list)
    for w in T.walks:
        if w['ok'] and w['total'] is not None:
            byp[w['point']].append(w)
    perform = collections.defaultdict(list)
    for pt, ws in byp.items():
        parts = collections.Counter()
        for w in ws:
            parts.update(w['parts'])
        tot = sum(w['total'] for w in ws) / len(ws)
        perform[pts[pt]['rkey']].append((pt, tot, {k: v / len(ws) for k, v in parts.items()}, len(ws)))
    rows = []
    for rkey, lst in perform.items():
        f = fs[rkey]
        tot = sum(x[1] for x in lst) / len(lst)
        parts = collections.Counter()
        for x in lst:
            for k, v in x[2].items():
                parts[k] += v / len(lst)
        tree = D.parse(f['target'])
        dag = D.FormDag(f['target'])
        rows.append(dict(key=rkey, task=f['task'], form=f['form'], held=f['held'], group=f['group'], census_bits=f['census_bits'], total=tot, parts=dict(parts), component=tree[2], n_points=len(lst), n_walks=sum(x[3] for x in lst),
                         ports=sum(1 for b in dag.bodies if b.role.startswith('port')), sum_diff=round(sum(parts.values()) - tot, 3)))
    # read picks
    reads = []
    fulls = {}
    psets = {}
    for (pt, k), e in T.entries.items():
        p = pts[pt]
        if e['place'] not in ('key', 'port') or e['phase'] != 'root' or e['gold_idx'] is None:
            continue
        g = e['gold_idx']
        if e['opts'][g][1] != 'relation':
            continue
        rkey = p['rkey']
        if rkey not in fulls:
            fulls[rkey] = D.ProgramDag(progs[rkey]['lines'])
        if pt not in psets:
            psets[pt] = UL.PointSets(p['scope'], fulls[rkey], p['key'])
        sets = psets[pt].at(e['downset'])
        sets['all'] = psets[pt].scope_forms
        ders = [x[0][2:].partition('.')[0] for x in e['opts'] if x[1] == 'relation']
        gk = e['opts'][g][0][2:].partition('.')[0]
        counts = {s: sum(c in sets[s] for c in ders) for s in READ_SETS}
        reads.append(dict(key=rkey, point=pt, held=fs[rkey]['held'], place=e['place'], w=RW.weight(T, e), bits=e['q_bits'], counts=counts, log2={s: (math.log2(c) if c else None) for s, c in counts.items()}, target_in={s: gk in sets[s] and counts[s] > 0 for s in READ_SETS},
                          n_points=len(perform[rkey])))
    return rows, reads, pts, T, fs


def parts_rows(rows, splits):
    out = []
    for name, keep in SETS:
        sel = [r for r in rows if keep(r)]
        n = len(sel)
        for p in ARTS + READ_PARTS:
            xs = [splits[r['key']][p] for r in sel]
            under = sum(1 for r, x in zip(sel, xs) if r['total'] - x < BAR)
            out.append(dict(set=name, forms=n, part=p, total=round(sum(xs), 1), share=round(sum(xs) / sum(r['total'] for r in sel), 3) if n else None, median=round(st.median(xs), 2) if n else None, under=under))
    return out


def pairs_rows(rows, splits):
    out = []
    for a, b in itertools.combinations(UNITS, 2):
        row = dict(a=a, b=b)
        for name, keep in SETS:
            sel = [r for r in rows if keep(r)]
            row[name] = sum(1 for r in sel if r['total'] - splits[r['key']][a] - splits[r['key']][b] < BAR)
        out.append(row)
    for a in ('component', 'ports', 'key labels', 'heads'):
        row = dict(a=a, b='reads')
        for name, keep in SETS:
            sel = [r for r in rows if keep(r)]
            row[name] = sum(1 for r in sel if r['total'] - splits[r['key']][a] - splits[r['key']]['reads'] < BAR)
        out.append(row)
    return sorted(out, key=lambda x: -x['all'])


def read_summary(reads):
    """Per set and place: reads of an earlier form, log2 of each count, gold's target in each set, bits paid. Weighted by the pick's weight over the form's points."""
    out = []
    for name, keep in SETS:
        for place in ('key', 'port'):
            sel = [x for x in reads if keep(x) and x['place'] == place]
            if not sel:
                continue
            w = np.array([x['w'] / x['n_points'] for x in sel])
            row = dict(set=name, place=place, reads=len(sel), weight=round(float(w.sum()), 1), median_bits=round(st.median(x['bits'] for x in sel), 2), sum_bits=round(float((w * np.array([x['bits'] for x in sel])).sum()), 1))
            for m in READ_SETS:
                inn = np.array([x['target_in'][m] for x in sel])
                lg = np.array([x['log2'][m] or 0.0 for x in sel])
                bt = np.array([x['bits'] for x in sel])
                row[m + '_median_count'] = st.median(x['counts'][m] for x in sel)
                row[m + '_median_log2'] = round(float(st.median(lg)), 2)
                row[m + '_gold_in'] = int(inn.sum())
                row[m + '_sum_log2_gold_in'] = round(float((w * lg * inn).sum()), 1)
                row[m + '_sum_bits_gold_in'] = round(float((w * bt * inn).sum()), 1)
            out.append(row)
    return out


def uniform_under(rows, reads):
    """Forms under BAR where each read of an earlier form with gold's target in the set pays log2 of the set in place of its relation bits, and any other read pays as it does now."""
    byk = collections.defaultdict(list)
    for x in reads:
        byk[x['key']].append(x)
    out = {}
    for name, keep in SETS:
        row = {}
        for m in READ_SETS:
            n = 0
            for r in rows:
                if not keep(r):
                    continue
                t = r['total']
                for x in byk.get(r['key'], []):
                    if x['target_in'][m]:
                        t += (x['w'] / x['n_points']) * ((x['log2'][m] or 0) - x['bits'])
                n += t < BAR
            row[m] = n
        out[name] = row
    return out


def masked(w, gold, keep):
    return round(-math.log2(w[gold] / sum(w[c] for c in keep)), 2) if gold in keep else None


def component_rows(rows, comp_rows, pool, pts):
    by_key = {r['key']: r for r in rows}
    w = json.load(open(SRC + 'comp-priors.json'))
    earlier_by = collections.defaultdict(list)
    for p in pts.values():
        earlier_by[p['rkey']].append({D.parse(x)[2] for x in p['scope'] if x.startswith('(INIT')})
    found = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    for p in pool:
        found[p['task']][p['arm']].update(p['components'])
    out = []
    for c in comp_rows:
        if c['key'] not in by_key:
            continue
        rs = {k: v.get('status') for k, v in c['components'].items()}
        some = sorted(k for k, s in rs.items() if s in ('rows_all', 'rows_some'))
        every = sorted(k for k, s in rs.items() if s == 'rows_all')
        g = c['gold_component']
        r = by_key[c['key']]
        paid = r['parts'].get('component')
        eps = earlier_by[c['key']]
        in_pool = c['task'] in found
        pool_any = sorted(set(found[c['task']]['factored_search']) | set(found[c['task']]['control_search'])) if in_pool else None
        out.append(dict(key=c['key'], task=c['task'], held=c['held'], gold=g, gold_status=rs.get(g), listed=len(c['listed']), rows_some=len(some), rows_all=len(every), paid=paid, total=r['total'],
                        uniform_some=round(math.log2(len(some)), 2) if some else None, uniform_all=round(math.log2(len(every)), 2) if every else None, uniform_list=round(math.log2(len(c['listed'])), 2),
                        gold_in_some=g in some, gold_in_all=g in every, masked_list=masked(w, g, c['listed']), masked_some=masked(w, g, some), masked_all=masked(w, g, every),
                        earlier_count_mean=round(sum(len(e) for e in eps) / len(eps), 2), gold_in_earlier=round(sum(g in e for e in eps) / len(eps), 3), feasible_and_earlier=round(sum(len(set(some) & e) for e in eps) / len(eps), 2),
                        in_pool=in_pool, gold_in_pool=(g in pool_any) if in_pool else None, feasible_and_pool=len(set(some) & set(pool_any)) if in_pool else None))
    return out


def comp_summary(cr):
    out = []
    for name, keep in SETS:
        sel = [x for x in cr if keep(x)]
        if not sel:
            continue
        row = dict(set=name, picks=len(sel))
        for m in ('rows_some', 'rows_all'):
            row[m + '_quartiles'] = quart([x[m] for x in sel])
        row['paid_sum'] = round(sum(x['paid'] or 0 for x in sel), 1)
        row['paid_median'] = round(st.median(x['paid'] or 0 for x in sel), 2)
        for m in ('uniform_some', 'uniform_all', 'uniform_list', 'masked_some', 'masked_all'):
            row[m + '_sum'] = round(sum(x[m] or 0 for x in sel), 1)
            row[m + '_median'] = round(st.median(x[m] or 0 for x in sel), 2)
        row['under_at_0'] = sum(x['total'] - (x['paid'] or 0) < BAR for x in sel)
        for m in ('uniform_some', 'uniform_all', 'masked_some', 'masked_all'):
            row['under_' + m] = sum(x[m] is not None and x['total'] - (x['paid'] or 0) + x[m] < BAR for x in sel)
        row['gold_in_some'] = sum(x['gold_in_some'] for x in sel)
        row['gold_in_all'] = sum(x['gold_in_all'] for x in sel)
        row['gold_in_earlier'] = round(sum(x['gold_in_earlier'] for x in sel), 1)
        pooled = [x for x in sel if x['in_pool']]
        row['picks_in_pool'] = len(pooled)
        row['gold_in_pool'] = sum(bool(x['gold_in_pool']) for x in pooled)
        out.append(row)
    return out


def write_tsv(name, rows):
    if not rows:
        return
    head = list(rows[0])
    with open(ME + name, 'w') as f:
        f.write('\t'.join(head) + '\n')
        for r in rows:
            f.write('\t'.join(json.dumps(r[k]) if isinstance(r[k], (list, dict, tuple)) else str(r[k]) for k in head) + '\n')


def table(head, rows):
    out = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    out += ['| ' + ' | '.join(str(x) for x in r) + ' |' for r in rows]
    return out


def one(steers, seconds):
    rows, reads, pts, T, fs = forms_of(steers, seconds)
    comp = load_jsonl(SRC + 'component-rows.jsonl')
    pool = load_jsonl(SRC + 'pool-components.jsonl')
    splits = {r['key']: split_form(r['parts']) for r in rows}
    worst = max((abs(r['sum_diff']) for r in rows), default=None)
    sfx = '-' + steers
    write_tsv('init77-parts-by-form%s.tsv' % sfx, [dict(key=r['key'], held=r['held'], group=r['group'], gold_component=r['component'], bits_mean=round(r['total'], 3), census_bits=r['census_bits'], port_count=r['ports'], n_points=r['n_points'], n_walks=r['n_walks'], **{p: round(splits[r['key']][p], 3) for p in ARTS + READ_PARTS}) for r in rows])
    pr = parts_rows(rows, splits)
    write_tsv('init77-parts-table%s.tsv' % sfx, pr)
    pa = pairs_rows(rows, splits)
    write_tsv('init77-pairs-table%s.tsv' % sfx, pa)
    rs = read_summary(reads)
    write_tsv('init77-read-counts%s.tsv' % sfx, rs)
    uu = uniform_under(rows, reads)
    cr = component_rows(rows, comp, pool, pts)
    write_tsv('init77-component-picks%s.tsv' % sfx, cr)
    cs = comp_summary(cr)
    write_tsv('init77-component-summary%s.tsv' % sfx, cs)
    missing = sorted(set(fs) - {r['key'] for r in rows})
    summary = dict(steers=steers, forms_in_set=len(fs), forms_with_rows=len(rows), forms_missing=missing, walks=sum(r['n_walks'] for r in rows), held_rows=sum(r['held'] for r in rows), parts_sum_worst_gap=worst, read_picks=len(reads), uniform_relation_under=uu, parts=pr, pairs_top=pa[:12],
                   read_counts=rs, component_summary=cs, component_rows=len(cr), under_now={n: sum(r['total'] < BAR for r in rows if k(r)) for n, k in SETS}, mean_bits={n: round(float(np.mean([r['total'] for r in rows if k(r)])), 2) for n, k in SETS if any(k(r) for r in rows)},
                   gold_out_some=[(x['key'], x['gold'], x['gold_status']) for x in cr if not x['gold_in_some']], files=T.files)
    json.dump(summary, open(ME + 'init77-summary%s.json' % sfx, 'w'), indent=1, default=str)
    md = ['# INIT residual bits by part, steers %s' % steers, '', 'Forms with rows: %d of %d (missing: %s). Walks %d. The parts sum to each form\'s bits_mean within %s bits. Form bits are means over orders and over the two seeds of the cut scope.' % (len(rows), len(fs), missing[:6], summary['walks'], worst), '']
    md += ['## Bits by part', '', 'Each cell: total bits, median per form, forms under 25 with the part at 0 bits.', '']
    by = {(x['set'], x['part']): x for x in pr}
    body = []
    for p in ARTS + READ_PARTS:
        cells = [('  ' if p in READ_PARTS else '') + p]
        for s, _ in SETS:
            x = by[s, p]
            cells.append('%s / %s / %d of %d' % (fmt(x['total']), fmt(x['median'], 2), x['under'], x['forms']))
        body.append(cells)
    md += table(['Part'] + [s for s, _ in SETS], body)
    md += ['', '## Pairs at 0 bits, the first 12', '']
    md += table(['Pair'] + [s for s, _ in SETS], [['%s + %s' % (x['a'], x['b'])] + [x[s] for s, _ in SETS] for x in pa[:12]])
    md += ['', '## Reads of an earlier form', '', 'Scope = the forms of the cut scope. Cells: median count, median log2, gold in.', '']
    md += table(['Set, place', 'Reads', 'Weight', 'Median bits'] + list(READ_SETS), [['%s, %s' % (x['set'], x['place']), x['reads'], x['weight'], x['median_bits']] + ['%s, %s, %s' % (x[m + '_median_count'], x[m + '_median_log2'], x[m + '_gold_in']) for m in READ_SETS] for x in rs])
    md += ['', 'Forms under 25 with each read of an earlier form paying log2 of the set where gold\'s target is in the set: `%s`.' % json.dumps(uu), '']
    md += ['## Component pick', '']
    md += table(['Set', 'Picks', 'Rows on some input: Q1, median, Q3', 'Paid: sum, median', 'Uniform some: sum', 'Gold inside: some, every', 'Gold in earlier (scope) forms', 'Picks in the pool run, gold there', 'Under 25 at 0 / uniform some / priors some'],
                [[x['set'], x['picks'], x['rows_some_quartiles'], '%s, %s' % (x['paid_sum'], x['paid_median']), x['uniform_some_sum'], '%s, %s' % (x['gold_in_some'], x['gold_in_all']), x['gold_in_earlier'], '%s, %s' % (x['picks_in_pool'], x['gold_in_pool']),
                  '%s / %s / %s' % (x['under_at_0'], x['under_uniform_some'], x['under_masked_some'])] for x in cs])
    open(ME + 'init77-partial%s.md' % sfx, 'w').write('\n'.join(md) + '\n')
    print('\n'.join(md))
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--seconds', type=float, default=20)
    ap.add_argument('--steers', default='both')
    a = ap.parse_args()
    for s in (('off', 'live') if a.steers == 'both' else (a.steers,)):
        one(s, a.seconds)


if __name__ == '__main__':
    main()
