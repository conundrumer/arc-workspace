"""gq_pair.py RUN_A RUN_B: on the points where both runs give gold a q_steer, per point group: the median bits of gold under
P, under q_steer in A and in B, the median of B - A, and the share of points whose gold is within 10, 15 and 20 bits in each run.
Points where either run has q_steer 0 are counted apart; points whose gold differs between the runs (P differs) are left out."""
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


def golds_rows(d):
    """{point key: (point group, gold's log p, log q_steer (-inf where it is 0), gold's atoms)} of run d."""
    grp = {}
    for p in rows(d + '/points.jsonl.zst'):
        if 'error' not in p:
            grp[(p['task'], p['case'], json.dumps(p['point']))] = (p.get('point_group') or {}).get('point_group')
    out = {}
    for r in rows(d + '/draws.jsonl.zst'):
        if r.get('gold'):
            k = (r['task'], r['case'], json.dumps(r['point']))
            q = -math.inf if r.get('logq_steer_zero') else r.get('logq_steer')
            out[k] = (grp.get(k), r.get('logp'), q, len(r.get('logq_steer_parts') or []))
    return out


def main():
    a, b = golds_rows(sys.argv[1]), golds_rows(sys.argv[2])
    by = collections.defaultdict(lambda: dict(p=[], a=[], b=[], zero=0))
    changed = 0
    for k in a.keys() & b.keys():
        g, lp, qa, _ = a[k]
        qb = b[k][2]
        if qa is None or qb is None or lp is None:
            continue
        if b[k][1] is None or abs(b[k][1] - lp) > 1e-6:  # the point's gold changed between the runs (a rebuilt task)
            changed += 1
            continue
        s = by[g]
        if qa == -math.inf or qb == -math.inf:
            s['zero'] += 1
            continue
        s['p'].append(-lp / math.log(2))
        s['a'].append(-qa / math.log(2))
        s['b'].append(-qb / math.log(2))
    print('%-14s %4s %6s %7s %7s %7s   %-17s %-17s %s' % ('group', 'pts', 'P', 'A', 'B', 'B-A', 'A <=10/15/20', 'B <=10/15/20', 'q=0'))
    allv = dict(p=[], a=[], b=[], zero=0)
    for g in sorted(by, key=str) + ['all']:
        s = by[g] if g != 'all' else allv
        if g != 'all':
            for f in ('p', 'a', 'b'):
                allv[f] += s[f]
            allv['zero'] += s['zero']
        n = len(s['a'])
        if not n:
            continue
        share = lambda v: '/'.join('%.2f' % (sum(x <= t for x in v) / n) for t in (10, 15, 20))  # noqa: E731
        print('%-14s %4d %6.1f %7.2f %7.2f %7.2f   %-17s %-17s %d' % (
            g, n, statistics.median(s['p']), statistics.median(s['a']), statistics.median(s['b']),
            statistics.median(y - x for x, y in zip(s['a'], s['b'])), share(s['a']), share(s['b']), s['zero']))
    if changed:
        print('left out %d points whose gold differs between the runs' % changed)


if __name__ == '__main__':
    main()
