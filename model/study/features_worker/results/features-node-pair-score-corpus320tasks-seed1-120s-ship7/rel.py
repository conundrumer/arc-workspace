"""Per lib relation / construction: does content add over non-content features? Seeded pairs only, task-grouped folds.
Usage: rel.py TAG MINPOS MINTASKS"""
import sys, re, glob, pickle, json, collections, itertools
import numpy as np
from common import *
from evalpair import mk, task_auc, mean, boot, HGB
from sklearn.ensemble import HistGradientBoostingClassifier

TAG, MINPOS, MINT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
NC = ('st_', 'kd_', 'cl_', 'ty_', 'tc_', 'sz_')
WORD = re.compile(r'\((?!:)([A-Za-z_][A-Za-z_0-9.]*)')
SUFFIX = re.compile(r'\(&f\d+\.([A-Za-z_]+)')
KEY = {'DET', 'RULE', 'INIT'}


def rels(clause):
    """Library relation and construction identities of one clause. A pool reference &fN is dropped; its .method suffix is kept."""
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
        if w in ('OR', 'NOT', 'IF'):
            out.add('cx:' + w)
        else:
            out.add('bi:' + w)
    for m in SUFFIX.findall(clause):
        out.add('out:' + m)
    return out


# ---- load seeded pairs with tokens
rows = []; names = None
noderel = {}
for f in sorted(glob.glob(f'{SCR}/cache/*.pairs.{TAG}.pkl')):
    d = pickle.load(open(f, 'rb'))
    t = d['task']
    nodes = {n['token']: n for n in read_nodes(t)} if False else None
    sel = [(a, b, p, rd, ft) for a, b, p, rd, ft in d['rows'] if d['info'][a]['seeded'] and d['info'][b]['seeded']]
    if not sel:
        continue
    nd = {n['token']: n['clause'] for n in read_nodes(t) if n['tags']['seeded']}
    for a, b, p, rd, ft in sel:
        ia, ib = d['info'][a], d['info'][b]
        rows.append((t, p, min(ia['score'], ib['score']), max(ia['score'], ib['score']), ft, rels(nd[ia['tok']]), rels(nd[ib['tok']])))
names = sorted({k for r in rows for k in r[4]})
ix = {n: i for i, n in enumerate(names)}
X = np.full((len(rows), len(names)), np.nan, np.float32)
for i, r in enumerate(rows):
    for k, v in r[4].items():
        X[i, ix[k]] = v
task = np.array([r[0] for r in rows]); y = np.array([r[1] for r in rows]); S = np.array([[r[2], r[3]] for r in rows], np.float32)
RA = [r[5] for r in rows]; RB = [r[6] for r in rows]
print('tasks', len(set(task)), 'pairs', len(y), 'pos', int(y.sum()))

# ---- 1. counts per relation (a pair has a relation if either node has it) and per relation pair
cnt_pos = collections.Counter(); cnt_all = collections.Counter(); cnt_tasks = collections.defaultdict(set)
pcnt_pos = collections.Counter(); pcnt_all = collections.Counter()
for i in range(len(y)):
    u = RA[i] | RB[i]
    for r in u:
        cnt_all[r] += 1
        if y[i]:
            cnt_pos[r] += 1; cnt_tasks[r].add(task[i])
    for ra in RA[i]:
        for rb in RB[i]:
            k = tuple(sorted((ra, rb)))
            pcnt_all[k] += 1
            if y[i]:
                pcnt_pos[k] += 1
print('\nrelation / construction: positives, pairs, rate, tasks with a positive (pair has it in either node)')
for r, c in cnt_pos.most_common(45):
    print(f'  {r:24s} pos {c:4d} pairs {cnt_all[r]:6d} rate {c / cnt_all[r]:.3f} tasks {len(cnt_tasks[r])}')
print('\nrelation pairs (one in each node), top by positives (kind:/cx: omitted)')
shown = 0
for k, c in pcnt_pos.most_common():
    if any(x.startswith(('kind:', 'cx:')) for x in k):
        continue
    print(f'  {k[0]:20s} x {k[1]:20s} pos {c:3d} pairs {pcnt_all[k]:5d} rate {c / pcnt_all[k]:.3f}')
    shown += 1
    if shown >= 20:
        break

# ---- 2. fits
base_nc = [i for i, n in enumerate(names) if n.startswith(NC)]
content = [i for i, n in enumerate(names) if not n.startswith(NC)]
use = [r for r, c in cnt_pos.items() if c >= MINPOS and len(cnt_tasks[r]) >= MINT and not r.startswith('kind:')]
use += [r for r, c in cnt_pos.items() if r.startswith('kind:') and c >= MINPOS]
use = sorted(use)
print('\nrelations tested (>= %d positives and >= %d tasks with a positive): %d' % (MINPOS, MINT, len(use)))
flags = np.array([[float(r in (RA[i] | RB[i])) for r in use] for i in range(len(y))], np.float32)
tasks_u = np.unique(task)
SEEDS = (0, 1, 2)


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


A1 = pooled(np.hstack([S, X[:, base_nc]]))
A2 = pooled(np.hstack([S, X[:, base_nc + content]]))
A3a = pooled(np.hstack([S, X[:, base_nc], flags]))
A3b = pooled(np.hstack([S, X[:, base_nc + content], flags]))


def local(cols, mask):
    """Fit on the relation's pairs alone."""
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


def pval(d, n=4000, seed=1):
    ts = sorted(d)
    v = np.array([d[t] for t in ts]); rng = np.random.RandomState(seed)
    bs = np.array([v[rng.randint(0, len(v), len(v))].mean() for _ in range(n)])
    return v.mean(), np.percentile(bs, 2.5), np.percentile(bs, 97.5), min(1.0, 2 * min((bs <= 0).mean(), (bs >= 0).mean()) + 1.0 / n), len(v)


def diff(a, b):
    return {t: b[t] - a[t] for t in set(a) & set(b)}


allmask = np.ones(len(y), bool)
for nm, a, b in (('pooled, no flags: nc -> nc+content', A1, A2), ('relation flags in both: nc+flags -> nc+content+flags', A3a, A3b), ('flags only, no content: nc -> nc+flags', A1, A3a)):
    g = pval(diff(task_auc({'task': task}, a, allmask, y=y), task_auc({'task': task}, b, allmask, y=y)))
    print(f'ALL seeded pairs, {nm}: gain {g[0]:+.3f} [{g[1]:+.3f},{g[2]:+.3f}] over {g[4]} tasks')
res = []
print('\ncontent gain (AUC of non-content+content minus non-content), inside each relation; pairs where either node has it')
print('  columns: pos/tasks | pooled arm2 | pooled with relation flags (arm3a: nc+flags -> nc+content+flags) | fit on relation alone (arm3b)')
hdr = []
for j, r in enumerate(use):
    mask = flags[:, j] == 1
    npos = int(y[mask].sum()); nt = len(set(task[mask & (y == 1)]))
    a1, a2 = task_auc({'task': task}, A1, mask, y=y), task_auc({'task': task}, A2, mask, y=y)
    g2 = pval(diff(a1, a2))
    a3a, a3b = task_auc({'task': task}, A3a, mask, y=y), task_auc({'task': task}, A3b, mask, y=y)
    g3 = pval(diff(a3a, a3b))
    l1 = local(base_nc, mask); l2 = local(base_nc + content, mask)
    g4 = pval(diff(task_auc({'task': task}, l1, mask, y=y), task_auc({'task': task}, l2, mask, y=y)))
    res.append((r, npos, nt, g2, g3, g4, mean(a1)))
    print(f'  {r:22s} pos {npos:4d} tasks {nt:3d} | pooled {g2[0]:+.3f} [{g2[1]:+.3f},{g2[2]:+.3f}] p={g2[3]:.3f} | flags {g3[0]:+.3f} [{g3[1]:+.3f},{g3[2]:+.3f}] p={g3[3]:.3f} | alone {g4[0]:+.3f} [{g4[1]:+.3f},{g4[2]:+.3f}] p={g4[3]:.3f} | nc AUC {mean(a1):.3f} n={g2[4]}', flush=True)


def holm(ps):
    o = np.argsort(ps); m = len(ps); adj = np.zeros(m); run = 0
    for rank, i in enumerate(o):
        run = max(run, (m - rank) * ps[i]); adj[i] = min(1.0, run)
    return adj


print('\nHolm-adjusted p over %d relations' % len(use))
for nm, idx in (('pooled arm2', 3), ('relation flags arm3', 4), ('alone arm3b', 5)):
    adj = holm([r[idx][3] for r in res])
    sig = [(res[i][0], round(res[i][idx][0], 3), round(adj[i], 3)) for i in range(len(res)) if adj[i] < 0.1]
    print(f'  {nm}: relations with adjusted p < 0.1: {sig}; raw p < 0.05: {[(r[0], round(r[idx][0], 3)) for r in res if r[idx][3] < 0.05]}')

# ---- held-back check: choose relations with a positive gain on half the tasks, read the gain on the other half
rng = np.random.RandomState(11)
print('\nheld-back check (pooled arm2 predictions): pick relations with gain > 0.02 on task half A, read half B; and the reverse')
for rep in range(3):
    half = {t: rng.rand() < 0.5 for t in tasks_u}
    ha = np.array([half[t] for t in task])
    out = []
    for A_, B_ in ((ha, ~ha), (~ha, ha)):
        picked = []; gains = []
        for j, r in enumerate(use):
            m = flags[:, j] == 1
            a1 = task_auc({'task': task}, A1, m & A_, y=y); a2 = task_auc({'task': task}, A2, m & A_, y=y)
            ga = mean(diff(a1, a2)) if len(set(a1) & set(a2)) >= 8 else 0
            if ga > 0.02:
                picked.append(r)
                b1 = task_auc({'task': task}, A1, m & B_, y=y); b2 = task_auc({'task': task}, A2, m & B_, y=y)
                if len(set(b1) & set(b2)) >= 8:
                    gains.append(mean(diff(b1, b2)))
        out.append((len(picked), float(np.mean(gains)) if gains else float('nan')))
    print(f'  split {rep}: picked on A: {out[0][0]}, mean gain on B {out[0][1]:+.3f}; picked on B: {out[1][0]}, mean gain on A {out[1][1]:+.3f}')
