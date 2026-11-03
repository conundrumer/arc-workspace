"""Reads the sweep of every form on the non-held tasks.

Set-apart tasks leave the read. The null is the same read with the same number of positive labels moved to random tasks of the positive and plain sets, 2,000 times: the best-of-grid value each time, as a chance level for a maximum over the grid.

  features_sweep_read.py OUT.json SWEEP_ROWS...
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
names = json.load(open(HERE + 'sweep-forms.json'))
rows = []
for p in sys.argv[2:]:
    rows += [json.loads(x) for x in open(p)]
kept = [r for r in rows if not r['whole'][0] + r['whole'][1]]
print('rows', len(rows), 'kept', len(kept), 'forms', len(names))
T = len(kept)
H = np.zeros((len(names), T), dtype=bool)
G = np.zeros((len(names), T, 3), dtype=np.float32)
for t, r in enumerate(kept):
    for j, v in r['hits'].items():
        H[int(j), t] = True
        G[int(j), t] = v
grp = np.array([r['group'] for r in kept])
plain = grp == 'plain'
pos = grp == 'positive'
one = grp == 'one-pose'
print('positive', pos.sum(), 'one-pose', one.sum(), 'plain', plain.sum())


def read(mask):
    """Per form: hits among the mask, hits on plain, boolean AUC, bits at those hits."""
    tp = H[:, mask].sum(1).astype(float)
    fp = H[:, plain].sum(1).astype(float)
    n, m = mask.sum(), plain.sum()
    a = .5 + .5 * (tp / n - fp / m)
    base = n / (n + m)
    with np.errstate(divide='ignore', invalid='ignore'):
        prec = tp / (tp + fp)
        bits = np.where(tp > 0, np.log2(prec / base), -np.inf)
    return tp, fp, a, bits


out = {}
for label, mask in (('pos', pos), ('all', pos | one)):
    tp, fp, a, bits = read(mask)
    n = int(mask.sum())
    r5 = tp / n >= .5
    r3 = tp / n >= .3
    best_auc = np.argsort(-a)[:8]
    print(f'== {label}: n {n}, forms with any hit {int((tp > 0).sum())}, recall .5 {int(r5.sum())}, recall .3 {int(r3.sum())}')
    for j in best_auc:
        print(f'  AUC {a[j]:.3f} {names[j]} pos {int(tp[j])}/{n} plain {int(fp[j])}/{int(plain.sum())} bits {bits[j]:.2f}')
    for nm, flag in (('recall .5', r5), ('recall .3', r3)):
        if flag.any():
            idx = np.where(flag)[0]
            j = idx[np.argmax(bits[idx])]
            print(f'  best bits at {nm}: {bits[j]:.2f} {names[j]} pos {int(tp[j])}/{n} plain {int(fp[j])} AUC {a[j]:.3f}')
    # Graded scores at the best forms: AUC over all tasks.
    best_graded = []
    for j in np.argsort(-a)[:50]:
        for s, sname in enumerate(('pairs', 'size', 'share')):
            p, q = G[j, mask, s], G[j, plain, s]
            u = (np.sum(p[:, None] > q[None, :]) + .5 * np.sum(p[:, None] == q[None, :])) / (len(p) * len(q))
            best_graded.append((float(u), names[j], sname))
    best_graded.sort(reverse=True)
    print('  graded', best_graded[:3])
    rng = np.random.default_rng(11)
    pool = np.where(mask | plain)[0]
    null_auc, null_r3, null_r5 = [], [], []
    for _ in range(2000):
        pick = np.zeros(T, dtype=bool)
        pick[rng.choice(pool, n, replace=False)] = True
        rest = np.zeros(T, dtype=bool)
        rest[pool] = True
        rest &= ~pick
        tp0 = H[:, pick].sum(1)
        fp0 = H[:, rest].sum(1)
        a0 = .5 + .5 * (tp0 / n - fp0 / rest.sum())
        null_auc.append(float(a0.max()))
        with np.errstate(divide='ignore', invalid='ignore'):
            b0 = np.where(tp0 > 0, np.log2(tp0 / (tp0 + fp0) / (n / (n + rest.sum()))), -np.inf)
        null_r3.append(float(b0[tp0 / n >= .3].max()) if (tp0 / n >= .3).any() else float('nan'))
        null_r5.append(float(b0[tp0 / n >= .5].max()) if (tp0 / n >= .5).any() else float('nan'))
    best = float(a.max())
    q = lambda xs: [round(float(np.nanpercentile(xs, v)), 3) for v in (50, 95)]
    print(f'  null best-of-grid boolean AUC median, 95th {q(null_auc)}; observed {best:.3f}, share of null at or above {np.mean(np.array(null_auc) >= best):.3f}')
    print(f'  null best bits at recall .3 median, 95th {q(null_r3)}; at recall .5 {q(null_r5)}')
    out[label] = dict(n=n, plain=int(plain.sum()), any_hit=int((tp > 0).sum()), recall5=int(r5.sum()), recall3=int(r3.sum()),
                      top=[dict(form=names[j], tp=int(tp[j]), fp=int(fp[j]), auc=round(float(a[j]), 3), bits=round(float(bits[j]), 3)) for j in best_auc],
                      graded=best_graded[:3], null_auc=q(null_auc), null_share=float(np.mean(np.array(null_auc) >= best)), null_r3=q(null_r3), null_r5=q(null_r5))
    if r3.any():
        idx = np.where(r3)[0]
        j = idx[np.argmax(bits[idx])]
        out[label]['best_r3'] = dict(form=names[j], tp=int(tp[j]), fp=int(fp[j]), auc=round(float(a[j]), 3), bits=round(float(bits[j]), 3))
    if r5.any():
        idx = np.where(r5)[0]
        j = idx[np.argmax(bits[idx])]
        out[label]['best_r5'] = dict(form=names[j], tp=int(tp[j]), fp=int(fp[j]), auc=round(float(a[j]), 3), bits=round(float(bits[j]), 3))
json.dump(out, open(sys.argv[1], 'w'), indent=0)
