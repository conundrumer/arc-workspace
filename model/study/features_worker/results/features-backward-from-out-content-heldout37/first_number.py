"""First number on fit rows only: per depth, for the targets nearest OUT, baseline bits against conditional bits with 5 task folds. No held row is loaded.

  gold_tables_env.sh first_number.py
"""
import collections
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import backward_edges as E  # noqa: E402
import next_form_facts as F  # noqa: E402
import next_form_model as M  # noqa: E402

TARGETS = {'kind': ('t_kind', ('RULE', 'DET', 'INIT'), 1), 'comp INIT': ('t_comp', ('INIT',), 1), 'comp DET': ('t_comp', ('DET',), 1), 'cols': ('t_cols', ('RULE', 'DET', 'INIT'), 5), 'coarse cols': ('t_coarse', ('RULE', 'DET', 'INIT'), 5), 'geom': ('t_geom', ('RULE', 'DET', 'INIT'), 1), 'rel': ('t_rel', ('RULE', 'DET', 'INIT'), 1)}


def main():
    t0 = time.time()
    tasks = F.load('fit')
    print('load', round(time.time() - t0, 1), len(tasks), flush=True)
    libs = E.top_libs(tasks)
    rows, c = E.edge_rows('fit', tasks, libs)
    print('edges', round(time.time() - t0, 1), json.dumps(c), flush=True)
    print('primary by depth', sorted(E.depth_summary(rows).items()), flush=True)
    print(collections.Counter(r['fact']['b_rk'] for r in rows if r['primary']), flush=True)
    print('unknown hole types share', np.mean([r['fact']['b_hknown'] == 'none' for r in rows]), flush=True)
    json.dump(libs, open(HERE + '/top-libs.json', 'w'))
    prim = [r for r in rows if r['primary']]
    keysb = sorted({a for a in rows[0]['fact'] if a.startswith('b_')})
    keyso = sorted({a for a in rows[0]['fact'] if a.startswith(('n0_', 'g_'))})
    res = {}
    for name, (col, kinds, minn) in TARGETS.items():
        a = [dict(task=r['task'], form=r['form'], kind=r['kind'] if name != 'kind' else 'any', fact=r['fact'], y=r['y'][col], depth=min(r['depth'], 4)) for r in prim if r['kind'] in kinds and r['y'][col] is not None]
        V = M.vocab_of(a, minn)
        kk = sorted({r['kind'] for r in a})
        d = M.Data(a, V, kk)
        for fam, singles in (('body', keysb), ('out', keyso)):
            keys = [(k,) for k in singles]
            ch, b0, b1 = M.select(d, keys, top=8, pairs=True, max_keys=6, min_gain=.004)
            B, L = M.oof(d, ch) if ch else (M.oof(d, [])[0], {})
            # Greedy's bits come from the same rows the keys were picked on: this is a screen, not a read.
            stack = np.stack([L[k] for k in ch], 2) if ch else np.zeros((len(d.y), len(V), 0), dtype=np.float32)
            bit = np.zeros(len(d.y))
            for k in range(5):
                at = d.fold == k
                w = M.stack_fit(B[~at], stack[~at], d.y[~at], d.mask[~at])
                bit[at] = M.bits_of(B[at], stack[at], w, d.y[at], d.mask[at])
            base = -M.softmax_logp(B, d.mask)[np.arange(len(d.y)), d.y] / M.LOG2
            dp = np.array([r['depth'] for r in a])
            by = {str(x): [int((dp == x).sum()), round(float(base[dp == x].mean()), 3), round(float(bit[dp == x].mean()), 3)] for x in sorted(set(dp.tolist()))}
            res[name + '|' + fam] = dict(base=round(float(base.mean()), 3), model=round(float(bit.mean()), 3), keys=['*'.join(k) for k in ch], by_depth=by)
            print(name, fam, json.dumps(res[name + '|' + fam]), round(time.time() - t0), flush=True)
            json.dump(res, open(HERE + '/first-number-fit-oof.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
