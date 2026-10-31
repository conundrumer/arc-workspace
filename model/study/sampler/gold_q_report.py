"""gold_q_report.py RUN...: per run and point group, the median of -log2 q_steer(gold) over the points whose gold has one, and the median CPU-hours to hit gold:
cpu per draw (points.jsonl.zst: cpu / draws) * 2^bits / 3600. A point with q_steer 0 (gold fails an acceptance stage or a gate) counts as infinite bits and is listed apart."""
import collections
import io
import json
import math
import statistics
import sys

import zstandard as z


def rows(path):
    with open(path, 'rb') as f:
        for line in io.TextIOWrapper(z.ZstdDecompressor().stream_reader(f)):
            yield json.loads(line)


for d in sys.argv[1:]:
    cpu = {}
    for p in rows(d + '/points.jsonl.zst'):
        if 'error' not in p and p.get('draws'):
            cpu[(p['task'], p['case'], json.dumps(p['point']))] = (p.get('point_group') or {}).get('point_group'), p['cpu'] / p['draws']
    by = collections.defaultdict(lambda: dict(bits=[], hours=[], zero=0, none=0))
    for r in rows(d + '/draws.jsonl.zst'):
        if not r.get('gold'):
            continue
        k = (r['task'], r['case'], json.dumps(r['point']))
        g, c = cpu.get(k, (None, None))
        if c is None:
            continue
        a = by[g]
        if r.get('logq_steer') is not None:
            bits = -r['logq_steer'] / math.log(2)
            a['bits'].append(bits)
            a['hours'].append(c * 2 ** min(bits, 1000) / 3600)
        elif r.get('logq_steer_zero'):
            a['zero'] += 1
        else:
            a['none'] += 1
    print(d)
    for g in sorted(by, key=str):
        a = by[g]
        n = len(a['bits'])
        med = lambda v: ('%.2f' % statistics.median(v)) if v else '-'  # noqa: E731
        medh = ('%.3g' % statistics.median(a['hours'])) if a['hours'] else '-'
        print('  %-14s points with q %3d  q=0 %3d  not scored %3d  median -log2 q %7s  median CPU-h to hit gold %s' % (g, n, a['zero'], a['none'], med(a['bits']), medh))
