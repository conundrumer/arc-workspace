"""Rank of gold within its depth band, per policy: mean bits over log2(n), uniform 1.44 at the same formula, task-level bootstrap on the paired difference."""
import collections, glob, json, math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
tags = sys.argv[1:]
data = {}
for t in tags:
    d = collections.defaultdict(lambda: collections.defaultdict(list))
    for f in glob.glob(f'{HERE}/rank/{t}/*.json'):
        v = json.load(open(f))
        for g in v['gold']:
            d[g['band']][v['task']].append(math.log2(g['n']) - math.log2(max(g['rank'], 1)))
    data[t] = d
rng = random.Random(0)
for b in ('1', '2-3', '4-6', '7+'):
    for t in tags:
        d = data[t][b]; xs = [x for v in d.values() for x in v]
        if xs:
            print(b, t, 'tasks', len(d), 'gold', len(xs), 'mean bits', round(sum(xs) / len(xs), 2))
    if len(tags) == 2:
        a, c = data[tags[0]][b], data[tags[1]][b]; ts = sorted(set(a) & set(c))
        if ts:
            m = lambda p: sum(sum(c[t]) - sum(a[t]) for t in p) / sum(len(a[t]) for t in p)
            bs = sorted(m([rng.choice(ts) for _ in ts]) for _ in range(2000))
            print('   ', tags[1], 'minus', tags[0], round(m(ts), 2), '90%', round(bs[100], 2), round(bs[1900], 2))
