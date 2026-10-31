"""relpicks.py MODEL RUN OUT.tsv: per relation row of RUN/relrows.jsonl.zst, gold's bits under P and under MODEL (P's share
times exp(f), renormalized), gold's rank under MODEL, with the row's point, group, k, phase and gold's option."""
import math
import sys

import relsteer
from gq_pair import rows

L2 = math.log(2)


def main():
    sc = relsteer.Scorer(sys.argv[1], 'hgb')
    with open(sys.argv[3], 'w') as out:
        out.write('task\tcase\tpoint\tgroup\tk\tphase\tgold\tgold_kind\tn_options\tP_bits\tmodel_bits\tmodel_rank\n')
        for i, r in enumerate(rows(sys.argv[2] + '/relrows.jsonl.zst')):
            opts = r['options']
            g = next((j for j, o in enumerate(opts) if o['tok'] == r['gold']), None)
            if g is None:
                continue
            f = sc.f(r)
            lw = [math.log(max(o['p'], 1e-12)) + x for o, x in zip(opts, f)]
            m = max(lw)
            lz = m + math.log(sum(math.exp(v - m) for v in lw))
            pb = -math.log(max(opts[g]['p'], 1e-12)) / L2
            mb = -(lw[g] - lz) / L2
            rank = 1 + sum(v > lw[g] for v in lw)
            out.write('\t'.join(map(str, (r['task'], r['case'], r['point'], (r.get('point_group') or {}).get('point_group'), r['k'], r['phase'], opts[g]['name'], opts[g]['kind'],
                                          len(opts), round(pb, 3), round(mb, 3), rank))) + '\n')
            if i % 500 == 0:
                print(i, flush=True)


if __name__ == '__main__':
    main()
