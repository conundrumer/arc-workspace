"""What the frozen models learned: for each target and tier, the cells of the situation keys with the most pull: (lift over the kind's rate, in bits) times the count.

Writes situations.tsv. A row is a target form with a seed, so a count is of states. Counts come from fit rows. The dev columns count the same cell on dev tasks, so that a reader can check a line on tasks the fit did not read.
"""
import collections
import json
import math

import next_form_facts as F

TARGETS = {'comp INIT': ('t_comp', ('INIT',)), 'comp DET': ('t_comp', ('DET',)), 'coarse cols': ('t_coarse', ('RULE', 'DET', 'INIT')), 'geom': ('t_geom', ('RULE', 'DET', 'INIT')), 'rel': ('t_rel', ('RULE', 'DET', 'INIT'))}
BAGS = {'reads RULE DET': ('RULE', 'DET'), 'reads INIT': ('INIT',)}


def counts(rows, key):
    n = collections.Counter()
    c = collections.Counter()
    k = collections.Counter()
    ky = collections.Counter()
    tasks = collections.defaultdict(set)
    for r in rows:
        cell = (r['kind'],) + tuple(r['fact'][a] for a in key)
        n[cell, r['y']] += 1
        c[cell] += 1
        k[r['kind']] += 1
        ky[r['kind'], r['y']] += 1
        tasks[cell, r['y']].add(r['task'])
    return n, c, k, ky, tasks


def main():
    frozen = json.load(open(F.R + 'frozen.json'))
    tf, td = F.load('fit'), F.load('dev')
    fit = F.rows_of(tf)
    dev = F.rows_of(td)
    out = []
    for name in list(TARGETS) + list(BAGS):
        if name in TARGETS:
            a = F.categorical(fit, TARGETS[name][0], TARGETS[name][1])
            b = F.categorical(dev, TARGETS[name][0], TARGETS[name][1])
        else:
            a = F.bag(fit, BAGS[name])
            b = F.bag(dev, BAGS[name])
        seen = set()
        for tier in ('need', 'foundset', 'need+foundset'):
            for key in frozen['keys'][name][tier]:
                if tuple(key) in seen:
                    continue
                seen.add(tuple(key))
                n, c, k, ky, tasks = counts(a, key)
                nd, cd, _, _, _ = counts(b, key)
                rows = []
                for (cell, y), v in n.items():
                    ts = len(tasks[cell, y])
                    if v < 10 or ts < 5:
                        continue
                    p = v / c[cell]
                    q = ky[cell[0], y] / k[cell[0]]
                    lift = math.log2(p / q)
                    if lift < .7:
                        continue
                    rows.append((v * lift, name, tier, '*'.join(key), ' '.join(str(x) for x in cell), y, v, c[cell], ts, round(p, 3), round(q, 3), round(lift, 2), nd.get((cell, y), 0), cd.get(cell, 0)))
                rows.sort(reverse=True)
                out += rows[:6]
    with open(F.R + 'situations.tsv', 'w') as f:
        f.write('pull\ttarget\ttier\tkey\tcell\tnext\tn_next\tn_cell\ttasks\tp\tmarginal\tlift_bits\tdev_next\tdev_cell\n')
        for r in sorted(out, key=lambda r: -r[0]):
            f.write('\t'.join(str(round(x, 1) if isinstance(x, float) else x) for x in r) + '\n')
    print(len(out))


if __name__ == '__main__':
    main()
