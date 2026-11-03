"""Slices of finished reads, with no new model read. Writes slices.json and pool-gap-heads.tsv.

- reads_last: on fit rows, the share of forms that read the form written just before them.
- need_moves: on fit rows, the share of states where each need count differs from the state before.
- by_position, by_kind: the held per-form rows of the need+foundset tier and of the all tier, by third of the program and by kind.
- comp DET rows at 25 bits or more.
- pool heads: gold's marginal on fit tasks against the pool's share, per kind, from fit rows and junk nodes only.
"""
import collections
import json
import math

import final_read as R
import next_form_facts as F

out = {}
tf = F.load('fit')
n = hit = 0
kinds = collections.Counter()
for t, forms in tf.items():
    for f, r in enumerate(forms):
        if f == 0:
            continue
        n += 1
        if any(x[2] == f - 1 for x in r['reads']):
            hit += 1
            kinds[r['kind']] += 1
out['reads_last'] = dict(forms=n, read_the_form_before=hit, share=round(hit / n, 3), by_kind=dict(kinds))
moves = collections.Counter()
for t, forms in tf.items():
    for a, b in zip(forms, forms[1:]):
        moves['states'] += 1
        for k in ('uncov', 'unpos', 'xleft'):
            moves[k] += a['state'][k] != b['state'][k]
out['need_moves'] = dict(moves)
per = [json.loads(x) for x in open(F.R + 'per-form-held.jsonl')]
L = collections.Counter()
for p in per:
    L[p['task']] = max(L[p['task']], p['form'] + 1)
for tier in ('need+foundset', 'all'):
    key = 't1 ' + tier
    pos, kd = collections.defaultdict(list), collections.defaultdict(list)
    for p in per:
        if key in p:
            third = min(2, 3 * p['form'] // L[p['task']])
            pos[third].append((p['task'], p[key]))
            kd[p['kind']].append((p['task'], p[key]))
    out['by_position ' + tier] = {str(k): R.boot(v, None) for k, v in sorted(pos.items())}
    out['by_kind ' + tier] = {k: R.boot(v, None) for k, v in sorted(kd.items())}
out['comp_det_at25'] = R.boot([(p['task'], p['saved comp DET need+foundset']) for p in per if 'saved comp DET need+foundset' in p and p['bits'] >= 25], None)
out['bits_of_forms_at25'] = dict(forms=sum(1 for p in per if p['bits'] is not None and p['bits'] >= 25), mean=round(sum(p['bits'] for p in per if p['bits'] is not None and p['bits'] >= 25) / max(1, sum(1 for p in per if p['bits'] is not None and p['bits'] >= 25)), 2))
json.dump(out, open(F.R + 'slices.json', 'w'), indent=1)
print(json.dumps(out)[:2500])
fit = F.rows_of(tf)
junk = [json.loads(x) for x in open(F.R + 'junk-node-rows.jsonl')]
with open(F.R + 'pool-gap-heads.tsv', 'w') as f:
    f.write('kind\thead columns\tgold forms\tgold share\tpool share\tlog2 ratio\n')
    for k in ('RULE', 'DET', 'INIT'):
        p = collections.Counter(r['y']['t_coarse'] for r in fit if r['kind'] == k)
        q = collections.Counter(j['coarse'] for j in junk if j['kind'] == k)
        np_, nq = sum(p.values()), sum(q.values())
        rows = []
        for a, v in p.items():
            if v >= 30:
                x, y = v / np_, (q[a] + .5) / (nq + 1)
                rows.append((math.log2(x / y), a, v, x, y))
        rows.sort(reverse=True)
        for g, a, v, x, y in rows[:8] + rows[-4:]:
            f.write('%s\t%s\t%d\t%.3f\t%.4f\t%.2f\n' % (k, a, v, x, y, g))
