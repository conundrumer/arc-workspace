"""Fit one model per task fold on the live table, write them in the policy's model format, and write the held-out scores in the format of rank/ so pick_sim.py can read them. A task's score comes from the fold that did not train on it. Prints score spread beside the bundled policy's.

  live_model.py TAG
"""
import glob, hashlib, json, os, pickle, statistics, sys
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier as H
HERE = os.path.dirname(os.path.abspath(__file__))
tag = sys.argv[1]; FOLDS = 5
key = lambda t: hashlib.sha1(json.dumps(json.load(open(f'/Users/davidlu/code/arc-workspace/data/tasks/{t}.json'))['train'], sort_keys=True).encode()).hexdigest()
tasks = sorted(os.path.basename(f)[:8] for f in glob.glob(HERE + '/table/full/*.pkl'))
T = {t: pickle.load(open(f'{HERE}/table/full/{t}.pkl', 'rb')) for t in tasks}
names = sorted({k for v in T.values() for r in v for k in r['f']})
ix = {k: i for i, k in enumerate(names)}


def mat(rows):
    X = np.full((len(rows), len(names)), np.nan, np.float32)
    for i, r in enumerate(rows):
        for k, v in r['f'].items():
            X[i, ix[k]] = v
    return X


folds = []
os.makedirs(f'{HERE}/rank/{tag}', exist_ok=True)
live, old = [], []
for fold in range(FOLDS):
    te = tasks[fold::FOLDS]; tr = [t for t in tasks if t not in te]
    rows = [r for t in tr for r in T[t]]
    y = np.array([r['gold'] for r in rows])
    w = np.ones(len(rows)); w[y] = (~y).sum() / y.sum()
    m = H(max_iter=120, learning_rate=.06, max_depth=3, min_samples_leaf=8, l2_regularization=1., random_state=0).fit(mat(rows), y, sample_weight=w)
    folds.append(({key(t) for t in tr}, m))
    for t in te:
        s = m.decision_function(mat(T[t]))
        b = json.load(open(f'{HERE}/rank/full-s/{t}.json'))
        b['score'], ref = {str(r['id']): float(x) for r, x in zip(T[t], s)}, b['score']
        b['band'] = {k: v for k, v in b['band'].items() if k in b['score']}
        json.dump(b, open(f'{HERE}/rank/{tag}/{t}.json', 'w'))
        live.append(statistics.pstdev(s)); old.append(statistics.pstdev(ref.values()))
    print('fold', fold, 'fit', len(rows), 'gold', int(y.sum()), flush=True)
pickle.dump(dict(names=names, folds=folds), open(f'{HERE}/{tag}.pkl.new', 'wb')); os.replace(f'{HERE}/{tag}.pkl.new', f'{HERE}/{tag}.pkl')
print('score std within a task: live', round(statistics.median(live), 2), 'bundled', round(statistics.median(old), 2), 'names', len(names), flush=True)
