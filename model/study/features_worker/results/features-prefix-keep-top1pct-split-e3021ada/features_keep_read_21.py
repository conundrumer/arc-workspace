"""Held read of a keep model: on the RULE cases that miss, is a gold prefix of 1 to 3 atoms in the top K of the form's prefixes, and what do the top prefixes look like against gold's.

  features_keep_read_21.py HELD_ROWS MISS_CASES MODELS MODEL_NAME
"""
import collections, gzip, json, math, os, pickle, sys
import numpy as np
held, miss, models, name = sys.argv[1:5]
B = pickle.load(open(models, 'rb')); m = B['models'][name]; ix = {k: i for i, k in enumerate(B['names'])}
C = [json.loads(l) for l in open(miss)]
print('cases', len(C), list(C[0].keys())[:8])
MINB = float(os.environ.get('FEATURES_MIN_BITS', 0))
ORACLE = {'d59b0160', 'cb2d8a2c', '80a900e0'}
tot = collections.Counter(); seen = 0
for c in C:
    f = f"{held}/{c['task']}.{c['form']}.pkl.gz"
    if not os.path.exists(f):
        print(c['task'], c['form'], 'no rows'); continue
    with gzip.open(f, 'rb') as g:
        r = pickle.load(g)
    bag = collections.Counter()
    for x in r['rows']:
        if x['src'] == 'gold':
            bag |= collections.Counter(x['sigs'])
    S = {}
    for x in r['rows']:
        if x['place'] == 'RULE' and 1 <= x['atoms'] <= 3 and x['logq'] is not None and -x['logq'] >= MINB * math.log(2):
            y = x['src'] == 'gold' or not (collections.Counter(x['sigs']) - bag)
            S.setdefault((y, tuple(x['sigs'])), (y, x))
    R = [v[1] for v in S.values()]; Y = np.array([v[0] for v in S.values()])
    X = np.full((len(R), len(ix) + 1), np.nan, np.float32)
    for i, x in enumerate(R):
        X[i, -1] = x['atoms']
        for k, v in x['f'].items():
            j = ix.get(k)
            if j is not None and v is not None:
                X[i, j] = v
    if not len(R):
        continue
    s = m.decision_function(X); o = np.argsort(-s)
    best = int(np.where(Y[o])[0][0]) + 1 if Y.any() else None
    seen += 1
    for K in (3, 4, 16):
        tot[K] += bool(best and best <= K)
    show = lambda x: ' '.join(('!' if a else '') + str(b).replace('&', '') + '(' + ','.join(c_) + ')' for a, b, c_ in x['sigs'])
    gold = [R[i] for i in o if Y[i]][:1]
    print(('* ' if c['task'] in ORACLE else '  ') + f"{c['task']} {c['form']} pool {len(R)} gold rows {int(Y.sum())} best rank {best}", '| gold:', show(gold[0])[:70] if gold else None, '| top:', ' ; '.join(show(R[i])[:48] for i in o[:3] if not Y[i]))
print('cases read', seen, 'K=3', tot[3], 'K=4', tot[4], 'K=16', tot[16])
