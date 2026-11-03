#!/usr/bin/env python
"""Report of tp_end.py's result files, partial or whole, by the role of the target form.

  python3 tp_end_report.py [--points step4/POINTS.json] [OUT_DIR ...]        (default OUT_DIR: out/splitend; each DIR holds search/ and draw/)

The role of a result is that of the form in step4/POINTS.json: case `p<N>_whole` is `whole`, and case `p<N>_f<J>` has the J-th role of the point whose
clause index is N in the task (`branch`, `subjoin` or `join`). For each role and each arm that has results, prints the recall at 15, 30 and 60 CPU s (up
to the least budget of those jobs) by the end table (extensional match, the stop in it) and by text (syntactic match): the count of the cases with a
valid result (no `error`). A match counts at T when its CPU s is at most T. With both arms, it prints beside them the paired counts (both, search alone,
draw alone, neither) of the cases valid in both arms. Then the cases left out, by reason, and the cases whose forced clause had no finished table.
"""
import argparse
import collections
import glob
import json
import os
import sys

ARMS = ('search', 'draw')
TIMES = (15, 30, 60)
ROLES = ('branch', 'subjoin', 'join', 'whole')


def roles_of(points):
    """{(task, case): role} of the jobs of POINTS.json."""
    out = {}
    for rec in json.load(open(points)):
        if not rec['split']:
            continue
        out[(rec['task'], 'p%d_whole' % rec['p'])] = 'whole'
        for j, r in enumerate(rec['roles']):
            out[(rec['task'], 'p%d_f%d' % (rec['p'], j))] = r
    return out


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
    """Whether the job matched by `kind` ('end' or 'text') within t CPU s."""
    if kind == 'end':
        return bool(v.get('hit')) and v['hit_cpu'] <= t
    return bool(v.get('text_hit')) and v['text_cpu'] <= t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='*', default=['out/splitend'])
    ap.add_argument('--points', default='step4/POINTS.json')
    a = ap.parse_args()
    roles = roles_of(a.points)
    rows = load(a.dirs)
    print('%d cases with a result in some arm' % len(rows))
    valid = {arm: {k: v[arm] for k, v in rows.items() if arm in v and 'error' not in v[arm]} for arm in ARMS}
    left = collections.defaultdict(list)
    for k, v in sorted(rows.items()):
        for arm, x in v.items():
            if 'error' in x:
                left['%s: %s' % (arm, x['error'].split(':')[0][:70])].append(k[0])
    if left:
        print('left out:')
        for why, ks in sorted(left.items()):
            print('  %3d  %s  (%s)' % (len(ks), why, ' '.join(ks)))
    unf = [k[0] for k, v in rows.items() for x in v.values() if 'error' not in x and 'forced_ok' in x and x['forced_ok'] is None]
    if unf:
        print('forced clause with no finished table (no key check, search ran): %d jobs' % len(unf))
    present = [arm for arm in ARMS if valid[arm]]
    if not present:
        return
    budget = min(x['budget'] for arm in present for x in valid[arm].values())
    times = [t for t in TIMES if t <= budget] or [int(budget)]
    print('budget %g CPU s of process_time per job, from after the session and the sampler load' % budget)
    unknown = sorted({k[:2] for arm in present for k in valid[arm] if (k[0], k[1]) not in roles})
    if unknown:
        print('no role in POINTS.json for: %s' % unknown)
    for kind, name in (('end', 'end table (extensional, the stop in it)'), ('text', 'text (syntactic)')):
        print('recall by %s' % name)
        print('  %-8s %-6s ' % ('role', 'cases') + ' '.join('%-12s' % ('%s @%d' % (arm, t)) for arm in present for t in times))
        for role in ROLES + ('all',):
            cells, n = [], {}
            for arm in present:
                ks = [k for k in valid[arm] if role == 'all' or roles.get((k[0], k[1])) == role]
                n[arm] = len(ks)
                for t in times:
                    cells.append('%d/%d' % (sum(reached(valid[arm][k], kind, t) for k in ks), len(ks)))
            if any(n.values()):
                print('  %-8s %-6s ' % (role, '/'.join(str(n[arm]) for arm in present)) + ' '.join('%-12s' % c for c in cells))
    if len(present) == 2:
        both = sorted(set(valid['search']) & set(valid['draw']))
        print('paired, on %d cases valid in both arms (both / search alone / draw alone / neither), by end table' % len(both))
        for role in ROLES + ('all',):
            ks = [k for k in both if role == 'all' or roles.get((k[0], k[1])) == role]
            if not ks:
                continue
            cells = []
            for t in times:
                s = [reached(valid['search'][k], 'end', t) for k in ks]
                d = [reached(valid['draw'][k], 'end', t) for k in ks]
                cells.append('@%d %d/%d/%d/%d' % (t, sum(x and y for x, y in zip(s, d)), sum(x and not y for x, y in zip(s, d)), sum(y and not x for x, y in zip(s, d)),
                                                   sum(not x and not y for x, y in zip(s, d))))
            print('  %-8s %-3d %s' % (role, len(ks), '  '.join(cells)))
    for arm in present:
        x = list(valid[arm].values())
        cpu = sum(y['cpu'] for y in x)
        print('  %-6s proposals per CPU s %.1f, peak RSS MiB %d' % (arm, sum(y['tried'] for y in x) / max(cpu, 1e-9), max(y.get('maxrss_mib', 0) for y in x)))


if __name__ == '__main__':
    main()
