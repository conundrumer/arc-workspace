"""A fit's trees (one HistGradientBoostingRegressor per round) as flat arrays, for one-row scoring, and a batch call.

  F = Forest(models); F.predict(X) equals sum(m.predict(X)); F.predict_one(x) walks all trees at once with numpy.
"""
import numpy as np


class Forest:
    def __init__(self, models):
        self.models = models
        recs, base, roots, off = [], 0.0, [], 0
        for m in models:
            nd = m._predictors[0][0].nodes
            base += float(np.ravel(m._baseline_prediction)[0])
            roots.append(off)
            recs.append(nd)
            off += len(nd)
        nd = np.concatenate(recs)
        self.base = base
        self.roots = np.array(roots, np.int64)
        self.feat = nd['feature_idx'].astype(np.int64)
        self.thr = nd['num_threshold'].astype(np.float64)
        self.mgl = nd['missing_go_to_left'].astype(bool)
        self.leaf = nd['is_leaf'].astype(bool)
        sizes = np.array([len(r) for r in recs])
        shift = np.repeat(self.roots, sizes)
        self.left = nd['left'].astype(np.int64) + shift
        self.right = nd['right'].astype(np.int64) + shift
        self.val = nd['value'].astype(np.float64)
        self.maxd = int(nd['depth'].max()) + 1
        self.used = sorted(set(self.feat[~self.leaf].tolist()))

    def predict(self, X):
        s = np.zeros(len(X))
        for m in self.models:
            s += m.predict(X)
        return s

    def predict_one(self, x):
        cur = self.roots.copy()
        for _ in range(self.maxd):
            lf = self.leaf[cur]
            if lf.all():
                break
            v = x[self.feat[cur]]
            go = np.where(np.isnan(v), self.mgl[cur], v <= self.thr[cur])
            nxt = np.where(go, self.left[cur], self.right[cur])
            cur = np.where(lf, cur, nxt)
        return self.base + float(self.val[cur].sum())
