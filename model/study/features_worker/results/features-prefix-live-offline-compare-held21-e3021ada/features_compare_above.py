"""On live rows: of the rows that outrank a gold row, how many read the same relations as gold's row, the same relations and more, or others. Rows under the 8 bit bar stay in, so a floored gold row is ranked by its model score.

  features_compare_above.py LIVE_DIR MODELS
"""
import collections, glob, json, os, pickle, re, statistics as st, subprocess, sys
import numpy as np
live, mp = sys.argv[1:3]
B = pickle.load(open(mp, 'rb')); M = B['models']['form weight']; ix = {k: i for i, k in enumerate(B['names'])}
REL = re.compile(r'\((?:NOT )?\(?([&A-Za-z_][\w.]*)')


def rels(x):
    return collections.Counter(m for a in x['text'] for m in re.findall(r'\(([&\w.]+) \(:', a))


T = collections.Counter(); per = []; top = collections.Counter()
for f in sorted(glob.glob(live + '/*.jsonl.zst')):
    L = [json.loads(l) for l in subprocess.run(['zstd', '-dcq', f], capture_output=True, text=True).stdout.splitlines()]
    L = [x for x in L if 'done' not in x and 1 <= x['atoms'] <= 3]
    X = np.full((len(L), len(ix) + 1), np.nan, np.float32)
    for i, x in enumerate(L):
        X[i, -1] = x['atoms']
        for k, v in x['f'].items():
            j = ix.get(k)
            if j is not None and v is not None:
                X[i, j] = v
    s = M.decision_function(X)
    G = [i for i, x in enumerate(L) if x['gold']]
    if not G:
        continue
    g = max(G, key=lambda i: s[i]); rg = rels(L[g]); c = collections.Counter()
    for x, v in zip(L, s):
        if v > s[g]:
            r = rels(x)
            k = 'same relations' if r == rg else 'gold relations and more' if not (rg - r) else 'shares a relation' if rg & r else 'no relation of gold'
            c[k] += 1; c['atoms %d' % x['atoms']] += 1
    per.append(c); T.update(c)
n = sum(T[k] for k in ('same relations', 'gold relations and more', 'shares a relation', 'no relation of gold'))
print('cases', len(per), 'rows above gold', n)
for k in ('same relations', 'gold relations and more', 'shares a relation', 'no relation of gold', 'atoms 1', 'atoms 2', 'atoms 3'):
    print(k, T[k], round(T[k] / max(n, 1), 3), 'median per case', st.median(c[k] for c in per))
