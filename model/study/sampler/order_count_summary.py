#!/usr/bin/env python
"""Reads the jsonl of order_count.py (partial or whole) and prints the counts.

    order_count_summary.py OUT.jsonl [OUT2.jsonl ...] [--cases N]

Prints: the queries read; items per set by structure kind (histogram of item counts, and the sets with two items or more); the distinct write paths under `unordered`
(histogram by power-of-ten bucket, exact or not); the `ordered` outcomes; the unwritable queries by cause; the queries with more than one path.
"""
import argparse
import collections
import json
import re


def bucket(n):
    if n is None:
        return 'unknown'
    if n <= 10:
        return str(n)
    return '1e%d' % (len(str(n)) - 1)


def cause_of(o, sets=()):
    st = o['status']
    if st == 'stuck':
        why = o.get('why') or []
        txt = ' | '.join(w[1] for w in why)[:400]
        txt = re.sub(r'at: NodePath.*', '', txt)
        m = re.search(r'message: "([^"]*)"', txt)
        if m:
            return 'stuck in %s: %s' % (o.get('stuck_set'), m.group(1))
        return 'stuck in %s: %s' % (o.get('stuck_set'), txt[:120])
    if st == 'hash_mismatch':
        ds = o.get('diff_sites') or []
        marks = sorted({d[0] for d in ds})
        has_or = any(k == 'or' for k, n in sets)
        why = ('an OR branch or atom order moves the atom that makes an exported or key label' if has_or
               else 'the key body order changes the order of the key columns (`^` labels)' if '^' in marks else 'other')
        return 'hash_mismatch: %s (marks %s)' % (why, ','.join(marks) or 'none')
    return st + ': ' + str(o.get('why', ''))[:120]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path', nargs='+', help='one or more jsonl files (shards)')
    ap.add_argument('--cases', type=int, default=12)
    a = ap.parse_args()
    R = []
    for path in a.path:
        for l in open(path):
            try:
                R.append(json.loads(l))
            except ValueError:
                pass
    print('queries', len(R), 'tasks', len({r['task'] for r in R}), 'kinds', dict(collections.Counter(r['kind'] for r in R)))
    sizes = collections.defaultdict(collections.Counter)
    free = collections.Counter()
    for r in R:
        for k, n in r.get('sets', []):
            sizes[k][n] += 1
            if n >= 2:
                free[k] += 1
    print('\nitems per set, by kind: {items: sets}  (sets with 2+ items in the last column)')
    for k in sorted(sizes):
        print('  %-10s %s   free=%d' % (k, dict(sorted(sizes[k].items())), free[k]))
    sh = collections.Counter()
    for r in R:
        for k, v in (r.get('sites') or {}).items():
            sh[int(k)] += v
    print('  sites     (per atom; the QueryHash does not ignore their order)', dict(sorted(sh.items())), 'atoms with sites not in ascending column order:', sum(r.get('sites_not_ascending', 0) for r in R),
          '| symmetric comparisons of two labels (operand order, ignored by the hash):', sum(r.get('sym_cmp', 0) for r in R))
    nfree = collections.Counter(sum(1 for k, n in r.get('sets', []) if n >= 2) for r in R)
    print('queries by number of sets with 2+ items:', dict(sorted(nfree.items())))
    print('\nunordered: distinct write paths per query')
    hist = collections.Counter()
    inexact = []
    for r in R:
        u = r.get('unordered')
        if not u:
            continue
        n = int(u['paths']) if u.get('paths') is not None else None
        hist[bucket(n)] += 1
        if not u.get('exact'):
            inexact.append(r)
    order = sorted(hist, key=lambda k: (k == 'unknown', int(k) if k.isdigit() else 100 + int(k[2:]) if k.startswith('1e') else 999))
    print('  ', {k: hist[k] for k in order})
    print('   not exact (state limit):', len(inexact), [(r['task'], r['qid'][:6], r['sets'][:3]) for r in inexact[:a.cases]])
    print('\nordered: outcomes')
    st = collections.Counter(r['ordered']['status'] for r in R)
    print('  ', dict(st))
    causes = collections.defaultdict(list)
    for r in R:
        if r['ordered']['status'] not in ('ok',):
            causes[cause_of(r['ordered'], r.get('sets', []))].append(r)
    print('  unwritable by cause:')
    for c, rs in sorted(causes.items(), key=lambda kv: -len(kv[1])):
        print('   %4d  %s' % (len(rs), c))
        for r in rs[:a.cases]:
            print('          %s %s %s sets=%s' % (r['task'], r['qid'][:8], r['kind'], r.get('sets')))
    multi = [r for r in R if r['ordered'].get('paths', 0) > 1]
    tied = [r for r in R if r['ordered'].get('tie_paths', 0) > 1]
    print('\nordered: queries whose tie choices gave more than one stream before the end-of-query rule (least stream kept):', len(tied))
    ties = [r for r in R if r['ordered'].get('ties', 0) > 0]
    print('\nordered: queries with more than one path:', len(multi))
    for r in multi[:a.cases * 3]:
        print('   ', r['task'], r['qid'][:8], r['kind'], 'paths', r['ordered']['paths'], 'ties', r['ordered']['ties'], r.get('sets'))
    print('ordered: queries with a tie choice (equal keys) at some set:', len(ties), 'by set kind:', dict(collections.Counter(k for r in ties for k in r['ordered'].get('tie_sets', []))))
    print('ordered: queries with a tie but one path:', sum(1 for r in ties if r['ordered'].get('paths') == 1))
    oks = [r for r in R if r['ordered']['status'] == 'ok']
    print('ordered ok, canonical = written order:', sum(1 for r in oks if r['ordered'].get('gold_first_path')), 'of', len(oks))


if __name__ == '__main__':
    main()
