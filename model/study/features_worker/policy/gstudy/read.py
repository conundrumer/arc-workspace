"""Summary of rows.jsonl: within-point rank AUC of each measure for read against unread, co-read against not, and reach of split power by distance to OUT."""
import collections, json, os, statistics
HERE = os.path.dirname(os.path.abspath(__file__))
T, P = collections.defaultdict(list), collections.defaultdict(list)
for l in open(HERE + '/rows.jsonl'):
    r = json.loads(l)
    (T if r['r'] == 't' else P)[r['pt']].append(r)


def auc(groups, key, lab, sign=1):
    """Mean within-group probability that a positive beats a negative, with ties at half. Groups with no pair on this key are left out."""
    out = []
    for rows in groups.values():
        a = [sign * r[key] for r in rows if r[lab] and r.get(key) is not None]
        b = [sign * r[key] for r in rows if not r[lab] and r.get(key) is not None]
        if a and b:
            out.append(sum((x > y) + .5 * (x == y) for x in a for y in b) / (len(a) * len(b)))
    return (round(statistics.mean(out), 3), round(statistics.stdev(out) / len(out) ** .5, 3), len(out)) if len(out) > 1 else None


print('points', len(T), 'tasks', len({r['task'] for v in T.values() for r in v}), 'tables', sum(map(len, T.values())), 'mean available', round(statistics.mean(map(len, T.values())), 1), 'mean read', round(statistics.mean(sum(r['read'] for r in v) for v in T.values()), 2))
print('READ vs UNREAD within a point: (auc, se, points)')
for k, s in [('gap', -1), ('ddepth', 1), ('dout', -1), ('split', 1), ('same_all', -1), ('rows', 1), ('arity', 1), ('hasPos', 1)]:
    print(' ', k, 'sign', s, auc(T, k, 'read', s))
print('CO-READ pairs vs not, one table of each pair is read:')
for k in ('share', 'overlap'):
    print(' ', k, auc(P, k, 'co'))
print('split power by distance to OUT:')
by = collections.defaultdict(list)
for v in T.values():
    for r in v:
        if r.get('dout') is not None:
            by[min(r['dout'], 6)].append(r)
for d, v in sorted(by.items()):
    s = [r['split'] for r in v if r.get('split') is not None]
    print(' ', d, 'tables', len(v), 'with Position', round(sum(r['hasPos'] for r in v) / len(v), 2), 'split measured', len(s), 'mean', round(statistics.mean(s), 3) if s else '-', 'share > .1', round(sum(x > .1 for x in s) / len(s), 3) if s else '-', 'same across grids', round(statistics.mean(r['same_all'] for r in v if 'same_all' in r), 3))
print('same, for tables not reachable from OUT:', len([r for v in T.values() for r in v if r.get('dout') is None]))
