#!/usr/bin/env python
"""The held read of a fit model on a data set. Each call of this script on held rows is one held read, and reads.log keeps the count.

  python features_ps_read.py MODEL DATA [--eta .15]    writes read-MODEL-on-DATA.json, table-MODEL-on-DATA.md, saved-MODEL-on-DATA.npy

MODEL is a rows file: `as-fit:NAME` for the per-relation record's rows/NAME.jsonl.zst with its vocabulary, or NAME for this record's rows-NAME-w*.jsonl with scratch/vocab-NAME.json. DATA is the name of a scratch/data-DATA.npz.

Measures, each on the steered prior of the same rows, with a 10,000 resample of tasks:
  saved bits per pick: all picks and gold-alive picks
  by class and position
  per key: at gold picks, and net of the key's model alone over all picks that offer it, for keys with 8 tasks or 50 picks
  per form: the sum of saved bits over a walk's picks, and the forms under 25 bits, on `total`, the walk's bits per form
Scoring time is the CPU of applying the trees in one batch, per pick.
"""
import argparse
import glob
import io
import json
import os
import sys
import time

import numpy as np
import zstandard

sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-relation-pick-per-relation-pool-scope-heldout37')
import features_perrel_lib as L  # noqa: E402

OLD = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-relation-pick-per-relation-models-heldout37/'
CPS = (0, 1, 3, 6, 12, 25, 50, 100, 200, 400)


def lines(model):
    if model.startswith('as-fit:'):
        with open(OLD + 'rows/%s.jsonl.zst' % model[7:], 'rb') as f:
            return [json.loads(x) for x in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f), encoding='utf8')]
    z_ = L.ME + 'rows/%s.jsonl.zst' % model
    if os.path.exists(z_):
        with open(z_, 'rb') as f:
            return [json.loads(x) for x in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f), encoding='utf8')]
    out = []
    for p in sorted(glob.glob(L.ME + 'rows-%s-w*.jsonl' % model)):
        for x in open(p):
            if x.endswith('\n'):
                out.append(json.loads(x))
    return out


def chosen(d):
    tot = np.zeros(len(CPS))
    for f in d['folds']:
        tot += np.array(f['before'][0]) + np.array(f['parents'][0])
    i = int(np.argmax(tot))
    return CPS[i] if tot[i] > 0 else 0


def ratio_boot(num, den, B=10000, seed=0):
    W = np.random.RandomState(seed).multinomial(len(num), [1.0 / len(num)] * len(num), B).astype(np.float64)
    d = W @ den
    r = (W @ num)[d > 0] / d[d > 0]
    return float(num.sum() / max(den.sum(), 1)), float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('model')
    ap.add_argument('data')
    ap.add_argument('--eta', type=float, default=.15)
    a = ap.parse_args()
    tag = '%s-on-%s' % (a.model.replace('as-fit:', 'asfit-'), a.data)
    V = L.Vocabs(L.OUT + 'vocab-%s.json' % a.model.replace('as-fit:', ''))
    R = L.Picks([a.data], V)
    L.refine(R, V)
    R.freeze(V)
    z = np.load(L.OUT + 'data-%s.npz' % a.data, allow_pickle=False)
    forms = json.loads(str(z['forms']))
    q = -np.log2(R.q[R.goldrow])
    ls = lines(a.model)
    level = ls[0]['level']
    ix = L.Rows(R, level)
    names = V.m[level]
    t0 = time.process_time()
    F = np.zeros(len(R.q))
    solo = {}
    for d in ls:
        k = names.get(d['key'])
        if k is None or 'folds' not in d:
            continue
        rows = ix.get(k)
        r = chosen(d)
        if len(rows) == 0 or r == 0:
            continue
        st = [tuple(s) for s in d['stumps'][:r]]
        dl = L.path(R, rows, st, a.eta, [r])[:, 0]
        F[rows] += dl
        solo[d['key']] = (rows, dl)
    cost = (time.process_time() - t0) / R.n * 1000
    sv = L.saved_bits(R, F)
    np.save(L.ME + 'saved-%s.npy' % tag, sv)
    alive = ~R.m['gold_dead']
    all_ = np.ones(R.n, bool)
    u = sorted(set(R.task.tolist()))
    ti = {t: i for i, t in enumerate(u)}
    pt = np.array([ti[t] for t in R.task.tolist()])
    cl, ord_ = L.klass(R), R.m['ord']
    pos = np.where(ord_ >= 4, 4, ord_)
    tab = []

    def row(name, m):
        n, t = int(m.sum()), len(set(R.task[m].tolist()))
        if n:
            s = L.boot(sv, R.task, m)
            tab.append(dict(name=name, picks=n, tasks=t, prior_bits=float(q[m].mean()), saved=s[0], lo=s[1], hi=s[2]))

    row('All', all_)
    row('Gold alive', alive)
    nm = dict(derived='Derived relation in scope', lib='Lib relation', own="The form's own earlier atom", rest='The rest')
    pn = {1: 'First atom', 2: 'Second atom', 3: 'Third atom', 4: 'Later atoms'}
    for c in nm:
        row(nm[c], (cl == c) & alive)
    for p in pn:
        row(pn[p], (pos == p) & alive)
    for c in nm:
        for p in pn:
            row('%s, %s' % (nm[c], pn[p].lower()), (cl == c) & (pos == p) & alive)
    # keys
    gk = R.key[level][R.goldrow]
    rn = V.list(level)
    keysres = []
    for k in np.unique(gk).tolist():
        name = rn[k]
        m = gk == k
        n, t = int(m.sum()), len(set(R.task[m].tolist()))
        den = np.bincount(pt[m], minlength=len(u)).astype(float)
        s = ratio_boot(np.bincount(pt[m], sv[m], len(u)), den)
        nu = np.zeros(len(u))
        if name in solo:
            rows, dl = solo[name]
            g, pk = L.solo(R, rows, dl)
            nu = np.bincount(pt[pk], g / L.LN2, len(u))
        ns = ratio_boot(nu, den)
        keysres.append(dict(key=name, n=n, t=t, prior=float(q[m].mean()), saved=s, net=ns, net_total=float(nu.sum())))
    big = [r for r in keysres if r['t'] >= 8 or r['n'] >= 50]
    passn = [r for r in big if r['net'][0] >= 1 and r['net'][1] > 0]
    passg = [r for r in big if r['saved'][0] >= 1 and r['saved'][1] > 0]
    # per form: a walk is one row of `forms`, keyed by its line
    tot = {d['line']: d['total'] for d in forms if not (d['error'] or d['dead'] or d['bad'] or not d['aligned'])}
    lines_ = R.m['line']
    pf = {}
    for i in np.unique(lines_).tolist():
        pf[i] = float(sv[lines_ == i].sum())
    ids = sorted(pf)
    ftask = {int(i): t for i, t in zip(lines_.tolist(), R.task.tolist())}
    ft = np.array([ti[ftask[i]] for i in ids])
    now = np.array([tot[i] for i in ids], float)
    save = np.array([pf[i] for i in ids])
    den = np.bincount(ft, minlength=len(u)).astype(float)
    over = now >= 25
    per_form = dict(walks=len(ids), median_bits=float(np.median(now)), saved_all=ratio_boot(np.bincount(ft, save, len(u)), den), saved_over25=ratio_boot(np.bincount(ft[over], save[over], len(u)), np.bincount(ft[over], minlength=len(u)).astype(float)),
                    over25=int(over.sum()), under25_now=int((now < 25).sum()), under25_model=int((now - save < 25).sum()), taken_under=int(((now >= 25) & (now - save < 25)).sum()), pushed_over=int(((now < 25) & (now - save >= 25)).sum()))
    rep = dict(model=a.model, data=a.data, level=level, read_picks=int(R.n), read_forms=len(ids), read_tasks=len(u), prior_bits_per_pick=float(q.mean()), prior_bits_alive=float(q[alive].mean()), table=tab, per_form=per_form, score_ms_per_pick=cost, keys_with_model=len(solo),
               keys_8tasks_or_50picks=len(big), keys_pass_net=[(r['key'], r['net'][0], r['n']) for r in passn], keys_pass_gold=[(r['key'], r['saved'][0], r['n']) for r in passg], share_picks_pass_net=sum(r['n'] for r in passn) / R.n, share_picks_pass_gold=sum(r['n'] for r in passg) / R.n,
               held_gold_share_keys_no_model=float(sum(r['n'] for r in keysres if r['key'] not in solo)) / R.n, keys_table=keysres)
    json.dump(rep, open(L.ME + 'read-%s.json' % tag, 'w'), indent=1)
    with open(L.ME + 'reads.log', 'a') as f:
        f.write('%s %s %s picks %d\n' % (time.strftime('%H:%M:%S'), a.model, a.data, R.n))
    h = '| Picks read | Picks | Tasks | Prior bits per pick | Saved |\n|---|---|---|---|---|\n'
    txt = h + '\n'.join('| %s | %d | %d | %.2f | %+.2f (%+.2f to %+.2f) |' % (r['name'], r['picks'], r['tasks'], r['prior_bits'], r['saved'], r['lo'], r['hi']) for r in tab) + '\n'
    open(L.ME + 'table-%s.md' % tag, 'w').write(txt)
    print(json.dumps({k: v for k, v in rep.items() if k not in ('keys_table', 'table')}, indent=1))
    print(txt)


if __name__ == '__main__':
    main()
