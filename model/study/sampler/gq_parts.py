"""gq_parts.py RUN_A RUN_B [GROUP]: on the points of GROUP (default RULE depth 3+) where both runs give gold a finite q_steer,
gold's bits split into its atoms' draw q (lq_mix), the acceptance terms (-la) and the stop decisions (stop_q), with P's atom
bits (lp) beside them: mean and median per run, and the paired mean and median of B - A."""
import math
import statistics
import sys

from gq_pair import golds_rows, rows

L2 = math.log(2)


def parts(d, group):
    grp = {}
    for p in rows(d + '/points.jsonl.zst'):
        if 'error' not in p:
            grp[(p['task'], p['case'], str(p['point']))] = (p.get('point_group') or {}).get('point_group')
    out = {}
    for r in rows(d + '/draws.jsonl.zst'):
        k = (r['task'], r['case'], str(r['point']))
        if r.get('gold') and grp.get(k) == group and not r.get('logq_steer_zero') and r.get('logq_steer') is not None:
            ps = r.get('logq_steer_parts') or []
            out[k] = dict(total=-r['logq_steer'] / L2, atom_p=-sum(p['lp'] for p in ps) / L2,
                          atom_q=-sum(p['lq_mix'] for p in ps if p.get('lq_mix') is not None) / L2,
                          accept=sum(p['la'] for p in ps if p.get('la') is not None) / L2,
                          stop=-sum(p['stop_q'] for p in ps if p.get('stop_q') is not None) / L2, atoms=len(ps))
    return out


def main():
    group = sys.argv[3] if len(sys.argv) > 3 else 'RULE depth 3+'
    a, b = parts(sys.argv[1], group), parts(sys.argv[2], group)
    ks = sorted(k for k in a.keys() & b.keys() if abs(a[k]['atom_p'] - b[k]['atom_p']) < 1e-6)  # same gold in both runs
    print('%s: %d paired points; bits per clause' % (group, len(ks)))
    print('%-8s %8s %8s %8s %8s %10s %10s' % ('part', 'A mean', 'B mean', 'A med', 'B med', 'B-A mean', 'B-A med'))
    for f in ('total', 'atom_p', 'atom_q', 'accept', 'stop', 'atoms'):
        va, vb = [a[k][f] for k in ks], [b[k][f] for k in ks]
        print('%-8s %8.2f %8.2f %8.2f %8.2f %10.2f %10.2f' % (f, statistics.mean(va), statistics.mean(vb), statistics.median(va),
              statistics.median(vb), statistics.mean(y - x for x, y in zip(va, vb)), statistics.median(y - x for x, y in zip(va, vb))))


if __name__ == '__main__':
    main()
