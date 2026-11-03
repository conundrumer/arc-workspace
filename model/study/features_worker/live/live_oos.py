"""Link 1 on tasks the live model never saw: rank of gold nodes within a depth band, bundled policy against live model, on a table of nodes. Each model is its fold that did not train on the task. A task-level bootstrap gives the paired interval.

  live_oos.py TAG MODEL_PKL
"""
import collections, glob, hashlib, json, math, os, pickle, random, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
tag, new = sys.argv[1], pickle.load(open(sys.argv[2], 'rb'))
old = pickle.load(open('/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/ede6795c-2b6f-4633-a6da-08e90de33bc4/scratchpad/policy1/policy_model.pkl', 'rb'))
B = [(1, 1, '1'), (2, 3, '2-3'), (4, 6, '4-6'), (7, 99, '7+')]
bucket = lambda x: next(n for a, b, n in B if a <= x <= b)
key = lambda t: hashlib.sha1(json.dumps(json.load(open(f'/Users/davidlu/code/arc-workspace/data/tasks/{t}.json'))['train'], sort_keys=True).encode()).hexdigest()


def score(b, k, rows):
    ix = {n: i for i, n in enumerate(b['names'])}
    m = next((m for tr, m in b['folds'] if k not in tr), b['folds'][0][1])
    X = np.full((len(rows), len(ix)), np.nan, np.float32)
    for i, r in enumerate(rows):
        for n, v in r['f'].items():
            if n in ix:
                X[i, ix[n]] = v
    return m.decision_function(X)


def bits(s, rows):
    out = collections.defaultdict(list)
    for j, r in enumerate(rows):
        if r['gold']:
            pool = [s[i] for i, x in enumerate(rows) if bucket(x['depth']) == bucket(r['depth'])]
            rank = 1 + sum(x > s[j] for x in pool) + (sum(x == s[j] for x in pool) - 1) / 2
            out[bucket(r['depth'])].append(math.log2(len(pool)) - math.log2(max(rank, 1)))
    return out


d = {}
for f in sorted(glob.glob(f'{HERE}/table/{tag}/*.pkl')):
    t = os.path.basename(f)[:8]; rows = pickle.load(open(f, 'rb'))
    if not any(r['gold'] for r in rows):
        continue
    k = key(t)
    d[t] = (bits(score(old, k, rows), rows), bits(score(new, k, rows), rows))
rng = random.Random(0)
print('tasks with gold', len(d))
for _, _, b in B:
    ts = [t for t in d if d[t][0].get(b)]
    if not ts:
        continue
    n = sum(len(d[t][0][b]) for t in ts)
    o, a = sum(sum(d[t][0][b]) for t in ts) / n, sum(sum(d[t][1][b]) for t in ts) / n
    f = lambda p: sum(sum(d[t][1][b]) - sum(d[t][0][b]) for t in p) / sum(len(d[t][0][b]) for t in p)
    bs = sorted(f([rng.choice(ts) for _ in ts]) for _ in range(2000))
    print(f'{b}: tasks {len(ts)} gold {n} bundled {o:.2f} live {a:.2f} diff {a - o:+.2f} 90% {bs[100]:+.2f} {bs[1900]:+.2f}', flush=True)
