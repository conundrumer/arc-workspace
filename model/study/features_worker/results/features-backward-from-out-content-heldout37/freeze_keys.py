"""Freezes the keys of the two targets whose greedy pick stopped at body+cols.

On the targets that finished every tier (comp INIT, comp DET, kind, geom, rel, reads INIT), the greedy pick for `full` gave the same keys as `body+cols`, so `full` takes those keys here with no pick. `open` takes those keys plus the read atom's port and column names, with no pick, so its bound on these two targets may read low.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
for name in ('cols', 'reads-RULE-DET'):
    p = HERE + '/keys-%s.json' % name
    if os.path.exists(p):
        continue
    d = json.load(open(p + '.part'))
    b = d['tiers']['body+cols']
    d['tiers']['full'] = dict(keys=b['keys'], marginal=b['marginal'], greedy=b['greedy'], cv_with_weights=b['cv_with_weights'], note='keys of body+cols, no pick')
    d['tiers']['open'] = dict(keys=b['keys'] + [['a_port'], ['a_cols']], marginal=b['marginal'], greedy=None, cv_with_weights=None, note='keys of body+cols plus a_port and a_cols, no pick')
    json.dump(d, open(p, 'w'), indent=1)
    print(name, list(d['tiers']))
