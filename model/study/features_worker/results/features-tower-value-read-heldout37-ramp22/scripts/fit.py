"""Fit the value (T facts and tower facts) and the depth-only control on the N600 fit set. Never reads a held task.

  scripts/rt_r1.sh fit.py [--cv] [--only TASK ...] [--threads N] [--iters N]

Rows: n600-rows (X of FE.NAMES, built by the n600 rebuild) joined by node id to rows/fit/*.npz (tower facts and label). Nodes whose replay gave no table (row check 4) are left out of the fit.
Model: HistGradientBoostingClassifier, class_weight balanced, fixed settings (no tuning on any held task). --cv adds a 5-fold task-grouped AUC on the fit set.
Writes models/value.pkl and models/depth.pkl.
"""
import argparse
import glob
import json
import os
import pickle
import sys
import time

sys.dont_write_bytecode = True
ap = argparse.ArgumentParser()
ap.add_argument('--cv', action='store_true')
ap.add_argument('--only', nargs='*')
ap.add_argument('--threads', default='2')
ap.add_argument('--iters', type=int, default=200)
a = ap.parse_args()
os.environ.setdefault('OMP_NUM_THREADS', a.threads)
HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-tower-value-read-heldout37-ramp22/scripts'  # the data folder
sys.path.insert(0, HERE)
sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop/')
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
import common as C
import features_node_feats as FE

NAMES_T = FE.names_T()
FEATURES = NAMES_T + C.TOWER_NAMES
SETTINGS = dict(max_iter=a.iters, learning_rate=0.05, max_leaf_nodes=8, min_samples_leaf=50, l2_regularization=1.0, class_weight='balanced', early_stopping=False, random_state=0)


def load_fit(tasks):
    Xs, ys, gs, tw = [], [], [], []
    skipped = 0
    for t in tasks:
        z = np.load('%s/rows/fit/%s_s0.npz' % (C.REC, t))
        ids = z['node']
        pos = {int(n): i for i, n in enumerate(ids)}
        X = np.full((len(ids), len(NAMES_T)), np.nan, np.float32)
        ok = np.zeros(len(ids), bool)
        for p in sorted(glob.glob(C.N600_ROWS + t + '.part*.npz')):
            r = np.load(p, allow_pickle=False)
            names = list(r['names'])
            col = [names.index(nm) for nm in NAMES_T]
            for row, n in zip(range(len(r['meta'])), r['meta'][:, 0]):
                i = pos[int(n)]
                X[i] = r['X'][row][col]
                ok[i] = int(r['meta'][row, 2]) != 4
        T = np.stack([z[nm] for nm in C.TOWER_NAMES], 1).astype(np.float32)
        skipped += int((~ok).sum())
        Xs.append(np.hstack([X, T])[ok])
        ys.append(z['label'][ok])
        gs += [t] * int(ok.sum())
    return np.vstack(Xs), np.concatenate(ys), np.array(gs), skipped


def model():
    return HistGradientBoostingClassifier(**SETTINGS)


def main():
    t0 = time.time()
    tasks = a.only or C.words(C.FEAT + 'n600-tasks.txt')
    assert not (set(tasks) & C.held_union())
    X, y, g, skipped = load_fit(tasks)
    print('fit rows', X.shape, 'positives', int(y.sum()), 'tasks', len(set(g)), 'rows left out (no table)', skipped, 'load s %.1f' % (time.time() - t0), flush=True)
    di = FEATURES.index('t_depth')
    if a.cv and len(set(g)) >= 5:
        aucs = {'value': [], 'depth': []}
        for k, (tr, te) in enumerate(GroupKFold(5).split(X, y, g)):
            if y[te].sum() == 0:
                continue
            m = model().fit(X[tr], y[tr])
            aucs['value'].append(roc_auc_score(y[te], m.predict_proba(X[te])[:, 1]))
            d = model().fit(X[tr][:, [di]], y[tr])
            aucs['depth'].append(roc_auc_score(y[te], d.predict_proba(X[te][:, [di]])[:, 1]))
            print('cv fold', k, {kk: round(v[-1], 4) for kk, v in aucs.items()}, 'elapsed s %.0f' % (time.time() - t0), flush=True)
        print('cv mean', {kk: round(float(np.mean(v)), 4) for kk, v in aucs.items()})
    m = model().fit(X, y)
    print('value fit done, s %.1f' % (time.time() - t0), flush=True)
    d = model().fit(X[:, [di]], y)
    os.makedirs(C.REC + '/models', exist_ok=True)
    pickle.dump(dict(model=m, features=FEATURES, settings=SETTINGS, tasks=tasks, n_rows=len(y), n_pos=int(y.sum())), open(C.REC + '/models/value.pkl', 'wb'))
    pickle.dump(dict(model=d, features=['t_depth'], settings=SETTINGS, tasks=tasks, n_rows=len(y), n_pos=int(y.sum())), open(C.REC + '/models/depth.pkl', 'wb'))
    print('wrote models/value.pkl, models/depth.pkl; total s %.1f' % (time.time() - t0))


main()
