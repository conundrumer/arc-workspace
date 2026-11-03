#!/usr/bin/env python
"""The census's baseline on the held rows: which population gives 3.08, and a check that each pick equals the census's."""
import json
import math
import sys

import numpy as np

OUT = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-rank-context-rows-heldout37/'
W = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/'
z = np.load(OUT + 'data-held.npz', allow_pickle=False)
task, line, ord_, phase, qb, dead = z['m_task'], z['m_line'], z['m_ord'], z['m_phase'], z['m_q_bits'], z['m_gold_dead']
starts, gold, lq = z['starts'], z['gold'], z['S'][:, 0].astype(np.float64)
forms = json.loads(str(z['forms']))
valid = [f for f in forms if not (f['error'] or f['dead'] or f['bad'])]
atoms = sum(f['natoms'] for f in valid)
n = len(qb)
own = -(lq[starts[:-1] + gold]) / math.log(2)
print('forms', len(forms), 'valid', len(valid), 'atoms', atoms, 'picks', n, 'tasks', len(set(task.tolist())))
print('bits from the arrays against the walk: max abs gap %.4f' % np.abs(own - qb).max())
cen = {}
for l in open(W + 'sampler-relation-pick-read-heldout431-census/rel_all.jsonl'):
    d = json.loads(l)
    if d['rec'] == 'rel':
        cen[d['task'], d['line'], d['ord'], d['phase']] = d['q_bits']
gap = [abs(cen[k] - b) for k, b in zip(zip(task.tolist(), line.tolist(), ord_.tolist(), phase.tolist()), qb.tolist()) if k in cen]
print('picks matched to the census %d of %d, max abs gap %.4f, sum of bits here %.1f, census %.1f' % (len(gap), n, max(gap), qb.sum(), sum(cen.values())))
alive = ~dead
print('gold alive', alive.sum(), 'gold dead', dead.sum())
print('A sum over gold-alive picks / all atoms (the 3.08): %.3f' % (qb[alive].sum() / atoms))
print('B mean over gold-alive picks: %.3f' % qb[alive].mean())
print('C mean over all picks: %.3f' % qb.mean())
print('D sum over all picks / atoms: %.3f' % (qb.sum() / atoms))
