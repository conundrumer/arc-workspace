"""Sums the probe rows of all shards. Prints the funnel and each relation, with hits, chance hits and gold."""
import collections, glob, json, os, statistics, sys
rows = {}
for f in glob.glob(os.path.dirname(os.path.abspath(__file__)) + '/rows/*.jsonl'):
    for l in open(f):
        try:
            r = json.loads(l)
        except ValueError:
            continue
        rows[r['task']] = r
rows = list(rows.values())
n = len(rows)
print('tasks', n, 'tables', sum(r['tables'] for r in rows), 'classes', sum(r['classes'] for r in rows), 'gold tables', sum(r['gold_tables'] for r in rows), 'gold classes', sum(r['gold_classes'] for r in rows), 'truncated', sum(r['truncated'] for r in rows), 'nodes', sum(r['nodes'] for r in rows), 'empty', sum(r['empty'] for r in rows))
for k in rows[0]['funnel']:
    v = [r['funnel'][k] for r in rows]
    print('  %-55s median %6.0f  ratio to unique %.2f' % (k, statistics.median(v), sum(v) / sum(r['tables'] for r in rows)))
for name, s in (('classes', 'bins'), ('gold', 'gold_bins'), ('reached', 'reached_bins'), ('reached by chance', 'reached_null_bins')):
    c = collections.Counter()
    for r in rows:
        c.update(r[s])
    print(' ', name, dict(c))
C, G = sum(r['classes'] for r in rows), sum(r['gold_classes'] for r in rows)
a, b = sum(r['reached'] for r in rows), sum(r['reached_null'] for r in rows)
g, h = sum(r['reached_gold'] for r in rows), sum(r['reached_null_gold'] for r in rows)
print('reached one-way: all %.3f chance %.3f | gold %.3f chance %.3f' % (a / C, b / C, g / max(G, 1), h / max(G, 1)))
s = collections.defaultdict(collections.Counter)
for r in rows:
    for k, v in r['relations'].items():
        for x in ('hit', 'gold', 'built', 'built_gold', 'null', 'null_gold'):
            s[k][x] += v[x]
print('%-58s %6s %6s %6s %6s %6s' % ('relation', 'share', 'chance', 'gold', 'built', 'b gold'))
for k, v in sorted(s.items(), key=lambda x: -x[1]['hit']):
    print('%-58s %6.3f %6.3f %6.3f %6d %6d' % (k, v['hit'] / C, v['null'] / C, v['gold'] / max(G, 1), v['built'], v['built_gold']))
