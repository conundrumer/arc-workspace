#!/usr/bin/env python
"""The held read of final models. Run once per final model. Reads each arm's fit on all fit tasks, cut at the rounds that all four folds choose, on the 37 held tasks.

  python features_perrel_read.py ARM --eta E --alpha A [--control ARM2]   writes read-ARM.json, keys-ARM.tsv, saved-ARM.npy, table-ARM.md

Per key, two measures:
  gold picks: the saved bits of the whole model at the picks whose gold option has that key. These sum to the whole model's total.
  net: the bits that key's model alone gains or loses over every pick that offers the key, per gold pick of the key. A key pays here for raising itself at picks where gold is another key.
"""
import argparse
import glob
import json
import os
import pickle
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features_perrel_lib as L  # noqa: E402

HELD_TASKS = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/held/tasks.txt'
CPS = (0, 1, 3, 6, 12, 25, 50, 100, 200, 400)


def lines(arm):
    z = L.ME + 'rows/%s.jsonl.zst' % arm
    if os.path.exists(z):
        import io
        import zstandard
        with open(z, 'rb') as f:
            return [json.loads(x) for x in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f), encoding='utf8')]
    out = []
    for p in sorted(glob.glob(L.ME + 'rows-%s-w*.jsonl' % arm)):
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


def ratio_boot(num, den, tasks, B=10000, seed=0):
    """Sum of num over sum of den, with tasks resampled. num and den are per-task arrays."""
    W = np.random.RandomState(seed).multinomial(len(num), [1.0 / len(num)] * len(num), B).astype(np.float64)
    d = W @ den
    r = (W @ num)[d > 0] / d[d > 0]
    return float(num.sum() / max(den.sum(), 1)), float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))


def rank_table(R, sv, rank, names_):
    cl, ord_ = L.klass(R), R.m['ord']
    pos = np.where(ord_ >= 4, 4, ord_)
    q = -np.log2(R.q[R.goldrow])
    out = []
    head = '| Picks read | Picks | Tasks | Prior bits per pick | This model | Rank read, no content | Rank read, with content |\n|---|---|---|---|---|---|---|'

    def row(name, m):
        n, t = int(m.sum()), len(set(R.task[m].tolist()))
        if not n:
            return
        a, b, c = L.boot(sv, R.task, m), L.boot(rank['structure'], R.task, m), L.boot(rank['content'], R.task, m)
        out.append('| %s | %d | %d | %.2f | %+.2f (%+.2f to %+.2f) | %+.2f (%+.2f to %+.2f) | %+.2f (%+.2f to %+.2f) |' % (name, n, t, q[m].mean(), *a, *b, *c))

    row('All', np.ones(R.n, bool))
    row('Gold alive', ~R.m['gold_dead'])
    nm = dict(derived='Derived relation in scope', lib='Lib relation', own="The form's own earlier atom", rest='The rest')
    for c in nm:
        row(nm[c], cl == c)
    pn = {1: 'First atom', 2: 'Second atom', 3: 'Third atom', 4: 'Later atoms'}
    for p in pn:
        row(pn[p], pos == p)
    for c in nm:
        for p in pn:
            row('%s, %s' % (nm[c], pn[p].lower()), (cl == c) & (pos == p))
    return head + '\n' + '\n'.join(out) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('arm')
    ap.add_argument('--eta', type=float, default=.15)
    ap.add_argument('--alpha', type=float, default=1.0)
    a = ap.parse_args()
    arm = a.arm
    V = L.Vocabs(L.OUT + 'vocab-%s.json' % arm)
    R = L.Picks(['held'], V)
    L.refine(R, V)
    R.freeze(V)
    held = set(open(HELD_TASKS).read().split())
    assert set(R.task.tolist()) == held and R.n == 1959
    fp = np.load(L.OUT + 'final-picks.npz', allow_pickle=False)
    assert (fp['task'] == R.task).all() and (fp['line'] == R.m['line']).all() and (fp['ord'] == R.m['ord']).all() and (fp['phase'] == R.m['phase']).all()
    q = -np.log2(R.q[R.goldrow])
    gap = float(np.abs(q - fp['q']).max())
    assert gap < 1e-3
    rank = {n: np.load(L.OUT + 'final-saved-%s.npy' % n) for n in ('structure', 'content', 'control')}
    ls = lines(arm)
    level = ls[0]['level']
    ix = L.Rows(R, level)
    names = V.m[level]
    t0 = time.process_time()
    F = np.zeros(len(R.q))
    solo = {}
    nn = 0
    for d in ls:
        k = names.get(d['key'])
        if k is None or 'folds' not in d:
            continue
        rows = ix.get(k)
        r = chosen(d)
        if len(rows) == 0 or r == 0:
            continue
        st = [tuple(s) for s in d['stumps'][:r]]
        nn += r
        dl = L.path(R, rows, st, a.eta, [r])[:, 0]
        F[rows] += a.alpha * dl
        solo[d['key']] = (rows, a.alpha * dl)
    cost = (time.process_time() - t0) / R.n * 1000
    sv = L.saved_bits(R, F)
    np.save(L.ME + 'saved-%s.npy' % arm, sv)
    alive = ~R.m['gold_dead']
    all_ = np.ones(R.n, bool)
    u = sorted(held)
    ti = {t: i for i, t in enumerate(u)}
    pt = np.array([ti[t] for t in R.task.tolist()])
    gk = R.key[level][R.goldrow]
    rn = V.list(level)
    out = open(L.ME + 'keys-%s.tsv' % arm, 'w')
    out.write('key\tgold_picks\tgold_tasks\tfit_gold_rows\trounds\tprior_bits\tsaved_at_gold_picks\tlo\thi\tnet_bits_per_gold_pick\tnet_lo\tnet_hi\tnet_bits_total\n')
    fitpos = {d['key']: d for d in ls}
    keysres = []
    for k in np.unique(gk).tolist():
        name = rn[k]
        m = gk == k
        n, t = int(m.sum()), len(set(R.task[m].tolist()))
        den = np.bincount(pt[m], minlength=len(u)).astype(float)
        num = np.bincount(pt[m], sv[m], len(u))
        s = ratio_boot(num, den, u)
        nu = np.zeros(len(u))
        if name in solo:
            rows, dl = solo[name]
            g, pk = L.solo(R, rows, dl)
            nu = np.bincount(pt[pk], g / L.LN2, len(u))
        ns = ratio_boot(nu, den, u)
        d = fitpos.get(name, {})
        rnd = chosen(d) if 'folds' in d else 0
        row = dict(key=name, n=n, t=t, fit=d.get('pos', 0), rounds=rnd, prior=float(q[m].mean()), saved=s, net=ns, net_total=float(nu.sum()))
        keysres.append(row)
        out.write('%s\t%d\t%d\t%d\t%d\t%.3f\t%.3f\t%.3f\t%.3f\t%.3f\t%.3f\t%.3f\t%.1f\n' % (name, n, t, row['fit'], rnd, row['prior'], *s, *ns, row['net_total']))
    out.close()
    big = [r for r in keysres if r['t'] >= 8 or r['n'] >= 50]
    passg = [r for r in big if r['saved'][0] >= 1 and r['saved'][1] > 0]
    passn = [r for r in big if r['net'][0] >= 1 and r['net'][1] > 0]
    rep = dict(arm=arm, level=level, alpha=a.alpha, eta=a.eta, read_picks=int(R.n), prior_bits_per_pick=float(q.mean()), baseline_gap=gap, baseline_vs_rank_max_gap=gap,
               saved=L.boot(sv, R.task, all_), saved_alive=L.boot(sv, R.task, alive), saved_minus_rank_structure=L.boot(sv - rank['structure'], R.task, all_), saved_minus_rank_content=L.boot(sv - rank['content'], R.task, all_),
               score_ms_per_pick=cost, trees_used=nn, keys_with_model=len(solo), keys_in_level=len(ix.ks), keys_8tasks_or_50picks=len(big), keys_pass_gold=[r['key'] for r in passg], keys_pass_net=[r['key'] for r in passn],
               share_picks_pass_gold=sum(r['n'] for r in passg) / R.n, share_picks_pass_net=sum(r['n'] for r in passn) / R.n, sum_gold_saved_big=sum(r['saved'][0] * r['n'] for r in big), sum_net_big=sum(r['net_total'] for r in big), sum_net_all=sum(r['net_total'] for r in keysres),
               held_gold_share_keys_no_model=float(sum(r['n'] for r in keysres if r['key'] not in solo)) / R.n, keys_table=keysres)
    json.dump(rep, open(L.ME + 'read-%s.json' % arm, 'w'), indent=1)
    txt = rank_table(R, sv, rank, None)
    open(L.ME + 'table-%s.md' % arm, 'w').write(txt)
    print(json.dumps({k: v for k, v in rep.items() if k != 'keys_table'}, indent=1))
    print(txt)


if __name__ == '__main__':
    main()
