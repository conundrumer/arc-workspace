"""What the models learned, in words a person can check, on fit rows only: for each target's first keys in the `full` tier, the cells with the most lift over the kind's rate, at 30 rows or more.

  gold_tables_env.sh situations.py

Writes situations.tsv: target, key, cell, value, rows of the cell, rate in the cell, rate in the kind, log2 lift, bits saved over those rows.
"""
import collections
import json
import math
import os
import sys

HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-backward-from-out-content-heldout37'  # the data folder
sys.path.insert(0, HERE)
import tune as T  # noqa: E402
import backward_edges as E  # noqa: E402


def main():
    tasks, prim, _ = T.load_fit()
    E.open_keys_row(prim, tasks)
    out = []
    for name in ('comp INIT', 'comp DET', 'kind', 'cols', 'geom', 'rel', 'reads RULE DET', 'reads INIT'):
        keys = [tuple(k) for k in json.load(open(HERE + '/keys-%s.json' % name.replace(' ', '-')))['tiers']['full']['keys']]
        rows = T.bag_rows(prim, T.BAGS[name]) if name in T.BAGS else T.cat_rows(prim, name)
        base = collections.Counter((r['kind'], r['y']) for r in rows)
        nk = collections.Counter(r['kind'] for r in rows)
        forms = collections.Counter()
        seen = set()
        for r in rows:
            if (r['task'], r['form'], r['y']) not in seen:
                seen.add((r['task'], r['form'], r['y']))
        for key in keys[:3]:
            cell = collections.Counter()
            cn = collections.Counter()
            for r in rows:
                c = (r['kind'],) + tuple(r['fact'][a] for a in key)
                cell[c, r['y']] += 1
                cn[c] += 1
            for (c, y), n in cell.items():
                if n >= 30:
                    a = n / cn[c]
                    b = base[c[0], y] / nk[c[0]]
                    lift = math.log2(a / b)
                    out.append((name, '*'.join(key), '|'.join(c), y, n, cn[c], round(a, 3), round(b, 3), round(lift, 2), round(n * lift)))
    out.sort(key=lambda x: (x[0], -x[-1]))
    with open(HERE + '/situations.tsv', 'w') as f:
        f.write('target\tkey\tcell\tvalue\tn value in cell\tn cell\trate in cell\trate in kind\tlog2 lift\tbits over rows\n')
        for r in out:
            f.write('\t'.join(map(str, r)) + '\n')
    last = None
    c = 0
    for r in out:
        if r[0] != last:
            last, c = r[0], 0
        if c < 6 and r[8] > 0:
            print(r)
            c += 1


if __name__ == '__main__':
    main()
