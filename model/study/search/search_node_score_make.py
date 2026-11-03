"""Writes a node score file from a fitted model, and checks that the file's score equals the model's score bit for bit.

  KIT_POLICY=<kit>/policy PYTHONDONTWRITEBYTECODE=1 <engine python> -I search_node_score_make.py SOURCE KIND NAME OUT ROWS

SOURCE  the hand model bundle (policy_model.pkl, KIND H), or a fit's state file (a pickle of (models, rounds), KIND T or D).
KIND    H, T or D: the facts that the model reads. T: names_T() of features_node_feats.py. D: its three depth facts.
NAME    the name that the card and the policy's log line show.
OUT     the node score file to write.
ROWS    the folder of base row files (*.part*.npz, each with X, H, names, hand_names).

The check rows are 2000 rows of 4 part files and 200 rows of those with 30% of the entries set to NaN. The reference score of a row is
clf.decision_function(row) for each fold of H, and t * sum(m.predict(row)) for T and D. The check reads the file back with the policy's own reader.
Prints one line per check, and PASS or FAIL last. The exit status is 1 on FAIL.
"""
import glob
import hashlib
import json
import os
import pickle
import sys

import numpy as np

sys.dont_write_bytecode = True
KIT_POLICY = os.environ['KIT_POLICY']
sys.path.insert(0, KIT_POLICY)
sys.path.insert(0, KIT_POLICY + '/fe')
import features_node_feats as FE  # noqa: E402
import nodescore  # noqa: E402

FEATURES_DIR = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-rank-model-train-read-hour13-heldout37/'
SOURCE_SHA = {'H': '2ec93ed1', 'T': '916864da', 'D': 'd9be3226'}  # the start of each source file's sha256
ROUNDS = 150
PARTS, ROWS_TOTAL, ROWS_NAN, NAN_SHARE, SEED = 4, 2000, 200, .3, 7


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def flat(models):
    """(flat arrays, problems) of the trees of models, a list of (model, tbase), in order. tbase goes with each tree of the model. Only one tree per iteration and no categorical split are allowed."""
    cols = {n: [] for n in ('feat', 'thr', 'mgl', 'leaf', 'left', 'right', 'val')}
    roots, tbase, at, problems = [], [], 0, []
    for m, base in models:
        if m.n_trees_per_iteration_ != 1:
            problems.append('trees per iteration %d' % m.n_trees_per_iteration_)
        for it in m._predictors:
            if len(it) != 1:
                problems.append('iteration with %d trees' % len(it))
            nd = it[0].nodes
            if nd['is_categorical'].any():
                problems.append('categorical split')
            roots.append(at)
            tbase.append(base)
            cols['feat'].append(nd['feature_idx'].astype(np.int32))
            cols['thr'].append(nd['num_threshold'].astype(np.float64))
            cols['mgl'].append(nd['missing_go_to_left'].astype(np.uint8))
            cols['leaf'].append(nd['is_leaf'].astype(np.uint8))
            cols['left'].append(nd['left'].astype(np.int32) + at)
            cols['right'].append(nd['right'].astype(np.int32) + at)
            cols['val'].append(nd['value'].astype(np.float64))
            at += len(nd)
    out = {n: np.concatenate(v) for n, v in cols.items()}
    out.update(roots=np.array(roots, np.int64), tbase=np.array(tbase, np.float64))
    return out, problems


def rows_of(folder, kind, names):
    """(rows, how many rows came from the files, how many have NaN set): check rows in the order of names."""
    files = sorted(glob.glob(folder + '/*.part*.npz'))
    files = files[::len(files) // PARTS][:PARTS]
    got = []
    for path in files:
        z = np.load(path, allow_pickle=False)
        if kind == 'H':
            assert [str(n) for n in z['hand_names']] == names, 'hand names differ in ' + path
            got.append(z['H'])
        else:
            at = {str(n): i for i, n in enumerate(z['names'])}
            got.append(z['X'][:, [at[n] for n in names]])
    x = np.concatenate(got).astype(np.float32)
    rng = np.random.default_rng(SEED)
    x = x[rng.choice(len(x), ROWS_TOTAL, replace=False)]
    extra = x[rng.choice(len(x), ROWS_NAN, replace=False)].copy()
    extra[rng.random(extra.shape) < NAN_SHARE] = np.nan
    return np.concatenate([x, extra]), len(files)


def bits(a):
    return np.ascontiguousarray(a, np.float64).view(np.uint64)


def main():
    source, kind, name, out, folder = sys.argv[1:6]
    ok = True

    def say(label, good, text=''):
        nonlocal ok
        ok = ok and good
        print('%-6s %s %s' % ('ok' if good else 'FAIL', label, text), flush=True)
    sha = sha256_of(source)
    say('source sha256', sha.startswith(SOURCE_SHA[kind]), sha)
    with open(source, 'rb') as f:
        loaded = pickle.load(f)
    if kind == 'H':
        names = [str(n) for n in loaded['names']]
        t = 1.0
        folds = [(sorted(trained), m) for trained, m in loaded['folds']]
        models = None
        tree_sets = [[(m, 0.0)] for _, m in folds]
        base0s = [float(np.ravel(m._baseline_prediction)[0]) for _, m in folds]
        counts = [(m.n_iter_, len(m._predictors)) for _, m in folds]
        say('iterations', all(a == b for a, b in counts), str(counts))
        trained_sets = [trained for trained, _ in folds]
    else:
        models, done = loaded
        names = FE.names_T() if kind == 'T' else FE.names_depth()
        cards = [json.load(open(p)) for p in sorted(glob.glob(FEATURES_DIR + 'final-models/*.json'))]
        card = next(c for c in cards if c.get('sha256') == sha)
        t = float(card['t'])
        say('rounds', done == ROUNDS == len(models), 'rounds %s models %d' % (done, len(models)))
        say('names', [str(n) for n in card['feature_names']] == names, '%d names, equal to the model card' % len(names))
        tree_sets = [[(m, float(np.ravel(m._baseline_prediction)[0])) for m in models]]
        base0s = [0.0]
        trained_sets = [[]]
        say('one tree per model', all(len(m._predictors) == 1 for m in models))
        say('model width', all(m.n_features_in_ == len(names) for m in models), '%d' % len(names))
    arrays = {}
    for k, trees in enumerate(tree_sets):
        a, problems = flat(trees)
        say('fold %d trees' % k, not problems, '%d trees, %d nodes %s' % (len(a['roots']), len(a['feat']), sorted(set(problems))))
        arrays.update({'k%d_%s' % (k, n): v for n, v in a.items()})
        arrays['k%d_base0' % k] = np.array(base0s[k], np.float64)
    card = dict(format=nodescore.FORMAT, name=name, features=kind, names=names, t=t, source=os.path.abspath(source), source_sha256=sha, folds=trained_sets)
    np.savez_compressed(out, card=np.array(json.dumps(card)), **arrays)
    print('wrote', out, 'sha256', sha256_of(out), flush=True)
    x, nfiles = rows_of(folder, kind, names)
    say('check rows', len(x) == ROWS_TOTAL + ROWS_NAN, '%d rows from %d part files, %d with NaN set' % (len(x), nfiles, ROWS_NAN))
    card2, fold_trees, _ = nodescore.read_file(out)
    say('card round trip', card2 == card)
    xs = x.tolist()
    for k, trees in enumerate(fold_trees):
        got = np.array([card2['t'] * trees.score(r) for r in xs])
        if kind == 'H':
            ref = loaded['folds'][k][1].decision_function(x)
        else:
            ref = np.zeros(len(x))
            for m in models:
                ref += m.predict(x)
            ref = t * ref
        differ = int((bits(got) != bits(ref)).sum())
        say('fold %d score' % k, differ == 0, '%d of %d rows differ, max abs %.3g' % (differ, len(x), float(np.abs(got - ref).max())))
    print('PASS' if ok else 'FAIL', flush=True)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
