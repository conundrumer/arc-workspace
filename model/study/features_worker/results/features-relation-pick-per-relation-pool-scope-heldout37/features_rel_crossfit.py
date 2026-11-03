#!/usr/bin/env python
"""Steers refit by task fold on the train rows, so that a train task's steered prior comes from a steer that was not fit on it.

  python features_rel_crossfit.py matrix SCRATCH SHARD_I SHARD_N    writes the steer's feature rows of RULE picks, gold and a sample of the other options
  python features_rel_crossfit.py fit SCRATCH FOLD                  fits the steer without the fold's tasks, with the steer's recipe (150 trees of depth 5), and writes steer-fold<FOLD>.pkl in the run folder
  python features_rel_crossfit.py read SCRATCH FOLD                 bits on the test tasks' rows, against the steer in use

The rows are sampler-steers-context-rows-train: all earlier forms in scope, 3 atom orders, RULE forms. A pick keeps gold, the top TOP options by P and SAMPLE others at random, the sampled ones at the weight that stands for the options left out.
"""
import io
import json
import os
import pickle
import sys
import time
import zlib

import numpy as np
import zstandard

os.environ.setdefault('STEER_COVER', 'init,branch')
CODE = '/Users/davidlu/code/arc-workspace/model/study/sampler'
sys.path.insert(0, CODE)
import relfeat  # noqa: E402
import relsteer  # noqa: E402

W = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/'
OUT = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-per-relation-pool-scope-heldout37/scratch/rank-steers/'
STEER = OUT + 'steer-models/relR4_o.pkl'
TOP, SAMPLE = 20, 8
FOLDS = 4


def fold_of(task):
    return zlib.crc32(('steer' + task).encode()) % FOLDS


def rows(part):
    p = W + 'sampler-steers-context-rows-%s/relrows.jsonl.zst' % part
    with open(p, 'rb') as f:
        for line in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True), encoding='utf8'):
            d = json.loads(line)
            if d['kind'] == 'RULE':
                yield d


def matrix(scratch, i, n):
    leave = set(open(W + 'held/leave_out.txt').read().split())
    s = relsteer.Scorer(STEER)
    Xs, ys, ws, tasks = [], [], [], []
    rng = np.random.RandomState(i)
    t0 = time.time()
    c = 0
    for j, d in enumerate(rows('train')):
        if j % n != i:
            continue
        assert d['task'] not in leave
        toks = [o['tok'] for o in d['options']]
        if d['gold'] not in toks:
            continue
        g = toks.index(d['gold'])
        X, lp = s.matrix(relfeat.mask_row(d, s.mask))
        lp = np.array(lp)
        order = np.argsort(-lp)
        top = set(order[:TOP].tolist()) | {g}
        keep = sorted(top | set(rng.choice(len(lp), min(SAMPLE, len(lp)), replace=False).tolist()))
        w = np.array([1.0 if j in top else len(lp) / SAMPLE for j in keep], np.float32)
        Xs.append(X[keep])
        y = np.zeros(len(keep), bool)
        y[keep.index(g)] = True
        ys.append(y)
        ws.append(w)
        tasks.append(np.full(len(keep), fold_of(d['task']), np.int8))
        c += 1
        if c % 2000 == 0:
            print('%d rows %.0fs, %.1f rows/s' % (c, time.time() - t0, c / (time.time() - t0)), flush=True)
    np.save('%s/steerX-%d.npy' % (scratch, i), np.vstack(Xs))
    np.save('%s/steery-%d.npy' % (scratch, i), np.concatenate(ys))
    np.save('%s/steerw-%d.npy' % (scratch, i), np.concatenate(ws))
    np.save('%s/steerf-%d.npy' % (scratch, i), np.concatenate(tasks))
    print('shard', i, c, 'rows', flush=True)


def fit(scratch, fold):
    from sklearn.ensemble import HistGradientBoostingClassifier
    import glob
    ck = pickle.load(open(STEER, 'rb'))
    h = ck['hgb']
    Xs, ys, ws = [], [], []
    for p in sorted(glob.glob(scratch + '/steerX-*.npy')):
        i = p.rsplit('-', 1)[1][:-4]
        f = np.load('%s/steerf-%s.npy' % (scratch, i))
        X = np.load(p, mmap_mode='r')
        Xs.append(np.array(X[f != fold]))
        ys.append(np.load('%s/steery-%s.npy' % (scratch, i))[f != fold])
        ws.append(np.load('%s/steerw-%s.npy' % (scratch, i))[f != fold])
    X, y, w = np.vstack(Xs), np.concatenate(ys), np.concatenate(ws)
    del Xs
    print('fold', fold, X.shape, 'memory GB %.1f' % (X.nbytes / 2 ** 30), flush=True)
    params = {k: v for k, v in h['model'].get_params().items() if k in ('l2_regularization', 'learning_rate', 'max_depth', 'max_leaf_nodes', 'min_samples_leaf', 'max_iter', 'random_state')}
    t0 = time.time()
    m = HistGradientBoostingClassifier(early_stopping=False, max_bins=128, verbose=0, **params)
    m.fit(X, y, sample_weight=w)
    print('fit %.0fs' % (time.time() - t0), flush=True)
    new = dict(ck)
    new['hgb'] = dict(h, model=m)
    new.pop('logit', None)
    pickle.dump(new, open(OUT + 'steer-fold%d.pkl' % fold, 'wb'))


def read(scratch, fold):
    a, b = relsteer.Scorer(STEER), relsteer.Scorer(OUT + 'steer-fold%d.pkl' % fold)
    sa = sb = sp = 0.0
    n = 0
    t0 = time.time()
    for d in rows('test'):
        if d['order'] != 0:
            continue
        toks = [o['tok'] for o in d['options']]
        if d['gold'] not in toks:
            continue
        g = toks.index(d['gold'])
        lp = np.log(np.maximum([o['p'] for o in d['options']], 1e-9))
        for nm, s in (('a', a), ('b', b)):
            f = np.array(s.score(d)) + lp
            ls = f - np.logaddexp.reduce(f)
            if nm == 'a':
                sa += -ls[g] / np.log(2)
            else:
                sb += -ls[g] / np.log(2)
        sp += -(lp[g] - np.logaddexp.reduce(lp)) / np.log(2)
        n += 1
        if n % 1000 == 0:
            print(n, 'P %.3f in use %.3f fold %.3f (%.0fs)' % (sp / n, sa / n, sb / n, time.time() - t0), flush=True)
    print('test RULE rows', n, 'bits: P %.3f in use %.3f fold %d %.3f' % (sp / n, sa / n, fold, sb / n), flush=True)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'matrix':
        matrix(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    elif cmd == 'fit':
        fit(sys.argv[2], int(sys.argv[3]))
    else:
        read(sys.argv[2], int(sys.argv[3]))
