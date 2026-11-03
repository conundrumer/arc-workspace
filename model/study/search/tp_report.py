#!/usr/bin/env python3
"""Extensional match on split forms, plain against prune, from the result files of step4/tp.py. It reads partial output.

  python3 tp_report.py OUT_TP [POINTS.json] [--every SECONDS]

OUT_TP holds plain/ and prune/, each with <key>.<variant>.json. Recall counts test cases with a table match within the budget, and the
stop isn't required. Paired counts use the forms with a valid result in both arms. A job with `error` had no table of gold, so it is left
out of the denominator and listed. With POINTS.json, forms are also given by role: branch, subjoin, join.
"""
import argparse
import collections
import glob
import json
import os
import statistics
import time

BUDGETS = 15, 30, 60


def load(folder):
    out = {}
    for path in glob.glob(folder + '/*.json'):
        try:
            r = json.load(open(path))
        except ValueError:  # a file that is being written
            continue
        out[r['key'], r['variant']] = r
    return out


def within(r, t):
    return bool(r['hit'] and r['hit_cpu'] <= t)


def recall(rows, label):
    print('  %-22s n %3d  ' % (label, len(rows)) + '  '.join('%d s: %d' % (t, sum(within(r, t) for r in rows)) for t in BUDGETS))


def paired(p, q, keys, label):
    pl = [p[k] for k in keys]
    pr = [q[k] for k in keys]
    print(label)
    recall(pl, 'plain')
    recall(pr, 'prune')
    for t in BUDGETS:
        a = {k for k in keys if within(p[k], t)}
        b = {k for k in keys if within(q[k], t)}
        print('    at %2d CPU s: both %d, plain alone %d, prune alone %d, neither %d' % (t, len(a & b), len(a - b), len(b - a), len(keys) - len(a | b)))
    both = [k for k in keys if p[k]['hit'] and q[k]['hit']]
    if both:
        ratio = [q[k]['hit_cpu'] / max(p[k]['hit_cpu'], 1e-3) for k in both]
        print('    CPU to the match, prune / plain, on %d forms that both hit: median %.2f, prune faster on %d, slower on %d' % (
            len(both), statistics.median(ratio), sum(x < 1 for x in ratio), sum(x > 1 for x in ratio)))
        print('    median CPU to the match: plain %.2f s, prune %.2f s' % (statistics.median(p[k]['hit_cpu'] for k in both), statistics.median(q[k]['hit_cpu'] for k in both)))
    tables = sum(q[k].get('tables') or 0 for k in keys)
    print('    prefix tables pruned: %d of %d' % (sum(q[k].get('pruned') or 0 for k in keys), tables))


def report(a):
    p, q = load(a.out + '/plain'), load(a.out + '/prune')
    roles = {}
    if a.points:
        for rec in json.load(open(a.points)):
            for i, role in enumerate(rec.get('roles', ())):
                roles[rec['key'], 'f%d' % i] = role
    bad = sorted(k for k, r in {**p, **q}.items() if 'error' in r)
    forms = [k for k in p if k[1] != 'whole' and 'error' not in p[k]]
    whole = [k for k in p if k[1] == 'whole' and 'error' not in p[k]]
    keys = sorted(k for k in forms if k in q and 'error' not in q[k])
    print('files: plain %d, prune %d; no table of gold %d: %s' % (len(p), len(q), len(bad), ' '.join('%s/%s' % k for k in bad[:12])))
    print('whole OR clauses, plain only:')
    recall([p[k] for k in whole], 'plain')
    paired(p, q, keys, 'split forms, paired (%d):' % len(keys))
    if roles:
        by = collections.defaultdict(list)
        for k in keys:
            by[roles.get(k, '?')].append(k)
        for role, ks in sorted(by.items()):
            print('role %s:' % role)
            recall([p[k] for k in ks], 'plain')
            recall([q[k] for k in ks], 'prune')
    tasks = {k[0].split('|')[0] for k in keys}
    print('tasks in the paired set: %d' % len(tasks))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('points', nargs='?')
    ap.add_argument('--every', type=float, default=0)
    a = ap.parse_args()
    a.out = os.path.abspath(a.out)
    while True:
        report(a)
        if not a.every:
            return
        time.sleep(a.every)


if __name__ == '__main__':
    main()
