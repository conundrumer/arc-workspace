#!/usr/bin/env python3
"""Reads the records of dag_bits.py, partial or whole. Plain python3, no engine.

  python3 dag_bits_read.py OUT_DIR [--old-forms FORMS_JSONL] [--write-forms NEW_FORMS_JSONL] [--write-worst NEW_JSONL]

Reads every orders-shard*.jsonl of OUT_DIR and leaves out a line that doesn't parse (a broken last line of a shard that is still running). Prints how many
forms are done of the manifest's total, the forms with an error, a table of the bits of the written order (`orders.written`) and of the sum over orders (`total`)
for all forms, each kind, compound or not, and kind by compound, a table of the order counts, and a table of the estimated forms.
--write-forms writes a forms file of one row per form (task, text, bits, bits_written, kind, exact, context, source), and refuses a path that exists.
--old-forms is read to print the join with it: its rows that this run has no row for, and the median of new bits minus old bits.
--write-worst writes one row per task: task, forms, worst, sum, undrawn, and the `after` block that gold_heldout_ramp_pass1.py reads.
"""
import argparse
import collections
import glob
import json
import os
import statistics
import sys

COMPOUND_NOTE = 'compound: the text holds (OR , (ALL  or (IF '


def records_of(out_dir):
    out = []
    for path in sorted(glob.glob(os.path.join(out_dir, 'orders-shard*.jsonl'))):
        with open(path) as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    return out


def med(xs):
    return statistics.median(xs) if xs else None


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def fmt(x, w=7):
    return '%*s' % (w, '-') if x is None else '%*.2f' % (w, x)


def stats(rows, pairs=False):
    """One row of the table for the records in rows."""
    live = [r for r in rows if r.get('valid') and r.get('total') is not None]
    wr = [r['orders']['written'] for r in live if r['orders'].get('written') is not None]
    tot = [r['total'] for r in live]
    gap = [r['orders']['written'] - r['total'] for r in live if r['orders'].get('written') is not None]
    out = dict(forms=len(rows), valid=len(live), wr_med=med(wr), wr_mean=mean(wr), tot_med=med(tot), tot_mean=mean(tot), gap_med=med(gap), gap_mean=mean(gap),
               gap1=None if not gap else sum(g > 1 for g in gap) / len(gap))
    for n in (12, 18, 24):
        out['wr%d' % n] = sum(x <= n for x in wr)
        out['tot%d' % n] = sum(x <= n for x in tot)
    out['exact'] = sum(1 for r in live if r['orders'].get('exact'))
    out['est'] = sum(1 for r in live if not r['orders'].get('exact'))
    if pairs:
        d = [r['other_context_written'] - r['orders']['written'] for r in live if r.get('other_context_written') is not None and r['orders'].get('written') is not None]
        out.update(oc_n=len(d), oc_med=med(d), oc_mean=mean(d), oc_gap1=None if not d else sum(abs(x) > 1 for x in d) / len(d))
    return out


HEAD = '%-22s %5s %5s | %7s %7s | %7s %7s | %7s %7s %6s | %4s %4s %4s | %4s %4s %4s | %5s %5s'


def table(groups):
    print(HEAD % ('group', 'forms', 'valid', 'wr med', 'wr mean', 'tot med', 'tot mean', 'gap med', 'gap mean', '>1bit', 'w12', 'w18', 'w24', 't12', 't18', 't24', 'exact', 'est'))
    for name, rows in groups:
        s = stats(rows)
        print('%-22s %5d %5d | %s %s | %s %s | %s %s %s | %4d %4d %4d | %4d %4d %4d | %5d %5d' % (
            name, s['forms'], s['valid'], fmt(s['wr_med']), fmt(s['wr_mean']), fmt(s['tot_med']), fmt(s['tot_mean']), fmt(s['gap_med']), fmt(s['gap_mean']),
            '%6s' % ('-' if s['gap1'] is None else '%.0f%%' % (100 * s['gap1'])), s['wr12'], s['wr18'], s['wr24'], s['tot12'], s['tot18'], s['tot24'], s['exact'], s['est']))


def groups_of(rows):
    out = [('all', rows)]
    kinds = sorted({r['kind'] for r in rows})
    out += [(k, [r for r in rows if r['kind'] == k]) for k in kinds]
    out += [('compound', [r for r in rows if r.get('compound')]), ('not compound', [r for r in rows if not r.get('compound')])]
    out += [('%s %s' % (k, 'compound' if c else 'plain'), [r for r in rows if r['kind'] == k and bool(r.get('compound')) == c]) for k in kinds for c in (True, False) if any(r['kind'] == k and bool(r.get('compound')) == c for r in rows)]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out_dir')
    ap.add_argument('--old-forms')
    ap.add_argument('--write-forms')
    ap.add_argument('--write-worst')
    a = ap.parse_args()
    manifest = json.load(open(os.path.join(a.out_dir, 'manifest.json')))
    recs = records_of(a.out_dir)
    seen, uniq = set(), []
    for r in recs:  # a form that two shards both wrote counts once, the first
        if (r['task'], r['line']) not in seen:
            seen.add((r['task'], r['line']))
            uniq.append(r)
    recs = uniq
    total = sum(v['forms'] for v in manifest['task_set'].values())
    print('%s\ncontext %s  priors %s  gold %s  budget %s' % (a.out_dir, manifest['arm'], manifest['priors']['sha256'][:16], manifest['gold']['revision'], manifest['budget']))
    print('done %d of %d forms (%d skipped as CHOOSE, %d reused)' % (len(recs), total, sum(1 for r in recs if r.get('skip')), sum(1 for r in recs if r.get('reused'))))
    errs = [r for r in recs if 'error' in r]
    print('forms with an error: %d' % len(errs))
    for r in errs:
        print('  %s:%d %s %s' % (r['task'], r['line'], r['kind'], r['error'][:160]))
    rows = [r for r in recs if not r.get('skip') and 'error' not in r]
    print('\nbits of the written order (wr), of the sum over orders (tot), and wr minus tot (gap), over valid records; wN and tN count forms within N bits; %s' % COMPOUND_NOTE)
    table(groups_of(rows))
    pairs = [r for r in rows if r.get('valid') and r.get('other_context_written') is not None and r['orders'].get('written') is not None]
    d = [r['other_context_written'] - r['orders']['written'] for r in pairs]
    print('\nother_context_written minus written (the written order over every written line before it, against the written order over the canonical parents): %d forms with both; median %s, mean %s, %d differ by more than 1 bit' % (
        len(pairs), fmt(med(d)).strip(), fmt(mean(d)).strip(), sum(abs(x) > 1 for x in d)))
    for name, rs in groups_of(pairs)[:1] + [g for g in groups_of(pairs)[1:] if g[0] in sorted({r['kind'] for r in pairs})]:
        dd = [r['other_context_written'] - r['orders']['written'] for r in rs]
        print('  %-14s %5d  median %s  mean %s' % (name, len(rs), fmt(med(dd)), fmt(mean(dd))))
    print('\nforms with no valid order: %d of %d' % (sum(1 for r in rows if not r.get('valid')), len(rows)))

    ords = [r for r in rows if r.get('orders')]
    walked, valid = [r['orders'].get('walked') or 0 for r in ords], [r['orders'].get('valid') or 0 for r in ords]
    refused, why = collections.Counter(), collections.Counter()
    for r in ords:
        for k, v in (r['orders'].get('refused') or {}).items():
            refused[k] += v
    print('\norder counts, over %d forms: walked %d (median %s, max %d), valid %d, rules learned %d, text_differs %d (in %d forms), only_written %d forms' % (
        len(ords), sum(walked), med(walked), max(walked, default=0), sum(valid), sum(r['orders'].get('rules') or 0 for r in ords), sum(r['orders'].get('text_differs') or 0 for r in ords),
        sum(1 for r in ords if r['orders'].get('text_differs')), sum(1 for r in ords if r['orders'].get('only_written'))))
    print('  refused by reason:')
    for k, v in refused.most_common():
        print('    %6d  %s' % (v, k))
    secs = [r['seconds'] for r in rows if 'seconds' in r and not r.get('reused')]
    if secs:
        print('  seconds a form: median %.2f, mean %.2f, max %.1f, sum %.0f (%d forms)' % (med(secs), mean(secs), max(secs), sum(secs), len(secs)))
    est = [r for r in rows if r.get('orders') and not r['orders'].get('exact')]
    print('\nestimated or stopped forms: %d; forms with total over orders.written: %d; with no valid order: %d' % (
        len(est), sum(1 for r in rows if r.get('valid') and r['orders'].get('written') is not None and r['total'] > r['orders']['written'] + 0.006), sum(1 for r in est if not r.get('valid'))))
    print('%-10s %4s %-9s %12s %7s %5s %7s %9s %9s %7s %7s %6s' % ('task', 'line', 'kind', 'orders', 'walked', 'valid', 'total', 'walked_b', 'tight', 'se_bits', 'ess', 'only_w'))
    for r in sorted(est, key=lambda r: (r['task'], r['line'])):
        o = r['orders']
        print('%-10s %4d %-9s %12s %7s %5s %7s %9s %9s %7s %7s %6s' % (r['task'], r['line'], r['kind'], '%.4g' % o['orders'] if o.get('orders') is not None else '-', o.get('walked'), o.get('valid'),
                                                                        r.get('total'), o.get('walked_bits'), None if o.get('tight') is None else round(o['tight'], 2), o.get('se_bits'), o.get('ess'), o.get('only_written')))

    order = []
    for path in manifest['task_set']:
        if os.path.exists(path):
            order += [t for t in open(path).read().split() if t not in order]
    rank = {t: i for i, t in enumerate(order)}
    ordered = sorted(recs, key=lambda r: (rank.get(r['task'], len(rank)), r['line']))
    if a.write_forms:
        new = {}
        with open(a.write_forms, 'x') as f:
            for r in ordered:
                bits = r['total'] if r.get('valid') and not r.get('skip') and r.get('total') is not None else None
                row = dict(task=r['task'], text=r.get('target'), bits=bits, bits_written=(r.get('orders') or {}).get('written'), kind=r['kind'], exact=(r.get('orders') or {}).get('exact'), context=r.get('context'), source=r.get('source'))
                new[r['task'], row['text']] = bits
                f.write(json.dumps(row) + '\n')
        print('\nwrote %d rows to %s' % (len(ordered), a.write_forms))
        if a.old_forms:
            old = {}
            for line in open(a.old_forms):
                x = json.loads(line)
                old[x['task'], x['text']] = x.get('bits')
            lost = [k for k in old if k not in new]
            diff = [new[k] - old[k] for k in old if k in new and new[k] is not None and old[k] is not None]
            print('join with %s: %d old rows, %d with no row here; new minus old bits: median %s over %d forms' % (a.old_forms, len(old), len(lost), fmt(med(diff)).strip(), len(diff)))
            for k in lost[:20]:
                print('  no row for %s %s' % (k[0], k[1][:100]))
    if a.write_worst:
        by = collections.OrderedDict()
        for r in ordered:
            by.setdefault(r['task'], []).append(r)
        with open(a.write_worst, 'x') as f:
            for t, rs in by.items():
                bits = ['none' if r.get('skip') else (r['total'] if r.get('valid') and r.get('total') is not None else None) for r in rs]
                got = [b for b in bits if isinstance(b, (int, float))]
                after = dict(worst=max(got, default=0), bits=bits, undrawn=sum(b is None for b in bits), sum=round(sum(got), 2))
                f.write(json.dumps(dict(task=t, forms=len(rs), worst=after['worst'], sum=after['sum'], undrawn=after['undrawn'], after=after)) + '\n')
        print('wrote %d tasks to %s' % (len(by), a.write_worst))


if __name__ == '__main__':
    main()
