#!/usr/bin/env python3
"""Paired read of the prefix score on test cases, from search_prefix_score_hits.py's files. It reads partial output.

  python3 search_prefix_score_report.py BASE_DIR ARM_DIR

Each folder holds one JSON per test case, as tp_end.py writes. Bits gained on a case hit in both arms is log2 of proposals in the base over proposals in the arm, and the same in
CPU seconds. A match is extensional at the clause's end. Cases with an error in either arm are left out and counted.
"""
import glob
import json
import math
import os
import statistics
import sys


def load(folder):
    out = {}
    for path in glob.glob(folder + '/*.json'):
        try:
            r = json.load(open(path))
        except ValueError:
            continue
        out[os.path.basename(path)] = r
    return out


def main():
    a, b = load(sys.argv[1]), load(sys.argv[2])
    both = sorted(set(a) & set(b))
    bad = [k for k in both if a[k].get('error') or b[k].get('error')]
    keys = [k for k in both if k not in bad]
    print('cases in both %d, left out with an error %d, waiting %d' % (len(both), len(bad), len(set(a) ^ set(b))))
    for t in (15, 30, 60):
        x = {k for k in keys if a[k]['hit'] and a[k]['hit_cpu'] <= t}
        y = {k for k in keys if b[k]['hit'] and b[k]['hit_cpu'] <= t}
        print('  at %d CPU s: base %d, arm %d, both %d, base alone %d, arm alone %d, neither %d' % (t, len(x), len(y), len(x & y), len(x - y), len(y - x), len(keys) - len(x | y)))
    hit = [k for k in keys if a[k]['hit'] and b[k]['hit']]
    if hit:
        prop = [math.log2(max(a[k]['hit_tried'], 1) / max(b[k]['hit_tried'], 1)) for k in hit]
        cpu = [math.log2(max(a[k]['hit_cpu'], .001) / max(b[k]['hit_cpu'], .001)) for k in hit]
        print('  on %d cases hit by both: bits gained by proposals, median %.2f, mean %.2f, better %d, worse %d; by CPU s, median %.2f, mean %.2f' % (
            len(hit), statistics.median(prop), statistics.mean(prop), sum(x > 0 for x in prop), sum(x < 0 for x in prop), statistics.median(cpu), statistics.mean(cpu)))
        for k, p in sorted(zip(hit, prop), key=lambda z: z[1]):
            print('    %-34s base %5d, arm %5d proposals, %+.2f bits, %s bits under q' % (k[:34], a[k]['hit_tried'], b[k]['hit_tried'], p, a[k].get('bits')))
    rate = [sum(r[k]['tried'] or 0 for k in keys) / max(sum(r[k]['cpu'] or 0 for k in keys), 1e-9) for r in (a, b)]
    print('  proposals per CPU s: base %.1f, arm %.1f' % tuple(rate))


if __name__ == '__main__':
    main()
