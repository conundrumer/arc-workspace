"""Item 8: the softmax booster of the design, and the seeded-label classifier arm. Resumes from its state file.

  features_node_fit.py --features T|TS|H|D --sources n600,s120 --a 0|1 --fold K|all --label true|shuffle --rounds R --seconds S --name NAME
                       [--objective softmax|hgbc] [--leaves 15] [--step .08]

Loss per pool g (negatives N, positives P, weight w_p, l_g = (14700 / n_g) ** a):
  L_g = - sum_p w_p log( e^{s_p} / (e^{s_p} + l_g sum_n e^{s_n}) ).
A positive competes with negatives only. w_p = c_k / m_gk, with k in {DET depth 1, DET depth 2+, INIT, RULE}, m_gk the positives of
class k in pool g, c_k such that the four classes weigh the same in total. A negative with the plain form of a positive of its pool has
weight 0 (dropped). A tree fits all positives, the top 256 negatives of a pool by current score, and 1 in 6 of the others at weight 6;
a round is one Newton step: HistGradientBoostingRegressor(max_iter=1) on -g/h with sample weight h.
Fold K: the 10 tasks of N600 fold K leave every source. The model then scores those tasks: fit-out/NAME-fK.scores.npz.
--s120-holdout: the S120 tasks of fold K (an S120 task that is an N600 task keeps its N600 fold; the others, by sorted task id, go i % 5) also leave S120, and
the model scores them: fit-out/NAME-fK.scores-s120.npz. The tune read gives the Ident cell on these seeded positives. Without the option, an arm that
has S120 in --sources has no held-out S120 cell; an arm without S120 scores all S120 tasks.
Prints per round: loss, seconds. At the end: pooled AUC, for the record only.
"""
import argparse, os, pickle, sys, time
T0 = time.time()
HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop/'  # the data folder
sys.path.insert(0, HERE)
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
import features_node_data as DT

ap = argparse.ArgumentParser()
ap.add_argument('--features', default='T'); ap.add_argument('--sources', default='n600,s120'); ap.add_argument('--a', type=int, default=0)
ap.add_argument('--fold', default='0'); ap.add_argument('--label', default='true'); ap.add_argument('--rounds', type=int, default=150)
ap.add_argument('--seconds', type=float, default=20); ap.add_argument('--name', required=True); ap.add_argument('--objective', default='softmax')
ap.add_argument('--s120-holdout', action='store_true', help='also leave out the S120 tasks of the fold (features_node_data.s120_fold_map) and score them')
ap.add_argument('--leaves', type=int, default=15); ap.add_argument('--step', type=float, default=.08)
args = ap.parse_args()
OUT = HERE + 'fit-out/'
os.makedirs(OUT, exist_ok=True)
FOLDS = DT.folds(5)
exclude = set(FOLDS[int(args.fold)]) if args.fold != 'all' else set()
tag = '%s-f%s' % (args.name, args.fold)
srcs = args.sources.split(',')
s120_held = set()
if args.s120_holdout and args.fold != 'all' and 's120' in srcs:
    s120_held = {t for t, k in DT.s120_fold_map().items() if k == int(args.fold)}
D = DT.load(srcs, args.features, exclude=exclude, exclude_src={'s120': s120_held})
if s120_held:
    print('S120 tasks held out of the fit', len(s120_held), flush=True)
X, y, pool = D['X'], D['y'], D['pool']
use = (y == 0) | (y == 1)
print('rows', len(y), 'usable', int(use.sum()), 'pools', len(D['pools']), 'features', X.shape[1], 'load s', round(time.time() - T0, 1), flush=True)

# label shuffle control: labels permuted within each pool, count held
if args.label == 'shuffle':
    rng = np.random.default_rng(7)
    for g in range(len(D['pools'])):
        ix = np.nonzero((pool == g) & use)[0]
        y[ix] = y[rng.permutation(ix)]

# plain-form weight 0
drop = np.zeros(len(y), bool)
posplain = {}
for i in np.nonzero(use & (y == 1))[0]:
    posplain.setdefault(pool[i], set()).add(D['plain'][i])
for i in np.nonzero(use & (y == 0))[0]:
    if D['plain'][i] in posplain.get(pool[i], ()) and D['plain'][i] != 0:
        drop[i] = True
src_of = np.array([D['pools'][g][0] for g in pool]) if len(pool) else np.array([])
for s in srcs:
    print('plain-form negatives at weight 0, source', s, int((drop & (src_of == s)).sum()), 'of negatives', int((use & (y == 0) & (src_of == s)).sum()), flush=True)
use &= ~drop
ix = np.nonzero(use)[0]
Xt, yt, pt = X[ix], y[ix], pool[ix]
kt, dt = D['kind'][ix], D['depth'][ix]
# renumber pools to 0..G-1 over rows (rows are in pool order)
_, pt = np.unique(pt, return_inverse=True)
G = pt.max() + 1
starts = np.r_[0, np.nonzero(np.diff(pt))[0] + 1]
ng = np.diff(np.r_[starts, len(pt)])
cls = np.where(kt == 1, 3, np.where(kt == 2, 2, np.where(dt <= 1, 0, 1)))
pos = yt == 1
m_gk = {}
for g, k in zip(pt[pos], cls[pos]):
    m_gk[(g, k)] = m_gk.get((g, k), 0) + 1
pools_k = np.zeros(4)
for (g, k) in m_gk:
    pools_k[k] += 1
ck = np.where(pools_k > 0, pools_k[pools_k > 0].mean() / np.maximum(pools_k, 1), 0)
wp = np.zeros(len(yt))
for i in np.nonzero(pos)[0]:
    wp[i] = ck[cls[i]] / m_gk[(pt[i], cls[i])]
print('positives', int(pos.sum()), 'by class', [int(((cls == k) & pos).sum()) for k in range(4)], 'pools with positives', len({g for g, _ in m_gk}), flush=True)
lg = (14700.0 / ng) ** args.a
lrow = lg[pt]


def reduce(v):
    return np.add.reduceat(v, starts)


def grads(s):
    m = np.maximum.reduceat(s, starts)[pt]
    z = s - m
    ez = np.exp(z)
    Sn = reduce(np.where(pos, 0.0, lrow * ez))
    Sr = Sn[pt]
    q = np.where(pos, ez / (ez + Sr + 1e-300), 0.0)
    u = np.where(pos, 1 - q, 0.0)
    A = reduce(wp * u)
    B = reduce(wp * u * q)
    pi = np.where(pos, 0.0, lrow * ez / np.maximum(Sr, 1e-300))
    g_ = np.where(pos, -wp * u, A[pt] * pi)
    h_ = np.where(pos, wp * u * q, pi * (A[pt] * (1 - pi) + B[pt] * pi))
    loss = float(reduce(np.where(pos, wp * np.log1p(Sr / np.maximum(ez, 1e-300)), 0.0)).sum() / max(wp.sum(), 1e-12))
    return g_, h_, loss


def auc_pooled(s):
    out = []
    for g in range(G):
        a, b = starts[g], starts[g] + ng[g]
        sp, sn = s[a:b][pos[a:b]], np.sort(s[a:b][~pos[a:b]])
        if len(sp) and len(sn):
            out.append(np.mean((np.searchsorted(sn, sp, 'left') + np.searchsorted(sn, sp, 'right')) / 2 / len(sn)))
    return float(np.mean(out)) if out else float('nan')


st_path = OUT + tag + '.state.pkl'
if args.objective == 'hgbc':
    # restatement-exp's fit: HGB classifier, 100 iterations, 15 leaves, balanced class weight; seeded label on S120 rows
    m = HistGradientBoostingClassifier(max_iter=100, max_leaf_nodes=15, learning_rate=.1, min_samples_leaf=10, class_weight='balanced', random_state=0)
    m.fit(Xt, yt)
    models = [m]
    done_rounds = 100
else:
    models, done_rounds = [], 0
    if os.path.exists(st_path):
        models, done_rounds = pickle.load(open(st_path, 'rb'))
    s = np.zeros(len(yt))
    for m in models:
        s += m.predict(Xt)
    rng = np.random.default_rng(done_rounds)
    last = time.time()
    while done_rounds < args.rounds and time.time() - T0 < args.seconds:
        t1 = time.time()
        g_, h_, loss = grads(s)
        # rows of this tree
        sel = np.zeros(len(yt), bool)
        wmul = np.ones(len(yt))
        sel[pos] = True
        for g in range(G):
            a, b = starts[g], starts[g] + ng[g]
            neg = np.nonzero(~pos[a:b])[0] + a
            if len(neg) == 0:
                continue
            top = neg[np.argsort(-s[neg])[:256]]
            sel[top] = True
            rest = np.setdiff1d(neg, top, assume_unique=True)
            keep = rest[rng.random(len(rest)) < 1 / 6]
            sel[keep] = True
            wmul[keep] = 6.0
        hh = np.maximum(h_, 1e-4 * max(h_[sel].mean(), 1e-12))
        tgt = -g_ / hh
        reg = HistGradientBoostingRegressor(max_iter=1, max_leaf_nodes=args.leaves, learning_rate=args.step, min_samples_leaf=40, l2_regularization=1.0, max_bins=64, early_stopping=False, random_state=0)
        reg.fit(Xt[sel], tgt[sel], sample_weight=(hh * wmul)[sel])
        s += reg.predict(Xt)
        models.append(reg)
        done_rounds += 1
        print('round', done_rounds, 'loss %.4f' % loss, 'rows in tree', int(sel.sum()), 'seconds %.2f' % (time.time() - t1), flush=True)
    pickle.dump((models, done_rounds), open(st_path, 'wb'))
    print('pooled AUC (record only) %.3f' % auc_pooled(s), 'rounds done', done_rounds, 'of', args.rounds)
    el = time.time() - T0
    if done_rounds < args.rounds:
        print('NOT FINISHED: rounds left', args.rounds - done_rounds)
if args.objective == 'hgbc' or done_rounds >= args.rounds:
    # score the fold's tasks: N600 rows of the left-out tasks
    if args.fold != 'all':
        E = DT.load(['n600'], args.features, only_tasks=set(FOLDS[int(args.fold)]))
        sc = np.zeros(len(E['y']))
        for m in models:
            sc += m.decision_function(E['X']) if args.objective == 'hgbc' else m.predict(E['X'])
        np.savez_compressed(OUT + tag + '.scores.npz', score=sc, node=E['node'], pool=E['pool'], tasks=np.array([p[1] for p in E['pools']]), pool_sizes=np.array([p[2] for p in E['pools']]), y=E['y'])
        print('scored', len(sc), 'rows of', len(E['pools']), 'tasks', 'total s', round(time.time() - T0, 1))
        if s120_held:
            E2 = DT.load(['s120'], args.features, only_tasks=s120_held)
            sc2 = np.zeros(len(E2['y']))
            for m in models:
                sc2 += m.decision_function(E2['X']) if args.objective == 'hgbc' else m.predict(E2['X'])
            np.savez_compressed(OUT + tag + '.scores-s120.npz', score=sc2, node=E2['node'], tasks=np.array([p[1] for p in E2['pools']]), pool_sizes=np.array([p[2] for p in E2['pools']]))
            print('scored', len(sc2), 'held-out S120 rows of', len(E2['pools']), 'tasks')
        elif 's120' not in srcs:
            # S120 rows are held out of this model: score them too, for the Ident cell read of features_node_tune_read.py
            E2 = DT.load(['s120'], args.features)
            sc2 = np.zeros(len(E2['y']))
            for m in models:
                sc2 += m.decision_function(E2['X']) if args.objective == 'hgbc' else m.predict(E2['X'])
            np.savez_compressed(OUT + tag + '.scores-s120.npz', score=sc2, node=E2['node'], tasks=np.array([p[1] for p in E2['pools']]), pool_sizes=np.array([p[2] for p in E2['pools']]))
            print('scored', len(sc2), 'S120 rows of', len(E2['pools']), 'tasks')
