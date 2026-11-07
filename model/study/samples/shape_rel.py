"""The relative forms of a writing point's table tokens' shape values, which the fit's loader (fit_trees.py) and the writer's serving block compute alike.

At a point, each table token has a value per column: one number of one shape of the feature language's shape vector, for the token's table. A shape that a
table's vector lacks has its default value, 0. A NaN value (the shape has no value at any example of its scope) takes no part. Over the point's table tokens,
column by column:
- `rank`: the value's rank among the defined values, from 0 (least) to 1 (greatest), with tied values at their mean rank; 0.5 where only one value is
  defined; NaN where the value is NaN.
- `mdiff`: the value less the median of the defined values, over their span (greatest less least); 0 where all defined values are equal; NaN where the value
  is NaN.
"""
import numpy as np


def relative(values):
    """(rank, mdiff) of `values`, a float array (table tokens, columns), each the same shape, float32."""
    v = np.asarray(values, np.float64)
    n, m = v.shape
    rank = np.full((n, m), np.nan)
    mdiff = np.full((n, m), np.nan)
    for j in range(m):
        col = v[:, j]
        ok = ~np.isnan(col)
        k = int(ok.sum())
        if k == 0:
            continue
        x = col[ok]
        if k == 1:
            rank[ok, j] = 0.5
            mdiff[ok, j] = 0.0
            continue
        order = np.argsort(x, kind='stable')
        r = np.empty(k)
        r[order] = np.arange(k, dtype=np.float64)
        for value in np.unique(x):  # ties take their mean rank
            tie = x == value
            if tie.sum() > 1:
                r[tie] = r[tie].mean()
        rank[ok, j] = r / (k - 1)
        lo, hi = x.min(), x.max()
        mdiff[ok, j] = 0.0 if hi == lo else (x - np.median(x)) / (hi - lo)
    return rank.astype(np.float32), mdiff.astype(np.float32)


if __name__ == '__main__':  # a check of the definition on a small case
    rk, md = relative([[1.0, 0.0, np.nan], [3.0, 0.0, 2.0], [3.0, 0.0, np.nan], [2.0, 0.0, np.nan]])
    assert np.allclose(rk[:, 0], [0.0, 2.5 / 3, 2.5 / 3, 1 / 3]), rk[:, 0]
    assert np.allclose(rk[:, 1], 0.5) and np.allclose(md[:, 1], 0.0)
    assert np.isnan(rk[0, 2]) and rk[1, 2] == 0.5 and md[1, 2] == 0.0
    assert np.allclose(md[:, 0], [(1 - 2.5) / 2, (3 - 2.5) / 2, (3 - 2.5) / 2, (2 - 2.5) / 2]), md[:, 0]
    print('ok')
