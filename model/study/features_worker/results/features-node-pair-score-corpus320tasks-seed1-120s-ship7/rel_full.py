"""Relation test on the full pool, resumable. Each call works for about BUDGET seconds, caches finished stages, and exits with status 3 if not done.
Usage: rel_full.py TAG   (rerun until it prints the report)"""
import sys, re, glob, pickle, json, collections, os, time
import numpy as np
from common import *
from evalpair import mk, task_auc, mean, HGB

TAG = sys.argv[1]
BUDGET = 100
T0 = time.time()
NC = ('st_', 'kd_', 'cl_', 'ty_', 'tc_', 'sz_')
WORD = re.compile(r'\((?!:)([A-Za-z_][A-Za-z_0-9.]*)')
SUFFIX = re.compile(r'\(&f\d+\.([A-Za-z_]+)')
KEY = {'DET', 'RULE', 'INIT'}
USE = ['bi:axis_elem', 'bi:axis_of', 'bi:cell', 'bi:dir_elem', 'bi:input', 'bi:key', 'bi:margin', 'bi:member', 'bi:node', 'bi:split', 'cx:NOT',
       'dom:AxisDomain', 'dom:DirDomain', 'dom:DominantColor', 'kind:DET', 'kind:INIT', 'kind:RULE', 'op:BoundingBox', 'op:Connectivity', 'out:box', 'out:component']
SEEDS = (0, 1, 2)


def over():
    return time.time() - T0 > BUDGET


def stage(name, fn):
    p = f'{SCR}/cache/relfull_{TAG}.{name}.pkl'
    if os.path.exists(p):
        return pickle.load(open(p, 'rb'))
    if over():
        print('budget used; rerun to continue (waiting on %s)' % name); sys.exit(3)
    v = fn()
    pickle.dump(v, open(p + '.tmp', 'wb')); os.replace(p + '.tmp', p)
    return v


def rels(clause):
    out = set()
    toks = clause.replace('(', ' (').split()
    head = clause.split(' ', 1)[0].lstrip('(')
    out.add('kind:' + head)
    if head == 'INIT' and len(toks) > 2:
        out.add('op:' + re.sub(r'[^A-Za-z_]', '', toks[2]))
    if head == 'DET':
        m = re.match(r'\(DET &f\d+ ([A-Za-z_]+)\)\s*$', clause.strip())
        if m:
            out.add('dom:' + m[1])
    for w in WORD.findall(clause):
        if w in KEY:
            continue
        out.add(('cx:' + w) if w in ('OR', 'NOT', 'IF') else ('bi:' + w))
    for m in SUFFIX.findall(clause):
        out.add('out:' + m)
    return out


def load():
    rows = []
    for f in sorted(glob.glob(f'{SCR}/cache/*.pairs.{TAG}.pkl')):
        d = pickle.load(open(f, 'rb'))
        sel = [(a, b, p, ft) for a, b, p, rd, ft in d['rows'] if d['info'][a]['seeded'] and d['info'][b]['seeded']]
        if not sel:
            continue
        nd = {n['token']: n['clause'] for n in read_nodes(d['task']) if n['tags']['seeded']}
        for a, b, p, ft in sel:
            ia, ib = d['info'][a], d['info'][b]
            rows.append((d['task'], p, min(ia['score'], ib['score']), max(ia['score'], ib['score']), ft, rels(nd[ia['tok']]), rels(nd[ib['tok']])))
    return rows


rows = stage('load', load)
names = sorted({k for r in rows for k in r[4]})
ix = {n: i for i, n in enumerate(names)}
X = np.full((len(rows), len(names)), np.nan, np.float32)
for i, r in enumerate(rows):
    for k, v in r[4].items():
        X[i, ix[k]] = v
task = np.array([r[0] for r in rows]); y = np.array([r[1] for r in rows]); S = np.array([[r[2], r[3]] for r in rows], np.float32)
RA = [r[5] for r in rows]; RB = [r[6] for r in rows]
tasks_u = np.unique(task)
base_nc = [i for i, n in enumerate(names) if n.startswith(NC)]
content = [i for i, n in enumerate(names) if not n.startswith(NC)]
flags = np.array([[float(r in (RA[i] | RB[i])) for r in USE] for i in range(len(y))], np.float32)
DT = {'task': task}


def folds(sd):
    rng = np.random.RandomState(sd)
    perm = rng.permutation(len(tasks_u))
    fo = {t: i % 5 for i, t in zip(range(len(tasks_u)), tasks_u[perm])}
    return np.array([fo[t] for t in task])


def pooled(Z):
    out = np.zeros(len(y))
    for sd in SEEDS:
        f = folds(sd)
        for k in range(5):
            m = mk().fit(Z[f != k], y[f != k])
            out[f == k] += m.predict_proba(Z[f == k])[:, 1] / len(SEEDS)
    return out


def local(cols, mask):
    out = np.zeros(len(y))
    Z = np.hstack([S, X[:, cols]])
    for sd in SEEDS:
        f = folds(sd)
        for k in range(5):
            tr = (f != k) & mask
            if y[tr].sum() < 5:
                continue
            m = HGB(max_depth=3, max_iter=80, learning_rate=0.06, min_samples_leaf=15, l2_regularization=1.0, random_state=0).fit(Z[tr], y[tr])
            te = (f == k) & mask
            out[te] += m.predict_proba(Z[te])[:, 1] / len(SEEDS)
    return out


A1 = stage('A1', lambda: pooled(np.hstack([S, X[:, base_nc]])))
A2 = stage('A2', lambda: pooled(np.hstack([S, X[:, base_nc + content]])))
A3a = stage('A3a', lambda: pooled(np.hstack([S, X[:, base_nc], flags])))
A3b = stage('A3b', lambda: pooled(np.hstack([S, X[:, base_nc + content], flags])))
LOC = {}
for j, r in enumerate(USE):
    mask = flags[:, j] == 1
    LOC[r] = stage('loc_' + r.replace(':', '_'), lambda: (local(base_nc, mask), local(base_nc + content, mask)))


def diff(a, b):
    return {t: b[t] - a[t] for t in set(a) & set(b)}


def pval(d, n=4000, seed=1):
    v = np.array([d[t] for t in sorted(d)]); rng = np.random.RandomState(seed)
    bs = np.array([v[rng.randint(0, len(v), len(v))].mean() for _ in range(n)])
    return v.mean(), np.percentile(bs, 2.5), np.percentile(bs, 97.5), min(1.0, 2 * min((bs <= 0).mean(), (bs >= 0).mean()) + 1.0 / n), len(v)


def holm(ps):
    o = np.argsort(ps); m = len(ps); adj = np.zeros(m); run = 0
    for rank, i in enumerate(o):
        run = max(run, (m - rank) * ps[i]); adj[i] = min(1.0, run)
    return adj


print('tasks', len(tasks_u), 'seeded pairs', len(y), 'positives', int(y.sum()))
allm = np.ones(len(y), bool)
for nm, a, b in (('pooled, no flags: nc -> nc+content', A1, A2), ('flags in both: nc+flags -> nc+content+flags', A3a, A3b), ('flags only, no content: nc -> nc+flags', A1, A3a)):
    g = pval(diff(task_auc(DT, a, allm, y=y), task_auc(DT, b, allm, y=y)))
    print(f'ALL seeded pairs, {nm}: gain {g[0]:+.3f} [{g[1]:+.3f},{g[2]:+.3f}] over {g[4]} tasks')
res = []
print('\nrelation | positives | tasks with a positive | pairs | pooled (arm2) | flags (3b-3a) | alone (3c) | nc AUC')
for j, r in enumerate(USE):
    m = flags[:, j] == 1
    npos = int(y[m].sum()); nt = len(set(task[m & (y == 1)]))
    a1, a2, a3a, a3b = (task_auc(DT, A, m, y=y) for A in (A1, A2, A3a, A3b))
    l1, l2 = LOC[r]
    g2 = pval(diff(a1, a2)); g3 = pval(diff(a3a, a3b)); g4 = pval(diff(task_auc(DT, l1, m, y=y), task_auc(DT, l2, m, y=y)))
    res.append((r, g2, g3, g4))
    print(f'  {r:20s} {npos:4d} {nt:3d} {int(m.sum()):6d} | {g2[0]:+.3f} [{g2[1]:+.3f},{g2[2]:+.3f}] p={g2[3]:.3f} | {g3[0]:+.3f} [{g3[1]:+.3f},{g3[2]:+.3f}] p={g3[3]:.3f} | {g4[0]:+.3f} [{g4[1]:+.3f},{g4[2]:+.3f}] p={g4[3]:.3f} | {mean(a1):.3f} n={g2[4]}')
print('\nHolm over %d relations' % len(USE))
for nm, idx in (('pooled arm2', 1), ('flags arm3', 2), ('alone arm3c', 3)):
    adj = holm([r[idx][3] for r in res])
    print(f'  {nm}: adjusted p<0.1: {[(res[i][0], round(res[i][idx][0], 3), round(adj[i], 3)) for i in range(len(res)) if adj[i] < 0.1]}; raw p<0.05: {[(r[0], round(r[idx][0], 3)) for r in res if r[idx][3] < 0.05]}')

print('\nheld-back check: pick relations with gain > 0.02 on task half A, read the gain on half B (and reverse); 6 random splits')
rng = np.random.RandomState(11)
for nm, P0, P1 in (('pooled arm2', A1, A2), ('flags arm3', A3a, A3b)):
    outs = []
    for rep in range(6):
        half = {t: rng.rand() < 0.5 for t in tasks_u}
        ha = np.array([half[t] for t in task])
        for A_, B_ in ((ha, ~ha), (~ha, ha)):
            picked = 0; gains = []
            for j, r in enumerate(USE):
                m = flags[:, j] == 1
                a0 = task_auc(DT, P0, m & A_, y=y); a1 = task_auc(DT, P1, m & A_, y=y)
                if len(set(a0) & set(a1)) < 8 or mean(diff(a0, a1)) <= 0.02:
                    continue
                picked += 1
                b0 = task_auc(DT, P0, m & B_, y=y); b1 = task_auc(DT, P1, m & B_, y=y)
                if len(set(b0) & set(b1)) >= 8:
                    gains.append(mean(diff(b0, b1)))
            outs.append((picked, float(np.mean(gains)) if gains else float('nan')))
    g = [o[1] for o in outs if o[1] == o[1]]
    print(f'  {nm}: relations picked per split {[o[0] for o in outs]}; mean held-out gain {np.mean(g):+.3f} over {len(g)} splits (per-split {[round(x, 3) for x in g]})')
