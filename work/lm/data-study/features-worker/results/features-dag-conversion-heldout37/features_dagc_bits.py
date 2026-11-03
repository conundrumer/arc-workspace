#!/usr/bin/env python
"""Form bits of the walks (item 8): bits_mean, bits_sd, log2_valid and bits_set per form and scope, under each steer mode.

  features_dagc_env.sh 1 features_dagc_bits.py [--parts P,P] [--census-check] [--out form-bits-dag.tsv]

Streams the `form` lines of walks/*.jsonl.zst (the pick rows are skipped without parsing), so it reads whatever walks exist now and takes seconds. A point is one form on one scope. Per point:
  bits_mean   mean of the walk total over its finished walks (the valid orders it walked)
  bits_sd     sd of the same, 0 for one walk
  log2_valid  log2(n_orders * accepted / tried * walked share), with n_orders, tried, accepted from orders-*.jsonl, and the walked share = finished walks / (finished + dropped walks)
  bits_set    bits_mean - log2_valid, an upper bound on -log2 of the sum of the orders' chances
Writes form-bits-dag.tsv (one row per point and steer mode), form-parts-dag.tsv (the mean of each part over a point's walks), and form-bits-dag-summary.txt: forms under 25 bits by bits_mean and by bits_set, by kind and
scope rule and steer mode, with the mean of log2_valid, on forms (a form's points, its seeds of `cut`, are averaged). Checks, printed and appended to the summary: the parts sum to the total on every walk, and with
--census-check the bits_mean of `held-parents` under `live` against the census's random mean and sd (forms with no OR).
"""
import argparse
import collections
import glob
import io
import json
import math
import os
import statistics
import sys

import zstandard

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features_dagc_lib as L  # noqa: E402

ME = os.path.dirname(os.path.abspath(__file__)) + '/'
CENSUS = L.SCRATCH / 'records/features-dag-order-census-heldout37'
SOURCE = {'held-parents': 'held', 'held-cut': 'held', 'dev-cut': 'dev', 'held-pool': 'pass1', 'held-wide': 'pass1', 'test-parents': 'fit', 'test-cut': 'fit', 'fit-cut': 'fit', 'fit-pool': 'fit', 'init77': 'init77'}


def form_lines(path):
    with open(path, 'rb') as f:
        try:
            for line in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True), encoding='utf8'):
                if not line.endswith('\n'):
                    return
                if line.startswith('{"rec": "form"'):
                    yield json.loads(line)
        except zstandard.ZstdError:
            return


def load_orders(source):
    out = {}
    for p in sorted(glob.glob(ME + 'orders-%s-shard*.jsonl' % source)):
        for line in open(p):
            r = json.loads(line)
            out[r['task'], r['line_id']] = r
    return out


def collect(parts):
    """{(steers, part): {point: dict(task, line_id, kind, form, scope_id, nscope, totals, parts, drops)}} and the walks whose parts do not sum to the total."""
    got, bad, nwalks = {}, [], 0
    for path in sorted(glob.glob(ME + 'walks/*.jsonl.zst')):
        base = os.path.basename(path)
        part = base.split('-off-')[0].split('-live-')[0]
        steers = 'off' if '-off-' in base else 'live'
        if parts and part not in parts:
            continue
        for fm in form_lines(path):
            nwalks += 1
            pt = got.setdefault((steers, part), {}).setdefault(fm['point'], dict(task=fm['task'], line_id=fm['line_id'], kind=fm['kind'], form=fm['form'], scope_id=fm['scope_id'], nscope=fm['nscope'], totals=[], parts=collections.defaultdict(list), drops=0))
            if not fm['ok']:
                pt['drops'] += 1
                continue
            pt['totals'].append(fm['total'])
            for k, v in (fm['parts'] or {}).items():
                pt['parts'][k].append(v)
            if fm['parts'] is not None and abs(sum(fm['parts'].values()) - fm['total']) > 0.02:
                bad.append((base, fm['task'], fm['line_id'], fm['total'], sum(fm['parts'].values())))
    return got, bad, nwalks


def point_rows(got, orders_by_source):
    rows = []
    for (steers, part), pts in sorted(got.items()):
        orders = orders_by_source.setdefault(SOURCE[part], load_orders(SOURCE[part]))
        for point, pt in sorted(pts.items()):
            t = pt['totals']
            if not t:
                continue
            o = orders.get((pt['task'], pt['line_id']))
            n_orders, tried, accepted, law = (o['n_orders'], o['tried'], o['accepted'], o['law']) if o else (None, None, None, None)
            walked, dropped = len(t), pt['drops']
            mean = sum(t) / walked
            sd = statistics.pstdev(t) if walked > 1 else 0.0
            if n_orders and tried and accepted:
                lv = math.log2(n_orders * accepted / tried * walked / (walked + dropped))
            else:
                lv = float('nan')
            rows.append(dict(steers=steers, part=part, point=point, task=pt['task'], line_id=pt['line_id'], form=pt['form'], kind=pt['kind'], scope_rule=part.split('-')[-1] if part.split('-')[-1] in ('parents', 'cut', 'pool', 'wide') else ('cut' if part == 'init77' else part),
                             scope_id=pt['scope_id'], nscope=pt['nscope'], n_orders=n_orders, tried=tried, accepted=accepted, walked=walked, dropped=dropped, bits_mean=mean, bits_sd=sd, log2_valid=lv, bits_set=mean - lv, law=law,
                             has_or=bool(o and '(OR' in o['orders'][0]) if o and o['orders'] else None))
    return rows


COLS = ['steers', 'part', 'task', 'line_id', 'form', 'kind', 'scope_rule', 'scope_id', 'nscope', 'n_orders', 'tried', 'accepted', 'walked', 'dropped', 'bits_mean', 'bits_sd', 'log2_valid', 'bits_set', 'law']


def summary(rows):
    out = ['forms under 25 bits, by bits_mean and by bits_set, on forms (the points of a form, its seeds, are averaged). mean log2_valid over the same forms.', '',
           'steers\tpart\tkind\tforms\tunder25_bits_mean\tunder25_bits_set\tmean_bits_mean\tmean_log2_valid\tmean_bits_set']
    groups = collections.defaultdict(dict)
    for r in rows:
        groups[(r['steers'], r['part'], r['kind'])].setdefault((r['task'], r['line_id']), []).append(r)
    for (steers, part, kind), forms in sorted(groups.items()):
        bm = [sum(x['bits_mean'] for x in v) / len(v) for v in forms.values()]
        lv = [sum(x['log2_valid'] for x in v) / len(v) for v in forms.values()]
        bs = [sum(x['bits_set'] for x in v) / len(v) for v in forms.values()]
        ok = [i for i, x in enumerate(lv) if not math.isnan(x)]
        out.append('%s\t%s\t%s\t%d\t%d\t%d\t%.2f\t%.2f\t%.2f' % (steers, part, kind, len(bm), sum(x < 25 for x in bm), sum(bs[i] < 25 for i in ok), sum(bm) / len(bm), sum(lv[i] for i in ok) / max(len(ok), 1), sum(bs[i] for i in ok) / max(len(ok), 1)))
    return out


def census_check(rows):
    """held-parents under live: bits_mean against the census's random mean and sd (scope parents), on forms with no OR."""
    cen = {}
    for line in open(CENSUS / 'form-bits-join.tsv'):
        f = line.rstrip('\n').split('\t')
        if f[0] == 'task' or f[3] != 'parents' or not f[9]:
            continue
        cen[f[0], int(f[1])] = (float(f[9]), float(f[10]) if f[10] else 0.0, float(f[11]), float(f[12]), int(f[13]))
    mine = [r for r in rows if r['steers'] == 'live' and r['part'] == 'held-parents' and r['has_or'] is False and (r['task'], r['line_id']) in cen]
    out = ['census check: held-parents under live, forms with no OR, %d forms in both' % len(mine)]
    for kind in ('RULE', 'DET', 'INIT', 'all'):
        m = [r for r in mine if kind in (r['kind'], 'all')]
        if not m:
            continue
        n1 = sum(abs(r['bits_mean'] - cen[r['task'], r['line_id']][0]) <= max(cen[r['task'], r['line_id']][1], 1e-9) for r in m)
        n2 = sum(abs(r['bits_mean'] - cen[r['task'], r['line_id']][0]) <= 2 * cen[r['task'], r['line_id']][1] + 0.05 for r in m)
        n3 = sum(cen[r['task'], r['line_id']][2] - 0.05 <= r['bits_mean'] <= cen[r['task'], r['line_id']][3] + 0.05 for r in m)
        d = [r['bits_mean'] - cen[r['task'], r['line_id']][0] for r in m]
        out.append('  %s: %d forms, within 1 sd of the census mean %d, within 2 sd %d, within census min..max %d, mean difference %+.2f bits, mean census sd %.2f' % (kind, len(m), n1, n2, n3, sum(d) / len(d), sum(cen[r['task'], r['line_id']][1] for r in m) / len(m)))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--parts', default='')
    ap.add_argument('--census-check', action='store_true')
    ap.add_argument('--out', default=ME + 'form-bits-dag.tsv')
    a = ap.parse_args()
    parts = set(filter(None, a.parts.split(',')))
    got, bad, nwalks = collect(parts)
    rows = point_rows(got, {})
    with open(a.out, 'w') as f:
        f.write('\t'.join(COLS) + '\n')
        for r in rows:
            f.write('\t'.join('' if r[c] is None else ('%.3f' % r[c] if isinstance(r[c], float) else str(r[c])) for c in COLS) + '\n')
    with open(a.out.replace('form-bits-dag', 'form-parts-dag'), 'w') as f:
        f.write('steers\tpart\ttask\tline_id\tform\tscope_id\tpart_name\tmean_bits\twalks\n')
        for (steers, part), pts in sorted(got.items()):
            for point, pt in sorted(pts.items()):
                for k, v in sorted(pt['parts'].items()):
                    f.write('%s\t%s\t%s\t%d\t%s\t%s\t%s\t%.3f\t%d\n' % (steers, part, pt['task'], pt['line_id'], pt['form'], pt['scope_id'], k, sum(v) / len(v), len(pt['totals'])))
    lines = ['%d walks read, %d points with a finished walk' % (nwalks, len(rows)), 'parts sum to the total (within .02 bits) on every finished walk: %s (%d walks off)' % (not bad, len(bad)), *[str(x) for x in bad[:5]], ''] + summary(rows)
    if a.census_check:
        lines += [''] + census_check(rows)
    open(a.out.replace('.tsv', '-summary.txt'), 'w').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
