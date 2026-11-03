#!/usr/bin/env python
"""A final model: fit on all fit tasks, then its one held read.

  python features_ofree_read.py NAME GROUP ARM TIER LAM [MAXITER] [--control]

The ledger held-reads.jsonl has one line per held read. A name already in it stops the script before it loads a held row. Writes models/NAME.npz, read-NAME.json, saved-NAME.npy, keys-NAME.tsv.
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-relation-pick-order-free-per-relation-heldout37')
import features_ofree_lib as L  # noqa: E402
import features_ofree_ordered as O  # noqa: E402

CLASSES = ('derived', 'lib', 'fact', 'macro', 'NOT', 'comparison')


def table(s, b0, Dh, mask):
    out = {}
    tasks = Dh.task
    out['all'] = dict(n=int(mask.sum()), tasks=len(set(tasks[mask].tolist())), base=float(b0[mask].mean()), saved=L.boot(s, tasks, mask))
    for c in CLASSES:
        m = mask & (Dh.cl == c)
        if m.any():
            out[c] = dict(n=int(m.sum()), base=float(b0[m].mean()), saved=L.boot(s, tasks, m))
    return out


def keys_table(m, Dh, idx):
    """Per key: lib by name, derived by family. Bits saved at label rows, and net of the cost at the rows that offer the key."""
    X, ll, lo, ll0, lo0 = m.rows_key(Dh, idx)
    tasks = Dh.task[idx]
    rows = []
    fams = sorted({o['fam'] for o in Dh.oinfo})
    flat = [Dh.oinfo[j]['fam'] for j in X['ops'].tolist()]
    flat = np.array(flat)
    todo = [(k, j, None) for j, k in enumerate(Dh.libs) if (X['yl'] == j).any()] + [(f, None, flat == f) for f in fams]
    for name, j, mask in todo:
        s, hit = L.key_net(X, ll, lo, ll0, lo0, j, mask)
        if not hit.any():
            continue
        net = s.sum() / hit.sum()
        at = s[hit].mean()
        u = sorted(set(tasks.tolist()))
        ix = {t: i for i, t in enumerate(u)}
        ti = np.array([ix[t] for t in tasks.tolist()])
        sb = np.bincount(ti, s, len(u))
        nb = np.bincount(ti, hit, len(u)).astype(float)
        W = np.random.RandomState(0).multinomial(len(u), [1.0 / len(u)] * len(u), 4000)
        den = W @ nb
        r = (W @ sb)[den > 0] / den[den > 0]
        rows.append(dict(key=name, rows=int(hit.sum()), tasks=int((nb > 0).sum()), saved_at_label=float(at), net=float(net), net_lo=float(np.percentile(r, 2.5)), net_hi=float(np.percentile(r, 97.5)), net_total=float(s.sum())))
    rows.sort(key=lambda r: -r['net_total'])
    return rows


def main():
    a = sys.argv[1:]
    control = '--control' in a
    if control:
        a.remove('--control')
    name, group, armn, tier, lam = a[0], a[1], a[2], a[3], float(a[4])
    maxit = int(a[5]) if len(a) > 5 else 60
    led = L.ME + 'held-reads.jsonl'
    if os.path.exists(led):
        for x in open(led):
            if json.loads(x)['name'] == name:
                print('held read', name, 'is in the ledger: stopping')
                return
    t0 = time.time()
    recs = L.load('fit')
    libs = L.lib_vocab(recs)
    fa, fo = O.arm(armn, tier)
    D = L.Data(recs, group, libs, tier, fa, fo)
    tr = np.arange(D.n)
    ctrl = D.shuffled(7) if control else None
    print('fit %s: %d rows, %.0f s' % (name, D.n, time.time() - t0), flush=True)
    m = L.Model(D, tr, lam, maxiter=maxit, ctrl=ctrl)
    os.makedirs(L.ME + 'models', exist_ok=True)
    np.savez_compressed(L.ME + 'models/%s.npz' % name, theta=m.theta.astype(np.float32), names=np.array(m.names), facts=np.array([k for k, v in sorted(D.fv.items(), key=lambda x: x[1])]), fsel=m.fsel, nit=m.nit)
    print('fitted %s: %d keys, %d facts, %d iters, %.0f s' % (name, m.nk, m.nf, m.nit, time.time() - t0), flush=True)
    hrecs = L.load('held')
    Dh = L.Data(hrecs, group, libs, tier, fa, fo, like=D)
    if control:
        Dh.ygold_lib, Dh.ygold_opt = Dh.shuffled(8)
    with open(led, 'a') as f:
        f.write(json.dumps(dict(name=name, group=group, arm=armn, tier=tier, lam=lam, control=control, time=time.strftime('%Y-%m-%dT%H:%M:%S'))) + '\n')
    all_idx = np.arange(Dh.n)
    s, b0 = m.saved(Dh, all_idx)
    np.save(L.ME + 'saved-%s.npy' % name, s.astype(np.float32))
    top = ~Dh.neg
    res = dict(name=name, group=group, arm=armn, tier=tier, lam=lam, control=control, rows_fit=int(D.n), keys=m.nk, facts=m.nf, nit=m.nit, misses=Dh.miss, atoms=table(s, b0, Dh, top), inside_not=table(s, b0, Dh, ~top) if (~top).any() else None)
    if group == 'INIT':
        res['key_place'] = table(s, b0, Dh, top & (Dh.place == 'key'))['all']
        res['port_place'] = table(s, b0, Dh, top & (Dh.place == 'port'))['all']
    kt = keys_table(m, Dh, np.nonzero(top)[0])
    res['keys_table'] = kt
    json.dump(res, open(L.ME + 'read-%s.json' % name, 'w'), indent=1)
    with open(L.ME + 'keys-%s.tsv' % name, 'w') as f:
        f.write('key\trows\ttasks\tsaved_at_label\tnet_per_label\tnet_lo\tnet_hi\tnet_total\n')
        for r in kt:
            f.write('%s\t%d\t%d\t%.3f\t%.3f\t%.3f\t%.3f\t%.1f\n' % (r['key'], r['rows'], r['tasks'], r['saved_at_label'], r['net'], r['net_lo'], r['net_hi'], r['net_total']))
    t = res['atoms']['all']
    print(name, 'atoms %d, tasks %d, base %.3f, saved %.3f (%.3f to %.3f), %.0f s' % (t['n'], t['tasks'], t['base'], *t['saved'], time.time() - t0), flush=True)


if __name__ == '__main__':
    main()
