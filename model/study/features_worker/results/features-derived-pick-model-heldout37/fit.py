"""Fit of the derived pick model (design.md, "The model"): the conditional logit over the derived options of read-pick rows, the boosted ranker (ablation), the gate (variant M2), and the
5-fold cross-fit by task.

    bash REC/env.sh ../features-derived-pick-model-heldout37/fit.py [--rows 'GLOB'] [--out DIR] [--no-hgb] [--lam-scale 1000]

Reads X/rows/*.jsonl (rows.py), writes DIR (default X/fit): cv.json (counts and cross-fit tables), model.json (feature names, means, scales, coltypes, beta, lambda, the rank model chosen),
gate.json, hgb.pkl. Weights: a row weighs the order's chance share over the number of valid pairs of its form (a form is one source's task and gold form), so a form weighs 1.
All numbers are weighted means in bits. Skipped rows: no derived option of weight > 0, or gold takes a derived option of weight 0.
"""
import argparse
import collections
import glob
import json
import math
import os
import pickle
import sys
import time
import zlib

import numpy as np
import warnings

warnings.filterwarnings('ignore', message='.*encountered in matmul')  # spurious flags of the macOS BLAS: the products are exact (checked against einsum)

T0 = time.time()
X = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-derived-pick-model-heldout37'
SW = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker'
sys.path.insert(0, X)
import feats  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('--rows', default=X + '/rows/*.jsonl')
ap.add_argument('--out', default=X + '/fit')
ap.add_argument('--no-hgb', action='store_true')
ap.add_argument('--lam-scale', type=float, default=1000.0)
ARGS = ap.parse_args()
os.makedirs(ARGS.out, exist_ok=True)
NF = 5
HELD = set()
for f in ('tasks.txt', 'ramp-fold.txt', 'leave_out.txt'):
    HELD |= set(open(SW + '/held/' + f).read().split())
assert len(HELD) > 100


def log(*a):
    print('[%5.0fs]' % (time.time() - T0), *a, flush=True)


def lines_of(path):
    """The JSON lines of a rows file; a last line that is not whole (the writer is running) is left out."""
    for l in open(path):
        try:
            yield json.loads(l)
        except ValueError:
            continue


# ---------------------------------------------------------------- load

files = sorted(glob.glob(ARGS.rows))
assert files, ARGS.rows
log('files', len(files))
ct = collections.Counter()
tasks = set()
for p in files:
    for r in lines_of(p):
        assert r['task'] not in HELD, r['task']
        tasks.add(r['task'])
        for pr in r['pairs']:
            for row in pr['rows']:
                for d in row['D']:
                    for k, v in d[6].items():
                        if k.startswith('ct:'):
                            ct[k[3:]] += v
COLTYPES = [t for t, _ in ct.most_common(12)]
OPT_NAMES = feats.Std.column_names(feats.all_option_names(), COLTYPES)
OPT = feats.Std(OPT_NAMES, [0.0] * len(OPT_NAMES), [1.0] * len(OPT_NAMES), COLTYPES)
GATE_NAMES = feats.all_gate_names()
GATE = feats.Std(GATE_NAMES, [0.0] * len(GATE_NAMES), [1.0] * len(GATE_NAMES), [])
assert not set(feats.DIAG) & set(OPT_NAMES + GATE_NAMES)
log('column types', COLTYPES)

OX, OWS, ORF, OPOS, OGOLD = [], [], [], [], []
R = collections.defaultdict(list)  # per row
GATE_RAW = []
cnt = collections.Counter()
by_place, by_kind_forms, by_src_rows = collections.Counter(), collections.defaultdict(set), collections.Counter()
nD_read = []
kk_rows = []  # (k, facts) for the check that no fact equals or determines the atom index
rng = np.random.default_rng(0)
for p in files:
    for r in lines_of(p):
        if r['status'] != 'ok':
            cnt['task error'] += 1
            continue
        task, src = r['task'], r['src']
        fold = zlib.crc32(task.encode()) % NF
        valid = [pr for pr in r['pairs'] if pr['valid']]
        cnt['tasks'] += 1
        npair = collections.Counter(pr['g'] for pr in valid)
        cnt['pairs'] += len(valid)
        for g in npair:
            cnt['forms'] += 1
            by_kind_forms[src].add((task, g))
        for pr in valid:
            for row in pr['rows']:
                D = row['D']
                if not D:
                    cnt['skipped: no derived option of weight > 0'] += 1
                    continue
                if row['g0']:
                    cnt['skipped: gold derived of weight 0'] += 1
                    continue
                w = row['w'] / npair[pr['g']]
                gold_d = any(d[4] for d in D)
                gtype = 0 if gold_d else (1 if row['gb'][0] == 'lib' else 2)
                st = row['st']
                dd = OPT.dense([d[6] for d in D]).astype(np.float32)
                OX.append(dd)
                OWS += [d[2] for d in D]
                ORF += [d[3] for d in D]
                OPOS += [d[5] for d in D]
                OGOLD += [d[4] for d in D]
                gw = row['gb'][1:] if row['gb'] else [0.0, 1.0]
                for k_, v_ in (('n', len(D)), ('w', w), ('fold', fold), ('src', 0 if src == 'c120' else 1), ('gtype', gtype), ('pl', st['pl']), ('hk', st['hk']), ('ro', int(row['ro'])),
                               ('TB', row['TB']), ('ZB', row['ZB']), ('gws', gw[0]), ('grf', gw[1]), ('kind', pr['kind']), ('task', task), ('ph', st['ph'])):
                    R[k_].append(v_)
                gf = row['gf']
                GATE_RAW.append(gf)
                cnt['rows'] += 1
                by_src_rows[src] += 1
                if gtype == 0:
                    cnt['read-pick rows'] += 1
                    by_place[(st['pl'], 'rel_off' if row['ro'] else 'steered')] += 1
                    nD_read.append(len(D))
                    cnt['read rows, kind ' + pr['kind']] += 1
                if len(kk_rows) < 200000:
                    kk_rows.append((row['_k'], {**gf, **{k: v for d in D[:1] for k, v in d[6].items()}}))
    log('read', os.path.basename(p), dict(cnt))
Xraw = np.vstack(OX)
del OX
ows, orf, opos, ogold = (np.array(a, dtype=np.float64) for a in (OWS, ORF, OPOS, OGOLD))
n = np.array(R['n'])
NR = len(n)
starts = np.concatenate([[0], np.cumsum(n)[:-1]])
rid = np.repeat(np.arange(NR), n)
W = np.array(R['w'])
fold = np.array(R['fold'])
gtype = np.array(R['gtype'])
src = np.array(R['src'])
TB, ZB, gws, grf = (np.array(R[k]) for k in ('TB', 'ZB', 'gws', 'grf'))
place = np.array(R['pl'])
ro = np.array(R['ro'])
read = gtype == 0
log('rows', NR, 'options', len(rid), 'read rows', int(read.sum()), 'features', Xraw.shape[1])
bad = feats.check_not_index(kk_rows)
assert not bad, 'a fact equals or determines the atom index: %s' % bad
log('check: no fact equals or determines the atom index, on %d rows' % len(kk_rows))

mean = Xraw.mean(0)
scale = Xraw.std(0)
scale[scale < 1e-9] = 1.0
OPT.mean, OPT.scale = mean.tolist(), scale.tolist()
Xs = ((Xraw - mean) / scale).astype(np.float64)


def rsum(a):
    return np.add.reduceat(a, starts)


def rmax(a):
    return np.maximum.reduceat(a, starts)


# ---------------------------------------------------------------- the rank model

class Seg:
    """The read-pick rows of a mask, as contiguous segments."""

    def __init__(self, rowmask):
        om = rowmask[rid]
        self.X, self.pos = Xs[om], opos[om]
        self.n = n[rowmask]
        self.w = W[rowmask]
        self.st = np.concatenate([[0], np.cumsum(self.n)[:-1]])
        self.rid = np.repeat(np.arange(len(self.n)), self.n)


def loss_grad(beta, sg, lam):
    s = sg.X @ beta
    m = np.maximum.reduceat(s, sg.st)
    e = np.exp(s - m[sg.rid])
    Z = np.add.reduceat(e, sg.st)
    Zp = np.add.reduceat(e * sg.pos, sg.st)
    loss = float((sg.w * (np.log(Z) - np.log(Zp))).sum()) + lam * float(beta @ beta)
    coef = sg.w[sg.rid] * (e / Z[sg.rid] - e * sg.pos / Zp[sg.rid])
    return loss, sg.X.T @ coef + 2 * lam * beta


def fit_logit(rowmask, lam):
    from scipy.optimize import minimize
    sg = Seg(rowmask)
    r = minimize(loss_grad, np.zeros(Xs.shape[1]), args=(sg, lam), jac=True, method='L-BFGS-B', options=dict(maxiter=500))
    return r.x


def seg_scores(s):
    """Per row: lse, max, the log of the positives' share, hit (a positive has the largest score)."""
    mx = rmax(s)
    e = np.exp(s - mx[rid])
    Z = rsum(e)
    lse = mx + np.log(Z)
    Zp = rsum(e * opos)
    top = rmax(np.where(opos > 0, s, -np.inf))
    return lse, mx, np.log(Zp / Z), top >= mx


def wmean(v, w, m=None):
    if m is not None:
        v, w = v[m], w[m]
    return float((v * w).sum() / w.sum()) if len(v) and w.sum() > 0 else float('nan')


def oof_logit(lam):
    s = np.zeros(len(rid))
    for f in range(NF):
        b = fit_logit(read & (fold != f), lam)
        om = fold[rid] == f
        s[om] = Xs[om] @ b
    return s


# ---------------------------------------------------------------- the whole-pick shares

def shares(s, lse, sigma):
    """Bits of gold's share, per row, for off, M1 and M2 (arithmetic of design.md, with the logged ws and rf)."""
    SD = rsum(ows)
    SDr = rsum(ows * orf)
    gd = np.zeros(NR)
    gi = np.nonzero(ogold > 0)[0]
    gd[rid[gi]] = s[gi] - lse[rid[gi]]  # log (e_g / E) of rows where gold is derived
    gbw = gws * grf
    wsg = np.zeros(NR)
    wsg[rid[gi]] = ows[gi]
    rfg = np.zeros(NR)
    rfg[rid[gi]] = orf[gi]
    isd = gtype == 0
    sh_off = np.where(isd, wsg * rfg, gbw) / (ZB + SDr)
    with np.errstate(divide='ignore', invalid='ignore'):
        sh_m1 = np.where(isd, SD * np.exp(gd), np.where(ZB > 0, TB * gbw / ZB, 0.0)) / (SD + TB)
        sh_m2 = np.where(isd, np.where(TB > 0, sigma, 1.0) * np.exp(gd), (1 - sigma) * np.where(ZB > 0, gbw / ZB, 0.0))
    return [-np.log2(np.maximum(x, 1e-300)) for x in (sh_off, sh_m1, sh_m2)]


# ---------------------------------------------------------------- cross-fit: rank model

W_read = float(W[read].sum())
lam_grid = {c: c * W_read / ARGS.lam_scale for c in (0.01, 0.1, 1.0, 10.0)}
cv = dict(lam={})
best = None
for c, lam in lam_grid.items():
    s = oof_logit(lam)
    lse, mx, lp, hit = seg_scores(s)
    bits = wmean(-lp / math.log(2), W, read)
    cv['lam'][str(c)] = dict(lam=lam, bits=bits, top1=wmean(hit.astype(float), W, read))
    log('lambda x%s: cross-fit bits %.4f top1 %.3f' % (c, bits, cv['lam'][str(c)]['top1']))
    if best is None or bits < best[0]:
        best = (bits, c, lam, s)
bits_logit, c_best, lam_best, s_logit = best
log('lambda chosen: x%s' % c_best)

# today and even split, on read rows
nD = n.astype(float)
npos = rsum(opos)
SDr = rsum(ows * orf)
today_pos = rsum(ows * orf * opos) / SDr
b_even = -np.log2(npos / nD)
b_today = -np.log2(today_pos)
lse_l, mx_l, lp_l, hit_l = seg_scores(s_logit)
b_logit = -lp_l / math.log(2)
t_today = np.array([0.0] * NR)
top_today = rmax(np.where(opos > 0, ows * orf, -np.inf)) >= rmax(ows * orf)
cv['read_within'] = dict(rows=int(read.sum()), weight=W_read, even=wmean(b_even, W, read), today=wmean(b_today, W, read), logit=bits_logit, top1_today=wmean(top_today.astype(float), W, read),
                         top1_logit=wmean(hit_l.astype(float), W, read), npos_median=float(np.median(npos[read])), nD_median=float(np.median(nD[read])))
for nm, msk in (('c120', src == 0), ('n600', src == 1)):
    cv['read_within'][nm] = dict(even=wmean(b_even, W, read & msk), today=wmean(b_today, W, read & msk), logit=wmean(b_logit, W, read & msk))
for pl in sorted(set(place)):
    cv['read_within']['place ' + pl] = dict(rows=int((read & (place == pl)).sum()), even=wmean(b_even, W, read & (place == pl)), today=wmean(b_today, W, read & (place == pl)),
                                            logit=wmean(b_logit, W, read & (place == pl)))
log('read picks, within derived: even %.3f today %.3f logit %.3f' % (cv['read_within']['even'], cv['read_within']['today'], cv['read_within']['logit']))

# the ablation
rank_kind, s_rank, hgb_final = 'logit', s_logit, None
if not ARGS.no_hgb:
    from sklearn.ensemble import HistGradientBoostingClassifier as HGB

    def hgb(rowmask):
        om = rowmask[rid]
        m = HGB(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=50, random_state=0)
        m.fit(Xraw[om], opos[om] > 0, sample_weight=(W[rid] / n[rid])[om])
        return m
    s_h = np.zeros(len(rid))
    for f in range(NF):
        m = hgb(read & (fold != f))
        om = fold[rid] == f
        s_h[om] = m.decision_function(Xraw[om])
        log('hgb fold', f)
    lse_h, mx_h, lp_h, hit_h = seg_scores(s_h)
    b_hgb = -lp_h / math.log(2)
    cv['read_within']['hgb'] = wmean(b_hgb, W, read)
    cv['read_within']['top1_hgb'] = wmean(hit_h.astype(float), W, read)
    log('hgb cross-fit bits %.4f (logit %.4f)' % (cv['read_within']['hgb'], bits_logit))
    if cv['read_within']['hgb'] < bits_logit - 0.05:
        rank_kind, s_rank = 'hgb', s_h
    hgb_final = hgb(read)
cv['rank_kind'] = rank_kind
lse_r, mx_r, lp_r, hit_r = seg_scores(s_rank)

# ---------------------------------------------------------------- the gate

G = GATE.dense(GATE_RAW)
G[:, GATE.ix['lse']] = lse_r - np.log(nD)
G[:, GATE.ix['mx']] = mx_r - lse_r
gm, gs = G.mean(0), G.std(0)
gs[gs < 1e-9] = 1.0
GATE.mean, GATE.scale = gm.tolist(), gs.tolist()
Gs = (G - gm) / gs
y = (gtype == 0).astype(int)
from sklearn.linear_model import LogisticRegression  # noqa: E402


def oof_gate(C):
    sig = np.zeros(NR)
    for f in range(NF):
        m = LogisticRegression(C=C, max_iter=2000)
        m.fit(Gs[fold != f], y[fold != f], sample_weight=W[fold != f])
        sig[fold == f] = m.predict_proba(Gs[fold == f])[:, 1]
    return np.clip(sig, 1e-6, 1 - 1e-6)


cv['gate'] = {}
bestg = None
for C_ in (0.1, 1.0, 10.0):
    sig = oof_gate(C_)
    off, m1, m2 = shares(s_rank, lse_r, sig)
    cv['gate'][str(C_)] = wmean(m2, W)
    log('gate C=%s: cross-fit whole-pick bits (M2) %.4f' % (C_, cv['gate'][str(C_)]))
    if bestg is None or cv['gate'][str(C_)] < bestg[0]:
        bestg = (cv['gate'][str(C_)], C_, sig)
_, C_best, sig = bestg

# ---------------------------------------------------------------- cross-fit tables, whole pick
off, m1, m2 = shares(s_rank, lse_r, sig)
tab = {}
for nm, msk in (('all rows', np.ones(NR, bool)), ('read picks', gtype == 0), ('builtin picks', gtype == 1), ('op picks', gtype == 2), ('read picks, steered', (gtype == 0) & (ro == 0)),
                ('read picks, rel_off', (gtype == 0) & (ro == 1)), ('c120', src == 0), ('n600', src == 1)):
    tab[nm] = dict(rows=int(msk.sum()), off=wmean(off, W, msk), M1=wmean(m1, W, msk), M2=wmean(m2, W, msk))
for pl in sorted(set(place)):
    for nm, msk in (('place %s, all' % pl, place == pl), ('place %s, read picks' % pl, (place == pl) & (gtype == 0))):
        tab[nm] = dict(rows=int(msk.sum()), off=wmean(off, W, msk), M1=wmean(m1, W, msk), M2=wmean(m2, W, msk))
cv['whole_pick'] = tab
for k, v in tab.items():
    if not k.startswith('place'):
        log('whole pick %-22s rows %6d off %.4f M1 %.4f M2 %.4f' % (k, v['rows'], v['off'], v['M1'], v['M2']))

cv['counts'] = dict(cnt, tasks_total=len(tasks), rows_by_source=dict(by_src_rows), forms_by_source={k: len(v) for k, v in by_kind_forms.items()},
                    read_rows_by_place_and_steer={'%s/%s' % k: v for k, v in by_place.items()}, derived_options_per_read_row_median=float(np.median(nD_read)) if nD_read else None,
                    read_rows_share_rel_off=float(ro[read].mean()) if read.any() else None, pair_kind_read_rows={k: v for k, v in cnt.items() if k.startswith('read rows, kind')},
                    options=int(len(rid)), features=int(Xraw.shape[1]), weight_total=float(W.sum()), weight_read=W_read)

# ---------------------------------------------------------------- final models
beta = fit_logit(read, lam_best)
gate = LogisticRegression(C=C_best, max_iter=2000)
gate.fit(Gs, y, sample_weight=W)
json.dump(dict(OPT.to_json(), beta=beta.tolist(), lam=lam_best, lam_scale_c=c_best, rank=rank_kind, source_files=[os.path.basename(f) for f in files]), open(ARGS.out + '/model.json', 'w'))
json.dump(dict(GATE.to_json(), coef=gate.coef_[0].tolist(), intercept=float(gate.intercept_[0]), C=C_best), open(ARGS.out + '/gate.json', 'w'))
if hgb_final is not None:
    pickle.dump(hgb_final, open(ARGS.out + '/hgb.pkl', 'wb'))
top = sorted(zip(OPT_NAMES, beta), key=lambda t: -abs(t[1]))[:15]
cv['top_beta'] = [[a, round(float(b), 3)] for a, b in top]
json.dump(cv, open(ARGS.out + '/cv.json', 'w'), indent=1)
log('top coefficients', cv['top_beta'])
log('wrote', ARGS.out)
