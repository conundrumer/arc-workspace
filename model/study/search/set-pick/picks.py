"""The three scope picks on one pool, and the co-read lift of the fit.

ship_pick / refit_pick: Policy.scope of policy.py: the top max(1, k - k // 4) nodes by score - uses + Gumbel, then the least used (lowest id among ties, as policy.py does).
joint_pick: the first node is the top node by the shipped key (shipped score - uses + Gumbel, the same Gumbel draws as ship_pick).
  Each further node is the top node by  shipped key + beta * tau(x | scope),  tau = log of the mean, over the nodes already in the scope, of lift(shape of s, shape of x) * Ident factor.
  beta = None is the pure set pick: the top node by tau, the shipped key breaking ties.
lift(a, b) = P(b among the co-reads of a) / P(b among all co-reads), from the gold fit, smoothed level by level (L0 to L3) toward the coarser level with KAPPA pseudo-counts.
Nothing here reads atom order, atom index or last-atom facts. The least-used slot of ship_pick and refit_pick is the shipped policy's own rule.
"""
import json, math
import numpy as np

KAPPA = 2.0
HERE = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/set-pick'


class Model:
    def __init__(self, path=HERE + '/model.json'):
        m = json.load(open(path))
        self.C, self.M, self.ident = m['C'], m['M'], m['ident']
        self.Ca = [{a: sum(v.values()) for a, v in c.items()} for c in self.C]
        self.tot = [sum(x.values()) for x in self.M]

    def lift(self, a, b):
        """a, b: tuples of the four level keys."""
        up = 1.0
        for L in (3, 2, 1, 0):
            ca = self.Ca[L].get(a[L], 0.0)
            cab = self.C[L].get(a[L], {}).get(b[L], 0.0)
            p = self.M[L].get(b[L], 0.0) / self.tot[L]
            if p > 0:
                up = (cab + KAPPA * p * up) / ((ca + KAPPA) * p)
            else:
                up = up * KAPPA / (ca + KAPPA)
        return up


class Pool:
    """The facts of one job's nodes (prep record), with the lift of each anchor shape against each shape id cached."""

    def __init__(self, rec, model):
        self.model = model
        keys = list(zip(*rec['L']))
        self.shape_ids, sid = [], {}
        self.shapes = []
        for k in keys:
            if k not in sid:
                sid[k] = len(self.shapes)
                self.shapes.append(k)
            self.shape_ids.append(sid[k])
        self.shape_ids = np.array(self.shape_ids)
        self.src = [frozenset(s) for s in rec['src']]
        self.ident_nodes = np.array([i for i, s in enumerate(self.src) if s], dtype=np.int64)
        self.ship = np.array(rec['ship'], dtype=np.float64)
        self.refit = np.array(rec['refit'], dtype=np.float64) if rec.get('refit') is not None else None
        self.cache = {}
        self.f_same, self.f_diff = model.ident['same'], model.ident['diff']

    def lift_vec(self, a):
        v = self.cache.get(a)
        if v is None:
            v = self.cache[a] = np.array([self.model.lift(self.shapes[a], b) for b in self.shapes])
        return v

    def pair_factor(self, s, n):
        """Lift of every node 0..n-1 as a co-read of node s, with the Ident factor."""
        v = self.lift_vec(self.shape_ids[s])[self.shape_ids[:n]].copy()
        if self.src[s]:
            ss = self.src[s]
            for i in self.ident_nodes[self.ident_nodes < n]:
                v[i] *= self.f_same if self.src[i] & ss else self.f_diff
        return v


def gumbel(rng, n):
    r = rng.random(n)
    r = np.where(r == 0, 1e-12, r)
    return -np.log(-np.log(r))


def policy_pick(score, uses, g, n, k):
    if n == 0:
        return []
    key = score[:n] - uses[:n] + g[:n]
    nb = min(n, max(1, k - k // 4))
    best = list(np.argsort(-key, kind='stable')[:nb])
    bs = set(best)
    rest = sorted((i for i in range(n) if i not in bs), key=lambda i: (uses[i], i))[:k - nb]
    return [int(i) for i in best + rest]


def joint_pick(pool, uses, g, n, k, beta):
    if n == 0:
        return []
    base = pool.ship[:n] - uses[:n] + g[:n]
    first = int(np.argmax(base))
    got = [first]
    acc = pool.pair_factor(first, n)
    taken = np.zeros(n, bool)
    taken[first] = True
    while len(got) < min(k, n):
        tau = np.log(acc / len(got))
        key = (tau * 1e6 + base) if beta is None else (base + beta * tau)
        key = np.where(taken, -np.inf, key)
        x = int(np.argmax(key))
        got.append(x)
        taken[x] = True
        acc = acc + pool.pair_factor(x, n)
    return got
