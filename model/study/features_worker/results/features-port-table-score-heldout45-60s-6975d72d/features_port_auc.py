"""For each table feature on INIT prefix rows of fit tasks: the rate at which a gold prefix beats a search prefix of the same form, place and atom count, as a mean over gold prefixes, by place. A rate far from .5 marks a feature with signal. It screens and proves nothing alone.

  features_port_auc.py ROWS_DIR HELD_FORMS
"""
import collections, glob, pickle, sys
rows_dir, held_list = sys.argv[1:3]
heldt = {l.split()[0] for l in open(held_list) if l.strip()}
J = [r for r in (pickle.load(open(f, 'rb')) for f in sorted(glob.glob(rows_dir + '/*.pkl'))) if r['task'] not in heldt]
rate = collections.defaultdict(lambda: collections.defaultdict(list)); n = collections.Counter()
for r in J:
    bag = collections.Counter()
    for x in r['rows']:
        if x['src'] == 'gold' and len(x['sigs']) > sum(bag.values()):
            bag = collections.Counter(x['sigs']) | bag
    by = collections.defaultdict(lambda: ([], []))
    for x in r['rows']:
        g = x['src'] == 'gold' or not (collections.Counter(x['sigs']) - bag)
        by[x['place'], x['atoms']][not g].append(x)
    for (pl, k), (gold, rest) in by.items():
        if not gold or not rest:
            continue
        n[pl] += len(gold)
        for key in set().union(*(x['f'] for x in gold)):
            vals = [x['f'].get(key) or 0 for x in rest]
            for g in gold:
                v = g['f'].get(key) or 0
                rate[key][pl].append((sum(a < v for a in vals) + sum(a == v for a in vals) / 2) / len(vals))
mean = lambda x: sum(x) / len(x) if x else float('nan')
print('forms', len(J), 'gold prefixes', dict(n))
print('feature key port')
for k in sorted(rate, key=lambda k: -abs(mean(rate[k]['port']) - .5))[:16]:
    print(f'{k[:40]:40} {mean(rate[k]["key"]):.2f} {mean(rate[k]["port"]):.2f}')
