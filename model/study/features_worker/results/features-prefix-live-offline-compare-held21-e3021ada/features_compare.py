"""Scores the same held prefixes both ways: live rows of the resume harness against offline rows of the 60 CPU s pool. Prints, per case, the gold row's score and rank in each pool, what is above it, and how far the features of gold's prefix differ.

  features_compare.py LIVE_DIR OFFLINE_DIR MODELS
"""
import collections, glob, gzip, json, os, pickle, statistics as st, subprocess, sys
import numpy as np
live, off, mp = sys.argv[1:4]
B = pickle.load(open(mp, 'rb')); M = B['models']['form weight']; ix = {k: i for i, k in enumerate(B['names'])}
BAR = 8 * .6931


def score(rows):
    X = np.full((len(rows), len(ix) + 1), np.nan, np.float32)
    for i, x in enumerate(rows):
        X[i, -1] = x['atoms']
        for k, v in x['f'].items():
            j = ix.get(k)
            if j is not None and v is not None:
                X[i, j] = v
    return M.decision_function(X)


def fam(k):
    return k.split('.')[0] if '.' in k else 'node'


tot = collections.Counter(); dif = collections.Counter(); both = collections.Counter(); nul = collections.defaultdict(list); agree = []
print('task form | live rows gold-score gold-bits rank at-floor | off rows gold-score rank | same-atoms gold score live/off | pair.* filled live/off')
for f in sorted(glob.glob(live + '/*.jsonl.zst')):
    L = [json.loads(l) for l in subprocess.run(['zstd', '-dcq', f], capture_output=True, text=True).stdout.splitlines()]
    done = L[-1].get('done'); L = [x for x in L if 'done' not in x]
    t, form = os.path.basename(f).split('.')[:2]
    s = score(L); gold = [i for i, x in enumerate(L) if x['gold']]
    agree += [abs(a - x['score']) for a, x in zip(s, L) if x['score'] > -99]
    for i, x in enumerate(L):
        x['s'] = s[i] if 1 <= x['atoms'] <= 3 and -x['logp'] >= BAR else -100.
    o = sorted(x['s'] for x in L)
    rank = lambda v, a: 1 + sum(y > v for y in a) + (sum(y == v for y in a) - 1) / 2
    gs = [L[i] for i in gold]
    head = f'{t} {form} | {len(L)}'
    if gs:
        g = max(gs, key=lambda x: x['s']); head += f" {g['s']:.2f} {-g['logp'] / .6931:.1f} {rank(g['s'], o):.0f} {sum(x['s'] <= -99 for x in L)} a{g['atoms']}"
    else:
        head += ' none'
    p = f'{off}/{t}.{form}.pkl.gz'
    if not os.path.exists(p):
        print(head, '| no offline rows'); continue
    r = pickle.load(gzip.open(p))
    R = [x for x in r['rows'] if x['place'] == 'RULE' and 1 <= x['atoms'] <= 3]
    sv = score(R)
    for x, v in zip(R, sv):
        x['s'] = v
    og = [x for x in R if x['src'] == 'gold']
    a = sorted(x['s'] for x in R)
    head += f' | {len(R)}'
    if og:
        g2 = max(og, key=lambda x: x['s']); head += f" {g2['s']:.2f} {rank(g2['s'], a):.0f} a{g2['atoms']}"
    pairs = []
    for x in gs:
        y = [z for z in og if z['atoms'] == x['atoms']]
        if y:
            y = max(y, key=lambda z: z['s']); pairs.append((x, y))
            for k in ix:
                u, v = x['f'].get(k), y['f'].get(k)
                if u is None and v is None:
                    continue
                c = fam(k); tot[c] += 1
                if (u is None) != (v is None):
                    nul[c].append(k)
                elif abs(u - v) > 1e-6:
                    dif[c] += 1
                    both[k] += 1
    head += ' | ' + ' '.join(f"a{x['atoms']} {x['s']:.2f}/{y['s']:.2f}" for x, y in pairs)
    fill = lambda rows: np.mean([sum(v is not None for k, v in x['f'].items() if k.startswith('pair.')) for x in rows]) if rows else 0
    print(head, f'| {fill(L):.1f}/{fill(R):.1f}', flush=True)
print('live score recomputed: max gap', round(max(agree), 4), 'rows', len(agree))
for c in sorted(tot):
    print(c, 'compared', tot[c], 'value differs', dif[c], 'null on one side', len(nul[c]), collections.Counter(nul[c]).most_common(4))
print('columns that differ most', both.most_common(12))
