"""The gap between what a pool proposes and gold's marginal, in the kind, for column types and row shapes.

  gold_tables_env.sh pool_gap.py SPLIT

q(a | kind) is the share of attribute a among the junk nodes of junk-node-rows.jsonl, one row per clause, 150 fit tasks of the node records. p(a | kind) is gold's marginal on fit tasks. A steer that moved proposals of the kind from q to p would save log2(p(a) / q(a)) on a form with attribute a, needing no fact of the state. This is a marginal: the sampler's own chance of a at a state is not read here.
Writes pool-gap-<split>.json.
"""
import collections
import json
import math
import sys

import final_read as R
import next_form_facts as F

ATTR = {'coarse cols': ('t_coarse', 'coarse'), 'geom': ('t_geom', 'geom'), 'rel': ('t_rel', 'rel')}


def main():
    split = sys.argv[1]
    junk = [json.loads(x) for x in open(F.R + 'junk-node-rows.jsonl')]
    tf = F.load('fit')
    fit = F.rows_of(tf)
    ts = F.load(split)
    rows = F.rows_of(ts)
    census = R.census_rows()
    per = R.base_per(rows, census)
    ok = lambda k: per[k]['bits'] is not None  # noqa: E731
    out = dict(split=split, junk_rows=len(junk), targets={})
    for name, (col, jcol) in ATTR.items():
        q = collections.Counter((j['kind'], j[jcol]) for j in junk)
        qk = collections.Counter(j['kind'] for j in junk)
        p = collections.Counter((r['kind'], r['y'][col]) for r in fit)
        pk = collections.Counter(r['kind'] for r in fit)
        vals = {k[1] for k in q} | {k[1] for k in p}
        n = len(vals)
        sv = {}
        for r in rows:
            if r['kind'] not in ('RULE', 'DET', 'INIT'):
                continue
            a = r['y'][col]
            pp = (p[r['kind'], a] + .5 / n) / (pk[r['kind']] + .5)
            qq = (q[r['kind'], a] + .5 / n) / (qk[r['kind']] + .5)
            sv[r['task'], r['form']] = math.log2(pp / qq)
        out['targets'][name] = R.summarize(sv, per, ok)
    json.dump(out, open(F.R + 'pool-gap-%s.json' % split, 'w'), indent=1)
    print(json.dumps(out))


if __name__ == '__main__':
    main()
