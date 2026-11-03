"""For each held case, each gold prefix of the offline rows: its atoms, cost in bits, score and share of the offline pool, and whether the live pool holds a gold row of that atom count. Then ranks on live rows with the 8 bit bar and without it.

  features_compare_reach.py LIVE_DIR OFFLINE_DIR MODELS
"""
import collections, glob, gzip, json, os, pickle, statistics as st, subprocess, sys
import numpy as np
live, off, mp = sys.argv[1:4]
B = pickle.load(open(mp, 'rb')); M = B['models']['form weight']; ix = {k: i for i, k in enumerate(B['names'])}


def score(rows):
    X = np.full((len(rows), len(ix) + 1), np.nan, np.float32)
    for i, x in enumerate(rows):
        X[i, -1] = x['atoms']
        for k, v in x['f'].items():
            j = ix.get(k)
            if j is not None and v is not None:
                X[i, j] = v
    return M.decision_function(X)


rk = lambda v, a: 1 + sum(y > v for y in a) + (sum(y == v for y in a) - 1) / 2
tot = collections.Counter(); same = []; atoms_live = collections.Counter(); atoms_off = collections.Counter(); bits_by = collections.defaultdict(list); src = collections.Counter()
for f in sorted(glob.glob(live + '/*.jsonl.zst')):
    L = [json.loads(l) for l in subprocess.run(['zstd', '-dcq', f], capture_output=True, text=True).stdout.splitlines()]
    L = [x for x in L if 'done' not in x]
    t, form = os.path.basename(f).split('.')[:2]
    s = score(L)
    gold = [(x, v) for x, v in zip(L, s) if x['gold']]
    pool = [v for x, v in zip(L, s) if 1 <= x['atoms'] <= 3]
    barred = [v for x, v in zip(L, s) if 1 <= x['atoms'] <= 3 and -x['logp'] >= 8 * .6931]
    r = min((rk(v, pool) for _, v in gold), default=None)
    tot['cases'] += 1; tot['gold row'] += bool(gold)
    if r:
        tot['no bar top 3'] += r <= 3; tot['no bar top 16'] += r <= 16
    atoms_live.update(x['atoms'] for x, _ in gold)
    line = f"{t} {form} live gold " + ','.join(f"a{x['atoms']} {-x['logp'] / .6931:.1f}b {v:.2f} r{rk(v, pool):.0f}/{len(pool)}" for x, v in gold)
    p = f'{off}/{t}.{form}.pkl.gz'
    if os.path.exists(p):
        r_ = pickle.load(gzip.open(p))
        R = [x for x in r_['rows'] if x['place'] == 'RULE' and 1 <= x['atoms'] <= 3]
        for x, v in zip(R, score(R)):
            x['s'] = v
        a = [x['s'] for x in R]
        og = [x for x in R if x['src'] == 'gold']
        src.update(x['src'] for x in R)
        atoms_off.update(x['atoms'] for x in og)
        line += ' | offline ' + ','.join(f"a{x['atoms']} {(-x['logq'] / .6931 if x['logq'] is not None else float('nan')):.1f}b {x['s']:.2f} r{rk(x['s'], a):.0f}/{len(a)}" for x in sorted(og, key=lambda z: z['atoms']))
        for x, v in gold:
            y = [z for z in og if z['atoms'] == x['atoms'] and abs(z['s'] - v) < 1e-3]
            if y:
                same.append((t, rk(v, pool) / len(pool), rk(y[0]['s'], a) / len(a)))
        for x in og:
            bits_by[x['atoms']].append(-x['logq'] / .6931 if x['logq'] is not None else None)
    print(line, flush=True)
print(dict(tot), 'live gold atoms', sorted(atoms_live.items()), 'offline gold atoms', sorted(atoms_off.items()), 'offline row sources', src.most_common())
print('same prefix, same score, share of pool: live median', round(st.median(x[1] for x in same), 3), 'offline median', round(st.median(x[2] for x in same), 3), 'n', len(same))
for k, v in sorted(bits_by.items()):
    w = [x for x in v if x is not None]
    print('offline gold prefix atoms', k, 'n', len(v), 'no cost', len(v) - len(w), 'median bits', round(st.median(w), 1) if w else None)
