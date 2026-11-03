"""Per group and fact: tasks where it holds, bits over the base rate at positive against plain, first node and first DET, and cost per node.

  features_rigid_read.py ROWS
"""
import collections
import json
import math
import statistics
import sys

rows = [json.loads(x) for x in open(sys.argv[1])]
print('tasks with no record rows, left out:', [r['task'] for r in rows if not r['nodes']])
rows = [r for r in rows if r['nodes']]
by = collections.defaultdict(list)
for r in rows:
    by[r['group']].append(r)
print({g: len(v) for g, v in by.items()})
names = sorted({k for r in rows for k in r['hits']})
pos, neg = by.get('positive', []), by.get('plain', [])
base = len(pos) / max(len(pos) + len(neg), 1)
print('fact | ' + ' | '.join(by) + ' | bits over base, positive against plain | median first node, DET, positive | median first node, plain')
for k in names:
    n = {g: sum(k in r['hits'] for r in v) for g, v in by.items()}
    tp, fp = n.get('positive', 0), n.get('plain', 0)
    bits = math.log2((tp / (tp + fp)) / base) if tp else float('nan')
    med = lambda v, f: statistics.median([r[f][k] for r in v if k in r[f]]) if any(k in r[f] for r in v) else None
    print(k, '|', ' | '.join(f'{n[g]}/{len(by[g])}' for g in by), f'| {bits:.2f} |', med(pos, 'first'), med(pos, 'det_first'), '|', med(neg, 'first'))


def auc(field, total, k):
    '''The share of (positive, plain) pairs where the positive task has the larger share of nodes that hit; a tie counts .5.'''
    share = lambda r: r[field].get(k, 0) / max(r[total], 1)
    return sum((share(a) > share(b)) + .5 * (share(a) == share(b)) for a in pos for b in neg) / max(len(pos) * len(neg), 1)


print('fact | DET nodes only: ' + ' | '.join(by) + ' | bits | AUC by share of all nodes | AUC by share of DET nodes')
for k in names:
    n = {g: sum(k in r['det_hits'] for r in v) for g, v in by.items()}
    tp, fp = n.get('positive', 0), n.get('plain', 0)
    bits = math.log2((tp / (tp + fp)) / base) if tp else float('nan')
    print(k, '|', ' | '.join(f'{n[g]}/{len(by[g])}' for g in by), f"| {bits:.2f} | {auc('hits', 'nodes', k):.2f} | {auc('det_hits', 'dets', k):.2f}")
nodes, spent, rs = sum(r['nodes'] for r in rows), sum(r['spent'] for r in rows), sum(r['rows'] for r in rows)
print(f'nodes {nodes} seconds {spent:.1f} ms per node {1000 * spent / nodes:.2f} largest node ms {1000 * max(r["top"] for r in rows):.0f} us per row {1e6 * spent / rs:.2f} DET nodes {sum(r["dets"] for r in rows)} cut {sum(r["cut"] for r in rows)}')
