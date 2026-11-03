"""On seed 0 pool records: the rank of ground truth RULE nodes among a task's RULE nodes, by the table score alone, against random and draw order. A record holds complete forms, so this reads kept nodes, not prefixes.

  features_node_keep.py RECORD_DIR MODEL OUT
"""
import collections, glob, json, os, pickle, random, re, statistics as st, subprocess, sys, types
sys.path[:0] = [os.environ['POLICY_DIR']]
from nodefeat import Pair, features  # noqa: E402
sys.path.insert(0, '/Users/davidlu/code/arc-workspace/model/study/policy')
from outfeat import out_features  # noqa: E402
sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-prefix-score-corpus-final-e3021ada' + '/../prefix-score')
import numpy as np  # noqa: E402
import features_second as SECOND  # noqa: E402
rec, model, out = sys.argv[1:4]
b = pickle.load(open(model, 'rb')); ix = {k: i for i, k in enumerate(b['names'])}; PL = b['places']


def atoms(clause):
    d = n = 0
    for ch in clause:
        if ch == '(':
            d += 1; n += d == 2
        elif ch == ')':
            d -= 1
    return n


rows = []
fs = sorted(glob.glob(rec + '/*.nodes.jsonl.zst'))
for i, f in enumerate(fs, 1):
    task = os.path.basename(f)[:8]
    P = [Pair(p['input'], p['output']) for p in json.load(open(f'data/tasks/{task}.json'))['train']]
    R = [json.loads(x) for x in subprocess.run(['zstd', '-dcq', f], capture_output=True).stdout.splitlines() if x.startswith(b'{')]
    scope = {}
    for r in R:
        m = re.match(r'\((\w+) &f(\d+)', r['clause'] or '')
        if m:
            scope[int(m[2])] = dict(types=r['table_types'], labels=[], x_rows=r['x_rows'])
    for r in R:
        c = r['clause'] or ''
        if not c.startswith('(RULE'):
            continue
        n = dict(types=[], table_types=r['table_types'], arity=r['arity'], depth=1, parents=[], clause='', n_clauses=1, x_rows=r['x_rows'], examples=r['examples'])
        d = features(n, P); d.update(out_features(n, P)[0]); d.update(SECOND.features(n, [c.replace('&f', '&r')], scope, P))
        x = np.full((1, len(ix) + 6), np.nan, np.float32); x[0, -1] = atoms(c); x[0, -2] = 0; x[0, -3 - PL.index('RULE')] = 1
        for k, v in d.items():
            j = ix.get(k)
            if j is not None and v is not None:
                x[0, j] = v
        rows.append((task, r['tags'].get('kind') == 'gold', float(b['model'].decision_function(x)[0]), r['tags'].get('draw', 0), atoms(c)))
    print(i, len(fs), task, len(R), flush=True)
pickle.dump(rows, open(out, 'wb'))
T = collections.defaultdict(list)
for x in rows:
    T[x[0]].append(x)
NS = (16, 50, 200)
keep = collections.Counter(); gold = 0; pools = []
for t, v in T.items():
    g = [x for x in v if x[1]]; pool = [x for x in v if not x[1]]
    if not g or not pool:
        continue
    pools.append(len(pool))
    sv = sorted((x[2] for x in pool), reverse=True); dr = sorted(x[3] for x in pool)
    for x in g:
        gold += 1
        for n in NS:
            keep['score', n] += n > sum(z > x[2] for z in sv[:n]); keep['earliest draws', n] += n > sum(z < x[3] for z in dr[:n]); keep['random', n] += min(1, n / len(pool))
print('tasks', len(pools), 'gold nodes', gold, 'median pool', st.median(pools), {f'{a}@{n}': round(c / gold, 3) for (a, n), c in sorted(keep.items())})
