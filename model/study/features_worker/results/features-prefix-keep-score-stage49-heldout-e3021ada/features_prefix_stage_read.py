"""The rank of gold's stage prefixes among a task's junk prefixes, in bits over a uniform pick, on held rows, for each score given. A prefix is junk when any of its atoms isn't in gold's bag. A task-level bootstrap gives the interval.

  features_prefix_stage_read.py HELD_ROWS CHECKS NAME=MODEL ...
"""
import collections, glob, gzip, json, math, os, pickle, random, statistics as st, sys
import numpy as np
held, checks = sys.argv[1:3]
M = dict(x.split('=') for x in sys.argv[3:])
B = {k: pickle.load(open(v, 'rb')) for k, v in M.items()}
C = [json.loads(l) for l in open(checks)]
stages = collections.defaultdict(list)
for c in C:
    stages[c['task']].append((c['form'], c['split']))


def mat(rows, b):
    ix = {k: i for i, k in enumerate(b['names'])}
    X = np.full((len(rows), len(ix) + 6), np.nan, np.float32)
    for i, x in enumerate(rows):
        X[i, -1] = x['atoms']; X[i, -2] = x['keyed']; X[i, -3 - b['places'].index(x['place'])] = 1
        for k, v in x['f'].items():
            j = ix.get(k)
            if j is not None and v is not None:
                X[i, j] = v
    return X


res = collections.defaultdict(list); pools = {}; missing = []
for t, ss in sorted(stages.items()):
    junk, gold = {}, {}
    for f in glob.glob(f'{held}/{t}.*.pkl.gz'):
        with gzip.open(f, 'rb') as g:
            r = pickle.load(g)
        bag = collections.Counter()
        for x in r['rows']:
            if x['src'] == 'gold':
                bag |= collections.Counter(x['sigs'])
        for x in r['rows']:
            if x['src'] == 'gold':
                gold[r['line'], x['place'], x['atoms']] = x
            elif collections.Counter(x['sigs']) - bag:
                junk.setdefault((x['place'], tuple(x['sigs'])), x)
    jr = [x for x in junk.values() if x['logq'] is not None and x['place'] == 'RULE']
    pools[t] = len(jr)
    S = {k: b['model'].decision_function(mat(jr, b)) for k, b in B.items()}
    for form, split in ss:
        g = gold.get((form, 'RULE', split))
        if g is None:
            missing.append((t, form, split)); continue
        for k, b in B.items():
            s = float(b['model'].decision_function(mat([g], b))[0])
            res[k].append((t, form, split, math.log2(len(jr) + 1) - math.log2(1 + int((S[k] > s).sum()))))
        q = g['logq']
        res['log chance'].append((t, form, split, math.log2(len(jr) + 1) - math.log2(1 + sum(x['logq'] > q for x in jr))))
print('tasks', len(stages), 'stage prefixes', len(C), 'read', len(res[next(iter(B))]), 'missing', len(missing), missing[:12], 'pool median', st.median(pools.values()), 'range', min(pools.values()), max(pools.values()), flush=True)
rng = random.Random(0)


def boot(d):
    T = list(d); m = lambda p: sum(sum(d[t]) for t in p) / sum(len(d[t]) for t in p)
    b = sorted(m([rng.choice(T) for _ in T]) for _ in range(4000))
    return m(T), b[100], b[3899]


for k, v in res.items():
    d = collections.defaultdict(list)
    for t, f, s, x in v:
        d[t].append(x)
    print(f'{k}: mean bits over uniform %+.2f (95%% %+.2f %+.2f); median %+.2f' % (*boot(d), st.median(x[3] for x in v)), flush=True)
names = list(res)
for a, c in (('full', 'structure'), ('full', 'structure-size'), ('structure-size', 'structure'), ('full', 'log chance')):
    if a in res and c in res:
        d = collections.defaultdict(list)
        for x, y in zip(res[a], res[c]):
            d[x[0]].append(x[3] - y[3])
        print(f'paired {a} minus {c}: %+.2f (95%% %+.2f %+.2f), tasks {len(d)}' % boot(d), flush=True)
pickle.dump(dict(res), open(os.environ.get('FEATURES_READ_OUT', '/dev/null'), 'wb'))
