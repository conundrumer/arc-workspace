#!/usr/bin/env python
"""Report of tp_held.py's result files, partial or whole.

  python3 tp_held_report.py [OUT_DIR ...]        (default: out/heldtp; each DIR holds search/ and draw/)

Counts the cases that have a valid result in both arms (no `error`). For each of 15, 30 and 60 CPU s (up to the least budget of those jobs), prints the
recall by table (extensional match) and by text (syntactic match): the count for each arm, for both, for each arm alone and for neither, of the cases.
A match counts at T when its CPU s is at most T. Then the cases left out and why, and the median gap in CPU s from the table match to the end of the
clause (text match) on the cases that have both, per arm.
"""
import collections
import glob
import json
import os
import statistics
import sys

ARMS = ('search', 'draw')
TIMES = (15, 30, 60)


def load(dirs):
    rows = collections.defaultdict(dict)
    for d in dirs:
        for arm in ARMS:
            for f in sorted(glob.glob(os.path.join(d, arm, '*.json'))):
                try:
                    v = json.load(open(f))
                except ValueError:
                    continue
                rows[(v['task'], v['case'], tuple(v['point']))][arm] = v
    return rows


def reached(v, kind, t):
    """Whether the job matched by `kind` ('table' or 'text') within t CPU s."""
    if kind == 'table':
        return bool(v.get('hit')) and v['hit_cpu'] <= t
    return bool(v.get('text_hit')) and v['text_cpu'] <= t


def table(rows, kind, times):
    print('  by %s%s' % (kind, ' (extensional)' if kind == 'table' else ' (syntactic)'))
    print('    %-8s %-10s %-10s %-8s %-12s %-12s %-8s' % ('CPU s', 'search', 'draw', 'both', 'search alone', 'draw alone', 'neither'))
    n = len(rows)
    for t in times:
        s = [reached(r['search'], kind, t) for r in rows]
        d = [reached(r['draw'], kind, t) for r in rows]
        print('    %-8d %-10s %-10s %-8d %-12d %-12d %-8d' % (t, '%d/%d' % (sum(s), n), '%d/%d' % (sum(d), n), sum(a and b for a, b in zip(s, d)),
                                                              sum(a and not b for a, b in zip(s, d)), sum(b and not a for a, b in zip(s, d)), sum(not a and not b for a, b in zip(s, d))))


def main():
    dirs = sys.argv[1:] or ['out/heldtp']
    rows = load(dirs)
    both = {k: v for k, v in rows.items() if len(v) == 2 and not any('error' in x for x in v.values())}
    print('%d cases with a result in some arm, %d valid in both arms' % (len(rows), len(both)))
    out = collections.defaultdict(list)
    for k, v in sorted(rows.items()):
        if k in both:
            continue
        if len(v) < 2:
            out['no result yet in arm %s' % [a for a in ARMS if a not in v][0]].append(k[0])
        for why in sorted({x['error'].split(':')[0][:60] for x in v.values() if 'error' in x}):
            out[why].append(k[0])
    if out:
        print('left out:')
        for why, ks in sorted(out.items()):
            print('  %3d  %s  (%s)' % (len(ks), why, ' '.join(ks)))
    if not both:
        return
    vs = list(both.values())
    budget = min(x[arm]['budget'] for x in vs for arm in ARMS)
    times = [t for t in TIMES if t <= budget] or [int(budget)]
    print('budget %g CPU s of process_time per job, from after the session and the sampler load' % budget)
    print('recall at T of %d cases' % len(vs))
    for kind in ('table', 'text'):
        table(vs, kind, times)
    for arm in ARMS:
        x = [v[arm] for v in vs]
        cpu = sum(y['cpu'] for y in x)
        print('  %-6s proposals per CPU s %.1f, clauses per CPU s %.1f, peak RSS MiB %d' % (arm, sum(y['tried'] for y in x) / max(cpu, 1e-9), sum(y['clauses'] for y in x) / max(cpu, 1e-9),
                                                                                           max(y.get('maxrss_mib', 0) for y in x)))
    print('  text match with no table match (should be none): %s' % {arm: sum(bool(v[arm].get('text_hit')) and not v[arm].get('hit') for v in vs) for arm in ARMS})
    print('gap from the table match to the end of the clause, on cases with both')
    for arm in ARMS:
        g = [(v[arm]['text_cpu'] - v[arm]['hit_cpu'], v[arm]['text_tried'] - v[arm]['hit_tried']) for v in vs if v[arm].get('hit') and v[arm].get('text_hit')]
        if g:
            print('  %-6s %d cases: median %.2f CPU s (%.0f proposals), largest %.2f CPU s' % (arm, len(g), statistics.median(x for x, _ in g), statistics.median(y for _, y in g), max(x for x, _ in g)))
        else:
            print('  %-6s no case has both' % arm)


if __name__ == '__main__':
    main()
