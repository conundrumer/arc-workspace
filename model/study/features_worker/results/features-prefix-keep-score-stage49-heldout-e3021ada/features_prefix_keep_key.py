"""A keep key that doesn't favor long prefixes: the score as a z value among junk prefixes of equal atom count, with the mean and spread from non-held rows. Reads the 49 stage prefixes across a task's whole junk pool by that key, and the atom counts of each task's top 16.

  features_prefix_keep_key.py SPLIT_ROWS HELD_ROWS CHECKS MODEL OUT_JSON
"""
import collections, glob, gzip, json, math, os, pickle, random, statistics as st, sys
import numpy as np
split, held, checks, model, outj = sys.argv[1:6]
b = pickle.load(open(model, 'rb')); ix = {k: i for i, k in enumerate(b['names'])}


def mat(rows):
    X = np.full((len(rows), len(ix) + 6), np.nan, np.float32)
    for i, x in enumerate(rows):
        X[i, -1] = x['atoms']; X[i, -2] = x['keyed']; X[i, -3 - b['places'].index(x['place'])] = 1
        for k, v in x['f'].items():
            j = ix.get(k)
            if j is not None and v is not None:
                X[i, j] = v
    return X


def load(f):
    with gzip.open(f, 'rb') as g:
        return pickle.load(g)


def junk_of(r):
    bag = collections.Counter()
    for x in r['rows']:
        if x['src'] == 'gold':
            bag |= collections.Counter(x['sigs'])
    return [x for x in r['rows'] if x['src'] == 'search' and x['place'] == 'RULE' and collections.Counter(x['sigs']) - bag]


fs = sorted(glob.glob(split + '/*.pkl.gz')); random.Random(0).shuffle(fs)
by = collections.defaultdict(list); n = 0
for f in fs:
    r = load(f)
    if r['kind'] != 'RULE' or not any(k.startswith('pair.') for x in r['rows'] for k in x['f']):
        continue
    J = junk_of(r)
    if J:
        for x, s in zip(J, b['model'].decision_function(mat(J))):
            by[min(x['atoms'], 6)].append(float(s))
        n += 1
    if n >= 700:
        break
K = {a: (float(np.mean(v)), float(np.std(v)) or 1.) for a, v in sorted(by.items())}
print('forms', n, {a: (round(m, 2), round(s, 2), len(by[a])) for a, (m, s) in K.items()}, flush=True)
json.dump({str(a): v for a, v in K.items()}, open(outj + '.new', 'w')); os.replace(outj + '.new', outj)
key = lambda s, a: (s - K[min(a, 6)][0]) / K[min(a, 6)][1]
stages = collections.defaultdict(list)
for c in map(json.loads, open(checks)):
    stages[c['task']].append((c['form'], c['split']))
res = []; tops = collections.Counter(); kept = 0
for t, ss in sorted(stages.items()):
    jk, gold = {}, {}
    for f in glob.glob(f'{held}/{t}.*.pkl.gz'):
        r = load(f)
        for x in r['rows']:
            if x['src'] == 'gold':
                gold[r['line'], x['place'], x['atoms']] = x
        for x in junk_of(r):
            jk.setdefault(tuple(x['sigs']), x)
    jr = list(jk.values()); s = b['model'].decision_function(mat(jr)); z = s if os.environ.get('FEATURES_RAW') else np.array([key(float(v), x['atoms']) for v, x in zip(s, jr)])
    order = sorted(range(len(jr)), key=lambda i: -z[i])[:16]
    tops.update(min(jr[i]['atoms'], 6) for i in order)
    for form, sp in ss:
        g = gold.get((form, 'RULE', sp))
        v = float(b['model'].decision_function(mat([g]))[0])
        v = v if os.environ.get('FEATURES_RAW') else key(v, g['atoms'])
        rank = int((z > v).sum())
        res.append((t, sp, math.log2(len(jr) + 1) - math.log2(1 + rank), rank))
rng = random.Random(0)
d = collections.defaultdict(list)
for t, sp, x, _ in res:
    d[t].append(x)
T = list(d); m = lambda p: sum(sum(d[t]) for t in p) / sum(len(d[t]) for t in p)
bs = sorted(m([rng.choice(T) for _ in T]) for _ in range(4000))
print('stage prefixes', len(res), 'mean bits over uniform %+.2f (95%% %+.2f %+.2f), median %+.2f' % (m(T), bs[100], bs[3899], st.median(x[2] for x in res)))
print('kept in the top 16 of the task', sum(x[3] < 16 for x in res), 'top 50', sum(x[3] < 50 for x in res), 'of', len(res), '; by split', sorted(collections.Counter((x[1], x[3] < 16) for x in res).items()))
print('atom counts of the top 16 over tasks', sorted(tops.items()))
