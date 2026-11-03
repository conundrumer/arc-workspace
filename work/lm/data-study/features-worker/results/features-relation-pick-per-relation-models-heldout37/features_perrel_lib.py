"""Shared parts of the per-key fits: the picks with their keys, the binary facts of a key, boosted stumps with a soft-max offset, and the score of a model on rows.

A key's model is additive over binary facts. A fact is "this number of the option or the pick is at least t" or "this relation or component is in the prefix or scope". For a key k and rows of k at a pick, with q the steered prior:

  p(option j of k) = q_j exp(d_j) / (1 - sum over k of q + sum over k of q exp(d))

So a key's model is a block update of the pick's soft-max, on its own rows, and the other options stay at the prior. With one option of the key at a pick, this is logistic regression with log odds of q as the offset.
"""
import json
import math
import os
import re
import sys
import zlib

import numpy as np
import scipy.sparse as sp

ME = os.path.dirname(os.path.abspath(__file__)) + '/'
sys.path.insert(0, ME)
OUT = ME + 'scratch/'
import features_rel_content as FC  # noqa: E402

TYPES = ('Position', 'Color', 'Box', 'Nat', 'Int', 'Number', 'Ident', 'Dir', 'Offset', 'Axis')
STRUCT = ['lq', 'lp', 'steer', 'rank', 'gap_top', 'share_kind', 'is_lib', 'is_macro', 'is_fact', 'is_derived', 'is_not', 'is_cmp', 'dead_join', 'own', 'uses', 'arity', 'hit', 'hit_frac', 'none_in_scope', 'new_types',
          'readers', 'depth', 'defined', 'method', 'sibling', 'path', 'der_rank', 'k', 'ord', 'root2', 'in_branch', 'nscope', 'nopts', 'nder', 'nalive', 'entropy', 'top_q', 'last_derived', 'last_lib', 'last_not', 'ncmp', 'prefix_depth'] + ['type_' + t for t in TYPES]
EXTRA = ['t_rows_rel', 'j_match_rank', 'j_cont_rank', 's_cont_rank', 'der_rows_rank']
CONTENT = list(FC.OPTION) + list(FC.JOIN) + list(FC.PREFIX) + EXTRA
XCOLS = ['col%d_in_scope' % i for i in range(5)] + ['recency', 'recency_frac', 'form_atoms', 'form_not', 'form_or', 'kept_reads']
SCOPE = ['scope_n_' + t for t in TYPES]
GRID = json.load(open(OUT + 'grid-facts-names.json')) if os.path.exists(OUT + 'grid-facts-names.json') else []
NAMES = STRUCT + CONTENT + XCOLS + SCOPE + ['grid_' + g for g in GRID]
FIT_SETS = ['train-before-0', 'train-before-1', 'train-before-2', 'test-before']
QS = (.1, .25, .5, .75, .9)
DROP_COLS = set()  # columns that a fit leaves out
DROP_TOK = None  # tokens that a fit leaves out, as a bool array
LN2 = math.log(2)
FOLDS = 4


def fold_of(task):
    return zlib.crc32(('perrel' + task).encode()) % FOLDS


class Vocabs:
    def __init__(self, path=None):
        self.m = {k: {} for k in ('fam', 'comp', 'rel', 'heads', 'hyb')}
        if path and os.path.exists(path):
            self.m = json.load(open(path))

    def map(self, kind, strings, grow=True):
        d = self.m[kind]
        out = np.zeros(len(strings), np.int32)
        for i, s in enumerate(strings.tolist() if hasattr(strings, 'tolist') else strings):
            if s not in d:
                d[s] = len(d)
            out[i] = d[s]
        return out

    def list(self, kind):
        d = self.m[kind]
        return sorted(d, key=d.get)


class Picks:
    """Option rows and picks of data files. Keys and tokens carry ids of the shared vocabularies."""

    def __init__(self, names, V, label_seed=None):
        As, Ps, starts, gold, m = [], [], [0], [], {}
        lev = {k: [] for k in ('fam', 'comp', 'rel')}
        tp, tk = [], []
        grid = json.load(open(OUT + 'grid-facts.json'))
        np0 = 0
        for n in names:
            z = np.load(OUT + 'data-%s.npz' % n, allow_pickle=False)
            S, C, X = z['S'], z['C'], z['X']
            As.append(np.hstack([S, C, X], dtype=np.float32))
            task = z['m_task']
            G = np.array([grid[t] for t in task.tolist()], np.float32)
            Ps.append(np.hstack([z['scnt'], G], dtype=np.float32))
            gold.append(z['gold'])
            starts += list(starts[-1] + z['starts'][1:])
            for k in z.files:
                if k.startswith('m_'):
                    m.setdefault(k[2:], []).append(z[k])
            for k in lev:
                ids = V.map(k, z['v_' + k])
                lev[k].append(ids[z[k]])
            h = V.map('heads', z['v_heads'])
            npk = len(z['gold'])
            tp += [z['ph_p'] + np0, z['sc_p'] + np0, np.arange(npk) + np0]
            tk += [h[z['ph_k']], h[z['sc_k']], h[z['last']]]
            np0 += npk
        self.A, self.P = np.vstack(As), np.vstack(Ps)
        self.starts = np.array(starts)
        self.gold = np.concatenate(gold)
        self.m = {k: np.concatenate(v) for k, v in m.items()}
        self.key = {k: np.concatenate(v) for k, v in lev.items()}
        self.n = len(self.gold)
        self.pick = np.repeat(np.arange(self.n), np.diff(self.starts))
        self.task = self.m['task']
        self.fold = np.array([fold_of(t) for t in self.task.tolist()])
        lq = self.A[:, 0].astype(np.float64)
        mx = np.maximum.reduceat(lq, self.starts[:-1])
        e = np.exp(lq - mx[self.pick])
        self.q = e / np.add.reduceat(e, self.starts[:-1])[self.pick]
        self.goldrow = self.starts[:-1] + self.gold
        self.isgold = np.zeros(len(lq), bool)
        self.isgold[self.goldrow] = True
        tp, tk = np.concatenate(tp), np.concatenate(tk)
        self.tp, self.tk = tp, tk

    def freeze(self, V):
        """Builds what needs the whole vocabulary: refined relation keys are made first by `refine`."""
        nt = len(V.m['heads'])
        M = sp.coo_matrix((np.ones(len(self.tp), np.float32), (self.tp, self.tk)), shape=(self.n, nt)).tocsr()
        M.data[:] = 1
        self.tok = M
        self.tokc = M.tocsc()

    def relabel(self, seed):
        """A label drawn from q at each pick, as the rank read's control: under it the prior is right, and no fact can gain."""
        rng = np.random.RandomState(seed)
        u = rng.random_sample(self.n)
        c = np.cumsum(self.q)
        base = np.concatenate([[0.0], c[self.starts[1:-1] - 1]])
        g = np.searchsorted(c, base + u * (c[self.starts[1:] - 1] - base), side='right') - self.starts[:-1]
        g = np.minimum(np.maximum(g, 0), np.diff(self.starts) - 1)
        self.gold = g
        self.goldrow = self.starts[:-1] + g
        self.isgold[:] = False
        self.isgold[self.goldrow] = True


def refine(D, V):
    """The relation key of a form with a body gets the option's column types: `rule:input` holds many kinds of relation, and the types are in the option's row."""
    names = V.list('rel')
    ix = [STRUCT.index('type_' + t) for t in TYPES]
    isdet = np.array([n.startswith(('rule:', 'det:')) for n in names])
    rows = np.nonzero(isdet[D.key['rel']])[0]
    code = (D.A[rows][:, ix] > 0).astype(np.int64) @ (1 << np.arange(len(TYPES)))
    pair = D.key['rel'][rows].astype(np.int64) * 4096 + code
    u, inv = np.unique(pair, return_inverse=True)
    new = np.zeros(len(u), np.int32)
    d = V.m['rel']
    for i, p in enumerate(u.tolist()):
        n = names[p // 4096]
        c = p % 4096
        s = '%s|%s' % (n, ','.join(t for b, t in enumerate(TYPES) if c >> b & 1))
        if s not in d:
            d[s] = len(d)
        new[i] = d[s]
    D.key['rel'][rows] = new[inv]
    # The mixed level: a lib relation, fact or operator is its own key, and a derived option is the family of its form.
    fn = V.list('fam')
    rn = V.list('rel')
    isder = np.array([n.startswith('derived') for n in fn])
    hy = np.zeros(len(D.q), np.int32)
    der = isder[D.key['fam']]
    hd = V.m['hyb']
    fmap = np.array([hd.setdefault(n, len(hd)) if isder[i] else -1 for i, n in enumerate(fn)], np.int32)
    rmap = np.full(len(rn), -1, np.int32)
    used = np.unique(D.key['rel'][~der])
    for r in used.tolist():
        rmap[r] = hd.setdefault(rn[r], len(hd))
    hy[der] = fmap[D.key['fam'][der]]
    hy[~der] = rmap[D.key['rel'][~der]]
    D.key['hyb'] = hy


class Rows:
    """Index of rows by key at a level."""

    def __init__(self, D, level):
        k = D.key[level]
        o = np.argsort(k, kind='stable')
        ks, st = np.unique(k[o], return_index=True)
        self.o, self.ks, self.st = o, ks, np.append(st, len(o))
        self.ix = {int(x): i for i, x in enumerate(ks)}

    def get(self, key):
        i = self.ix.get(key)
        return self.o[self.st[i]:self.st[i + 1]] if i is not None else np.zeros(0, np.int64)


def sample_picks(D, rows, cap, seed):
    """Rows of the kept picks and their weights. A pick with gold in the key stays. Another stays with chance min(1, its key mass / tau), at weight 1 / chance."""
    pr = D.pick[rows]
    first = np.nonzero(np.diff(pr, prepend=-1))[0]
    ends = np.append(first[1:], len(rows))
    mass = np.add.reduceat(D.q[rows], first)
    hasg = np.logical_or.reduceat(D.isgold[rows], first)
    if len(rows) <= cap:
        return rows, np.ones(len(rows), np.float32)
    per = len(rows) / len(first)
    want = max(cap / per - hasg.sum(), 50)
    m = mass[~hasg]
    if len(m) == 0:
        return rows, np.ones(len(rows), np.float32)
    lo, hi = 1e-9, float(m.max()) + 1e-9
    for _ in range(40):
        mid = math.sqrt(lo * hi)
        if np.minimum(1, m / mid).sum() > want:
            lo = mid
        else:
            hi = mid
    pk = np.minimum(1, mass / hi)
    pk[hasg] = 1
    keep = np.random.RandomState(seed).random_sample(len(first)) < pk
    idx = np.nonzero(keep)[0]
    lens = ends - first
    sel = np.repeat(first[idx], lens[idx]) + np.concatenate([np.arange(x) for x in lens[idx]])
    w = np.repeat((1 / pk[idx]).astype(np.float32), lens[idx])
    return rows[sel], w


def groups(D, rows):
    """Group index of a row in rows (sorted by pick), the group starts, and the mass of the rest of each pick."""
    pr = D.pick[rows]
    gs = np.nonzero(np.diff(pr, prepend=-1))[0]
    gid = np.cumsum(np.diff(pr, prepend=-1) != 0) - 1
    rest = np.maximum(1 - np.add.reduceat(D.q[rows], gs), 1e-12)
    return gid, gs, rest


def soft(q, d, gid, gs, rest):
    e = q * np.exp(d)
    tot = rest + np.add.reduceat(e, gs)
    return e / tot[gid], tot


def dense(D, rows):
    return np.hstack([D.A[rows], D.P[D.pick[rows]]], dtype=np.float32)


def facts(D, rows, w, q, y, gid, gs, rest, ntok, lam, seed, selfkeys=0):
    """The binary facts of a key's rows: thresholds at quantiles of each number, and the tokens with most gain at the first step. (matrix, facts as (kind, column, threshold))"""
    Dm = dense(D, rows)
    n = len(rows)
    rng = np.random.RandomState(seed)
    sub = rng.choice(n, min(n, 2500), replace=False)
    Q = np.quantile(Dm[sub], QS, axis=0)
    lo = Dm[sub].min(axis=0)
    fl, cols = [], []
    for c in range(Dm.shape[1]):
        if c in DROP_COLS or (lo[c] == Q[-1, c] and Dm[sub, c].max() == lo[c]):
            continue
        ts = sorted({float(x) for x in Q[:, c] if x > lo[c]})
        if not ts and Dm[sub, c].max() > lo[c]:
            ts = [float(Dm[sub, c].max())]
        for t in ts:
            cols.append(Dm[:, c] >= t)
            fl.append(('x', c, t))
    if selfkeys:  # a family's trees may split on the option's own component or relation key, where its rows support that
        for lev, kind in (('comp', 'c'), ('rel', 'r')):
            k = D.key[lev][rows]
            ids, cnt = np.unique(k[y > 0], return_counts=True)
            for i in ids[np.argsort(-cnt)[:selfkeys]].tolist():
                cols.append(k == i)
                fl.append((kind, i, 1.0))
    p, _ = soft(q, np.zeros(n), gid, gs, rest)
    G, H = w * (y - p), w * np.maximum(p * (1 - p), 1e-6)
    T = D.tok[D.pick[rows]]
    Gt, Ht, Yt = T.T @ G, T.T @ H, T.T @ y
    Gs, Hs = G.sum(), H.sum()
    with np.errstate(divide='ignore', invalid='ignore'):
        gain = Gt ** 2 / (Ht + lam) + (Gs - Gt) ** 2 / (Hs - Ht + lam)
    gain[(Yt < 2) & (Ht < 2)] = -1
    if DROP_TOK is not None:
        gain[DROP_TOK] = -1
    top = np.argsort(-gain)[:ntok]
    top = top[gain[top] > 0]
    if len(top):
        dt = T[:, top].toarray().astype(np.float32)
        B = np.hstack([np.array(cols, dtype=np.float32).T.reshape(n, -1), dt])
        fl += [('t', int(t), 1.0) for t in top]
    else:
        B = np.array(cols, dtype=np.float32).T.reshape(n, -1)
    return B, fl


def side_split(B, G, H, lam, minh):
    """The best split of a side's rows: (column or -1, value if the fact holds, value if not)."""
    Gs, Hs = float(G.sum()), float(H.sum())
    base = Gs ** 2 / (Hs + lam)
    G1, H1 = B.T @ G, B.T @ H
    G0, H0 = Gs - G1, Hs - H1
    gain = G1 ** 2 / (H1 + lam) + G0 ** 2 / (H0 + lam)
    gain[(H1 < minh) | (H0 < minh)] = -1
    c = int(np.argmax(gain))
    if gain[c] <= base:
        return -1, Gs / (Hs + lam), Gs / (Hs + lam)
    return c, float(G1[c] / (H1[c] + lam)), float(G0[c] / (H0[c] + lam))


def grow(B, G, H, m, lam, minh, depth):
    """A tree on the binary facts over rows m (a 0/1 float array): a leaf's value, or (column, tree where the fact holds, tree where not)."""
    Gm, Hm = G * m, H * m
    Gs, Hs = float(Gm.sum()), float(Hm.sum())
    leaf = Gs / (Hs + lam)
    if depth == 0 or Hs < 2 * minh:
        return leaf
    c, _v1, _v0 = side_split(B, Gm, Hm, lam, minh)
    if c < 0:
        return leaf
    x = B[:, c]
    return (c, grow(B, G, H, m * x, lam, minh, depth - 1), grow(B, G, H, m * (1 - x), lam, minh, depth - 1))


def tree_values(t, B):
    if not isinstance(t, tuple):
        return t
    a, b = tree_values(t[1], B), tree_values(t[2], B)
    return np.where(B[:, t[0]] > 0, a, b)


def boost_trees(q, y, w, gid, gs, rest, B, rounds, eta, lam, minh, depth):
    """Boosted trees of the given depth on the binary facts, each a Newton step on the block's soft-max loss."""
    np.seterr(all='ignore')
    n = len(q)
    d = np.zeros(n)
    out = []
    w64 = w.astype(np.float64)
    one = np.ones(n, np.float32)
    for r in range(rounds):
        p, _ = soft(q, d, gid, gs, rest)
        G = (w64 * (y - p)).astype(np.float32)
        H = (w64 * np.maximum(p * (1 - p), 1e-6)).astype(np.float32)
        t = grow(B, G, H, one, lam, minh, depth)
        out.append(t)
        d += eta * tree_values(t, B)
    return out


def tree_json(t, fl):
    """A tree with its facts as (kind, column, threshold): a number, or [fact, tree if it holds, tree if not]."""
    if not isinstance(t, tuple):
        return round(t, 5)
    return [list(fl[t[0]]), tree_json(t[1], fl), tree_json(t[2], fl)]


def tree_eval(D, rows, t, cache):
    if not isinstance(t, list):
        return t
    x = mask_of(D, rows, tuple(t[0]), cache)
    return np.where(x, tree_eval(D, rows, t[1], cache), tree_eval(D, rows, t[2], cache))


def boost(q, y, w, gid, gs, rest, B, rounds, eta, lam, minh):
    """Stumps on the binary facts, each a Newton step on the block's soft-max loss. (column, value if the fact holds, value if not) per round; column -1 is the intercept."""
    np.seterr(all='ignore')  # Accelerate's float32 matmul sets the flags on finite values
    n = len(q)
    d = np.zeros(n)
    out = []
    w64 = w.astype(np.float64)
    for r in range(rounds):
        p, _ = soft(q, d, gid, gs, rest)
        G = (w64 * (y - p)).astype(np.float32)
        H = (w64 * np.maximum(p * (1 - p), 1e-6)).astype(np.float32)
        Gs, Hs = float(G.sum()), float(H.sum())
        best, bc, b1, b0 = Gs ** 2 / (Hs + lam), -1, Gs / (Hs + lam), Gs / (Hs + lam)
        if B.shape[1]:
            G1, H1 = B.T @ G, B.T @ H
            G0, H0 = Gs - G1, Hs - H1
            gain = G1 ** 2 / (H1 + lam) + G0 ** 2 / (H0 + lam)
            gain[(H1 < minh) | (H0 < minh)] = -1
            c = int(np.argmax(gain))
            if gain[c] > best:
                best, bc, b1, b0 = float(gain[c]), c, float(G1[c] / (H1[c] + lam)), float(G0[c] / (H0[c] + lam))
        out.append((bc, b1, b0))
        if bc < 0:
            d += eta * b1
        else:
            x = B[:, bc]
            d += eta * (b1 * x + b0 * (1 - x))
    return out


def mask_of(D, rows, f, cache):
    k = (f[0], f[1], f[2])
    v = cache.get(k)
    if v is None:
        if f[0] == 'c':
            v = D.key['comp'][rows] == f[1]
        elif f[0] == 'r':
            v = D.key['rel'][rows] == f[1]
        elif f[0] == 'x':
            c = f[1]
            na = D.A.shape[1]
            col = D.A[rows, c] if c < na else D.P[D.pick[rows], c - na]
            v = col >= f[2]
        else:
            t = f[1]
            m = np.zeros(D.n, bool)
            m[D.tokc.indices[D.tokc.indptr[t]:D.tokc.indptr[t + 1]]] = True
            v = m[D.pick[rows]]
        cache[k] = v
    return v


def path(D, rows, stumps, eta, cps):
    """The model's delta on rows at each checkpoint of rounds. (rows x checkpoints)"""
    out = np.zeros((len(rows), len(cps)))
    d = np.zeros(len(rows))
    cache = {}
    cps = list(cps)
    if 0 in cps:
        out[:, cps.index(0)] = 0
    for r, st in enumerate(stumps, 1):
        kind = st[0]
        if kind == 'T':
            d = d + eta * tree_eval(D, rows, st[1], cache)
        elif kind == 'i':
            d = d + eta * st[3]
        else:
            c, t, v1, v0 = st[1:]
            x = mask_of(D, rows, (kind, c, t), cache)
            d = d + eta * np.where(x, v1, v0)
        if r in cps:
            out[:, cps.index(r)] = d
    return out


def solo(D, rows, d):
    """Nats gained at each pick of `rows` when only this key's delta applies, with the picks. Each pick counts its loss too, where gold is another key's."""
    gid, gs, rest = groups(D, rows)
    _, tot = soft(D.q[rows], d, gid, gs, rest)
    gain = -np.log(tot)
    g = np.nonzero(D.isgold[rows])[0]
    np.add.at(gain, gid[g], d[g])
    return gain, D.pick[rows[gs]]


def apply_models(D, level_rows, models, eta, keep=None):
    """Sum of the deltas of models {(level, key): stumps at their chosen length} over D's option rows."""
    F = np.zeros(len(D.q))
    for (level, key), st in models.items():
        rows = level_rows[level].get(key)
        if keep is not None:
            rows = rows[keep[D.pick[rows]]]
        if len(rows) == 0 or not st:
            continue
        F[rows] += path(D, rows, st, eta, [len(st)])[:, 0]
    return F


def saved_bits(D, F):
    """Bits saved at each pick by the soft-max of q exp(F), against q."""
    e = D.q * np.exp(F)
    tot = np.add.reduceat(e, D.starts[:-1])
    return (F[D.goldrow] - np.log(tot)) / LN2


CLS = {'relation': 'derived', 'lib relation': 'lib'}


def klass(D):
    out = []
    for k, own in zip(D.m['gold_kind'].tolist(), D.m['own'].tolist()):
        if k in ('NOT', 'CMP'):
            out.append('rest')
        elif own:
            out.append('own')
        else:
            out.append(CLS.get(k, 'rest'))
    return np.array(out)


def boot(saved, tasks, mask, B=10000, seed=0):
    """(mean saved per pick, 95% interval) by resampling tasks: the rank read's function."""
    u = sorted(set(tasks.tolist()))
    ix = {t: i for i, t in enumerate(u)}
    t = np.array([ix[x] for x in tasks.tolist()])
    s = np.bincount(t[mask], saved[mask], len(u))
    n = np.bincount(t[mask], minlength=len(u)).astype(float)
    W = np.random.RandomState(seed).multinomial(len(u), [1.0 / len(u)] * len(u), B)
    den = W @ n
    r = (W @ s)[den > 0] / den[den > 0]
    return float(s.sum() / max(n.sum(), 1)), float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))
