"""Tune read: each target, fit on fit tasks with task folds, read on the 62 dev tasks. Held rows are not loaded. A row is a target form with a seed; saved_per_form is per state, so a form with two seeds counts twice.

  gold_tables_env.sh 1 dev_read.py [TARGET ...]   (rows in rows/ of this folder; ROWS=DIR reads another folder, DEV_TIERS=need,foundset,need+foundset)
"""
import json
import os
import sys
import time

import numpy as np

import next_form_facts as F
import next_form_model as M

OUT = F.R + 'dev-read.jsonl'


def mask_of(rows, vocab):
    """The derived keys of a row open at its state; every other value open."""
    ix = {v: i for i, v in enumerate(vocab)}
    m = np.ones((len(rows), len(vocab)), dtype=bool)
    dk = [i for v, i in ix.items() if v.startswith('D:')]
    m[:, dk] = False
    for i, r in enumerate(rows):
        for k in r['open']:
            j = ix.get(k)
            if j is not None:
                m[i, j] = True
    # A key that a form reads is open: a table with no rows for one of the found form's relations can leave it out of r['open'].
    for i, r in enumerate(rows):
        j = ix.get(r['y'])
        if j is not None:
            m[i, j] = True
    return m


TARGETS = {
    'comp INIT': ('t_comp', ('INIT',)),
    'comp DET': ('t_comp', ('DET',)),
    'cols': ('t_cols', ('RULE', 'DET', 'INIT')),
    'coarse cols': ('t_coarse', ('RULE', 'DET', 'INIT')),
    'geom': ('t_geom', ('RULE', 'DET', 'INIT')),
    'rel': ('t_rel', ('RULE', 'DET', 'INIT')),
    'shape': ('t_shape', ('RULE', 'DET', 'INIT')),
    'content': ('t_content', ('RULE', 'DET', 'INIT')),
}
BAGS = {'reads RULE DET': ('RULE', 'DET'), 'reads INIT': ('INIT',)}


def main():
    t0 = time.time()
    folder = os.environ.get('ROWS')
    tf, td = F.load('fit', folder), F.load('dev', folder)
    fit = F.rows_of(tf)
    dev = F.rows_of(td)
    print('rows', len(fit), len(dev), round(time.time() - t0, 1), flush=True)
    fam = F.family_keys(fit)
    only = sys.argv[1:] or list(TARGETS) + list(BAGS)
    tiers = os.environ.get('DEV_TIERS', 'need,foundset,need+foundset').split(',')
    with open(OUT, 'a') as out:
        for name in only:
            if name in TARGETS:
                col, kinds = TARGETS[name]
                a = F.categorical(fit, col, kinds)
                b = F.categorical(dev, col, kinds)
                V = M.vocab_of(a, 5 if col in ('t_cols', 't_coarse', 't_head', 't_content', 't_shape') else 1)
                kk = sorted({r['kind'] for r in a})
                da, db = M.Data(a, V, kk), M.Data(b, V, kk)
            else:
                kinds = BAGS[name]
                a = F.bag(fit, kinds)
                b = F.bag(dev, kinds)
                V = M.vocab_of(a, 8)
                kk = sorted({r['kind'] for r in a})
                da, db = M.Data(a, V, kk, mask_of(a, V)), M.Data(b, V, kk, mask_of(b, V))
            nf = len({(r['task'], r['form'], r['seed']) for r in dev if r['kind'] in kinds})
            for tier in tiers:
                t1 = time.time()
                singles = [(k,) for fm in F.TIERS[tier] for k in fam[fm]]
                chosen, b0, b1 = M.select(da, singles, top=6 if len(V) > 200 else 8, log=print)
                m = M.Model(da, chosen)
                mb, mm, rk = m.read(db)
                row = dict(target=name, tier=tier, nfit=len(a), ndev=len(b), dev_forms=nf, vocab=len(V), keys=['*'.join(k) for k in chosen], w=[round(float(x), 3) for x in m.w], cv_base=round(b0, 3), cv=round(b1, 3),
                           dev_marginal=round(float(mb.mean()), 3), dev_model=round(float(mm.mean()), 3), saved_per_form=round(float((mb - mm).sum() / nf), 3), top1=round(float((rk == 0).mean()), 3), top5=round(float((rk < 5).mean()), 3), seconds=round(time.time() - t1, 1))
                print(json.dumps(row), flush=True)
                out.write(json.dumps(row) + '\n')
                out.flush()


if __name__ == '__main__':
    main()
