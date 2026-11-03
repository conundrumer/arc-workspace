"""Shared pieces of the gate calibration (training rows only): load the cache, whole-pick bits under M2 for a given sigma, calibration tables."""
import numpy as np

X = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-derived-pick-model-heldout37'
NF = 5


class C:
    def __init__(self, tag='cache'):
        z = np.load(X + '/cal/%s.npz' % tag)
        for k in z.files:
            setattr(self, k, z[k])
        self.NR = len(self.n)
        self.starts = np.concatenate([[0], np.cumsum(self.n)[:-1]])
        self.rid = np.repeat(np.arange(self.NR), self.n)
        mx = np.maximum.reduceat(self.s, self.starts)
        self.mx = mx
        self.lse = mx + np.log(np.add.reduceat(np.exp(self.s - mx[self.rid]), self.starts))
        self.names = list(self.gate_names)
        ix = {n: i for i, n in enumerate(self.names)}
        self.ix = ix
        G = self.G.copy()
        G[:, ix['lse']] = self.lse - np.log(self.n)
        G[:, ix['mx']] = self.mx - self.lse
        self.G = G
        self.y = (self.gtype == 0).astype(int)
        self.read = self.y == 1
        SD = np.add.reduceat(self.ows, self.starts)
        self.SD = SD
        SDr = np.add.reduceat(self.ows * self.orf, self.starts)
        gi = np.nonzero(self.ogold > 0)[0]
        gd = np.zeros(self.NR)
        gd[self.rid[gi]] = self.s[gi] - self.lse[self.rid[gi]]
        wsg = np.zeros(self.NR)
        wsg[self.rid[gi]] = self.ows[gi]
        rfg = np.zeros(self.NR)
        rfg[self.rid[gi]] = self.orf[gi]
        gbw = self.gws * self.grf
        isd = self.read
        self.log2_inD = gd / np.log(2)  # log2 of gold's share within D (read rows)
        with np.errstate(divide='ignore', invalid='ignore'):
            self.log2_inB = np.log2(np.where(self.ZB > 0, gbw / np.where(self.ZB > 0, self.ZB, 1), 0.0))  # builtin/op rows: log2 of gold's share within B
        self.off_bits = -np.log2(np.maximum(np.where(isd, wsg * rfg, gbw) / (self.ZB + SDr), 1e-300))
        self.TBpos = self.TB > 0

    def m2_bits(self, sigma):
        """Whole-pick bits under M2. Where TB == 0 and gold is derived, sigma is 1 (as fit.py)."""
        sh = np.where(self.read, np.where(self.TBpos, sigma, 1.0) * np.exp(self.log2_inD * np.log(2)),
                      (1 - sigma) * np.where(self.ZB > 0, np.exp(self.log2_inB * np.log(2)), 0.0))
        return -np.log2(np.maximum(sh, 1e-300))

    def m1_bits(self):
        with np.errstate(divide='ignore', invalid='ignore'):
            gbw = self.gws * self.grf
            sh = np.where(self.read, self.SD * np.exp(self.log2_inD * np.log(2)), np.where(self.ZB > 0, self.TB * gbw / np.where(self.ZB > 0, self.ZB, 1), 0.0)) / (self.SD + self.TB)
        return -np.log2(np.maximum(sh, 1e-300))

    def wmean(self, v, m=None):
        w = self.W
        if m is not None:
            v, w = v[m], w[m]
        return float((v * w).sum() / w.sum())

    def tab(self, bits):
        out = {}
        for nm, m in (('all', np.ones(self.NR, bool)), ('read', self.read), ('builtin', self.gtype == 1), ('op', self.gtype == 2)):
            out[nm] = self.wmean(bits, m)
        return out


def sig(z):
    return 1.0 / (1.0 + np.exp(-z))
