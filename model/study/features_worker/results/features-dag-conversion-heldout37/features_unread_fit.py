#!/usr/bin/env python
"""The mixture weight w of the unread-forms read (item 14), fit on non-held walks only. Reads no held row.

  features_dagc_env.sh 1 features_unread_fit.py [--seconds S] [--off-from test-cut|dev-cut]

The mixture at a pick, for a set U: weight w uniform over U, 1-w on the prior of the walk. Every pick of a form pays under it, whatever its class. A pick with U empty stays as it is. Two versions of U:
- forms: U is the forms of the set, gold's target pays -log2(w/|U| + (1-w)p), a pick outside pays -log2((1-w)p).
- options: U is the derived options at the pick whose form is in the set.
w is fit by golden section on the log-odds of w, over all picks of the part (all kinds), each weighing its walks over the form's walks, the two seeds of a form each counting their own picks.
Steers live: test-cut live. Steers off: test-cut off where it exists; test-cut has no off pass in the walk plan (item 7), so the default is dev-cut off (62 dev tasks, none held). Writes unread-fit.json.
"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-dag-conversion-heldout37')
import features_dagc_rows as RW  # noqa: E402
import features_dagc_unread_rows as UR  # noqa: E402
import features_unread_lib as UL  # noqa: E402

ME = RW.ME


def arrays(picks, name, variant):
    n = np.array([p['n'][name] if variant == 'forms' else p['o'][name] for p in picks], float)
    ins = np.array([bool(p['inside'][name]) and (variant == 'forms' or p['o'][name] > 0) for p in picks])
    q = np.array([p['bits'] for p in picks], float)
    w = np.array([p['w'] for p in picks], float)
    return n, ins, q, w


def loss(w_mix, n, ins, q, w):
    p = 2.0 ** -q
    with np.errstate(divide='ignore'):
        new = -np.log2((1 - w_mix) * p + np.where(ins & (n > 0), w_mix / np.maximum(n, 1), 0.0))
    new = np.where(n > 0, new, q)
    return float((w * new).sum())


def fit_one(picks, name, variant):
    n, ins, q, w = arrays(picks, name, variant)
    lo, hi = -9.0, 6.0
    g = (math.sqrt(5) - 1) / 2

    def f(x):
        return loss(1 / (1 + math.exp(-x)), n, ins, q, w)
    a, b = hi - g * (hi - lo), lo + g * (hi - lo)
    fa, fb = f(a), f(b)
    for _ in range(40):
        if fa < fb:
            hi, b, fb = b, a, fa
            a = hi - g * (hi - lo)
            fa = f(a)
        else:
            lo, a, fa = a, b, fb
            b = lo + g * (hi - lo)
            fb = f(b)
    x = (lo + hi) / 2
    wm = 1 / (1 + math.exp(-x))
    base = float((w * q).sum())
    return wm, (base - loss(wm, n, ins, q, w)) / float(w.sum())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--seconds', type=float, default=20)
    ap.add_argument('--off-from', default='')
    a = ap.parse_args()
    t0 = time.time()
    out = dict(source={}, w={})
    for steers in ('off', 'live'):
        part = 'test-cut'
        if steers == 'off':
            part = a.off_from or ('test-cut' if any(os.path.exists(f) for f in __import__('glob').glob(ME + 'walks/test-cut-off-*.zst')) else 'dev-cut')
        R = UR.build(part, steers, seconds=a.seconds)
        assert not {p['task'] for p in R.picks} & RW.HELD, 'a held task in the fit rows'
        out['source'][steers] = dict(part=part, picks=len(R.picks), forms=len(R.forms), tasks=len({p['task'] for p in R.picks}), files=R.files)
        res = dict(picks=len(R.picks), derived_picks=sum(p['derived'] for p in R.picks), bits_per_pick=round(float(np.average([p['bits'] for p in R.picks], weights=[p['w'] for p in R.picks])), 4))
        der = [p for p in R.picks if p['derived']]
        for name in UL.SETS:
            for variant in ('forms', 'options'):
                wm, saved = fit_one(R.picks, name, variant)
                n, ins, q, w = arrays(der, name, variant)
                res['%s:%s' % (name, variant)] = dict(w=round(wm, 5), saved_per_pick=round(saved, 4), saved_per_derived_pick=round((float((w * q).sum()) - loss(wm, n, ins, q, w)) / float(w.sum()), 4),
                                                       inside_derived=round(float((w * ins).sum() / w.sum()), 4), median_n=float(np.median(n)))
        out['w'][steers] = res
        print(steers, part, json.dumps(res), '%.0fs' % (time.time() - t0), flush=True)
    json.dump(out, open(ME + 'unread-fit.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
