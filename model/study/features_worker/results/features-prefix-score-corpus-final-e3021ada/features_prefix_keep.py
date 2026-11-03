"""If a search keeps only its top N prefixes per task as nodes, what share of gold prefixes stays? Ranks a task's prefixes on held rows by the table score alone and by the path's log chance, against random keeping at the same N. Distinct prefixes by atom text.

  features_prefix_keep.py HELD_ROWS MODEL
"""
import collections, glob, gzip, pickle, random, statistics as st, sys
import numpy as np
held, model = sys.argv[1:3]
b = pickle.load(open(model, 'rb')); ix = {k: i for i, k in enumerate(b['names'])}; PL = b['places']


def mat(rows):
    X = np.full((len(rows), len(ix) + 6), np.nan, np.float32)
    for i, x in enumerate(rows):
        X[i, -1] = x['atoms']; X[i, -2] = x['keyed']; X[i, -3 - PL.index(x['place'])] = 1
        for k, v in x['f'].items():
            j = ix.get(k)
            if j is not None and v is not None:
                X[i, j] = v
    return X


T = collections.defaultdict(list)
for f in sorted(glob.glob(held + '/*.pkl.gz')):
    with gzip.open(f, 'rb') as g:
        r = pickle.load(g)
    rows = r['rows']
    if not rows:
        continue
    s = b['model'].decision_function(mat(rows))
    for x, v in zip(rows, s):
        T[r['task'], r['kind']].append((x['src'] == 'gold', float(v), x['logq'], x['atoms'], (r['line'], x['place'], tuple(x['sigs']))))
rng = random.Random(0)
NS = (50, 200, 1000)
for kind in sorted({k for _, k in T}):
    for lo in (1, 2):
        keep = collections.defaultdict(lambda: [0, 0]); pools = []
        for (t, k), rows in T.items():
            if k != kind:
                continue
            seen = {}
            for g, v, q, a, key in rows:
                seen[key] = (seen[key][0] or g, v, q, a) if key in seen else (g, v, q, a)
            pool = [x for x in seen.values() if not x[0] and x[2] is not None]
            gold = [x for x in seen.values() if x[0] and x[3] >= lo]
            if not gold or not pool:
                continue
            pools.append(len(pool))
            sv = sorted((x[1] for x in pool), reverse=True); sq = sorted((x[2] for x in pool), reverse=True)
            for n in NS:
                for g in gold:
                    keep['score', n][0] += n > sum(1 for z in sv[:n] if z > g[1])
                    keep['logq', n][0] += g[2] is not None and n > sum(1 for z in sq[:n] if z > g[2])
                    keep['score', n][1] += 1; keep['logq', n][1] += 1
                    keep['random', n][0] += min(1., n / len(pool)); keep['random', n][1] += 1
        print(kind, 'atoms >=', lo, 'tasks', len(pools), 'median pool', st.median(pools) if pools else 0, 'gold prefixes', keep['score', 50][1], {f'{a}@{n}': round(v[0] / max(v[1], 1), 3) for (a, n), v in sorted(keep.items())}, flush=True)
