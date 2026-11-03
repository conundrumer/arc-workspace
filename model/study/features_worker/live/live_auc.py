"""For each feature in a live table: within each depth band and task, the rate at which a gold node beats a non-gold node, averaged over gold nodes. A rate far from .5 at one depth band and not at another shows where a feature changes meaning. Prints the features furthest from .5 at the chosen band, with the same feature's rate at the other bands.

  live_auc.py TAG [BAND] [TOP]
"""
import collections, glob, os, pickle, sys
HERE = os.path.dirname(os.path.abspath(__file__))
tag = sys.argv[1]; want = sys.argv[2] if len(sys.argv) > 2 else '4-6'; top = int(sys.argv[3]) if len(sys.argv) > 3 else 25
B = [(1, 1, '1'), (2, 3, '2-3'), (4, 6, '4-6'), (7, 99, '7+')]
bucket = lambda x: next(n for a, b, n in B if a <= x <= b)
rate = collections.defaultdict(lambda: collections.defaultdict(list))
counts = collections.Counter()
for f in sorted(glob.glob(f'{HERE}/table/{tag}/*.pkl')):
    by = collections.defaultdict(list)
    for r in pickle.load(open(f, 'rb')):
        by[bucket(r['depth'])].append(r)
    for b, rows in by.items():
        gold = [r for r in rows if r['gold']]
        rest = [r for r in rows if not r['gold']]
        counts[b] += len(gold)
        if not gold or not rest:
            continue
        for k in rows[0]['f']:
            vals = sorted(r['f'].get(k) or 0 for r in rest)
            for g in gold:
                v = g['f'].get(k) or 0
                lo = sum(x < v for x in vals); eq = sum(x == v for x in vals)
                rate[k][b].append((lo + eq / 2) / len(vals))
print('gold', dict(counts))
mean = lambda x: sum(x) / len(x) if x else float('nan')
rows = sorted(rate, key=lambda k: -abs(mean(rate[k][want]) - .5))
print('feature', *[b for *_, b in B])
for k in rows[:top]:
    print(f'{k[:44]:44}', *[f'{mean(rate[k][b]):.2f}' for *_, b in B])
