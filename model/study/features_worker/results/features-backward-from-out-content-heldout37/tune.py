"""Situation keys per target and tier, picked on fit tasks with task folds. No held row and no row of the 99 is loaded.

  gold_tables_env.sh tune.py TARGET ...

Writes keys-TARGET.json. A rerun skips a target with a file.

Tiers, by the families their keys may read:
  out        n0_, g_     the output need at OUT and the grids
  body       b_          the reader's body as a set, hole types from the lib signature, the masked atom
  body+cols  b_, c_      and the reader's own columns
  full       b_, c_, n0_, g_   the primary tier
  open       and a_      the read atom unmasked, an upper bound that reads the read form's own port and column names
"""
import json
import os
import sys
import time

import numpy as np

HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-backward-from-out-content-heldout37'  # the data folder
sys.path.insert(0, HERE)
import backward_edges as E  # noqa: E402
import next_form_facts as F  # noqa: E402
import next_form_model as M  # noqa: E402

ALLK = ('RULE', 'DET', 'INIT')
TARGETS = {'kind': ('t_kind', ALLK, 1), 'comp INIT': ('t_comp', ('INIT',), 1), 'comp DET': ('t_comp', ('DET',), 1), 'cols': ('t_cols', ALLK, 5), 'coarse cols': ('t_coarse', ALLK, 5), 'geom': ('t_geom', ALLK, 1), 'rel': ('t_rel', ALLK, 1), 'shape': ('t_shape', ALLK, 5), 'content': ('t_content', ALLK, 5)}
BAGS = {'reads RULE DET': ('RULE', 'DET'), 'reads INIT': ('INIT',)}
TIERS = {'out': ('n0_', 'g_'), 'body': ('b_',), 'body+cols': ('b_', 'c_'), 'full': ('b_', 'c_', 'n0_', 'g_'), 'open': ('b_', 'c_', 'n0_', 'g_', 'a_')}


def load_fit():
    tasks = F.load('fit')
    libs = json.load(open(HERE + '/top-libs.json'))
    rows, c = E.edge_rows('fit', tasks, libs)
    return tasks, [r for r in rows if r['primary']], c


def cat_rows(rows, name):
    col, kinds, minn = TARGETS[name]
    return [dict(task=r['task'], form=r['form'], reader=r['reader'], kind=r['kind'] if name != 'kind' else 'any', fact=r['fact'], y=r['y'][col], depth=min(r['depth'], 4), open=r.get('open')) for r in rows if r['kind'] in kinds and r['y'][col] is not None]


def bag_rows(rows, kinds):
    out = []
    for r in rows:
        if r['kind'] in kinds:
            for t in r['y']['t_lib'] + r['y']['t_keys']:
                out.append(dict(task=r['task'], form=r['form'], reader=r['reader'], kind=r['kind'], fact=r['fact'], y=t, depth=min(r['depth'], 4), open=r.get('open')))
    return out


def mask_of(rows, vocab):
    ix = {v: i for i, v in enumerate(vocab)}
    m = np.ones((len(rows), len(vocab)), dtype=bool)
    m[:, [i for v, i in ix.items() if v.startswith('D:')]] = False
    for i, r in enumerate(rows):
        for k in r['open']:
            j = ix.get(k)
            if j is not None:
                m[i, j] = True
        j = ix.get(r['y'])
        if j is not None:
            m[i, j] = True
    return m


def data_of(name, rows):
    if name in BAGS:
        a = bag_rows(rows, BAGS[name])
        V = M.vocab_of(a, 8)
        kk = sorted({r['kind'] for r in a})
        return a, M.Data(a, V, kk, mask_of(a, V))
    a = cat_rows(rows, name)
    V = M.vocab_of(a, TARGETS[name][2])
    kk = sorted({r['kind'] for r in a})
    return a, M.Data(a, V, kk)


def main():
    t0 = time.time()
    tasks, prim, c = load_fit()
    if any(n in BAGS for n in sys.argv[1:]):
        E.open_keys_row(prim, tasks)
    print('rows', len(prim), round(time.time() - t0, 1), flush=True)
    names = sorted({k for r in prim[:50] for k in r['fact']})
    for name in sys.argv[1:]:
        path = HERE + '/keys-%s.json' % name.replace(' ', '-')
        if os.path.exists(path):
            continue
        a, d = data_of(name, prim)
        res = dict(target=name, rows=len(a), vocab=len(d.v), tiers={})
        if os.path.exists(path + '.part'):
            res = json.load(open(path + '.part'))
        for tier, pre in TIERS.items():
            if tier in res['tiers']:
                continue
            singles = [(k,) for k in names if k.startswith(pre)]
            ch, b0, b1 = M.select(d, singles, top=10, pairs=True, max_keys=8, min_gain=.003)
            cv = M.cv_stack(d, *M.oof(d, ch), ch, folds=5) if ch else b0
            res['tiers'][tier] = dict(keys=[list(k) for k in ch], marginal=round(b0, 3), greedy=round(b1, 3), cv_with_weights=round(float(cv), 3))
            print(name, tier, res['tiers'][tier], 'rate %.0f s elapsed' % (time.time() - t0), flush=True)
            json.dump(res, open(path + '.part', 'w'), indent=1)
        os.replace(path + '.part', path)
    print('done', round(time.time() - t0), flush=True)


if __name__ == '__main__':
    main()
