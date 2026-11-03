"""Prints a few nodes of one read run with their parents and cover ids, read straight from the bank and the cover file, to check labels by hand."""
import json, sys, os
import numpy as np
sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-tower-value-read-heldout37-ramp22/scripts')
import common as C
task, seed = sys.argv[1], sys.argv[2]
arm = sys.argv[3] if len(sys.argv) > 3 else None
base = (C.PASS_R1 + 'out/%s_%s/%s/work/%s.out.jsonl' % (arm, seed, task, task)) if arm else (C.R1 + 'out/bundle_%s/%s/work/%s.out.jsonl' % (seed, task, task))
bank = C.load_bank(base + '.bank')
nodes = bank['nodes']
cov = C.read_lines(base + '.cover')
z = np.load('%s/rows/pass/%s_%s_%s.npz' % (C.REC, arm, task, seed) if arm else '%s/rows/read/%s_%s.npz' % (C.REC, task, seed))
idx = {int(n): i for i, n in enumerate(z['node'])}
covnodes = {x['node']: x for x in cov if x['node'] in nodes}
print('cover lines', len(cov), 'distinct nodes', len(covnodes))
anc_pos = [n for n in idx if z['label'][idx[n]] and not z['self_cover'][idx[n]]]
print('non-self positives', anc_pos[:8])
for n in anc_pos[:3]:
    i = idx[n]; nd = nodes[n]
    kids = [c for c in covnodes if n in nodes[c].parents]
    print('node', n, 'parents', nd.parents, 'depth', nd.depth, 'cover_ids', z['cover_ids'][i], 'covering children by hand (direct)', kids, 'exposure', z['exposure'][i], 'before cover', z['exposure_before_cover'][i], 'first cover time', z['first_cover_time'][i])
    for c in json.loads(str(z['cover_ids'][i])):
        # walk up parents by hand
        path, cur, seen = [c], c, False
        stack = [c]; reach = set()
        while stack:
            y = stack.pop()
            for p in nodes[y].parents:
                if p not in reach: reach.add(p); stack.append(p)
        print('   covering node', c, 'ancestors contain', n, n in reach, 'cover line time', covnodes[c]['time'], 'gold', covnodes[c]['gold'])
# negatives: a sibling and a random node
neg = [n for n in idx if not z['label'][idx[n]]][:2]
for n in neg + [list(idx)[len(idx)//2]]:
    stack = [c for c in covnodes]; hit = []
    for c in covnodes:
        st = [c]; reach = {c}
        while st:
            y = st.pop()
            for p in nodes[y].parents:
                if p not in reach: reach.add(p); st.append(p)
        if n in reach: hit.append(c)
    print('node', n, 'label', z['label'][idx[n]], 'by-hand covering descendants', hit)
