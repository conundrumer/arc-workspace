"""AUC machinery shared by read-auc.py and summary.py: strata, the AUC of a feature inside strata, per-task means and the task bootstrap."""
import zlib
import numpy as np
import pandas as pd

BANDS = [(1, 1), (2, 3), (4, 6), (7, 10 ** 9)]
BAND_NAMES = ['1', '2-3', '4-6', '7+']
NBOOT = 2000


def depth_band(d):
    d = np.asarray(d)
    return np.where(d <= 1, 0, np.where(d <= 3, 1, np.where(d <= 6, 2, 3)))


def strata(T, kind):
    """Integer stratum code per row of a table frame; -1 drops the row (as positive and as negative)."""
    n = len(T)
    if kind == 'raw':
        return np.zeros(n, np.int64)
    ab = T['age_bin'].values
    xb = T['x_bin'].values
    if kind == 'S1':
        return np.where(xb >= 1, ab * 5 + xb - 1, -1)
    if kind == 'S2':
        return ab * 10 + T['score_bin'].values
    if kind == 'band':
        return depth_band(T['depth'].values)
    if kind == 'S3':
        rb = T['r_bin'].values
        return np.where((xb >= 1) & (rb >= 1), (ab * 5 + xb - 1) * 5 + rb, -1)
    if kind == 'S4':
        e = T['ext_bin'].values
        return np.where(e >= 1, (depth_band(T['depth'].values) * 5 + ab) * 5 + e, -1)
    raise ValueError(kind)


def auc_run(f, code, y):
    """(mean over positives of the share of same-stratum negatives that a positive beats, ties 1/2; positives kept; positives dropped for lack of a negative)."""
    f = np.asarray(f, float)
    pos_mask = y & (code >= 0)
    if not pos_mask.any():
        return np.nan, 0, 0
    shares = []
    dropped = 0
    for s in np.unique(code[pos_mask]):
        sm = code == s
        neg = np.sort(f[sm & ~y])
        pm = sm & y
        if len(neg) == 0:
            dropped += int(pm.sum())
            continue
        p = f[pm]
        lo = np.searchsorted(neg, p, 'left')
        hi = np.searchsorted(neg, p, 'right')
        shares.append((lo + .5 * (hi - lo)) / len(neg))
    if not shares:
        return np.nan, 0, dropped
    v = np.concatenate(shares)
    return float(v.mean()), len(v), dropped


def shuffled(T, col, kind, seed):
    """Values of column col permuted among rows inside strata `kind` (x = 0 rows inside S1 form a stratum of their own)."""
    code = strata(T, kind)
    if kind == 'S1':
        code = np.where(code < 0, -1 - T['age_bin'].values, code)
    rng = np.random.default_rng(seed)
    v = T[col].values.copy()
    out = v.copy()
    order = np.argsort(code, kind='stable')
    cs = code[order]
    cuts = np.nonzero(np.diff(cs))[0] + 1
    for g in np.split(order, cuts):
        out[g] = v[rng.permutation(g)]
    return out


def seed_of(*a):
    return zlib.crc32('|'.join(map(str, a)).encode())


def boot_idx(ntasks):
    rng = np.random.default_rng(0)
    return rng.integers(0, ntasks, size=(NBOOT, ntasks))


def band(vals, idx):
    """(point, low, high): the mean over tasks with a value, and the 90% band of the task bootstrap with the same resamples for every row."""
    vals = np.asarray(vals, float)
    point = float(np.nanmean(vals)) if np.isfinite(vals).any() else np.nan
    m = np.isfinite(vals)
    if not m.any():
        return point, np.nan, np.nan
    v = np.where(m, vals, 0.0)
    num = v[idx].sum(1)
    den = m[idx].sum(1)
    ok = den > 0
    bm = num[ok] / den[ok]
    return point, float(np.quantile(bm, .05)), float(np.quantile(bm, .95))
