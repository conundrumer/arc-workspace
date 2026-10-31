"""relcheap: a harness for cheap models of gold's relation pick at an atom start, with pluggable features.

score(option) = sum of w[feature] * value over the option's features; the 'logp' feature (log of P's share) starts at weight 1.
  logit: conditional logit (softmax over a row's options), L2 on the sparse cross features chosen on a dev split held out by task
  hgb:   sklearn HistGradientBoostingClassifier on the dense features -> is-gold; its log-odds is the score (logp is a feature)
Features are functions  fn(row, option) -> {name: float}  (row = a relrows row, option = one of row['options']).
A name that starts with 'x:' is a sparse cross feature (kept when train rows of >= --min-tasks tasks fire it, L2 = lambda);
any other name is a dense feature.  Built in:
  struct  relfit's own features without recency        b  r14b.option_features (relfit --b)
  x       crosses: option name x prefix relation names; option types x scope types; kind x k; kind x point group
  ctx     for the tree: kind, k, group, phase, option types and scope types as multi-hot
A plugin file (--plugin f.py) defines FEATURE_FUNCS = {name: fn}; a new function is used by listing its name in --logit-feats /
--hgb-feats.  Fields a row may lack are read with .get.

  relcheap.py --train runR_dev runR2_dev --test runR_holdout --baselines --curve --save-model relcheap.pkl
  relcheap.py --merge bits_a.npz bits_b.npz        # one table from saved test bits
Use from the sampler:  from relcheap import score_options;  f = score_options(row)   # log factor per option; weight *= exp(f)
"""
import argparse
import collections
import importlib.util
import math
import os
import pickle
import random
import re
import sys
import time
import zlib

import numpy as np
import torch
import torch.nn.functional as TF

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sampler_paths as P  # noqa: E402
sys.path.append(P.CODE)
from judge3.framed_jsonl import iter_json  # noqa: E402

import relfeat as FEAT  # noqa: E402
import relnet as R  # noqa: E402  (table, relfit_ns, pad_feats, split_tasks, n_lines)

LN2 = math.log(2)
HERE = os.path.dirname(os.path.abspath(__file__))
_NS = {}


def ns(use_b):
    if use_b not in _NS:
        _NS[use_b] = R.relfit_ns(use_b)
    return _NS[use_b]


FEATURE_FUNCS = FEAT.FEATURE_FUNCS


def load_plugin(path):
    sys.path += [P.STUDY, P.STUDY + '/features']  # as relfit.py does for r14b
    spec = importlib.util.spec_from_file_location('relcheap_plugin', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    FEATURE_FUNCS.update(mod.FEATURE_FUNCS)


class FeatVocab:
    def __init__(self):
        self.ids, self.names, self.group = {}, [], []

    def id(self, name, group):
        i = self.ids.get(name)
        if i is None:
            i = self.ids[name] = len(self.names)
            self.names.append(name)
            self.group.append(group)
        return i


MASK = 'all'  # the derived-name mask of the run (relfeat.mask_row)


def row_triples(row, fnames, fv, mask=None):
    """(option index, feature id, value) arrays of a row, for the feature functions in fnames, after the derived-name mask."""
    row = FEAT.mask_row(row, MASK if mask is None else mask)
    oi, fi, vv = [], [], []
    lid = fv.id('logp', 'base')
    for i, o in enumerate(row['options']):
        oi.append(i)
        fi.append(lid)
        vv.append(math.log(max(o['p'], 1e-9)))
        for g in fnames:
            for n, v in (FEATURE_FUNCS[g](row, o) or {}).items():
                if v and n != 'logp':
                    oi.append(i)
                    fi.append(fv.id(FEAT.qualify(g, n), g))
                    vv.append(float(v))
    return np.array(oi, np.int32), np.array(fi, np.int32), np.array(vv, np.float32)


class Data:
    """Rows streamed from run dirs: padded option layout, flat sparse (position, feature, value) triples."""

    def __init__(self):
        self.meta, self._o, self._f, self._v, self.nopt, self.gold, self.task_id = [], [], [], [], [], [], []
        self.tasks = {}

    def add(self, row, fnames, fv):
        toks = [o['tok'] for o in row['options']]
        if row['gold'] not in toks:
            return False
        oi, fi, vv = row_triples(row, fnames, fv)
        self._o.append(oi), self._f.append(fi), self._v.append(vv)
        self.nopt.append(len(toks))
        self.gold.append(toks.index(row['gold']))
        pg = row.get('point_group') or {}
        self.meta.append(dict(task=row['task'], grp=pg.get('point_group'), kind=row['options'][toks.index(row['gold'])]['kind'], k=row['k'],
                              clause='%s|%s|%s' % (row['task'], row['case'], row['point'])))
        self.task_id.append(self.tasks.setdefault(row['task'], len(self.tasks)))
        return True

    def finish(self):
        self.n = len(self.meta)
        self.O = max(self.nopt)
        lens = [len(o) for o in self._o]
        self.row_of_trip = np.repeat(np.arange(self.n, dtype=np.int32), lens)
        self.opt = np.concatenate(self._o)
        self.fid = np.concatenate(self._f)
        self.val = np.concatenate(self._v)
        self.task_id = np.array(self.task_id)
        self.gold = torch.tensor(self.gold)
        self.mask = torch.arange(self.O)[None, :] < torch.tensor(self.nopt)[:, None]
        self._o = self._f = self._v = None
        return self


def stream(dirs, fnames, fv, label, hook=None, max_rows=0):
    D = Data()
    t0, done = time.time(), 0
    for d in dirs:
        path = os.path.join(d, 'relrows.jsonl.zst')
        if not os.path.exists(path):
            print('%s: %s missing, skipped' % (label, path), flush=True)
            continue
        total = R.n_lines(path)
        for r in iter_json(path):
            done += 1
            if max_rows and done > max_rows:
                break
            if D.add(r, fnames, fv) and hook:
                hook(r, len(D.meta) - 1)
            if done % 1000 == 0:
                rate = done / (time.time() - t0)
                print('%s %s: %d rows, %.0f rows/s%s' % (label, os.path.basename(d.rstrip('/')), done, rate,
                                                        ', eta %.0fs' % ((total - done) / rate) if total and total > done else ''), flush=True)
    print('%s: %d rows in %.0fs' % (label, len(D.meta), time.time() - t0), flush=True)
    return D.finish()


def bits_from_scores(s, mask, gold):
    s = s.masked_fill(~mask, -1e9)
    return (-(s - torch.logsumexp(s, -1, keepdim=True)).gather(1, gold[:, None])[:, 0] / LN2).numpy()


class Sel:
    """A model's view of the features: the ids it uses (by group), compact ids; sparse ones need >= min_tasks train tasks."""

    def __init__(self, fv, groups, D, rows, min_tasks, nf):
        keep_g = set(groups) | {'base'}
        ids = [i for i in range(nf) if fv.group[i] in keep_g]
        sp = [i for i in ids if fv.names[i].startswith('x:')]
        if sp:
            m = np.isin(D.row_of_trip, rows) & np.isin(D.fid, sp)
            pairs = np.unique(np.stack([D.fid[m].astype(np.int64), D.task_id[D.row_of_trip[m]].astype(np.int64)], 1), axis=0)
            cnt = collections.Counter(pairs[:, 0].tolist())
            bad = {i for i in sp if cnt[i] < min_tasks}
            ids = [i for i in ids if i not in bad]
        self.ids = ids
        self.remap = np.full(nf, -1, np.int64)
        self.remap[ids] = np.arange(len(ids))
        self.sparse = np.array([fv.names[i].startswith('x:') for i in ids], bool)
        self.names = [fv.names[i] for i in ids]

    def triples(self, D, rows):
        """Flat option positions within the given rows (row index * D.O + option), compact feature ids, values."""
        pos = np.full(D.n, -1, np.int64)
        pos[rows] = np.arange(len(rows))
        cid = np.full(len(D.fid), -1, np.int64)
        ok = D.fid < len(self.remap)
        cid[ok] = self.remap[D.fid[ok]]
        m = (pos[D.row_of_trip] >= 0) & (cid >= 0)
        p = pos[D.row_of_trip[m]] * D.O + D.opt[m]
        return torch.from_numpy(p), torch.from_numpy(cid[m]), torch.from_numpy(D.val[m])


class Logit:
    def fit(self, D, rows, sel, lam, iters, w0=None):
        rows = np.asarray(rows)
        p, c, v = sel.triples(D, rows)
        mask, gold = D.mask[rows], D.gold[rows]
        N, O = len(rows), D.O
        reg = torch.where(torch.from_numpy(sel.sparse), torch.tensor(lam), torch.tensor(1e-4))
        w = torch.zeros(len(sel.ids))
        w[sel.names.index('logp')] = 1.0
        if w0 is not None:
            w = w0.clone()
        w.requires_grad_(True)
        opt = torch.optim.LBFGS([w], lr=1.0, max_iter=iters, line_search_fn='strong_wolfe')

        def closure():
            opt.zero_grad()
            s = torch.zeros(N * O).index_add(0, p, w[c] * v).reshape(N, O).masked_fill(~mask, -1e9)
            loss = TF.cross_entropy(s, gold) + 0.5 * (reg * w ** 2).sum()
            loss.backward()
            return loss
        opt.step(closure)
        self.w, self.sel = w.detach(), sel
        return self

    def bits(self, D, rows):
        rows = np.asarray(rows)
        p, c, v = self.sel.triples(D, rows)
        s = torch.zeros(len(rows) * D.O).index_add(0, p, self.w[c] * v).reshape(len(rows), D.O)
        return bits_from_scores(s, D.mask[rows], D.gold[rows])


def fit_logit(D, tr, va, fv, nf, groups, lams, min_tasks, iters):
    sel = Sel(fv, groups, D, tr, min_tasks, nf)
    nsp = int(sel.sparse.sum())
    best, w0 = None, None
    for lam in sorted(lams, reverse=True):  # warm start from the larger penalty
        t0 = time.time()
        m = Logit().fit(D, tr, sel, lam, iters if w0 is None else max(iters // 2, 15), w0)
        w0 = m.w
        v = m.bits(D, va).mean()
        print('    logit %s: %d dense + %d sparse features, lambda %.4g: dev %.3f bits (%.0fs)' % (
            '+'.join(groups), len(sel.ids) - nsp, nsp, lam, v, time.time() - t0), flush=True)
        if best is None or v < best[0]:
            best = (v, lam, m)
    return best


def dense_matrix(D, rows, sel):
    """Dense features (a line per real option of the rows) of the selected non-sparse features; also the option mask."""
    rows = np.asarray(rows)
    p, c, v = sel.triples(D, rows)
    dcols = np.nonzero(~sel.sparse)[0]
    cm = np.full(len(sel.ids), -1)
    cm[dcols] = np.arange(len(dcols))
    p, c, v = p.numpy(), c.numpy(), v.numpy()
    k = cm[c] >= 0
    mk = D.mask[rows].reshape(-1).numpy()
    compact = np.cumsum(mk) - 1  # padded position -> line among the real options
    X = np.zeros((int(mk.sum()), len(dcols)), np.float32)
    X[compact[p[k]], cm[c[k]]] = v[k]
    return X, mk, [sel.names[i] for i in dcols]


def stage_scores(d, mk, N, O, beta):
    s = torch.full((N * O,), -1e9)
    s[torch.from_numpy(mk)] = torch.from_numpy(np.asarray(d, np.float32)) * beta
    return s.reshape(N, O)


def fit_hgb(D, tr, va, fv, nf, groups, min_tasks, a):
    from sklearn.ensemble import HistGradientBoostingClassifier
    sel = Sel(fv, groups, D, tr, min_tasks, nf)
    X, mk, names = dense_matrix(D, tr, sel)
    y = (torch.arange(D.O)[None, :] == D.gold[tr][:, None]).reshape(-1).numpy()[mk]
    t0 = time.time()
    m = HistGradientBoostingClassifier(max_iter=a.hgb_iters, learning_rate=a.hgb_lr, max_depth=a.hgb_depth, min_samples_leaf=a.hgb_leaf,
                                       early_stopping=False, l2_regularization=1.0, random_state=0).fit(X, y)
    Xv, mkv, _ = dense_matrix(D, va, sel)
    best = (1e9, 0, 1.0)
    for st, d in enumerate(m.staged_decision_function(Xv), 1):
        if st % 10 and st != a.hgb_iters:
            continue
        for beta in (0.5, 1.0):
            v = bits_from_scores(stage_scores(d, mkv, len(va), D.O, beta), D.mask[va], D.gold[va]).mean()
            if v < best[0]:
                best = (v, st, beta)
    print('    hgb %s: %d options x %d features: dev %.3f at stage %d beta %.1f (%.0fs)' % (
        '+'.join(groups), len(X), X.shape[1], best[0], best[1], best[2], time.time() - t0), flush=True)
    return m, sel, best


def hgb_test_bits(m, sel, D, stage, beta):
    X, mk, _ = dense_matrix(D, np.arange(D.n), sel)
    for st, d in enumerate(m.staged_decision_function(X), 1):
        if st == stage:
            break
    return bits_from_scores(stage_scores(d, mk, D.n, D.O, beta), D.mask, D.gold)


def task_subset(meta, frac, seed=0):
    tasks = sorted({m['task'] for m in meta})
    random.Random(seed).shuffle(tasks)
    cnt = collections.Counter(m['task'] for m in meta)
    want, got, keep = frac * len(meta), 0, set()
    for t in tasks:
        if got >= want:
            break
        keep.add(t)
        got += cnt[t]
    return keep


from relsteer import Scorer, score_options  # noqa: E402,F401  (the runtime scorer)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--train', nargs='+', default=[HERE + '/runR_dev', HERE + '/runR2_dev'])
    ap.add_argument('--test', default=HERE + '/runR_holdout')
    ap.add_argument('--models', nargs='*', default=['logit', 'hgb'])
    ap.add_argument('--logit-feats', nargs='+', action='append', help='feature sets of a logit column; repeat for several columns')
    ap.add_argument('--hgb-feats', nargs='+', default=['struct', 'b', 'ctx'])
    ap.add_argument('--plugin', default='')
    ap.add_argument('--mask', default='all', choices=['all', 'group', 'none', 'all_nogrp'], help='derived-name mask (relfeat.mask_row)')
    ap.add_argument('--baselines', action='store_true', help='also fit relfit and relfit --b as they are (reservoir of --base-rows)')
    ap.add_argument('--base-rows', type=int, default=6000)
    ap.add_argument('--curve', action='store_true')
    ap.add_argument('--fracs', type=float, nargs='+', default=[0.25, 0.5, 1.0], help='train fractions (by task) of --curve')
    ap.add_argument('--lams', type=float, nargs='+', default=[0.01, 0.003, 0.001])
    ap.add_argument('--min-tasks', type=int, default=3)
    ap.add_argument('--iters', type=int, default=60)
    ap.add_argument('--hgb-iters', type=int, default=150)
    ap.add_argument('--hgb-lr', type=float, default=0.1)
    ap.add_argument('--hgb-depth', type=int, default=5)
    ap.add_argument('--hgb-leaf', type=int, default=40)
    ap.add_argument('--threads', type=int, default=2)
    ap.add_argument('--max-rows', type=int, default=0)
    ap.add_argument('--merge', nargs='+', default=[], help='print the table of saved .npz columns and exit')
    ap.add_argument('--save-bits', default='')
    ap.add_argument('--save-model', default='')
    a = ap.parse_args()
    global MASK
    MASK = a.mask
    torch.set_num_threads(a.threads)
    if a.plugin:
        load_plugin(a.plugin)
    if a.merge:
        tm = []
        for r in iter_json(a.test + '/relrows.jsonl.zst'):
            toks = [o['tok'] for o in r['options']]
            if r['gold'] in toks:
                pg = r.get('point_group') or {}
                tm.append(dict(task=r['task'], grp=pg.get('point_group'), kind=r['options'][toks.index(r['gold'])]['kind'], k=r['k'],
                               clause='%s|%s|%s' % (r['task'], r['case'], r['point'])))
        cols = {}
        for f in a.merge:
            z = np.load(f)
            for k in z.files:
                cols.setdefault(k, z[k])
        R.table(tm, cols, 'TEST (%s): mean bits per gold pick' % a.test)
        return
    logit_sets = a.logit_feats or [['struct', 'x']]
    used = sorted({g for s in logit_sets for g in s} | (set(a.hgb_feats) if 'hgb' in a.models else set()))
    fv = FeatVocab()
    reservoir, seen, rr = {}, [0], random.Random(0)
    test_feats = []

    def keep_train(r, idx):
        if not a.baselines:
            return
        seen[0] += 1
        if len(reservoir) >= a.base_rows:
            if rr.randrange(seen[0]) >= a.base_rows:
                return
            del reservoir[rr.choice(list(reservoir))]
        toks = [o['tok'] for o in r['options']]
        reservoir[idx] = (ns(False)['features'](r).astype(np.float32), ns(True)['features'](r).astype(np.float32), toks.index(r['gold']))

    def keep_test(r, idx):
        if a.baselines:
            toks = [o['tok'] for o in r['options']]
            test_feats.append((ns(False)['features'](r).astype(np.float32), ns(True)['features'](r).astype(np.float32), toks.index(r['gold'])))
    Dtr = stream(a.train, used, fv, 'train', keep_train, a.max_rows)
    nf = len(fv.names)
    Dte = stream([a.test], used, fv, 'test', keep_test, a.max_rows)
    print('features: %d (train), %d triples train' % (nf, len(Dtr.val)), flush=True)
    cols = {}
    lp = Logit()  # P alone: only the 'logp' feature, weight 1
    lp.sel = Sel(fv, [], Dtr, np.arange(Dtr.n), 1, nf)
    lp.w = torch.ones(1)
    cols['P'] = lp.bits(Dte, np.arange(Dte.n))
    if a.baselines:
        for nm, j in (('relfit', 0), ('relfit+b', 1)):
            ids = sorted(reservoir)
            X, g, m = R.pad_feats([reservoir[i][j] for i in ids], [reservoir[i][2] for i in ids])
            w = R.fit_logit(X, g, m)
            Xt, gt, mt = R.pad_feats([f[j] for f in test_feats], [f[2] for f in test_feats])
            cols[nm] = bits_from_scores(Xt @ w, mt, gt)
            print('%s fit on %d train rows' % (nm, len(ids)), flush=True)
    isval = R.split_tasks(Dtr.meta)
    fracs = a.fracs if a.curve else [1.0]
    curve = collections.defaultdict(dict)
    allte = np.arange(Dte.n)
    ck = {'plugin': a.plugin or None, 'mask': a.mask}
    for fr in fracs:
        keep = task_subset(Dtr.meta, fr)
        sel_rows = np.array([m['task'] in keep for m in Dtr.meta])
        tr, va = np.nonzero(sel_rows & ~isval)[0], np.nonzero(sel_rows & isval)[0]
        if len(va) < 30:
            dev = {t for t in keep if zlib.crc32(t.encode()) % 6 == 0}
            isd = np.array([m['task'] in dev for m in Dtr.meta])
            tr, va = np.nonzero(sel_rows & ~isd)[0], np.nonzero(sel_rows & isd)[0]
        print('== %d%% of train rows: %d fit, %d dev' % (fr * 100, len(tr), len(va)), flush=True)
        if 'logit' in a.models:
            for groups in logit_sets:
                v, lam, m = fit_logit(Dtr, tr, va, fv, nf, groups, a.lams, a.min_tasks, a.iters)
                b = m.bits(Dte, allte)
                name = 'lin+' + '+'.join(groups)
                print('  %s lambda %.4g: test %.3f' % (name, lam, b.mean()), flush=True)
                curve[name][fr] = b.mean()
                if fr == fracs[-1]:
                    cols[name] = b
                    ck['logit'] = dict(groups_used=sorted(set(groups)), weights=m.w.numpy(),
                                       index={n: i for i, n in enumerate(m.sel.names)})
        if 'hgb' in a.models:
            m, sel, (v, st, beta) = fit_hgb(Dtr, tr, va, fv, nf, a.hgb_feats, a.min_tasks, a)
            b = hgb_test_bits(m, sel, Dte, st, beta)
            name = 'hgb+' + '+'.join(a.hgb_feats)
            print('  %s stage %d beta %.1f: test %.3f' % (name, st, beta, b.mean()), flush=True)
            curve[name][fr] = b.mean()
            if fr == fracs[-1]:
                cols[name] = b
                m._predictors = m._predictors[:st]  # keep the stage that dev chose, so decision_function is that stage
                ck['hgb'] = dict(groups_used=sorted(set(a.hgb_feats)), model=m, names=[sel.names[i] for i in np.nonzero(~sel.sparse)[0]],
                                 beta=beta, stage=st)
    R.table(Dte.meta, cols, 'TEST (%s): mean bits per gold pick' % a.test)
    if a.curve:
        print('\nlearning curve, test bits per pick (P %.3f):' % cols['P'].mean())
        for nm, d in curve.items():
            print('  %-24s ' % nm + '  '.join('%d%%: %.3f' % (f * 100, v) for f, v in sorted(d.items())))
    if a.save_bits:
        np.savez(a.save_bits, **cols)
    if a.save_model:
        old = pickle.load(open(a.save_model, 'rb')) if os.path.exists(a.save_model) else {}
        old.update({k: v for k, v in ck.items() if v is not None})  # a run adds its models to the file
        with open(a.save_model, 'wb') as f:
            pickle.dump(old, f)
        print('saved', a.save_model)


if __name__ == '__main__':
    main()
