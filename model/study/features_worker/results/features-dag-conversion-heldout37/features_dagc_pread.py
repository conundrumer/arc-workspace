#!/usr/bin/env python
"""The read of a per-relation fit on a data set (item 10): the copy of features_ps_read.py for the DAG conversion.

  features_dagc_env.sh 1 features_dagc_pread.py MODEL DATA [--eta .15] [--live-bits scratch/bits-X.npz] [--forms form-bits-dag.tsv] [--held]

MODEL is the arm name of perrel/rows-MODEL-w*.jsonl, with perrel/vocab-MODEL.json. DATA is the name of scratch/data-DATA.npz.
A read of a data set that holds a held task needs --held, requires every task of DATA to be held, and appends a line to held-reads.jsonl (each such call is one held read). A read without --held stops if DATA holds a held task.
The check of the model: the facts of the trees at the chosen rounds pass check_columns and check_tokens.

Measures, weighted by the pick weight `w`, 95% from 10,000 resamples of tasks:
  saved bits per pick over `off` (the offset) and over `live` (the mean live bits at the same pick keys less the model's bits): all picks and gold-alive picks
  by class, by `d_depth` band (0, 1, 2, 3 or more), and by class and band
  per key: at gold picks, and net of the key's model alone over all picks that offer it, for keys with 8 tasks or 50 picks
  per form: the sum of w * saved over a form's picks (the mean over its orders of the sum over a walk's picks), on forms at 25 bits or more by `bits_mean` under live (form-bits-dag.tsv), and under 25
Scoring time is the CPU of applying the trees in one batch, per pick.
"""
import argparse
import glob
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-dag-conversion-heldout37')
import features_dagc_facts as FACT  # noqa: E402
import features_dagc_fitlib as L  # noqa: E402
import features_dagc_matrix as MX  # noqa: E402

CPS = (0, 1, 3, 6, 12, 25, 50, 100, 200, 400)
BANDS = {0: 'D empty (band 0)', 1: 'band 1', 2: 'band 2', 3: 'band 3 or more'}
HELD_LEDGER = L.ME + 'held-reads.jsonl'


def lines(model):
    out = []
    for p in sorted(glob.glob(L.ROWS + 'rows-%s-w*.jsonl' % model)):
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


def tree_facts(t, out):
    if isinstance(t, list):
        out.append(t[0])
        tree_facts(t[1], out), tree_facts(t[2], out)


def check_model(ls, V):
    """Raises BannedFact if a column or a sparse token that a chosen tree splits on is outside the allowed lists. Returns (columns, tokens) used."""
    heads = V.list('heads')
    cols, toks = set(), set()
    for d in ls:
        if 'folds' not in d:
            continue
        r = chosen(d)
        fs = []
        for s in d['stumps'][:r]:
            if s[0] == 'T':
                tree_facts(s[1], fs)
            elif s[0] == 'x':
                fs.append(s[:3])
            elif s[0] == 't':
                fs.append(s[:3])
        for k, c, _t in fs:
            if k == 'x':
                cols.add(L.NAMES[int(c)])
            elif k == 't':
                toks.add(heads[int(c)])
    FACT.check_columns(sorted(cols))
    FACT.check_tokens(sorted(toks))
    return sorted(cols), sorted(toks)


def ratio_boot(num, den, B=10000, seed=0):
    W = np.random.RandomState(seed).multinomial(len(num), [1.0 / len(num)] * len(num), B).astype(np.float64)
    d = W @ den
    r = (W @ num)[d > 0] / d[d > 0]
    return float(num.sum() / max(den.sum(), 1e-12)), float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))


def live_bits(R, path):
    z = np.load(path)
    ix = np.minimum(np.searchsorted(z['pkey'], R.pkey), len(z['pkey']) - 1)
    return np.where(z['pkey'][ix] == R.pkey, z['bits'][ix], np.nan)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('model')
    ap.add_argument('data')
    ap.add_argument('--eta', type=float, default=.15)
    ap.add_argument('--live-bits', default='')
    ap.add_argument('--forms', default='')
    ap.add_argument('--part', default='held-parents', help='the part of form-bits-dag.tsv whose live bits_mean sets the 25 bit cut')
    ap.add_argument('--held', action='store_true')
    a = ap.parse_args()
    tag = '%s-on-%s' % (a.model, a.data)
    V = L.Vocabs(L.ROWS + 'vocab-%s.json' % a.model)
    R = L.Picks([a.data], V)
    tasks = set(R.task.tolist())
    if a.held:
        if not tasks <= L.HELD:
            raise SystemExit('--held: DATA holds a non-held task')
    elif tasks & L.HELD:
        raise SystemExit('DATA holds a held task: this is a held read, pass --held')
    ls = lines(a.model)
    cols, toks = check_model(ls, V)
    L.refine(R, V)
    R.freeze(V)
    q = -np.log2(R.q[R.goldrow])
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
    lb = live_bits(R, a.live_bits) if a.live_bits else np.full(R.n, np.nan)
    has_live = ~np.isnan(lb)
    svl = np.where(has_live, lb - (q - sv), 0.0)
    np.savez(L.ROWS + 'saved-%s.npz' % tag, pkey=R.pkey, q_off=q, saved_off=sv, live=lb)
    w = R.w
    alive = ~R.m['gold_dead']
    cl, band = L.klass(R), np.minimum(R.m['d_depth'], 3)
    u = sorted(tasks)
    ti = {t: i for i, t in enumerate(u)}
    pt = np.array([ti[t] for t in R.task.tolist()])
    tab = []

    def row(name, m):
        n, t = int(m.sum()), len(set(R.task[m].tolist()))
        if n:
            s = L.boot(sv, R.task, m, w)
            ml = m & has_live
            sl = L.boot(svl, R.task, ml, w) if ml.any() else (float('nan'),) * 3
            tab.append(dict(name=name, picks=n, tasks=t, prior_bits=float(np.average(q[m], weights=w[m])), over_off=s, over_live=sl, live_picks=int(ml.sum())))

    row('All', np.ones(R.n, bool))
    row('Gold alive', alive)
    nm = dict(derived='Derived relation in scope', lib='Lib relation', own="The form's own earlier atom", rest='The rest')
    for c in nm:
        row(nm[c], (cl == c) & alive)
    for b in BANDS:
        row(BANDS[b], (band == b) & alive)
    for c in nm:
        for b in BANDS:
            row('%s, %s' % (nm[c], BANDS[b].lower()), (cl == c) & (band == b) & alive)
    gk = R.key[level][R.goldrow]
    rn = V.list(level)
    keysres = []
    for k in np.unique(gk).tolist():
        name = rn[k]
        m = gk == k
        n, t = int(m.sum()), len(set(R.task[m].tolist()))
        den = np.bincount(pt[m], w[m], len(u))
        s = ratio_boot(np.bincount(pt[m], (sv * w)[m], len(u)), den)
        nu = np.zeros(len(u))
        if name in solo:
            rows, dl = solo[name]
            g, pk = L.solo(R, rows, dl)
            nu = np.bincount(pt[pk], g * w[pk] / L.LN2, len(u))
        ns = ratio_boot(nu, den)
        keysres.append(dict(key=name, n=n, t=t, prior=float(np.average(q[m], weights=w[m])), saved=s, net=ns, net_total=float(nu.sum())))
    big = [r for r in keysres if r['t'] >= 8 or r['n'] >= 50]
    passn = [r for r in big if r['net'][0] >= 1 and r['net'][1] > 0]
    passg = [r for r in big if r['saved'][0] >= 1 and r['saved'][1] > 0]
    per_form = None
    if a.forms:
        bm = {}
        for line in open(a.forms):
            f = line.rstrip('\n').split('\t')
            if f[0] == 'live' and f[1] == a.part:
                bm[f[2], int(f[3]), f[7]] = float(f[14])
        keys = list(zip(R.task.tolist(), R.m['line_id'].tolist(), R.m['scope_id'].tolist()))
        byform = {}
        for i, k in enumerate(keys):
            if k in bm:
                byform.setdefault(k, []).append(i)
        per_form = {}
        for sel_name, sel in (('25 bits or more', lambda b: b >= 25), ('under 25 bits', lambda b: b < 25)):
            fs = [(k, np.array(v)) for k, v in byform.items() if sel(bm[k])]
            if not fs:
                continue
            ft = np.array([ti[k[0]] for k, _ in fs])
            so = np.array([(w[v] * sv[v]).sum() for _, v in fs])
            sl = np.array([(w[v] * svl[v]).sum() for _, v in fs])
            bmv = np.array([bm[k] for k, _ in fs])
            den = np.bincount(ft, minlength=len(u)).astype(float)
            per_form[sel_name] = dict(forms=len(fs), mean_bits_live=float(bmv.mean()), saved_over_off=ratio_boot(np.bincount(ft, so, len(u)), den), saved_over_live=ratio_boot(np.bincount(ft, sl, len(u)), den),
                                      taken_under_25_over_live=int(((bmv >= 25) & (bmv - sl < 25)).sum()), pushed_over_25_over_live=int(((bmv < 25) & (bmv - sl >= 25)).sum()))
    allrow = next((r for r in tab if r['name'] == 'All'), None)
    control = None
    if 'control' in a.model and allrow:
        control = dict(reads_zero=bool(allrow['over_off'][1] <= 0 <= allrow['over_off'][2]), keys_pass_net=len(passn), keys_pass_gold=len(passg))
    rep = dict(control=control, model=a.model, data=a.data, level=level, held=a.held, read_picks=int(R.n), read_tasks=len(u), prior_bits_per_pick_off=float(np.average(q, weights=w)), prior_bits_alive_off=float(np.average(q[alive], weights=w[alive])),
               live_coverage_by_weight=float(w[has_live].sum() / w.sum()), table=tab, per_form=per_form, score_ms_per_pick=cost, keys_with_model=len(solo), keys_8tasks_or_50picks=len(big),
               keys_pass_net=[(r['key'], r['net'][0], r['n']) for r in passn], keys_pass_gold=[(r['key'], r['saved'][0], r['n']) for r in passg], share_picks_pass_net=sum(r['n'] for r in passn) / R.n,
               held_gold_share_keys_no_model=float(sum(r['n'] for r in keysres if r['key'] not in solo)) / R.n, facts_columns=cols, facts_tokens=len(toks), facts_check='check_columns and check_tokens pass', keys_table=keysres)
    json.dump(rep, open(L.ROWS + 'read-%s.json' % tag, 'w'), indent=1)
    if a.held:
        with open(HELD_LEDGER, 'a') as f:
            f.write(json.dumps(dict(time=time.strftime('%Y-%m-%dT%H:%M:%S'), script='features_dagc_pread.py', item=10, model=a.model, data=a.data, picks=int(R.n))) + '\n')
    h = '| Picks read | Picks | Tasks | Bits per pick under off | Saved over off | Saved over live |\n|---|---|---|---|---|---|\n'
    txt = h + '\n'.join('| %s | %d | %d | %.2f | %+.2f (%+.2f to %+.2f) | %+.2f (%+.2f to %+.2f) |' % (r['name'], r['picks'], r['tasks'], r['prior_bits'], *r['over_off'], *r['over_live']) for r in tab) + '\n'
    open(L.ROWS + 'table-%s.md' % tag, 'w').write(txt)
    print(json.dumps({k: v for k, v in rep.items() if k not in ('keys_table', 'table')}, indent=1))
    print(txt)


if __name__ == '__main__':
    main()
