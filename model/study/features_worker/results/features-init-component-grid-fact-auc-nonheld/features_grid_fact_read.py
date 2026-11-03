#!/usr/bin/env python3
"""Read the rows: per component, the best observable on the pick half, its AUC on the read half, the control, the cost and the bits.

The pick half (half 0) chooses the observable, its direction, the bin edges and the tables. The read half (half 1) only scores them.
A component pick is one INIT form of a gold program. Writes table.json and the read section of partial.md.

Usage: <python> features_grid_fact_read.py
"""
import json
import math
import pathlib
import pickle
import time

import numpy as np
from scipy.stats import rankdata, spearmanr

import features_grid_fact_rows as R

PRIOR = R.ROOT / 'work/lm/data-study/sampler/sampler-worker/sampler-priors-refit-heldout-8a5ffec60/live_priors.pkl'
MIN_POS, N_BOOT, N_SHUF, K_SMOOTH, SEED = 20, 2000, 500, 10.0, 20261101
OUT = R.HERE / 'table.json'


def LEAVE_OUT_SET():
    return {x.strip() for x in (R.ROOT / 'work/lm/data-study/sampler/sampler-worker/held/leave_out.txt').read_text().splitlines() if x.strip()}


def auc(y, ranks):
    """y is tasks by comparisons or tasks; ranks is tasks by observables, in one half."""
    n1 = y.sum(0)
    return (np.einsum('ij,ik->jk', y, ranks) - (n1 * (n1 + 1) / 2)[..., None]) / (n1 * (len(y) - n1))[..., None]


def edges_of(x):
    vals = np.unique(x)
    if len(vals) <= 4:
        return vals[:-1]
    e = np.unique(np.quantile(x, [.25, .5, .75]))
    return e[e < vals[-1]]


def bin_of(x, e):
    return np.searchsorted(e, x, side='left')


def bits(X, C, half, kept_ix, best, sign, prior):
    """Bits saved per pick on the read half, each component with its own table, then all tables together."""
    p, r = half == 0, half == 1
    nc = C.shape[1]
    cp = C[p].sum(0)
    m = (cp + .5) / (cp.sum() + .5 * nc)  # the marginal rate of each component over the pick half's picks
    w = C[r]
    n_read = w.sum()
    per = []
    q_all = np.tile(m, (r.sum(), 1))
    for j, c in enumerate(kept_ix):
        x = X[:, best[j]]
        e = edges_of(x[p])
        bp, br = bin_of(x[p], e), bin_of(x[r], e)
        t = np.zeros(len(e) + 1)
        for b in range(len(t)):
            n_b = C[p][bp == b].sum()
            t[b] = (C[p][bp == b][:, c].sum() + K_SMOOTH * m[c]) / (n_b + K_SMOOTH)
        tr = t[br]
        hit = w[:, c]
        rest = w.sum(1) - hit
        vs_m = (hit * np.log2(tr / m[c]) + rest * np.log2((1 - tr) / (1 - m[c])))
        row = {'bits_all_picks': float(vs_m.sum() / n_read), 'bits_on_own_picks': float((hit * np.log2(tr / m[c])).sum() / hit.sum()) if hit.sum() else None}
        if prior is not None:
            q = np.minimum(prior[c] * tr / m[c], .999)
            v0 = hit * np.log2(q / prior[c]) + rest * np.log2((1 - q) / (1 - prior[c]))
            row['bits_all_picks_prior'] = float(v0.sum() / n_read)
        per.append(row)
        q_all[:, c] = tr
    q_all /= q_all.sum(1, keepdims=True)
    one = (w * (np.log2(q_all) - np.log2(m))).sum(1)  # per task
    out = {'per': per, 'task_saved': one}
    if prior is not None:
        q0 = prior * (q_all / m)
        q0 /= q0.sum(1, keepdims=True)
        out['task_saved_tilt_prior'] = (w * (np.log2(q0) - np.log2(prior))).sum(1)
        out['task_saved_table_vs_prior'] = (w * (np.log2(q_all) - np.log2(prior))).sum(1)
        out['task_marginal_vs_prior'] = (w * (np.log2(m) - np.log2(prior))).sum(1)
    out['task_picks'] = w.sum(1)
    return out


def main():
    t0 = time.time()
    rows = [json.loads(line) for line in R.ROWS.read_text().splitlines()]
    rows.sort(key=lambda d: d['task'])
    names = R.NAMES
    half = np.array([d['half'] for d in rows])
    X = np.array([[d['obs'][n] for n in names] for d in rows], dtype=float)
    assert not np.isnan(X).any()
    comps = sorted({c for d in rows for c in d['components']})
    pri_all = pickle.load(open(PRIOR, 'rb'))
    pri = pri_all['comps']
    assert set(comps) <= set(pri), set(comps) - set(pri)
    comps = sorted(pri)
    prior = np.array([pri[c] for c in comps], dtype=float)
    prior /= prior.sum()
    C = np.array([[d['components'].get(c, 0) for c in comps] for d in rows], dtype=float)
    pos = (C > 0).sum(0)
    kept_ix = [i for i, n in enumerate(pos) if n >= MIN_POS]
    kept = [comps[i] for i in kept_ix]
    p, r = half == 0, half == 1
    Rp, Rr = rankdata(X[p], axis=0), rankdata(X[r], axis=0)

    def picked(Cn):
        Y = Cn[:, kept_ix] > 0
        ap = auc(Y[p].astype(float), Rp)
        best = np.abs(ap - .5).argmax(1)
        pa = ap[np.arange(len(kept)), best]
        sign = np.where(pa >= .5, 1.0, -1.0)
        ar = auc(Y[r].astype(float), Rr)
        ra = ar[np.arange(len(kept)), best]
        return Y, best, pa, sign, np.where(sign > 0, ra, 1 - ra)

    Y, best, pick_auc, sign, read_auc = picked(C)
    real = bits(X, C, half, kept_ix, best, sign, prior)

    rng = np.random.default_rng(SEED)
    # control: one permutation of the tasks' labels inside each half, then the whole pick and read again
    shuf_auc, shuf_saved, shuf_per = np.zeros((N_SHUF, len(kept))), np.zeros(N_SHUF), np.zeros((N_SHUF, len(kept)))
    ip, ir = np.where(p)[0], np.where(r)[0]
    for s in range(N_SHUF):
        perm = np.arange(len(rows))
        perm[ip] = rng.permutation(ip)
        perm[ir] = rng.permutation(ir)
        Cs = C[perm]
        _, bs, _, ss, ra = picked(Cs)
        shuf_auc[s] = ra
        b = bits(X, Cs, half, kept_ix, bs, ss, prior)
        shuf_saved[s] = b['task_saved'].sum() / b['task_picks'].sum()
        shuf_per[s] = [q['bits_all_picks'] for q in b['per']]

    # task bootstrap on the read half, with the pick fixed
    n_r = len(ir)
    boots, bbits = np.zeros((N_BOOT, len(kept))), {k: np.zeros(N_BOOT) for k in ['task_saved', 'task_saved_tilt_prior', 'task_saved_table_vs_prior']}
    xr = X[r][:, best] * sign
    yr = Y[r]
    for b in range(N_BOOT):
        ix = rng.integers(0, n_r, n_r)
        y = yr[ix]
        rk = rankdata(xr[ix], axis=0)
        n1 = y.sum(0)
        with np.errstate(divide='ignore', invalid='ignore'):
            boots[b] = ((y * rk).sum(0) - n1 * (n1 + 1) / 2) / (n1 * (n_r - n1))
        tp = real['task_picks'][ix].sum()
        for k in bbits:
            bbits[k][b] = real[k][ix].sum() / tp

    ms = np.array([[d['ms'][n] for n in names] for d in rows])
    table = []
    for j, c in enumerate(kept):
        o = names[best[j]]
        lo, hi = np.nanpercentile(boots[:, j], [2.5, 97.5])
        cl, ch = np.percentile(shuf_auc[:, j], [2.5, 97.5])
        table.append({
            'component': c, 'positives': int(pos[kept_ix[j]]), 'positives_pick': int(Y[p][:, j].sum()), 'positives_read': int(Y[r][:, j].sum()),
            'base_rate_read': float(Y[r][:, j].mean()), 'observable': o, 'direction': 'high' if sign[j] > 0 else 'low',
            'pick_auc': float(max(pick_auc[j], 1 - pick_auc[j])), 'read_auc': float(read_auc[j]), 'read_auc_lo': float(lo), 'read_auc_hi': float(hi),
            'control_auc_mean': float(shuf_auc[:, j].mean()), 'control_auc_lo': float(cl), 'control_auc_hi': float(ch),
            'control_share_at_or_over_read': float((shuf_auc[:, j] >= read_auc[j]).mean()),
            'ms_median': float(np.median(ms[:, best[j]])), 'ms_largest': float(ms[:, best[j]].max()),
            **real['per'][j], 'control_bits_all_picks_mean': float(shuf_per[:, j].mean())})
    tp = real['task_picks'].sum()
    ap_all, ar_all = auc(Y[p].astype(float), Rp), auc(Y[r].astype(float), Rr)

    def ci(k):
        return [float(v) for v in np.percentile(bbits[k], [2.5, 97.5])]
    summary = {
        'tasks': len(rows), 'pick_half': int(p.sum()), 'read_half': int(r.sum()), 'components_seen': int((pos > 0).sum()), 'components_kept': len(kept), 'observables': len(names),
        'read_picks': int(tp), 'pick_picks': int(C[p].sum()), 'n_boot': N_BOOT, 'n_shuffles': N_SHUF, 'k_smooth': K_SMOOTH, 'seed': SEED,
        'bits_all_tables_vs_marginal': float(real['task_saved'].sum() / tp), 'bits_all_tables_vs_marginal_ci': ci('task_saved'),
        'bits_all_tables_control_mean': float(shuf_saved.mean()), 'bits_all_tables_control_range': [float(v) for v in np.percentile(shuf_saved, [2.5, 97.5])],
        'bits_tilted_prior_vs_prior': float(real['task_saved_tilt_prior'].sum() / tp), 'bits_tilted_prior_vs_prior_ci': ci('task_saved_tilt_prior'),
        'bits_all_tables_vs_prior': float(real['task_saved_table_vs_prior'].sum() / tp), 'bits_all_tables_vs_prior_ci': ci('task_saved_table_vs_prior'),
        'bits_marginal_vs_prior': float(real['task_marginal_vs_prior'].sum() / tp),
        'director_named_read_auc_pick_direction': {n: {c: float(a if b >= .5 else 1 - a) for c, a, b in zip(kept, ar_all[:, names.index(n)], ap_all[:, names.index(n)])} for n in ['has_components', 'has_enclosure', 'has_order']},
        'components_with_interval_over_half': sum(t['read_auc_lo'] > .5 for t in table),
        'spearman_in_cells_vs_picks_read': float(spearmanr(X[r][:, names.index('in_cells')], C[r].sum(1)).statistic),
        'spearman_object_size_vs_picks_read': float(spearmanr(X[r][:, names.index('object_size')], C[r].sum(1)).statistic),
        'prior_tasks': int(pri_all['tasks']),
        'prior_leave_out_equals_the_99': LEAVE_OUT_SET() == R.eval_tasks(),
        'json_ms_median': float(np.median([d['json_ms'] for d in rows])), 'json_ms_largest': float(max(d['json_ms'] for d in rows)),
        'left_out_components': {comps[i]: int(pos[i]) for i in range(len(comps)) if pos[i] < MIN_POS},
        'read_seconds': time.time() - t0}
    OUT.write_text(json.dumps({'summary': summary, 'table': table, 'definitions': {n: R.DEFS[n][1] for n in names}}, indent=1))

    L = [R.READ_MARK, '', f"Read on {summary['tasks']} rows: pick half {summary['pick_half']}, read half {summary['read_half']}. {summary['read_picks']} read-half component picks.", '']
    L += ['| component | positives (read) | base rate | observable | pick AUC | read AUC [95%] | control mean [range] | ms median/largest | bits all picks | bits vs prior |', '|---|---|---|---|---|---|---|---|---|---|']
    for t in table:
        L.append(f"| {t['component']} | {t['positives']} ({t['positives_read']}) | {t['base_rate_read']:.3f} | {t['observable']} ({t['direction']}) | {t['pick_auc']:.3f} | {t['read_auc']:.3f} [{t['read_auc_lo']:.3f}, {t['read_auc_hi']:.3f}] | {t['control_auc_mean']:.3f} [{t['control_auc_lo']:.3f}, {t['control_auc_hi']:.3f}] | {t['ms_median']:.2f}/{t['ms_largest']:.2f} | {t['bits_all_picks']:.4f} | {t['bits_all_picks_prior']:.4f} |")
    L += ['', '```', json.dumps({k: v for k, v in summary.items() if k != 'director_named_read_auc_pick_direction'}, indent=1), '```', '']
    (R.PARTIAL).write_text(R.PARTIAL.read_text().split(R.READ_MARK)[0] + '\n'.join(L))
    print(json.dumps(summary, indent=1))
    print('\n'.join(L[4:4 + 2 + len(table)]))


if __name__ == '__main__':
    main()
