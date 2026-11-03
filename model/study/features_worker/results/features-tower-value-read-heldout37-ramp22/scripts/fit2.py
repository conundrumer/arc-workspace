"""Second fit: N600 as in fit.py, plus the 22 ramp tasks from round 1's bundle arm (rows/read, rows/read_x) and the arms bundle and pass of search-pass-r1 (rows/pass, rows/pass_x).

  <engine python> -I fit2.py [--cv] [--threads N] [--iters N] [--only-n600 TASK ...]

Ramp rows enter only where exposure is 1 or more (a scope held the node) and the replay gave a table. N600 rows (no exposure) enter as in fit.py: every node with a table.
No task of the 37 or of the 99 enters (asserted). Writes models/value-fit2.pkl and models/depth-fit2.pkl; the first fit's files are not touched.
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
ap.add_argument('--threads', default='2')
ap.add_argument('--iters', type=int, default=200)
ap.add_argument('--only-n600', nargs='*')
ap.add_argument('--skip-unfinished', action='store_true', help='sample runs only: leave out ramp runs whose T rows are not finished')
ap.add_argument('--suffix', default='', help='model file suffix, for sample runs')
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


def x_from_parts(paths, ids, bad_code):
    """T facts aligned to the sorted node ids; ok marks nodes with a table (row check not bad_code)."""
    X = np.full((len(ids), len(NAMES_T)), np.nan, np.float32)
    ok = np.zeros(len(ids), bool)
    for p in paths:
        r = np.load(p, allow_pickle=False)
        names = list(r['names'])
        col = [names.index(nm) for nm in NAMES_T]
        idx = np.searchsorted(ids, r['meta'][:, 0])
        assert (ids[idx] == r['meta'][:, 0]).all()
        X[idx] = r['X'][:, col]
        ok[idx] = r['meta'][:, 2] != bad_code
    return X, ok


def tower_of(z):
    return np.stack([z[nm] for nm in C.TOWER_NAMES], 1).astype(np.float32)


def load_n600(tasks):
    out = []
    for t in tasks:
        z = np.load('%s/rows/fit/%s_s0.npz' % (C.REC, t))
        ids = z['node']
        X, ok = x_from_parts(sorted(glob.glob(C.N600_ROWS + t + '.part*.npz')), ids, 4)
        out.append(dict(src='n600', task=t, X=np.hstack([X, tower_of(z)])[ok], y=z['label'][ok], dropped_no_table=int((~ok).sum())))
    return out


def load_ramp():
    out = []
    specs = []
    for g, seed, t, base in C.read_runs():
        if g == 'ramp':
            specs.append(('r1-bundle', t, 'read', 'read_x', '%s_%s' % (t, seed)))
    for g, seed, t, base, arm in C.pass_runs():
        specs.append(('pass-r1-' + arm, t, 'pass', 'pass_x', '%s_%s_%s' % (arm, t, seed)))
    for src, t, ld, xd, stem in specs:
        pp = '%s/rows/%s/%s.progress.json' % (C.REC, xd, stem)
        prog = json.load(open(pp)) if os.path.exists(pp) else dict(done=False)
        if not prog['done'] and a.skip_unfinished:
            continue
        assert prog['done'], stem
        z = np.load('%s/rows/%s/%s.npz' % (C.REC, ld, stem))
        ids = z['node']
        X, ok = x_from_parts(sorted(glob.glob('%s/rows/%s/%s.part*.npz' % (C.REC, xd, stem))), ids, 3)
        exposed = z['exposure'] >= 1
        keep = ok & exposed
        out.append(dict(src=src, task=t, X=np.hstack([X, tower_of(z)])[keep], y=z['label'][keep], dropped_no_table=int((~ok).sum()), dropped_unexposed=int((ok & ~exposed).sum())))
    return out


def model():
    return HistGradientBoostingClassifier(**SETTINGS)


def main():
    t0 = time.time()
    n600_tasks = a.only_n600 or C.words(C.FEAT + 'n600-tasks.txt')
    parts = load_n600(n600_tasks)
    parts += load_ramp()
    fit_tasks = sorted({p['task'] for p in parts})
    forbidden = set(C.words(C.HELD37)) | set(C.words(C.E99))
    assert not (set(fit_tasks) & forbidden), 'a task of the 37 or the 99 is in the fit'
    X = np.vstack([p['X'] for p in parts])
    y = np.concatenate([p['y'] for p in parts])
    g = np.concatenate([[p['task']] * len(p['y']) for p in parts])
    by_src = {}
    for p in parts:
        d = by_src.setdefault(p['src'], dict(runs=0, rows=0, positives=0, dropped_no_table=0, dropped_unexposed=0))
        d['runs'] += 1; d['rows'] += len(p['y']); d['positives'] += int(p['y'].sum()); d['dropped_no_table'] += p['dropped_no_table']; d['dropped_unexposed'] += p.get('dropped_unexposed', 0)
    print('fit2 rows', X.shape, 'positives', int(y.sum()), 'tasks', len(fit_tasks), 'load s %.1f' % (time.time() - t0), flush=True)
    for k, v in by_src.items():
        print('  ', k, v, flush=True)
    di = FEATURES.index('t_depth')
    if a.cv:
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
    meta = dict(settings=SETTINGS, tasks=fit_tasks, n_rows=len(y), n_pos=int(y.sum()), by_source=by_src,
                fit_set='N600 (50 tasks, every node with a table) + the 22 ramp tasks from r1 bundle and search-pass-r1 bundle and pass, ramp nodes with exposure of 1 or more')
    pickle.dump(dict(model=m, features=FEATURES, **meta), open(C.REC + '/models/value-fit2%s.pkl' % a.suffix, 'wb'))
    pickle.dump(dict(model=d, features=['t_depth'], **meta), open(C.REC + '/models/depth-fit2%s.pkl' % a.suffix, 'wb'))
    print('wrote models/value-fit2%s.pkl, models/depth-fit2%s.pkl; total s %.1f' % (a.suffix, a.suffix, time.time() - t0))


main()
