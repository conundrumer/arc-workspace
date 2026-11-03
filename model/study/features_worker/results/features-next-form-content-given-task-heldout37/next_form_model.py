"""Per-situation models of one categorical target.

A row is one draw of the target. A row may carry a mask of the values open at its state: a derived key is open only where a found form has that key.

An expert is a situation key, one fact or a pair of facts, inside the form's kind. Its table gives a rate per value: (n(y, cell) + ALPHA b(y)) / (a(y, cell) + ALPHA), with n the count of y, a the count of rows where y is open, and b the rate of y in the kind. That is the fallback for a sparse cell.

The model is a softmax over the open values:
    log p(y | s) = log b(y) + sum over experts w_i * log(r_i(y | s) / b(y)) + const, with w_i >= 0.
Weights are fit on out-of-fold expert tables over task folds, so a cell never reads its own task in the weight fit.
"""
import hashlib
import math
from collections import Counter

import numpy as np
from scipy.optimize import minimize

ALPHA = 4.0
BETA = .5
LOG2 = math.log(2)


def fold_of(task, k=5):
    return int(hashlib.sha1(task.encode()).hexdigest(), 16) % k


class Data:
    """rows: dicts with task, kind, fact, y. vocab: the target's values, with '<other>' last. mask: rows by values bool, or None."""

    def __init__(self, rows, vocab, kinds, mask=None):
        self.rows = rows
        self.v = vocab
        self.ix = {y: i for i, y in enumerate(vocab)}
        o = self.ix['<other>']
        self.y = np.array([self.ix.get(r['y'], o) for r in rows], dtype=np.int32)
        self.kinds = kinds
        kx = {k: i for i, k in enumerate(kinds)}
        self.k = np.array([kx[r['kind']] for r in rows], dtype=np.int32)
        self.mask = mask if mask is not None else np.ones((len(rows), len(vocab)), dtype=bool)
        self.fold = np.array([fold_of(r['task']) for r in rows], dtype=np.int32)

    def sub(self, at):
        return Sub(self, at)


class Sub:
    def __init__(self, d, at):
        self.rows = [d.rows[i] for i in at]
        self.v, self.ix, self.kinds = d.v, d.ix, d.kinds
        self.y, self.k, self.mask, self.fold = d.y[at], d.k[at], d.mask[at], d.fold[at]

    def sub(self, at):
        return Sub(self, at)


class Base:
    """b(y | kind) on train rows."""

    def __init__(self, d):
        nk, nv = len(d.kinds), len(d.v)
        self.n = np.zeros((nk, nv))
        self.a = np.zeros((nk, nv))
        np.add.at(self.n, (d.k, d.y), 1)
        np.add.at(self.a, d.k, d.mask)
        u = 1 / nv
        self.rate = (self.n + BETA * u) / (self.a + BETA)
        self.lrate = np.log(self.rate)

    def l(self, d):
        return self.lrate[d.k]


def group_ids(rows, key, table=None):
    """Group ids of rows on the key; a new table where table is None. A cell outside table gets -1."""
    if table is None:
        table = {}
        grow = True
    else:
        grow = False
    out = np.zeros(len(rows), dtype=np.int64)
    for i, r in enumerate(rows):
        c = (r['kind'],) + tuple(r['fact'][a] for a in key)
        g = table.get(c)
        if g is None:
            if grow:
                g = table[c] = len(table)
            else:
                g = -1
        out[i] = g
    return out, table


class Expert:
    def __init__(self, d, base, key, alpha=ALPHA):
        self.key, self.alpha, self.base = key, alpha, base
        g, self.table = group_ids(d.rows, key)
        ng, nv = len(self.table), len(d.v)
        self.n = np.zeros((ng, nv))
        self.a = np.zeros((ng, nv))
        np.add.at(self.n, (g, d.y), 1)
        np.add.at(self.a, g, d.mask)

    def lift(self, d):
        """log(r(y | s) / b(y)) for the rows of d, as rows by values."""
        g, _ = group_ids(d.rows, self.key, self.table)
        b = self.base.rate[d.k]
        out = np.zeros(b.shape, dtype=np.float32)
        hit = g >= 0
        r = (self.n[g[hit]] + self.alpha * b[hit]) / (self.a[g[hit]] + self.alpha)
        out[hit] = np.log(r) - np.log(b[hit])
        return out


def softmax_logp(z, mask):
    z = np.where(mask, z, -1e30)
    z = z - z.max(1, keepdims=True)
    return z - np.log(np.exp(z).sum(1, keepdims=True))


def stack_fit(B, stack, y, mask, l2=1e-3):
    m = stack.shape[2]
    if m == 0:
        return np.zeros(0)
    n = np.arange(len(y))
    S_ = stack.astype(np.float64)

    def f(w):
        lp = softmax_logp(B + (S_ * w[None, None, :]).sum(2), mask)
        p = np.exp(lp)
        loss = -lp[n, y].mean() + l2 * (w ** 2).sum()
        g = -(S_[n, y, :] - (p[:, :, None] * S_).sum(1)).mean(0) + 2 * l2 * w
        return loss, g

    return minimize(f, np.full(m, 1 / m), jac=True, method='L-BFGS-B', bounds=[(0, None)] * m, options=dict(maxiter=50)).x


def bits_of(B, stack, w, y, mask):
    z = B + (stack * w[None, None, :]).sum(2) if stack.shape[2] else B
    return -softmax_logp(z, mask)[np.arange(len(y)), y] / LOG2


def oof(d, keys, folds=5):
    """Out-of-fold base logs and lifts."""
    B = np.zeros((len(d.y), len(d.v)))
    L = {k: np.zeros((len(d.y), len(d.v)), dtype=np.float32) for k in keys}
    for k in range(folds):
        tr = d.sub(np.nonzero(d.fold != k)[0])
        at = np.nonzero(d.fold == k)[0]
        te = d.sub(at)
        base = Base(tr)
        B[at] = base.l(te)
        for key in keys:
            L[key][at] = Expert(tr, base, key).lift(te)
    return B, L


def screen(d, keys, folds=5):
    """{key: mean out-of-fold bits of its table alone}."""
    out = {}
    tot = np.zeros(len(keys))
    for k in range(folds):
        tr = d.sub(np.nonzero(d.fold != k)[0])
        te = d.sub(np.nonzero(d.fold == k)[0])
        base = Base(tr)
        B = base.l(te)
        for i, key in enumerate(keys):
            L = Expert(tr, base, key).lift(te)
            tot[i] += (-softmax_logp(B + L, te.mask)[np.arange(len(te.y)), te.y] / LOG2).sum()
    for i, key in enumerate(keys):
        out[key] = tot[i] / len(d.y)
    return out


def cv_stack(d, B, L, keys, folds=5):
    y, mask, fold = d.y, d.mask, d.fold
    stack = np.stack([L[k] for k in keys], 2) if keys else np.zeros((len(y), len(d.v), 0), dtype=np.float32)
    tot = 0.0
    for k in range(folds):
        at = fold == k
        w = stack_fit(B[~at], stack[~at], y[~at], mask[~at])
        tot += bits_of(B[at], stack[at], w, y[at], mask[at]).sum()
    return tot / len(y)


def select(d, singles, top=8, pairs=True, max_keys=6, min_gain=.004, log=None, weights=(.25, .5, 1.0)):
    """Situation keys by a greedy forward pick on out-of-fold bits: each step adds the key and the weight that cut the bits most, with the earlier weights fixed.
    The screen runs on singles, then on pairs of the top singles, on a task-hashed part of the rows where the rows are many."""
    part = d if len(d.y) * len(d.v) <= 2000000 else d.sub(np.nonzero(d.fold < 2)[0])
    s = screen(part, singles, folds=5 if part is d else 2)
    first = sorted(s, key=s.get)[:top]
    cands = list(first)
    if pairs:
        pr = [tuple(sorted(a + b)) for i, a in enumerate(first) for b in first[i + 1:]]
        pr = [p for p in pr if len(set(p)) == 2]
        sp = screen(part, pr, folds=5 if part is d else 2)
        cands += sorted(sp, key=sp.get)[:top]
    B, L = oof(d, cands)
    n = np.arange(len(d.y))
    z = B.copy()
    bits = lambda x: float((-softmax_logp(x, d.mask)[n, d.y] / LOG2).mean())  # noqa: E731
    cur = b0 = bits(z)
    chosen = []
    while len(chosen) < max_keys:
        best, bb, bw = None, cur, 0
        for k in cands:
            if k in chosen:
                continue
            for w in weights:
                x = bits(z + w * L[k])
                if x < bb:
                    best, bb, bw = k, x, w
        if best is None or cur - bb < min_gain:
            break
        chosen.append(best)
        z = z + bw * L[best]
        cur = bb
        if log:
            log('  + %s w %.2f -> %.3f' % ('*'.join(best), bw, cur))
    return chosen, b0, cur


class Model:
    def __init__(self, d, keys):
        self.keys = keys
        B, L = oof(d, keys)
        stack = np.stack([L[k] for k in keys], 2) if keys else np.zeros((len(d.y), len(d.v), 0), dtype=np.float32)
        self.w = stack_fit(B, stack, d.y, d.mask)
        self.base = Base(d)
        self.ex = [Expert(d, self.base, k) for k in keys]

    def read(self, t):
        """(bits under the kind's rates, bits under the model, rank of gold) per row of data t."""
        B = self.base.l(t)
        z = B.copy()
        for w, e in zip(self.w, self.ex):
            z += w * e.lift(t)
        n = np.arange(len(t.y))
        lb = softmax_logp(B, t.mask)
        lp = softmax_logp(z, t.mask)
        rank = (lp > lp[n, t.y][:, None]).sum(1)
        return -lb[n, t.y] / LOG2, -lp[n, t.y] / LOG2, rank


def vocab_of(rows, min_n=1):
    c = Counter(r['y'] for r in rows)
    return sorted(k for k, n in c.items() if n >= min_n) + ['<other>']
