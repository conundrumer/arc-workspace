"""The read-side pick hook (design.md, "How the score enters the pick"): the pick state and facts of an atom start, the fitted model, and the weight arithmetic of the arms.

Imported by job3.py (the read) and checks.py (row parity). The facts come from feats.py, as in rows.py.

Arms (weights `w` of the options; D the derived options, B the others; T_D, T_B, T their sums; e_o = exp(s_o) where w[o] > 0 else 0; E the sum of e over D; Z_B = sum over B of w * rf):
    off   weights * rf
    M1    D: T_D e / E        B: T_B w rf / Z_B
    M2    D: T sigma e / E    B: T (1 - sigma) w rf / Z_B           (where E == 0, B gets T)
    M2s   M2 at the picks where today's steer acts; at rel_off picks (rf = 1 there) the weights stay as P has them
    G     M1's lines with s_o = log(w[o] rf[o])  (group_steer with the kit's factors)
Where E == 0 the D lines keep w; where Z_B == 0 the B lines keep w.
"""
import math

import numpy as np
import warnings

warnings.filterwarnings('ignore', message='.*encountered in matmul')  # spurious flags of the macOS BLAS: the products are exact (checked against einsum)

import feats


def base_of(dr, t):
    """(head, j) of the derived option token t, as rows.py:base_of."""
    name = dr.V.name(t)
    nm = dr.prog_names.get(name, name)
    h, _, sub = nm.partition('.')
    head = dr._pg.written.get(h, h)
    return (head, int(sub) if sub.isdigit() else (sub or None))


def pick_state(dr, n):
    der, bd, nd, nb = feats.drawn_state(dr, dr._pg)
    hk = 'DET' if dr._kind == 'RIGID_DET' else dr._kind
    return dict(hk=hk, pl=feats.place_of(getattr(dr, 'place', None)), ph=n.phase, sty=sorted({str(x) for x in dr.p_scope}), dd=der, bd=bd)


def pick_facts(dr, n, opts, ws, scope, miss=None):
    """(st, d_idx, bases, facts, gate facts) for the derived options with ws > 0 (d_idx their indices in opts)."""
    KIND = dr.fr.KIND
    st = pick_state(dr, n)
    d_idx = [i for i, t in enumerate(opts) if KIND[t] == 'relation' and ws[i] > 0]
    bases = [base_of(dr, opts[i]) for i in d_idx]
    return st, d_idx, bases, feats.option_facts(scope, st, bases, miss), feats.gate_facts(scope, st, len(d_idx))


class Model:
    def __init__(self, fitdir):
        import json
        import os
        import pickle
        m = json.load(open(fitdir + '/model.json'))
        self.opt, self.beta, self.rank = feats.Std.from_json(m), np.array(m['beta']), m['rank']
        g = json.load(open(fitdir + '/gate.json'))
        self.gate, self.coef, self.icpt = feats.Std.from_json(g), np.array(g['coef']), g['intercept']
        self.temp, self.bias = g.get('temp', 1.0), g.get('bias', 0.0)  # a temperature and bias on the gate's logit (identity where the gate file has none)
        self.hgb = pickle.load(open(fitdir + '/hgb.pkl', 'rb')) if self.rank == 'hgb' and os.path.exists(fitdir + '/hgb.pkl') else None
        assert self.rank == 'logit' or self.hgb is not None

    def scores(self, facts):
        if self.rank == 'hgb':
            return self.hgb.decision_function(self.opt.dense(facts))
        return self.opt.matrix(facts) @ self.beta

    def sigma(self, gf, s):
        mx = float(np.max(s))
        lse = mx + math.log(float(np.sum(np.exp(s - mx))))
        d = self.gate.dense([gf])
        d[0, self.gate.ix['lse']] = lse - math.log(len(s))
        d[0, self.gate.ix['mx']] = mx - lse
        z = (((d - np.array(self.gate.mean)) / np.array(self.gate.scale))[0] @ self.coef + self.icpt) * self.temp + self.bias
        return 1.0 / (1.0 + math.exp(-z))


def arm_weights(arm, w, rf, is_d, e, sigma):
    """The weights of one list (the main weights or alt) under the arm. w, rf: lists; is_d: flags; e: the exp scores (0 where w is 0 or the option is not in D); sigma for M2."""
    out = list(w)
    D = [i for i in range(len(w)) if is_d[i]]
    B = [i for i in range(len(w)) if not is_d[i]]
    TD, TB = sum(w[i] for i in D), sum(w[i] for i in B)
    T = TD + TB
    E = sum(e[i] for i in D if w[i] > 0)
    ZB = sum(w[i] * rf[i] for i in B)
    if arm == 'M2':
        dt, bt = T * sigma, (T * (1 - sigma) if E > 0 else T)
    else:
        dt, bt = TD, TB
    if E > 0:
        for i in D:
            out[i] = dt * e[i] / E if w[i] > 0 else 0.0
    if ZB > 0:
        for i in B:
            out[i] = bt * w[i] * rf[i] / ZB
    return out
