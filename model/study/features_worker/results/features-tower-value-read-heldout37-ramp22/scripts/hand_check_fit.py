import json, sys, os, glob
import numpy as np
sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-tower-value-read-heldout37-ramp22/scripts')
import common as C
t = sys.argv[1]
bank = C.load_bank(C.N600 + '%s/work/%s.out.jsonl.bank' % (t, t))
nodes = bank['nodes']
tagged = {}
for p in sorted(glob.glob(C.N600_ROWS + t + '.part*.npz')):
    z = np.load(p); g = json.loads(str(z['gold'][0]))
    for i in range(len(z['meta'])):
        if g[i]: tagged[int(z['meta'][i, 0])] = g[i]
z = np.load('%s/rows/fit/%s_s0.npz' % (C.REC, t)); idx = {int(n): i for i, n in enumerate(z['node'])}
print('tagged nodes', len(tagged), 'gold lists', list(tagged.items())[:5])
def ancs(c):
    st = [c]; r = set()
    while st:
        for p in nodes[st.pop()].parents:
            if p not in r: r.add(p); st.append(p)
    return r
nonself = [n for n in idx if z['label'][idx[n]] and not z['self_cover'][idx[n]]]
print('non-self positives', nonself[:6])
for n in nonself[:3]:
    print(n, 'cover_ids', z['cover_ids'][idx[n]], 'by hand', [c for c in tagged if n in ancs(c)])
for n in [m for m in idx if not z['label'][idx[m]]][:3]:
    print(n, 'label 0, by hand', [c for c in tagged if n in ancs(c) or n == c])
