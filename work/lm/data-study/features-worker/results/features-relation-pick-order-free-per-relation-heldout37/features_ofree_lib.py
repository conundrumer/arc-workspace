"""Rows as arrays, the baseline, and a soft-max with a model per key.

Options of a row: every lib relation, macro, fact and comparison of the corpus and registry, NOT, and the scope's derived relations.

Baseline: q(option) is the option's rate of being the label among the rows that offer it, on fit rows of the same group (kind of body, and under NOT or not). A derived option's rate is by its component port or proposer, shrunk to its form family. No fact and no order enters.

Model: each key k has a weight per fact f. An option's score is log q plus, over the option's keys, the key's intercept plus the sum of the key's weights on the row's facts. A lib relation has one key, its name. A derived option has its family, its component, its port, and one key per head of its form's body, as a set. A key with under min_gold gold rows has no weights, so it stays at its marginal, or at the keys above it. So a sparse key falls back. Option facts add one weight each, shared over the derived options.
"""
import json
import math
import os
import sys
import time
import zlib

import numpy as np
import scipy.optimize as so
import scipy.sparse as sp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features_ofree_facts as FL  # noqa: E402
import features_ofree_text as T  # noqa: E402

ME = os.path.dirname(os.path.abspath(__file__)) + '/'
LN2 = math.log(2)
np.seterr(all='ignore')  # Accelerate's matmul sets the flags on finite values
FOLDS = 4
GROUP = {'RULE': 'RULE', 'DET': 'DET', 'key': 'INIT', 'port': 'INIT'}
OPS = ['op:NOT'] + ['op:' + x for x in T.CMP]
SHRINK = 5.0
ALPHA = .5


def fold_of(task):
    return zlib.crc32(('ofree' + task).encode()) % FOLDS


def load(which):
    with open(ME + 'rows/%s.jsonl' % which) as f:
        return [json.loads(x) for x in f]


def lib_vocab(recs):
    """Lib names of the registry and of the fit rows. The set never reads held rows."""
    reg = T.Registry()
    s = set(reg.kind) | {'derived-unknown'}
    for rc in recs:
        for r in rc['rows']:
            if r['cl'] not in ('derived', 'NOT', 'comparison'):
                s.add(r['key'])
    return OPS + sorted(s)


def option_keys(o):
    out = ['D:' + o['fam'], 'T:' + o['tok']]
    if o['comp']:
        out.append('C:' + o['comp'])
    if o['fam'] in ('derived-rule', 'derived-det'):
        out += ['B:' + h for h in o['heads']]
    return out


class Data:
    """Rows of one group. `facts_of(r, rec)` gives a row's fact names and `opt_of(o, r, rec)` an option's. `like` shares the fact ids of a fit's Data."""

    def __init__(self, recs, group, libs, tier, facts_of=None, opt_of=None, like=None):
        self.libs = libs
        self.lix = {k: i for i, k in enumerate(libs)}
        self.fv = like.fv if like is not None else {}
        self.pv = like.pv if like is not None else {}
        facts_of = facts_of or (lambda r, rec: FL.row_facts(r, rec, tier))
        opt_of = opt_of or (lambda o, r, rec: FL.option_facts(o, r, rec, tier))
        fp, fi = [0], []
        self.task, self.line, self.key, self.cl, self.neg, self.ygold_lib, self.ygold_opt, self.place = [], [], [], [], [], [], [], []
        orow, oinfo, ofacts_p, ofacts_i = [], [], [0], []
        miss = 0
        fv = self.fv
        pv = self.pv
        for rc in recs:
            for r in rc['rows']:
                if GROUP[r['place']] != group:
                    continue
                i = len(self.task)
                self.task.append(rc['task'])
                self.line.append(rc['line'])
                self.key.append(r['key'])
                self.cl.append(r['cl'])
                self.place.append(r['place'])
                self.neg.append('not' in r['under'])
                for n in facts_of(r, rc):
                    fi.append(fv.setdefault(n, len(fv)))
                fp.append(len(fi))
                gold_opt = -1
                start = len(oinfo)
                for o in rc['opts']:
                    orow.append(i)
                    if r['fid'] == o['f'] and r['lp'] == o['p']:
                        gold_opt = len(oinfo)
                    oinfo.append(o)
                    for n in opt_of(o, r, rc):
                        ofacts_i.append(pv.setdefault(n, len(pv)))
                    ofacts_p.append(len(ofacts_i))
                gl = self.lix.get(r['key'], -1) if r['cl'] != 'derived' else -1
                if r['cl'] == 'derived' and gold_opt < 0:
                    miss += 1
                    for j, o in enumerate(rc['opts']):  # a port that the registry doesn't list: the form's first port stands for it
                        if o['f'] == r['fid']:
                            gold_opt = start + j
                            break
                    if gold_opt < 0:
                        gl = self.lix['derived-unknown']
                if r['cl'] != 'derived' and gl < 0:
                    miss += 1
                    gl = self.lix['derived-unknown']
                self.ygold_lib.append(gl)
                self.ygold_opt.append(gold_opt)
        self.n = len(self.task)
        self.miss = miss
        self.task = np.array(self.task)
        self.line = np.array(self.line)
        self.neg = np.array(self.neg, bool)
        self.cl = np.array(self.cl)
        self.keys = np.array(self.key)
        self.place = np.array(self.place)
        self.ygold_lib = np.array(self.ygold_lib, np.int64)
        self.ygold_opt = np.array(self.ygold_opt, np.int64)
        self.F = sp.csr_matrix((np.ones(len(fi), np.float64), np.array(fi, np.int64), np.array(fp)), shape=(self.n, max(len(fv), 1)))
        self.orow = np.array(orow, np.int64)
        self.oinfo = oinfo
        self.m = len(oinfo)
        self.P = sp.csr_matrix((np.ones(len(ofacts_i)), np.array(ofacts_i, np.int64), np.array(ofacts_p)), shape=(self.m, max(len(pv), 1)))
        self.fold = np.array([fold_of(t) for t in self.task])
        self.mask_ops = np.zeros((self.n, len(libs)), bool)
        self.mask_ops[np.ix_(np.nonzero(self.neg)[0], np.arange(len(OPS)))] = True

    def shuffled(self, seed):
        """The labels of a control: a permutation of the labels over rows, under NOT or not apart. A derived label moves to an option of the same port, else of the same family, else to any option of the row."""
        rng = np.random.RandomState(seed)
        yl, yo = self.ygold_lib.copy(), self.ygold_opt.copy()
        first = np.searchsorted(self.orow, np.arange(self.n))
        last = np.searchsorted(self.orow, np.arange(self.n), side='right')
        for ng in (False, True):
            r = np.nonzero(self.neg == ng)[0]
            p = rng.permutation(r)
            for i, s in zip(r.tolist(), p.tolist()):
                j = self.ygold_opt[s]
                if j < 0:
                    yl[i], yo[i] = self.ygold_lib[s], -1
                    continue
                o = self.oinfo[j]
                c = list(range(first[i], last[i]))
                a = [x for x in c if self.oinfo[x]['tok'] == o['tok']] or [x for x in c if self.oinfo[x]['fam'] == o['fam']] or c
                if a:
                    yl[i], yo[i] = -1, a[rng.randint(len(a))]
                else:
                    yl[i], yo[i] = self.lix['derived-unknown'], -1
        return yl, yo


class Baseline:
    """The marginal among the options, under NOT or not, with a port's rate shrunk to its family's."""

    def __init__(self, D, tr):
        ntr = np.bincount(D.neg[tr].astype(int), minlength=2).astype(float)
        cnt = np.zeros((2, len(D.libs)))
        g = D.ygold_lib[tr]
        ok = g >= 0
        np.add.at(cnt, (D.neg[tr][ok].astype(int), g[ok]), 1)
        self.loglib = np.log((cnt + ALPHA) / (ntr[:, None] + 1.0))
        trm = np.zeros(D.n, bool)
        trm[tr] = True
        gold = np.zeros(D.m, bool)
        y = D.ygold_opt[tr]
        gold[y[y >= 0]] = True
        offf, offt, gf, gt = {}, {}, {}, {}
        for j in np.nonzero(trm[D.orow])[0].tolist():
            o = D.oinfo[j]
            ng = int(D.neg[D.orow[j]])
            a, b = (ng, o['fam']), (ng, o['tok'])
            offf[a] = offf.get(a, 0) + 1
            offt[b] = offt.get(b, 0) + 1
            if gold[j]:
                gf[a] = gf.get(a, 0) + 1
                gt[b] = gt.get(b, 0) + 1
        self.rf = {a: (gf.get(a, 0) + ALPHA) / (v + 1.0) for a, v in offf.items()}
        self.offt, self.gt = offt, gt
        self.floor = ALPHA / (float(ntr.max()) + 1.0)

    def rate(self, ng, o):
        fr = self.rf.get((ng, o['fam']), self.floor)
        b = (ng, o['tok'])
        return (self.gt.get(b, 0) + SHRINK * fr) / (self.offt.get(b, 0) + SHRINK)

    def fill(self, D):
        memo = {}
        out = np.zeros(D.m)
        for j, (i, o) in enumerate(zip(D.orow.tolist(), D.oinfo)):
            k = (bool(D.neg[i]), o['fam'], o['tok'])
            v = memo.get(k)
            if v is None:
                v = memo[k] = math.log(max(self.rate(int(k[0]), o), 1e-9))
            out[j] = v
        return out


class Model:
    def __init__(self, D, tr, lam, min_gold=5, min_df=8, maxiter=80, ctrl=None):
        """Fits on rows tr of D. ctrl gives the labels of a control, as (lib labels, option labels)."""
        self.D, self.lam, self.min_gold = D, lam, min_gold
        if ctrl is not None:
            D.ygold_lib, D.ygold_opt = ctrl
        self.base = Baseline(D, tr)
        df = np.asarray(D.F[tr].sum(0)).ravel()
        self.fsel = np.nonzero(df >= min_df)[0]
        ylib = D.ygold_lib
        cntlib = np.bincount(ylib[tr][ylib[tr] >= 0], minlength=len(D.libs))
        self.libk = -np.ones(len(D.libs), np.int64)
        names = []
        for j in np.nonzero(cntlib >= min_gold)[0].tolist():
            self.libk[j] = len(names)
            names.append('L:' + D.libs[j])
        cnt = {}
        for j in D.ygold_opt[tr].tolist():
            if j >= 0:
                for k in option_keys(D.oinfo[j]):
                    cnt[k] = cnt.get(k, 0) + 1
        self.ix = {}
        for k, v in sorted(cnt.items()):
            if v >= min_gold:
                self.ix[k] = len(names)
                names.append(k)
        self.names = names
        self.nk, self.nf, self.np = len(names), len(self.fsel), D.P.shape[1]
        self.X = self.arrays(D, tr)
        res = so.minimize(self.obj, np.zeros(self.nk * self.nf + self.nk + self.np), jac=True, method='L-BFGS-B', options=dict(maxiter=maxiter, maxcor=20))
        self.theta, self.nit, self.loss = res.x, res.nit, res.fun
        self.X = None

    def arrays(self, D, idx):
        """Arrays of rows idx of D: facts, flat options, their keys, labels."""
        mp = -np.ones(D.n, np.int64)
        mp[idx] = np.arange(len(idx))
        F = D.F[idx]
        if F.shape[1] < self.fsel.max(initial=0) + 1:
            F = sp.csr_matrix((F.data, F.indices, F.indptr), shape=(F.shape[0], int(self.fsel.max()) + 1))
        F = F[:, self.fsel].tocsr()
        ops = np.nonzero(mp[D.orow] >= 0)[0]
        back = -np.ones(D.m, np.int64)
        back[ops] = np.arange(len(ops))
        memo = {}
        ro, co = [], []
        for x in ops.tolist():
            o = D.oinfo[x]
            k = id(o)
            v = memo.get(k)
            if v is None:
                v = memo[k] = [self.ix[c] for c in option_keys(o) if c in self.ix]
            for c in v:
                ro.append(back[x])
                co.append(c)
        logq = self.base.fill(D)[ops]
        P = D.P[ops]
        if P.shape[1] < self.np:
            P = sp.csr_matrix((P.data, P.indices, P.indptr), shape=(P.shape[0], self.np))
        elif P.shape[1] > self.np:
            P = P[:, :self.np]
        yo = D.ygold_opt[idx]
        return dict(idx=idx, F=F, orow=mp[D.orow[ops]], ops=ops, P=P, logq=logq, tok_o=np.array(ro, np.int64), tok_k=np.array(co, np.int64),
                    loglib=self.base.loglib[D.neg[idx].astype(int)], mask=D.mask_ops[idx], yl=D.ygold_lib[idx], yo=np.where(yo >= 0, back[np.maximum(yo, 0)], -1))

    def scores(self, X, W, b, v):
        Z = np.asarray(X['F'] @ W.T) + b
        n = Z.shape[0]
        ll = X['loglib'].copy()
        sel = self.libk >= 0
        ll[:, sel] += Z[:, self.libk[sel]]
        ll[X['mask']] = -np.inf
        lo = X['logq'] + X['P'] @ v
        if len(X['tok_o']):
            lo = lo + np.bincount(X['tok_o'], Z[X['orow'][X['tok_o']], X['tok_k']], len(lo))
        ml = np.full(n, -np.inf)
        np.maximum.at(ml, X['orow'], lo)
        mx = np.maximum(ll.max(1), ml)
        el = np.exp(ll - mx[:, None])
        eo = np.exp(lo - mx[X['orow']])
        tot = el.sum(1) + np.bincount(X['orow'], eo, n)
        return Z, ll, lo, el, eo, tot, mx

    def obj(self, th):
        nk, nf = self.nk, self.nf
        W = th[:nk * nf].reshape(nk, nf)
        b = th[nk * nf:nk * nf + nk]
        v = th[nk * nf + nk:]
        X = self.X
        yl, yo = X['yl'], X['yo']
        Z, ll, lo, el, eo, tot, mx = self.scores(X, W, b, v)
        n = Z.shape[0]
        gl = yl >= 0
        r = np.nonzero(gl)[0]
        lg = np.zeros(n)
        lg[r] = ll[r, yl[gl]]
        ox = yo >= 0
        lg[ox] = lo[yo[ox]]
        nll = (np.log(tot) + mx - lg).sum()
        pl = el / tot[:, None]
        po = eo / tot[X['orow']]
        GZ = np.zeros((n, nk))
        sel = self.libk >= 0
        GZ[:, self.libk[sel]] = pl[:, sel]
        y = yl[gl]
        s = self.libk[y] >= 0
        GZ[r[s], self.libk[y[s]]] -= 1
        go = po.copy()
        go[yo[ox]] -= 1
        if len(X['tok_o']):
            GZ += np.bincount(X['orow'][X['tok_o']] * nk + X['tok_k'], go[X['tok_o']], n * nk).reshape(n, nk)
        gW = np.asarray(X['F'].T @ GZ).T
        lam = self.lam
        f = nll + .5 * lam * (W * W).sum() + .05 * (b * b).sum() + .5 * lam * (v * v).sum()
        return f, np.concatenate([(gW + lam * W).ravel(), GZ.sum(0) + .1 * b, X['P'].T @ go + lam * v])

    def parts(self):
        nk, nf = self.nk, self.nf
        return self.theta[:nk * nf].reshape(nk, nf), self.theta[nk * nf:nk * nf + nk], self.theta[nk * nf + nk:]

    def saved(self, D, idx):
        """(bits saved against the baseline, baseline bits) on rows idx of D."""
        X = self.arrays(D, idx)
        W, b, v = self.parts()
        return self.saved_at(X, W, b, v)

    def saved_at(self, X, W, b, v):
        yl, yo = X['yl'], X['yo']
        _, ll, lo, _, _, tot, mx = self.scores(X, W, b, v)
        _, ll0, lo0, _, _, tot0, mx0 = self.scores(X, W * 0, b * 0, v * 0)
        n = len(yl)
        a, a0 = np.zeros(n), np.zeros(n)
        gl = yl >= 0
        r = np.nonzero(gl)[0]
        a[r], a0[r] = ll[r, yl[gl]], ll0[r, yl[gl]]
        ox = yo >= 0
        a[ox], a0[ox] = lo[yo[ox]], lo0[yo[ox]]
        pm = -(a - mx - np.log(tot)) / LN2
        p0 = -(a0 - mx0 - np.log(tot0)) / LN2
        return p0 - pm, p0

    def rows_key(self, D, idx):
        """The arrays a per-key table needs: per-row log rates under the model and the baseline."""
        X = self.arrays(D, idx)
        W, b, v = self.parts()
        _, ll, lo, _, _, _, _ = self.scores(X, W, b, v)
        _, ll0, lo0, _, _, _, _ = self.scores(X, W * 0, b * 0, v * 0)
        return X, ll, lo, ll0, lo0


def key_net(X, ll, lo, ll0, lo0, lib_index, opt_mask):
    """Bits saved at each row when only one key's delta applies, others at the baseline: lib_index for a lib key, opt_mask over flat options for a family. Each row counts its loss too, where the label is another key's. (saved per row, label at this key per row)"""
    n = len(X['yl'])
    d0 = np.exp(ll0)
    d0[X['mask']] = 0
    tot0 = d0.sum(1) + np.bincount(X['orow'], np.exp(lo0), n)
    hit = np.zeros(n, bool)
    if lib_index is not None:
        new = np.exp(ll[:, lib_index])
        old = np.exp(ll0[:, lib_index])
        ok = ~X['mask'][:, lib_index]
        delta = np.where(ok, ll[:, lib_index] - ll0[:, lib_index], 0.0)
        tot = tot0 + np.where(ok, new - old, 0.0)
        hit = X['yl'] == lib_index
        lg = np.where(hit, delta, 0.0)
    else:
        q0 = np.exp(lo0)
        q1 = np.exp(lo)
        tot = tot0 + np.bincount(X['orow'][opt_mask], (q1 - q0)[opt_mask], n)
        lg = np.zeros(n)
        ox = np.nonzero(X['yo'] >= 0)[0]
        g = X['yo'][ox]
        h = opt_mask[g]
        lg[ox[h]] = (lo - lo0)[g[h]]
        hit[ox[h]] = True
    return (lg - np.log(tot / tot0)) / LN2, hit


def boot(saved, tasks, mask, B=10000, seed=0):
    """(mean saved per row, 95% interval) by resampling tasks."""
    u = sorted(set(tasks.tolist()))
    ix = {t: i for i, t in enumerate(u)}
    t = np.array([ix[x] for x in tasks.tolist()])
    s = np.bincount(t[mask], saved[mask], len(u))
    n = np.bincount(t[mask], minlength=len(u)).astype(float)
    W = np.random.RandomState(seed).multinomial(len(u), [1.0 / len(u)] * len(u), B)
    den = W @ n
    r = (W @ s)[den > 0] / den[den > 0]
    return float(s.sum() / max(n.sum(), 1)), float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))
