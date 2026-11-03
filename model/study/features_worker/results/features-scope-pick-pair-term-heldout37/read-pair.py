"""The read of the pair term on the scope pick: one JSON line per section in reads.jsonl. A section already in the file is skipped on a rerun.

Rows: scope-rows.tsv (facts), label-rows.tsv, cover-slot-rows.tsv (labels), visit-slot-rows.tsv, and from the earlier records map-exposure-rows.tsv, form-rows.tsv, decompose.jsonl, fit-keyed.jsonl.

Matched sets: for a positive scope, negative scopes of the same run and kind: up to M/2 nearest before it and up to M/2 nearest after it in the run's order of scopes, at most W scopes away, with at least 1 on each side, so a positive early in a run isn't compared only with later scopes. A negative has no cover event of any kind. Both have pair facts: at least 2 leaf forms and all forms in the bank.

AUC of a fact: per positive, the share of its matched negatives it beats, ties 1/2; mean over positives of a task; mean over tasks. The interval resamples tasks. The control moves the positive to a random member of each matched set.

Tilt: a pick by node score plus a pair term has P'(S) proportional to P(S) e^g(S), with g = beta x. For the pool at one time, E'[h] = E[h e^g] / E[e^g]. So each drawn scope takes the weight m = e^g / Z. Z is the tries-weighted mean of e^g in a block of B consecutive scopes of the run, which keeps the proposals of the block. beta is a conditional logistic fit on the matched sets of the other tasks, with fixed ridge.
"""
import collections
import csv
import json
import math
import os
import sys
import time

import numpy as np

HERE = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-scope-pick-pair-term-heldout37/'
MAP = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-kind-pick-given-scope-contents-heldout37/'
BASE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-base-cost-read-heldout37/'
OUT = HERE + 'reads.jsonl'
SEED = 20261101
BOOT = 2000
SHUF = 200
M, W, B = 6, 30, 20
RIDGE = 1.0
FACTS = ('coltype', 'ident', 'join', 'overlap', 'overlap_P', 'overlap_C', 'overlap_N', 'overlap_I', 'overlap_O', 'lineage')
MAIN = ('coltype', 'ident', 'join', 'overlap')
LABELS = ('first', 'any', 'first_r1', 'first_r2', 'any_r2', 'first_late', 'hold1', 'hold2')
KINDS = ('RULE', 'DET', 'INIT')
t00 = time.time()
have = {json.loads(l)['section'] for l in open(OUT)} if os.path.exists(OUT) else set()
out = open(OUT, 'a')


def emit(name, value):
    out.write(json.dumps(dict(section=name, value=value)) + '\n')
    out.flush()
    print('%s at %.1f s' % (name, time.time() - t00), flush=True)


rows = list(csv.DictReader(open(HERE + 'scope-rows.tsv'), delimiter='\t'))
ix = {(r['arm'], r['task'], r['slot']): i for i, r in enumerate(rows)}
n = len(rows)
tasks = sorted({r['task'] for r in rows})
TI = {t: i for i, t in enumerate(tasks)}
runs = sorted({(r['arm'], r['task']) for r in rows})
RI = {x: i for i, x in enumerate(runs)}
task = np.array([TI[r['task']] for r in rows])
run = np.array([RI[r['arm'], r['task']] for r in rows])
order = np.array([int(r['order']) for r in rows])
kind = np.array([r['kind'] for r in rows])
size = np.array([r['size'] for r in rows])
tries = np.array([float(r['tries']) for r in rows])
has = np.array([r['coltype_mean'] != '' for r in rows])
FC = [k + x for k in FACTS for x in ('_mean', '_max')]
F = {c: np.array([float(r[c]) if r[c] != '' else np.nan for r in rows]) for c in FC}
F['forms'] = np.log2(np.array([float(r['forms']) + 1 for r in rows]))
for c in ('score_mean', 'score_max'):
    F[c] = np.array([float(r[c]) if r[c] != '' else np.nan for r in rows])
F['depth'] = np.array([float(r['depth']) if r['depth'] != '' else np.nan for r in rows])
F['order'] = order.astype(float)
F['d0'] = np.array([float(r['d0']) for r in rows])
has &= ~np.isnan(F['score_mean'])
vslot = {(r['arm'], r['task'], r['visit']): ix[r['arm'], r['task'], r['slot']] for r in csv.DictReader(open(HERE + 'visit-slot-rows.tsv'), delimiter='\t')}

# labels
Y = {k: np.zeros(n) for k in LABELS}
for r in csv.DictReader(open(HERE + 'label-rows.tsv'), delimiter='\t'):
    i = ix[r['arm'], r['task'], r['slot']]
    for k in ('first', 'any', 'first_r1', 'first_r2', 'first_late'):
        Y[k][i] = int(r[k])
covers = list(csv.DictReader(open(HERE + 'cover-slot-rows.tsv'), delimiter='\t'))
for r in covers:
    if int(r['clause_parents']) >= 2:
        Y['any_r2'][ix[r['arm'], r['task'], r['slot']]] += 1
forms = {}
for r in csv.DictReader(open(BASE + 'form-rows.tsv'), delimiter='\t'):
    if r['arm'].startswith('base'):
        forms[r['arm'], r['task'], r['form']] = r
fit = {}
for l in open(BASE + 'fit-keyed.jsonl'):
    q = json.loads(l)
    fit[q['section']] = q['value']
S_OF = {k: fit['earlier']['base all ' + k]['s'] for k in ('any',) + KINDS}
dec = {}
for l in open(BASE + 'decompose.jsonl'):
    q = json.loads(l)
    if q['section'] == 'identity':
        dec = q['value']
# exposure of forms in scopes that hold their read forms, up to the first cover: the `out` term of decompose.py
ER = collections.defaultdict(list)  # task index: (form key index, slot index, n)
FK, FI = [], {}
for r in csv.DictReader(open(MAP + 'map-exposure-rows.tsv'), delimiter='\t'):
    if not r['arm'].startswith('base'):
        continue
    key = r['arm'], r['task'], r['form']
    f = forms[key]
    if f['bits'] in ('', 'None') or f['own_key'] != '1':
        continue
    if key not in FI:
        FI[key] = len(FK)
        FK.append(f)
    s = vslot.get((r['arm'], r['task'], r['visit']))
    if s is None:
        continue
    ER[TI[r['task']]].append((FI[key], s, int(r['n'])))
    if int(f['nreads']) >= 1:
        Y['hold1'][s] = 1
    if int(f['nreads']) >= 2:
        Y['hold2'][s] = 1
ER = {t: np.array(v, dtype=np.int64) for t, v in ER.items()}
fbits = np.array([float(f['bits']) for f in FK])
fkind = np.array([f['kind'] for f in FK])
fw = {'any': 2.0 ** (-S_OF['any'] * fbits)}
for k in KINDS:
    fw[k] = 2.0 ** (-S_OF[k] * fbits)
# W and Wr of the out term, on all rows of decompose.py
R0 = []
for key, f in forms.items():
    if f['bits'] in ('', 'None') or f['own_key'] != '1':
        continue
    tot = sum(int(f[x]) for x in ('e_hk', 'e_hx', 'e_mk', 'e_mx'))
    held = int(f['e_hk']) + int(f['e_hx'])
    after = max(0, tot - int(f['ready_draw'])) if f['ready_draw'] != '' else 0
    R0.append((TI[f['task']], f['kind'], float(f['bits']), max(after, held), held))
tA = np.array([x[0] for x in R0])
kA = np.array([x[1] for x in R0])
bA = np.array([x[2] for x in R0])
rA = np.array([x[3] for x in R0], float)
hA = np.array([x[4] for x in R0], float)


RX, HX = [], []
for f in forms.values():
    if f['bits'] in ('', 'None') or f['own_key'] != '1':
        continue
    tot = sum(int(f[x]) for x in ('e_hk', 'e_hx', 'e_mk', 'e_mx'))
    held = int(f['e_hk']) + int(f['e_hx'])
    after = max(0, tot - int(f['ready_draw'])) if f['ready_draw'] != '' else 0
    RX.append(max(after, held))
    HX.append(held)


def wr_of(k):
    s = S_OF[k]
    m = np.ones(len(bA), bool) if k == 'any' else kA == k
    return m, 2.0 ** (-s * bA)


def make_sets(y, mask=None, same=None):
    """Matched sets: (positive index, [negative indices]). mask limits the rows, same is an extra array to match on."""
    ok = has if mask is None else has & mask
    neg = ok & (Y['any'] == 0) & (y == 0)
    pos = np.flatnonzero(ok & (y > 0))
    byrun = collections.defaultdict(list)
    for i in np.flatnonzero(neg):
        k = run[i], kind[i], (same[i] if same is not None else 0)
        byrun[k].append(i)
    for k in byrun:
        byrun[k] = np.array(sorted(byrun[k], key=lambda i: order[i]))
    out_, nomatch = [], 0
    for p in pos:
        c = byrun.get((run[p], kind[p], (same[p] if same is not None else 0)))
        if c is None:
            nomatch += 1
            continue
        d = order[c] - order[p]
        before = c[(d < 0) & (d >= -W)][-(M // 2):]
        after = c[(d > 0) & (d <= W)][:M // 2]
        if not len(before) or not len(after):
            nomatch += 1
            continue
        out_.append((p, np.concatenate([before, after])))
    return out_, nomatch


def pack(sets):
    P_ = np.array([p for p, _ in sets], dtype=np.int64)
    Nn = -np.ones((len(sets), M), dtype=np.int64)
    for i, (_, q) in enumerate(sets):
        Nn[i, :len(q)] = q
    return P_, Nn


def wins(x, P_, Nn):
    """Per positive, the share of its negatives beaten, ties 1/2."""
    a = x[P_][:, None]
    b = np.where(Nn >= 0, x[np.maximum(Nn, 0)], np.nan)
    w = (a > b) + .5 * (a == b)
    v = Nn >= 0
    return (w * v).sum(1) / v.sum(1)


def task_stat(u, tk):
    """Per task: sum of u, count."""
    return np.bincount(tk, u, minlength=len(tasks)), np.bincount(tk, minlength=len(tasks)).astype(float)


def auc_of(a, c):
    q = c > 0
    return float((a[q] / c[q]).mean()) if q.any() else float('nan')


def boot_auc(a, c, rng, nb=BOOT):
    got = []
    t = np.flatnonzero(c > 0)
    for _ in range(nb):
        i = t[rng.integers(0, len(t), len(t))]
        got.append((a[i] / c[i]).mean())
    return [round(float(np.quantile(got, .025)), 4), round(float(np.quantile(got, .975)), 4)]


def shuffled(x, P_, Nn, tk, rng, nb=SHUF):
    """AUC with the positive moved to a random member of each set."""
    S_ = np.concatenate([P_[:, None], Nn], 1)
    v = S_ >= 0
    vals = np.where(v, x[np.maximum(S_, 0)], np.nan)
    got = []
    for _ in range(nb):
        r = rng.random(S_.shape) * v
        pick = r.argmax(1)
        a = vals[np.arange(len(pick)), pick][:, None]
        keep = v.copy()
        keep[np.arange(len(pick)), pick] = False
        w = ((a > vals) + .5 * (a == vals)) * keep
        u = w.sum(1) / keep.sum(1)
        got.append(auc_of(*task_stat(u, tk)))
    return round(float(np.mean(got)), 4), [round(float(np.quantile(got, .025)), 4), round(float(np.quantile(got, .975)), 4)]


def read_fact(x, P_, Nn, seed):
    rng = np.random.default_rng(seed)
    tk = task[P_]
    u = wins(x, P_, Nn)
    a, c = task_stat(u, tk)
    return dict(auc=round(auc_of(a, c), 4), pooled=round(float(u.mean()), 4), range=boot_auc(a, c, rng))


def clogit(X, mask, ridge=RIDGE, iters=12):
    """beta of a conditional logit: X (sets, members, p), member 0 the positive; mask of real members."""
    p = X.shape[2]
    beta = np.zeros(p)
    for _ in range(iters):
        eta = X @ beta
        eta = np.where(mask, eta, -np.inf)
        eta -= eta.max(1, keepdims=True)
        w = np.exp(eta)
        w /= w.sum(1, keepdims=True)
        mean = (w[..., None] * X).sum(1)
        g = (X[:, 0] - mean).sum(0) - ridge * beta
        d = X - mean[:, None]
        H = np.einsum('ij,ijk,ijl->kl', w, d, d, optimize=True) + ridge * np.eye(p)
        step = np.linalg.solve(H, g)
        beta += step
        if np.abs(step).max() < 1e-5:
            break
    return beta


def design(cols):
    Z = np.stack([np.nan_to_num(F[c]) for c in cols], 1)
    return Z


def fit_loto(cols, P_, Nn, shuffle_rng=None):
    """{left-out task: (mu, sd, beta)}: fits on the sets of the other tasks."""
    Z = design(cols)
    S_ = np.concatenate([P_[:, None], Nn], 1)
    mask = S_ >= 0
    if shuffle_rng is not None:  # the positive moves to a random member of its set
        r = shuffle_rng.random(S_.shape) * mask
        pick = r.argmax(1)
        S2 = S_.copy()
        S2[np.arange(len(pick)), pick] = S_[:, 0]
        S2[:, 0] = S_[np.arange(len(pick)), pick]
        S_ = S2
        mask = S_ >= 0
    tk = task[P_]
    ok = np.unique(S_[mask])
    mu, sd = Z[ok].mean(0), Z[ok].std(0)
    sd = np.where(sd > 1e-9, sd, 1.0)
    X = (Z[np.maximum(S_, 0)] - mu) / sd
    out_ = {}
    for t in range(len(tasks)):
        tr = tk != t
        out_[t] = clogit(X[tr], mask[tr]) / sd if tr.sum() >= 5 else np.zeros(Z.shape[1])
    return Z, mu, out_


def score_loto(Z, mu, betas):
    g = np.zeros(n)
    for t, b in betas.items():
        q = task == t
        g[q] = (Z[q] - mu) @ b
    return g


RUNROWS = [np.flatnonzero((run == r) & has) for r in range(len(runs))]
for i, q in enumerate(RUNROWS):
    RUNROWS[i] = q[np.argsort(order[q])]


def tilt(g, block=B, c=1.0, skip=0):
    """Weights m of the scopes of each run. The first skip scopes of a run keep weight 1."""
    m = np.ones(n)
    for q in RUNROWS:
        q = q[skip:]
        if not len(q):
            continue
        bl = np.arange(len(q)) // block
        e = np.exp(np.clip(c * g[q], -30, 30))
        den = np.bincount(bl, tries[q] * e) / np.maximum(np.bincount(bl, tries[q]), 1e-9)
        m[q] = e / np.maximum(den[bl], 1e-12)
    return m


COV = dict(first=[], first_late=[], first_r2=[])
for r in covers:
    s = ix[r['arm'], r['task'], r['slot']]
    if r['first'] == '1':
        COV['first'].append((TI[r['task']], s, r['kind'], r['visit_kind']))
        if r['cond'] == '1':
            COV['first_late'].append((TI[r['task']], s, r['kind'], r['visit_kind']))
        if int(r['clause_parents']) >= 2:
            COV['first_r2'].append((TI[r['task']], s, r['kind'], r['visit_kind']))


def bits_of(m, rng, kinds=False):
    """Savings in bits under weights m, with 95% task ranges."""
    res = {}
    nt = len(tasks)

    def rate(a, c):
        return math.log2(a.sum() / c.sum()) if c.sum() else float('nan')

    def boot(fn, *arr):
        got = []
        for _ in range(BOOT // 2):
            i = rng.integers(0, nt, nt)
            v = fn(*[x[i] for x in arr])
            if v == v:
                got.append(v)
        return [round(float(np.quantile(got, .025)), 3), round(float(np.quantile(got, .975)), 3)] if got else None
    for name, L in COV.items():
        for k in (None,) + (KINDS if kinds else ()):
            q = [x for x in L if k is None or x[2] == k]
            a, c = np.zeros(nt), np.zeros(nt)
            for t, s, _, _ in q:
                a[t] += m[s]
                c[t] += 1
            res['%s %s' % (name, k or 'any')] = dict(saving=round(rate(a, c), 3), range=boot(rate, a, c), covers=int(c.sum()), tasks=int((c > 0).sum()))
    # the out term: W held in the left-out task under m over W held
    for k in (None,) + (KINDS if kinds else ()):
        wn = 'any' if k is None else k
        w = fw[wn]
        h0, h1 = np.zeros(nt), np.zeros(nt)
        for t, e in ER.items():
            fi, s, nn = e[:, 0], e[:, 1], e[:, 2]
            sel = np.ones(len(fi), bool) if k is None else fkind[fi] == k
            h0[t] = float((w[fi[sel]] * nn[sel]).sum())
            h1[t] = float((w[fi[sel]] * nn[sel] * m[s[sel]]).sum())
        res['out %s' % (k or 'any')] = dict(saving=round(rate(h1, h0), 3), range=boot(rate, h1, h0), rows=int(sum((fkind[e[:, 0]] == k).sum() if k else len(e) for e in ER.values())), tasks=int((h0 > 0).sum()))
    return res


MODELS = dict(pair=[k + x for k in MAIN for x in ('_mean', '_max')], lineage=['lineage_mean', 'lineage_max'], pair_lineage=[k + x for k in MAIN + ('lineage',) for x in ('_mean', '_max')],
              first_order=['forms', 'score_mean', 'score_max'], first_order_pair=['forms', 'score_mean', 'score_max'] + [k + x for k in MAIN for x in ('_mean', '_max')], size=['forms'], score=['score_mean', 'score_max'])
for f_ in FACTS:
    MODELS['alone ' + f_] = [f_ + '_mean', f_ + '_max']

SETS = {k: make_sets(Y[k]) for k in LABELS}
SETS_SIZE = {k: make_sets(Y[k], same=size) for k in ('first', 'any', 'first_r1', 'first_late')}


def sec_rows():
    d = dict(slots=n, slots_with_pair_facts=int(has.sum()), slots_missing_a_form=int(sum(r['missing'] != '0' for r in rows)), slots_empty_or_one_leaf=int(sum(r['missing'] == '0' and r['coltype_mean'] == '' for r in rows)), runs=len(runs), tasks=len(tasks), by_kind=dict(collections.Counter(kind.tolist())), by_size=dict(collections.Counter(size.tolist())), s_of=S_OF)
    d['positives'] = {k: dict(slots=int((Y[k] > 0).sum()), with_facts=int(((Y[k] > 0) & has).sum()), sets=len(SETS[k][0]), no_match=SETS[k][1], negatives_mean=round(float(np.mean([len(q) for _, q in SETS[k][0]])), 2) if SETS[k][0] else None, tasks=len({task[p] for p, _ in SETS[k][0]})) for k in LABELS}
    d['negatives_all'] = int((has & (Y['any'] == 0)).sum())
    # the out term rebuilt from the exposure rows, against decompose.py
    chk = {}
    for k in ('any',) + KINDS:
        q, w = wr_of(k)
        Wr, Wh = float((w[q] * rA[q]).sum()), float((w[q] * hA[q]).sum())
        wf = fw[k]
        e = 0.0
        for v in ER.values():
            sel = np.ones(len(v), bool) if k == 'any' else fkind[v[:, 0]] == k
            e += float((wf[v[sel, 0]] * v[sel, 2]).sum())
        chk[k] = dict(out_rebuilt=round(math.log2(Wr / Wh), 3), out_decompose=dec['base %s all' % k]['out'], from_exposure_rows=round(math.log2(Wr / e), 3))
    d['out_check'] = chk
    by = {}
    fr = [(int(f['nreads']), f['kind'], float(f['bits']), f) for f in forms.values() if f['bits'] not in ('', 'None') and f['own_key'] == '1']
    for name, test in (('0', lambda x: x == 0), ('1', lambda x: x == 1), ('2+', lambda x: x >= 2)):
        q = np.array([test(x[0]) for x in fr])
        Wr = sum(2.0 ** (-S_OF['any'] * x[2]) * rx for x, rx, ok in zip(fr, RX, q) if ok)
        Wh = sum(2.0 ** (-S_OF['any'] * x[2]) * hx for x, hx, ok in zip(fr, HX, q) if ok)
        by[name] = dict(form_rows=int(q.sum()), ready_rows=int(sum(x[3]['ready_draw'] != '' for x, ok in zip(fr, q) if ok)), rows_with_held_exposure=int(sum(hx > 0 for hx, ok in zip(HX, q) if ok)), covered=int(sum(x[3]['draw'] != '' for x, ok in zip(fr, q) if ok)), out=round(math.log2(Wr / Wh), 3) if Wh else None, share_of_W_ready=round(Wr / sum(2.0 ** (-S_OF['any'] * x[2]) * rx for x, rx in zip(fr, RX)), 4), share_of_W_held=round(Wh / sum(2.0 ** (-S_OF['any'] * x[2]) * hx for x, hx in zip(fr, HX)), 4))
    d['out_by_reads'] = by
    Wr_all = sum(2.0 ** (-S_OF['any'] * x[2]) * rx for x, rx in zip(fr, RX))
    Wh_all = sum(2.0 ** (-S_OF['any'] * x[2]) * hx for x, hx in zip(fr, HX))
    Wr_2 = sum(2.0 ** (-S_OF['any'] * x[2]) * rx for x, rx in zip(fr, RX) if x[0] >= 2)
    Wh_2 = sum(2.0 ** (-S_OF['any'] * x[2]) * hx for x, hx in zip(fr, HX) if x[0] >= 2)
    d['ceiling'] = dict(note='the out term if every proposal after the reads exist counted as held for forms with 2 or more reads, all other forms as they are', out_now=round(math.log2(Wr_all / Wh_all), 3), out_at_ceiling=round(math.log2(Wr_all / (Wh_all - Wh_2 + Wr_2)), 3), saving=round(math.log2((Wh_all - Wh_2 + Wr_2) / Wh_all), 3))
    return d


def sec_auc():
    res = {}
    for lab in LABELS:
        sets, _ = SETS[lab]
        if not sets:
            continue
        P_, Nn = pack(sets)
        tk = task[P_]
        d = {}
        rng = np.random.default_rng(SEED)
        for c in FC + ['forms', 'score_mean', 'score_max', 'depth', 'order', 'd0']:
            q = read_fact(np.nan_to_num(F[c]), P_, Nn, SEED)
            if lab in ('first', 'any'):
                q['shuffled'], q['shuffled_range'] = shuffled(np.nan_to_num(F[c]), P_, Nn, tk, rng)
            d[c] = q
        res[lab] = dict(sets=len(sets), tasks=len(set(tk.tolist())), facts=d)
        print(' ', lab, len(sets), round(time.time() - t00), flush=True)
    return res


def sec_auc_size():
    """The same AUC with negatives matched on the size bucket too."""
    res = {}
    for lab, (sets, nm) in SETS_SIZE.items():
        P_, Nn = pack(sets)
        res[lab] = dict(sets=len(sets), no_match=nm, tasks=len(set(task[P_].tolist())), facts={c: read_fact(np.nan_to_num(F[c]), P_, Nn, SEED) for c in FC + ['forms', 'score_mean', 'score_max', 'depth', 'order']})
    return res


def sec_together():
    res = {}
    for lab in LABELS:
        sets, _ = SETS[lab]
        if len(sets) < 10:
            continue
        P_, Nn = pack(sets)
        tk = task[P_]
        d = {}
        for name, cols in MODELS.items():
            if name.startswith('alone') and lab not in ('first', 'any', 'hold1'):
                continue
            Z, mu, betas = fit_loto(cols, P_, Nn)
            g = score_loto(Z, mu, betas)
            q = read_fact(g, P_, Nn, SEED)
            q['beta_median'] = {c: round(float(np.median([betas[t][i] for t in betas])), 3) for i, c in enumerate(cols)}
            d[name] = q
        rng = np.random.default_rng(SEED + 1)
        ctl = []
        for _ in range(50):
            Z, mu, betas = fit_loto(MODELS['pair'], P_, Nn, rng)
            g = score_loto(Z, mu, betas)
            ctl.append(auc_of(*task_stat(wins(g, P_, Nn), tk)))
        res[lab] = dict(sets=len(sets), models=d, shuffled_fit=dict(rounds=50, mean=round(float(np.mean(ctl)), 4), range=[round(float(np.quantile(ctl, .025)), 4), round(float(np.quantile(ctl, .975)), 4)]))
        print(' ', lab, len(sets), round(time.time() - t00), flush=True)
    return res


def sec_bits():
    res = {}
    for lab in ('first', 'any', 'hold1', 'first_r1', 'any_r2', 'first_late'):
        P_, Nn = pack(SETS[lab][0])
        d = {}
        for name, cols in MODELS.items():
            Z, mu, betas = fit_loto(cols, P_, Nn)
            g = score_loto(Z, mu, betas)
            rng = np.random.default_rng(SEED)
            m = tilt(g)
            q = bits_of(m, rng, kinds=not name.startswith('alone'))
            q['weights'] = dict(max=round(float(m[has].max()), 2), q99=round(float(np.quantile(m[has], .99)), 2), sd=round(float(m[has].std()), 3), ess_share=round(float(m[has].sum() ** 2 / (m[has] ** 2).sum() / has.sum()), 3))
            d[name] = q
        Z, mu, betas = fit_loto(MODELS['pair'], P_, Nn)
        g = score_loto(Z, mu, betas)
        sens = {}
        for bk in (5, 10, 20, 40):
            for c in (.5, 1.0, 2.0):
                sens['block %d beta x %.1f' % (bk, c)] = bits_of(tilt(g, bk, c), np.random.default_rng(SEED))
        sens['block 20 first 20 scopes untilted'] = bits_of(tilt(g, 20, 1.0, 20), np.random.default_rng(SEED))
        rng = np.random.default_rng(SEED + 2)
        ctl = collections.defaultdict(list)
        for _ in range(50):
            Z2, mu2, b2 = fit_loto(MODELS['pair'], P_, Nn, rng)
            m = tilt(score_loto(Z2, mu2, b2))
            a = sum(m[s] for _, s, _, _ in COV['first']) / len(COV['first'])
            ctl['first any'].append(math.log2(a))
            a = sum(m[s] for _, s, _, _ in COV['first_late']) / len(COV['first_late'])
            ctl['first_late any'].append(math.log2(a))
            h0 = h1 = 0.0
            for e in ER.values():
                w = fw['any'][e[:, 0]] * e[:, 2]
                h0 += float(w.sum())
                h1 += float((w * m[e[:, 1]]).sum())
            ctl['out any'].append(math.log2(h1 / h0))
        res[lab] = dict(sets=len(SETS[lab][0]), models=d, sensitivity=sens, shuffled_fit={k: dict(rounds=50, mean=round(float(np.mean(v)), 3), range=[round(float(np.quantile(v, .025)), 3), round(float(np.quantile(v, .975)), 3)]) for k, v in ctl.items()})
        print(' ', lab, len(SETS[lab][0]), round(time.time() - t00), flush=True)
    return res


def sec_gain():
    """first_order_pair against first_order on one resample of tasks: the AUC and the savings, per fit label."""
    res = {}
    for lab in ('first', 'any', 'hold1', 'first_r1', 'first_late'):
        P_, Nn = pack(SETS[lab][0])
        tk = task[P_]
        nt = len(tasks)
        st = {}
        for name in ('first_order', 'first_order_pair', 'size', 'pair'):
            Z, mu, betas = fit_loto(MODELS[name], P_, Nn)
            g = score_loto(Z, mu, betas)
            m = tilt(g)
            a, c = task_stat(wins(g, P_, Nn), tk)
            q = {}
            for cn in ('first', 'first_late'):
                x, y = np.zeros(nt), np.zeros(nt)
                for t, s_, _, _ in COV[cn]:
                    x[t] += m[s_]
                    y[t] += 1
                q[cn] = x, y
            x, y = np.zeros(nt), np.zeros(nt)
            for t, e in ER.items():
                w = fw['any'][e[:, 0]] * e[:, 2]
                y[t] = float(w.sum())
                x[t] = float((w * m[e[:, 1]]).sum())
            q['out'] = x, y
            st[name] = (a, c), q
        rng = np.random.default_rng(SEED + 3)
        d = {}
        for hi, lo in (('first_order_pair', 'first_order'), ('pair', 'size')):
            pts = {k: auc_of(*st[hi][0]) - auc_of(*st[lo][0]) if k == 'auc' else math.log2(st[hi][1][k][0].sum() / st[hi][1][k][1].sum()) - math.log2(st[lo][1][k][0].sum() / st[lo][1][k][1].sum()) for k in ('auc', 'first', 'first_late', 'out')}
            got = collections.defaultdict(list)
            for _ in range(BOOT // 2):
                i = rng.integers(0, nt, nt)
                ok = st[hi][0][1][i] > 0
                if ok.any():
                    got['auc'].append((st[hi][0][0][i][ok] / st[hi][0][1][i][ok]).mean() - (st[lo][0][0][i][ok] / st[lo][0][1][i][ok]).mean())
                for k in ('first', 'first_late', 'out'):
                    a1, b1 = st[hi][1][k]
                    a0, b0 = st[lo][1][k]
                    if b1[i].sum() and a1[i].sum() and a0[i].sum():
                        got[k].append(math.log2(a1[i].sum() / b1[i].sum()) - math.log2(a0[i].sum() / b0[i].sum()))
            d['%s less %s' % (hi, lo)] = {k: dict(gain=round(float(pts[k]), 4), range=[round(float(np.quantile(v, .025)), 4), round(float(np.quantile(v, .975)), 4)]) for k, v in got.items()}
        res[lab] = d
        print(' ', lab, round(time.time() - t00), flush=True)
    return res


def cell_row(name, sets, g, m, want_bits=None):
    P_, Nn = pack(sets) if sets else (np.zeros(0, int), np.zeros((0, M), int))
    if not len(P_):
        return dict(cell=name, rows=0, tasks=0, thin=True)
    tk = task[P_]
    nt = len(set(tk.tolist()))
    rngs = {}
    for c, x in (('together', g), ('coltype_mean', F['coltype_mean']), ('coltype_max', F['coltype_max']), ('ident_max', F['ident_max']), ('join_mean', F['join_mean']), ('join_max', F['join_max']), ('overlap_mean', F['overlap_mean']), ('overlap_max', F['overlap_max'])):
        rngs[c] = read_fact(np.nan_to_num(x), P_, Nn, SEED)
    r = dict(cell=name, rows=len(P_), tasks=nt, thin=bool(len(P_) < 50 or nt < 8), auc=rngs)
    return r


def sec_cells():
    res = {}
    for lab in ('first', 'any'):
        sets, _ = SETS[lab]
        P_, Nn = pack(sets)
        Z, mu, betas = fit_loto(MODELS['pair'], P_, Nn)
        g = score_loto(Z, mu, betas)
        m = tilt(g)
        tab = []
        for k in KINDS:
            tab.append(cell_row('kind ' + k, [s for s in sets if kind[s[0]] == k], g, m))
        for sz in ('3-4', '5-8', '9-16', '17+'):
            s2, _ = make_sets(Y[lab], mask=size == sz)
            tab.append(cell_row('size ' + sz, s2, g, m))
        for k in KINDS:
            for sz in ('5-8', '9-16'):
                s2, _ = make_sets(Y[lab], mask=(size == sz) & (kind == k))
                tab.append(cell_row('kind %s size %s' % (k, sz), s2, g, m))
        res[lab] = tab
    # the saving by kind of the gold form under the tilt fitted on first covers
    P_, Nn = pack(SETS['first'][0])
    Z, mu, betas = fit_loto(MODELS['pair'], P_, Nn)
    m = tilt(score_loto(Z, mu, betas))
    res['bits_by_kind'] = bits_of(m, np.random.default_rng(SEED), kinds=True)
    sz = {}
    for b_ in ('5-8', '9-16', '17+'):
        v = [x for x in COV['first'] if size[x[1]] == b_]
        a = np.zeros(len(tasks))
        c = np.zeros(len(tasks))
        for t, s, _, _ in v:
            a[t] += m[s]
            c[t] += 1
        sz[b_] = dict(log2_mean_weight=round(math.log2(a.sum() / c.sum()), 3) if c.sum() else None, covers=int(c.sum()), tasks=int((c > 0).sum()), thin=bool(c.sum() < 50 or (c > 0).sum() < 8))
    res['bits_by_size'] = sz
    return res


def sec_cost():
    import array
    import pickle
    import sys as _s
    v = np.array([float(r['pair_ms']) for r, h in zip(rows, has) if h])
    rel, form_, run_, mem = [], [], [], []
    for a, t in runs:
        d = pickle.load(open(HERE + 'sketches/%s-%s.pkl' % (a, t), 'rb'))
        tot = 0
        for f, q in d.items():
            b = [sum(len(x) + 6 for c in sk['cols'] for _, x in c.values()) for sk in q]
            rel += b
            form_.append(sum(b))
            tot += sum(b)
            for sk in q:
                mm = 0
                for c in sk['cols']:
                    for _, x in c.values():
                        u = array.array('I')
                        u.frombytes(x)
                        mm += _s.getsizeof(frozenset(u)) + 32 * len(u) + 80
                mem.append(mm)
        run_.append(tot)
    q5 = lambda x: dict(median=int(np.median(x)), p90=int(np.quantile(x, .9)), largest=int(np.max(x)))  # noqa: E731
    sk = list(csv.DictReader(open(HERE + 'cost-sketch-rows.tsv'), delimiter='\t')) if os.path.exists(HERE + 'cost-sketch-rows.tsv') else []
    ms = np.array([float(r['ms']) for r in sk]) if sk else np.zeros(1)
    chk = [r['check'] for r in sk if r['check'] != '']
    extra = dict(sketch_bytes_per_relation=q5(rel), sketch_bytes_per_form=q5(form_), sketch_bytes_per_run=q5(run_), python_set_bytes_per_relation=q5(mem), sketches_relations=len(rel), sketch_build_relations=len(sk), sketch_build_ms=dict(median=round(float(np.median(ms)), 4), p90=round(float(np.quantile(ms, .9)), 3), largest=round(float(ms.max()), 2)), sketch_build_rows=dict(median=int(np.median([int(r['rows']) for r in sk])), largest=max(int(r['rows']) for r in sk)) if sk else None, row_count_check=dict(forms=len(chk), same=sum(c == '1' for c in chk)))
    return dict(**extra, scopes=len(v), median_ms=round(float(np.median(v)), 4), p90_ms=round(float(np.quantile(v, .9)), 4), p99_ms=round(float(np.quantile(v, .99)), 4), largest_ms=round(float(v.max()), 3), mean_ms=round(float(v.mean()), 4))


def sec_stage():
    """The savings split by the place of the scope in its run: the first 20 scopes and the rest, with the tilt of the whole run."""
    res = {}
    nt = len(tasks)

    def split(m, test):
        out_ = {}
        for name, L in (('first', COV['first']), ('first_late', COV['first_late'])):
            a, c = np.zeros(nt), np.zeros(nt)
            for t, s_, _, _ in L:
                if test(order[s_]):
                    a[t] += m[s_]
                    c[t] += 1
            rng = np.random.default_rng(SEED)
            got = []
            for _ in range(BOOT // 2):
                i = rng.integers(0, nt, nt)
                if c[i].sum():
                    got.append(math.log2(a[i].sum() / c[i].sum()))
            out_[name] = dict(saving=round(math.log2(a.sum() / c.sum()), 3) if c.sum() else None, range=[round(float(np.quantile(got, .025)), 3), round(float(np.quantile(got, .975)), 3)] if got else None, covers=int(c.sum()), tasks=int((c > 0).sum()))
        h0, h1 = np.zeros(nt), np.zeros(nt)
        for t, e in ER.items():
            q = test(order[e[:, 1]])
            w = fw['any'][e[q, 0]] * e[q, 2]
            h0[t] = float(w.sum())
            h1[t] = float((w * m[e[q, 1]]).sum())
        rng = np.random.default_rng(SEED)
        got = [math.log2(h1[i].sum() / h0[i].sum()) for i in (rng.integers(0, nt, nt) for _ in range(BOOT // 2)) if h0[i].sum()]
        out_['out'] = dict(saving=round(math.log2(h1.sum() / h0.sum()), 3), range=[round(float(np.quantile(got, .025)), 3), round(float(np.quantile(got, .975)), 3)], share_of_held_w=None)
        out_['held_w'] = float(h0.sum())
        return out_
    for lab in ('first', 'any'):
        P_, Nn = pack(SETS[lab][0])
        for model in ('pair', 'first_order', 'score'):
            Z, mu, betas = fit_loto(MODELS[model], P_, Nn)
            g = score_loto(Z, mu, betas)
            for bk in (5, 20):
                m = tilt(g, bk)
                q = dict(early=split(m, lambda x: x < 20), late=split(m, lambda x: x >= 20))
                tot = q['early']['held_w'] + q['late']['held_w']
                for k in ('early', 'late'):
                    q[k]['out']['share_of_held_w'] = round(q[k].pop('held_w') / tot, 4)
                res['%s %s block %d' % (lab, model, bk)] = q
    return res


def sec_sketch_counts():
    import pickle
    c = collections.Counter()
    for l in open(HERE + 'sketch-runs.tsv'):
        q = l.rstrip('\n').split('\t')
        c.update(json.loads(q[5]))
    big = tot = 0
    for a, t in runs:
        d = pickle.load(open(HERE + 'sketches/%s-%s.pkl' % (a, t), 'rb'))
        for f, v in d.items():
            for sk in v:
                for col in sk['cols']:
                    for n_, _ in col.values():
                        tot += 1
                        big += n_ > 64
    idn = F['ident_max'] > 0
    pos = {k: int(sum(idn[p] for p, _ in SETS[k][0])) for k in ('first', 'any', 'first_late')}
    return dict(counts=c, columns_examples=tot, over_64_values=big, share_over_64=round(big / tot, 4), scopes_with_an_ident_pair=int((idn & has).sum()), positives_with_an_ident_pair=pos, first_covers_by_stage=dict(first=int(sum(order[x[1]] < 20 for x in COV['first'])), of=len(COV['first']), late=int(sum(order[x[1]] < 20 for x in COV['first_late'])), late_of=len(COV['first_late'])))


SECTIONS = dict(rows=sec_rows, auc=sec_auc, auc_size=sec_auc_size, together=sec_together, gain=sec_gain, bits=sec_bits, cells=sec_cells, cost=sec_cost, stage=sec_stage, sketch_counts=sec_sketch_counts)
names = sys.argv[1:] or list(SECTIONS)
for i, k in enumerate(names):
    if k not in have:
        emit(k, SECTIONS[k]())
    el = time.time() - t00
    print('%d of %d sections, %.1f s, eta %.0f s' % (i + 1, len(names), el, el / (i + 1) * (len(names) - i - 1)), flush=True)
